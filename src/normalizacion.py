"""Normalización de delitos, cruce con nomenclador ministerial y trámites.

Esta es la lógica central del pipeline. Se preserva 100% de la prudencia
jurisprudencial del notebook original:

- No se fuerzan matches cuando hay ambigüedad: el estado de match es
  `match_univoco`, `match_ambiguo` o `sin_equivalencia_definida`.
- Los delitos múltiples se marcan como `posible_delito_multiple` pero no
  se separan automáticamente.
- Las excepciones operativas del juzgado están explícitas en
  `EXCEPCIONES_NO_MULTIPLES`.

Cumple PY-05 (separar transformación de I/O), DATA-02 (validar cardinalidad
de merges con `validate=`) y DATA-07 (validar shape post-merge).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src import config
from src.limpieza import (
    FALTANTES_DELITO,
    FALTANTES_TRAMITE,
    PROCESOS_ESPECIALES,
    REGLAS_DELITOS,
    aplicar_reglas_regex,
    limpiar_para_match,
    limpiar_texto,
    limpiar_tramite,
    normalizar_nombre_columna,
)
from src.logging_setup import get_logger

logger = get_logger(__name__)


# --- Constantes de dominio ------------------------------------------------

# Patrones para detectar tentativa después de la limpieza.
PATRON_TENTATIVA: str = r"\b(?:tentativa)\b"

# Patrón regex para flag de delito agravado o calificado.
PATRON_AGRAVADO: str = r"\bagravad[oa]s?\b|\bcalificad[oa]s?\b"

# Patrones de los 5 subtipos de agravante reconocidos por el juzgado.
PATRONES_AGRAVANTES: dict[str, str] = {
    "agravante_poblado_banda": r"poblado y en banda|despoblado y banda",
    "agravante_arma": r"arma|armas",
    "agravante_escalamiento": r"escalamiento",
    "agravante_efraccion": r"efraccion",
    "agravante_vehiculo_via_publica": r"vehiculo.*via publica|de vehiculos|de vehiculo",
}

# Delitos que parecen múltiples por contener " y " o "," pero son una
# sola figura jurídica compuesta. Se excluyen de `posible_delito_multiple`.
EXCEPCIONES_NO_MULTIPLES: frozenset[str] = frozenset({
    "robo agravado en poblado y en banda",
    "robo agravado arma no apta en poblado y en banda",
    "robo agravado por el uso de arma",
    "robo agravado por el uso de arma de fuego",
    "robo agravado por uso de arma no apta",
    "robo agravado por efraccion",
    "robo agravado por escalamiento",
    "robo agravado de vehiculo dejado en la via publica",
    "hurto agravado de vehiculo dejado en la via publica",
    "hurto agravado por escalamiento",
})

# Renombres de columnas de la planilla fuente al snake_case del pipeline.
RENAME_MAP: dict[str, str] = {
    "fecha de ingreso": "fecha_ingreso",
    "ipp": "ipp",
    "tipo tramite": "tipo_tramite",
    "caratula anonimizada": "caratula_anonimizada",
    "responsable": "responsable",
    "observaciones": "observaciones",
    "delito": "delito",
}


# --- Carga de datos crudos ------------------------------------------------

def cargar_datos_raw(
    path: Path | None = None,
    sheet_name: str = config.RAW_SHEET,
    usecols: str = config.RAW_USECOLS,
    anio_minimo: int = config.ANIO_MINIMO,
) -> pd.DataFrame:
    """Carga la planilla Excel fuente y aplica la limpieza estructural mínima.

    - Lee la hoja `Registro` (columnas A:F).
    - Normaliza nombres de columnas a snake_case sin tildes.
    - Tipifica `ipp`, `tipo_tramite`, etc. como string.
    - Convierte `fecha_ingreso` a datetime y deriva `anio`.
    - Filtra causas con `anio >= anio_minimo`.
    - Hace backup de columnas raw: `delito_raw` y `tipo_tramite_raw`.

    Args:
        path: ruta al Excel. Si es None, usa `config.RAW_FILE`.
        sheet_name: nombre de la hoja a leer.
        usecols: rango de columnas a leer (formato openpyxl).
        anio_minimo: año desde el cual conservar causas.

    Returns:
        DataFrame con columnas tipificadas y backups `_raw`.

    Raises:
        FileNotFoundError: si el Excel no existe.
    """
    fuente = path if path is not None else config.RAW_FILE
    if not fuente.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de causas en {fuente}. "
            "Colocá el Excel en data/raw/ con el nombre esperado."
        )

    df_raw = pd.read_excel(
        fuente,
        sheet_name=sheet_name,
        header=0,
        usecols=usecols,
    )
    df_raw.columns = [normalizar_nombre_columna(c) for c in df_raw.columns]
    df_raw = df_raw.rename(columns=RENAME_MAP)

    df = df_raw.dropna(subset=config.COLUMNAS_CLAVE, how="all").copy()

    for col in ("ipp", "tipo_tramite", "caratula_anonimizada",
                "responsable", "observaciones", "delito"):
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()

    df["fecha_ingreso"] = pd.to_datetime(df["fecha_ingreso"], errors="coerce")
    df["anio"] = df["fecha_ingreso"].dt.year
    df = df[df["anio"] >= anio_minimo].copy()

    # Backups raw para auditoría.
    df["delito_raw"] = df["delito"].copy()
    df["tipo_tramite_raw"] = df["tipo_tramite"].copy()

    logger.info("Datos crudos cargados: %d filas desde %d", len(df), anio_minimo)
    return df


# --- Normalización de delitos --------------------------------------------

def normalizar_delitos(
    df: pd.DataFrame,
    dict_delitos_local: pd.DataFrame,
) -> pd.DataFrame:
    """Aplica la cadena completa de normalización de delitos.

    Etapas:
    1. Limpieza textual base con `limpiar_texto`.
    2. Reemplazo de valores faltantes por NA.
    3. Aplicación de las 50+ reglas regex (`REGLAS_DELITOS`).
    4. Detección de tentativa y construcción de `delito_sin_tentativa`.
    5. Identificación de procesos especiales (amparo, habeas corpus).
    6. Cruce con diccionario local — fallback a `delito_no_informado`.
    7. Cálculo de flags: agravado, sub-agravantes, no especificado.
    8. Detección de posible delito múltiple (con excepciones operativas).

    Args:
        df: DataFrame con la columna `delito_raw`.
        dict_delitos_local: diccionario local de equivalencias.

    Returns:
        DataFrame con todas las columnas derivadas agregadas.
    """
    filas_inicial = len(df)
    df = df.copy()

    # 1-2. Limpieza textual + reemplazo de faltantes.
    df["delito_limpio"] = df["delito_raw"].apply(limpiar_texto)
    df["delito_limpio"] = df["delito_limpio"].replace(list(FALTANTES_DELITO), pd.NA)

    # 3. Reglas regex secuenciales (típos, abreviaturas, expansiones).
    df["delito_limpio"] = df["delito_limpio"].apply(
        lambda x: aplicar_reglas_regex(x, REGLAS_DELITOS)
    )

    # 4. Tentativa: detección y eliminación del texto.
    df["tentativa"] = df["delito_limpio"].astype("string").str.contains(
        PATRON_TENTATIVA, regex=True, na=False
    )
    df["delito_sin_tentativa"] = (
        df["delito_limpio"].astype("string")
        .str.replace(r"\ben\s+tentativa\b", "", regex=True)
        .str.replace(r"\btentativa\b", "", regex=True)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip(" .,-_/")
    )

    # 5. Procesos especiales (no son delitos en sentido estricto).
    df["es_proceso_especial"] = df["delito_sin_tentativa"].isin(PROCESOS_ESPECIALES)

    # 6. Match con diccionario local. Se aplica `limpiar_para_match` en ambos
    # lados del merge para uniformar las claves.
    dic = dict_delitos_local.copy()
    dic["delito_fuente_limpio"] = dic["delito_fuente"].apply(limpiar_para_match)
    dic["delito_estandar"] = dic["delito_estandar"].apply(limpiar_para_match)

    df["delito_key"] = df["delito_sin_tentativa"].apply(limpiar_para_match)

    # Validación de cardinalidad m:1: el diccionario local debe ser único por
    # delito_fuente_limpio. Si no lo es, alguien duplicó equivalencias.
    df = df.merge(
        dic[["delito_fuente_limpio", "delito_estandar"]].drop_duplicates(
            subset=["delito_fuente_limpio"]
        ),
        left_on="delito_key",
        right_on="delito_fuente_limpio",
        how="left",
        validate="m:1",
    )

    df["delito_estandar"] = df["delito_estandar"].fillna(df["delito_key"])
    df["delito_estandar"] = df["delito_estandar"].fillna("delito_no_informado")
    df["delito_informado"] = np.where(
        df["delito_estandar"].eq("delito_no_informado"), "no", "si"
    )

    # 7. Flags jurídicos.
    delito_str = df["delito_estandar"].astype("string")
    df["agravado_flag"] = delito_str.str.contains(PATRON_AGRAVADO, regex=True, na=False)

    for flag, patron in PATRONES_AGRAVANTES.items():
        df[flag] = delito_str.str.contains(patron, regex=True, na=False)

    # Agravado pero ninguno de los sub-agravantes específicos: sigue siendo
    # agravado pero queda "sin especificar" — útil para auditoría.
    df["agravante_no_especificado"] = (
        df["agravado_flag"]
        & ~df["agravante_poblado_banda"]
        & ~df["agravante_arma"]
        & ~df["agravante_escalamiento"]
        & ~df["agravante_efraccion"]
        & ~df["agravante_vehiculo_via_publica"]
    )

    # 8. Posible delito múltiple: tiene ',' o ' y ', no es proceso especial,
    # y no está en la lista de figuras compuestas conocidas.
    df["posible_delito_multiple"] = (
        ~df["es_proceso_especial"]
        & delito_str.str.contains(r",|\s+y\s+", regex=True, na=False)
        & ~df["delito_estandar"].isin(EXCEPCIONES_NO_MULTIPLES)
    )

    # Validación de shape (DATA-07).
    assert len(df) == filas_inicial, (
        f"normalizar_delitos cambió la cantidad de filas: "
        f"{filas_inicial} → {len(df)}"
    )

    logger.info(
        "Delitos normalizados: %d filas | %d con tentativa | %d agravados | "
        "%d posibles múltiples",
        len(df), df["tentativa"].sum(), df["agravado_flag"].sum(),
        df["posible_delito_multiple"].sum(),
    )
    return df


# --- Cruce con nomenclador del Ministerio ---------------------------------

def cruzar_ministerio(
    df: pd.DataFrame,
    dict_delitos_ministerio: pd.DataFrame,
    nomenclador: pd.DataFrame,
) -> pd.DataFrame:
    """Cruza los delitos estandarizados con el nomenclador oficial.

    Modela el cruce en tres estados principales: `match_univoco`,
    `match_ambiguo` y `sin_equivalencia_definida`. Más dos estados auxiliares
    para casos no aplicables: `proceso_especial` y `sin_delito_informado`.

    Args:
        df: DataFrame con `delito_estandar`, `delito_informado` y
            `es_proceso_especial` ya calculados.
        dict_delitos_ministerio: puente local entre `delito_estandar` y
            `objetivo_ministerio`.
        nomenclador: nomenclador oficial cargado con
            `cargar_nomenclador_ministerio`.

    Returns:
        DataFrame con columnas agregadas:
        `objetivo_ministerio`, `descripcion_ministerio`,
        `articulo_ministerio`, `codigo_delito_ministerio`,
        `tipo_registro_ministerio`, `cantidad_codigos_ministerio`,
        `estado_match_ministerio`.
    """
    filas_inicial = len(df)
    df = df.copy()

    # 1. Preparar puente local: aplicar limpieza de match a sus claves.
    puente = dict_delitos_ministerio.copy()
    puente["delito_estandar"] = puente["delito_estandar"].apply(limpiar_para_match)
    puente["objetivo_ministerio"] = puente["objetivo_ministerio"].apply(limpiar_para_match)

    # 2. Agregar el nomenclador oficial por descripción limpia.
    nom = nomenclador.copy()
    nom["delito_ministerio_limpio"] = nom["delito_descripcion"].apply(limpiar_para_match)

    nom_agg = (
        nom.groupby("delito_ministerio_limpio", dropna=False)
        .agg(
            descripcion_ministerio=(
                "delito_descripcion",
                lambda s: " | ".join(sorted(pd.unique(s.astype(str)))),
            ),
            articulo_ministerio=(
                "delito_articulo",
                lambda s: " | ".join(sorted(pd.unique(s.astype(str)))),
            ),
            codigo_delito_ministerio=(
                "codigo_delito",
                lambda s: " | ".join(sorted(pd.unique(s.astype(str)))),
            ),
            tipo_registro_ministerio=(
                "tipo",
                lambda s: " | ".join(sorted(pd.unique(s.astype(str)))),
            ),
            cantidad_codigos_ministerio=("codigo_delito", "nunique"),
        )
        .reset_index()
    )

    # 3. Primer merge: df → puente (vía delito_estandar limpio).
    df["delito_estandar_key"] = df["delito_estandar"].apply(limpiar_para_match)

    puente_dedup = puente[[
        "delito_estandar", "objetivo_ministerio", "criterio_match"
    ]].drop_duplicates(subset=["delito_estandar"])

    df = df.merge(
        puente_dedup,
        left_on="delito_estandar_key",
        right_on="delito_estandar",
        how="left",
        suffixes=("", "_dicmin"),
        validate="m:1",
    )

    # 4. Segundo merge: df → nomenclador agregado (vía objetivo_ministerio limpio).
    df["objetivo_ministerio_limpio"] = df["objetivo_ministerio"].apply(limpiar_para_match)

    df = df.merge(
        nom_agg,
        left_on="objetivo_ministerio_limpio",
        right_on="delito_ministerio_limpio",
        how="left",
        validate="m:1",
    )

    # 5. Estado del match: lógica jurídicamente prudente del notebook.
    df["estado_match_ministerio"] = np.select(
        condlist=[
            df["es_proceso_especial"],
            df["delito_informado"].eq("no"),
            df["criterio_match"].eq("sin_equivalencia_definida"),
            df["cantidad_codigos_ministerio"].eq(1),
            df["cantidad_codigos_ministerio"].gt(1),
            df["objetivo_ministerio"].isna(),
        ],
        choicelist=[
            "proceso_especial",
            "sin_delito_informado",
            "sin_equivalencia_definida",
            "match_univoco",
            "match_ambiguo",
            "sin_equivalencia_definida",
        ],
        default="sin_match",
    )

    # Validación de shape (DATA-07).
    assert len(df) == filas_inicial, (
        f"cruzar_ministerio cambió la cantidad de filas: "
        f"{filas_inicial} → {len(df)}"
    )

    logger.info(
        "Cruce ministerial completado. Distribución: %s",
        df["estado_match_ministerio"].value_counts().to_dict(),
    )
    return df


# --- Normalización de trámites --------------------------------------------

# Reglas residuales aplicadas tras el merge con el diccionario de trámites.
# Capturan operatorias específicas del juzgado que el diccionario no cubre
# en forma exhaustiva.
def _aplicar_reglas_residuales_tramite(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica overrides locales al tipo_tramite_estandar después del merge.

    Mutación in-place sobre `tipo_tramite_estandar`. Devuelve el mismo df
    por conveniencia.
    """
    tram = df["tipo_tramite_limpio"].astype("string").str.lower().str.strip()

    mask_elev = tram.str.contains(r"elevacion|requisitoria", regex=True, na=False)
    mask_sjp = tram.str.contains(r"\bsjp\b", regex=True, na=False)
    df.loc[mask_elev & ~mask_sjp, "tipo_tramite_estandar"] = "elevacion_a_juicio"
    df.loc[mask_elev & mask_sjp, "tipo_tramite_estandar"] = "elevacion_a_juicio_ofrece_sjp"

    mask_remite = tram.str.contains(r"^remite a|^radicacion", regex=True, na=False)
    df.loc[mask_remite, "tipo_tramite_estandar"] = "competencia"

    mask_decl = tram.str.contains(r"declinatoria|delinatoria", regex=True, na=False)
    df.loc[mask_decl, "tipo_tramite_estandar"] = "declinatoria_de_competencia"

    return df


def normalizar_tramites(
    df: pd.DataFrame,
    dict_tramites: pd.DataFrame,
) -> pd.DataFrame:
    """Normaliza el tipo de trámite con diccionario local + reglas residuales.

    1. Limpieza textual del trámite con `limpiar_tramite`.
    2. Reemplazo de faltantes por NA.
    3. Merge con diccionario local.
    4. Fallback: si no hay match, queda el `tipo_tramite_limpio`.
    5. Reglas residuales por operatoria del juzgado (elevación, competencia,
       declinatoria).

    Args:
        df: DataFrame con `tipo_tramite_raw`.
        dict_tramites: diccionario local de trámites.

    Returns:
        DataFrame con `tipo_tramite_limpio` y `tipo_tramite_estandar`.
    """
    filas_inicial = len(df)
    df = df.copy()

    df["tipo_tramite_limpio"] = df["tipo_tramite_raw"].apply(limpiar_tramite)
    df["tipo_tramite_limpio"] = df["tipo_tramite_limpio"].replace(
        list(FALTANTES_TRAMITE), pd.NA
    )

    dic = dict_tramites.copy()
    dic["tramite_fuente"] = dic["tramite_fuente"].apply(limpiar_tramite)
    dic["tramite_estandar"] = dic["tramite_estandar"].apply(limpiar_tramite)

    df = df.merge(
        dic[["tramite_fuente", "tramite_estandar", "categoria"]].drop_duplicates(
            subset=["tramite_fuente"]
        ),
        left_on="tipo_tramite_limpio",
        right_on="tramite_fuente",
        how="left",
        validate="m:1",
    )

    df["tipo_tramite_estandar"] = df["tramite_estandar"].fillna(df["tipo_tramite_limpio"])

    df = _aplicar_reglas_residuales_tramite(df)

    assert len(df) == filas_inicial, (
        f"normalizar_tramites cambió la cantidad de filas: "
        f"{filas_inicial} → {len(df)}"
    )
    logger.info("Trámites normalizados: %d filas", len(df))
    return df


# --- Columnas finales del dataset analítico -------------------------------

COLUMNAS_FINALES: tuple[str, ...] = (
    "fecha_ingreso",
    "anio",
    "ipp",
    "tipo_tramite_raw",
    "tipo_tramite_limpio",
    "tipo_tramite_estandar",
    "caratula_anonimizada",
    "responsable",
    "delito_raw",
    "delito_limpio",
    "delito_sin_tentativa",
    "delito_estandar",
    "delito_informado",
    "tentativa",
    "es_proceso_especial",
    "agravado_flag",
    "agravante_poblado_banda",
    "agravante_arma",
    "agravante_escalamiento",
    "agravante_efraccion",
    "agravante_vehiculo_via_publica",
    "agravante_no_especificado",
    "posible_delito_multiple",
    "objetivo_ministerio",
    "descripcion_ministerio",
    "articulo_ministerio",
    "codigo_delito_ministerio",
    "estado_match_ministerio",
)


def seleccionar_columnas_finales(df: pd.DataFrame) -> pd.DataFrame:
    """Recorta el DataFrame al conjunto de columnas analíticas finales.

    Falla si falta alguna columna esperada (validación de contrato).
    """
    faltantes = [c for c in COLUMNAS_FINALES if c not in df.columns]
    if faltantes:
        raise ValueError(
            f"Faltan columnas para el dataset final: {faltantes}"
        )
    # Si alguna columna 'responsable' u 'observaciones' no estaba en el raw,
    # rellenar con NA para no romper el contrato.
    if "responsable" not in df.columns:
        df = df.copy()
        df["responsable"] = pd.NA
    return df[list(COLUMNAS_FINALES)].copy()
