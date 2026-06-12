"""
Normalización de delitos

Sale del notebook original:

- No se fuerzan matches cuando hay ambigüedad: el estado de match es
  `match_univoco`, `match_ambiguo` o `sin_equivalencia_definida`.
- Los delitos múltiples se marcan como `posible_delito_multiple` pero no
  se separan automáticamente.
- Las excepciones operativas del juzgado están explícitas en
  `EXCEPCIONES_NO_MULTIPLES`.


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


# patrones
PATRON_TENTATIVA: str = r"\b(?:tentativa)\b"
PATRON_AGRAVADO: str = r"\bagravad[oa]s?\b|\bcalificad[oa]s?\b"

# estos son unicos por como el juzgado ingresa datos juzgado.
PATRONES_AGRAVANTES: dict[str, str] = {
    "agravante_poblado_banda": r"poblado y en banda|despoblado y banda",
    "agravante_arma": r"arma|armas",
    "agravante_escalamiento": r"escalamiento",
    "agravante_efraccion": r"efraccion",
    "agravante_vehiculo_via_publica": r"vehiculo.*via publica|de vehiculos|de vehiculo",
}

# Delitos que parecen múltiples por contener " y " o "," pero son una
# Se excluyen de `posible_delito_multiple`
EXCEPCIONES_NO_MULTIPLES: frozenset[str] = frozenset(
    {
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
    }
)


RENAME_MAP: dict[str, str] = {
    "fecha de ingreso": "fecha_ingreso",
    "ipp": "ipp",
    "tipo tramite": "tipo_tramite",
    "caratula anonimizada": "caratula_anonimizada",
    "responsable": "responsable",
    "observaciones": "observaciones",
    "delito": "delito",
}


# carga


def cargar_datos_raw(
    path: Path | None = None,
    sheet_name: str = config.RAW_SHEET,
    usecols: str = config.RAW_USECOLS,
    anio_minimo: int = config.ANIO_MINIMO,
) -> pd.DataFrame:
    """
    ccarga excel y

    - lee la hoja `Registro` (columnas A:F).
    - normaliza nombres de columnas a snake_case sin tildes.
    - tipifica `ipp`, `tipo_tramite`, etc. como string.
    - convierte `fecha_ingreso` a datetime y deriva `anio`.
    - filtra causas con `anio >= anio_minimo`.
    - hace backup de columnas raw: `delito_raw` y `tipo_tramite_raw`.

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

    for col in (
        "ipp",
        "tipo_tramite",
        "caratula_anonimizada",
        "responsable",
        "observaciones",
        "delito",
    ):
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


# normalizacion de delitos


def normalizar_delitos(
    df: pd.DataFrame,
    dict_delitos_local: pd.DataFrame,
) -> pd.DataFrame:
    """

    Etapas:
    1. limpieza textual base con `limpiar_texto`
    2. remplazo de valores faltantes por NA
    3. aplicación de las reglas regex  que estan en `REGLAS_DELITOS`
    4. detección de tentativa y construcción de `delito_sin_tentativa`
    5. id de procesos especiales (amparo, habeas corpus)
    6. cruce con diccionario local y  fallback a `delito_no_informado`
    7. calculo de flags: agravantes yno especificado
    8. detección de posible delito mutiple

    """

    filas_inicial = len(df)
    df = df.copy()

    # limpieza textual + reemplazo de faltantes
    df["delito_limpio"] = df["delito_raw"].apply(limpiar_texto)
    df["delito_limpio"] = df["delito_limpio"].replace(list(FALTANTES_DELITO), pd.NA)

    # rglas regex secuenciales
    df["delito_limpio"] = df["delito_limpio"].apply(
        lambda x: aplicar_reglas_regex(x, REGLAS_DELITOS)
    )

    # tentativa
    df["tentativa"] = (
        df["delito_limpio"].astype("string").str.contains(PATRON_TENTATIVA, regex=True, na=False)
    )
    df["delito_sin_tentativa"] = (
        df["delito_limpio"]
        .astype("string")
        .str.replace(r"\ben\s+tentativa\b", "", regex=True)
        .str.replace(r"\btentativa\b", "", regex=True)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip(" .,-_/")
    )

    # procesos especiales
    df["es_proceso_especial"] = df["delito_sin_tentativa"].isin(PROCESOS_ESPECIALES)

    # match con diccionario local
    dic = dict_delitos_local.copy()
    dic["delito_fuente_limpio"] = dic["delito_fuente"].apply(limpiar_para_match)
    dic["delito_estandar"] = dic["delito_estandar"].apply(limpiar_para_match)

    df["delito_key"] = df["delito_sin_tentativa"].apply(limpiar_para_match)

    # valid de cardinalidad m:1
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
    df["delito_informado"] = np.where(df["delito_estandar"].eq("delito_no_informado"), "no", "si")

    # flags juridicos
    delito_str = df["delito_estandar"].astype("string")
    df["agravado_flag"] = delito_str.str.contains(PATRON_AGRAVADO, regex=True, na=False)

    for flag, patron in PATRONES_AGRAVANTES.items():
        df[flag] = delito_str.str.contains(patron, regex=True, na=False)

    df["agravante_no_especificado"] = (
        df["agravado_flag"]
        & ~df["agravante_poblado_banda"]
        & ~df["agravante_arma"]
        & ~df["agravante_escalamiento"]
        & ~df["agravante_efraccion"]
        & ~df["agravante_vehiculo_via_publica"]
    )

    df["posible_delito_multiple"] = (
        ~df["es_proceso_especial"]
        & delito_str.str.contains(r",|\s+y\s+", regex=True, na=False)
        & ~df["delito_estandar"].isin(EXCEPCIONES_NO_MULTIPLES)
    )

    # validacion de shape
    assert len(df) == filas_inicial, (
        f"normalizar_delitos cambió la cantidad de filas: {filas_inicial} → {len(df)}"
    )

    logger.info(
        "Delitos normalizados: %d filas | %d con tentativa | %d agravados | %d posibles múltiples",
        len(df),
        df["tentativa"].sum(),
        df["agravado_flag"].sum(),
        df["posible_delito_multiple"].sum(),
    )
    return df


# cruce de delitos estandarizados con nomenclador del Ministerio


def cruzar_ministerio(
    df: pd.DataFrame,
    dict_delitos_ministerio: pd.DataFrame,
    nomenclador: pd.DataFrame,
) -> pd.DataFrame:
    filas_inicial = len(df)
    df = df.copy()

    puente = dict_delitos_ministerio.copy()
    puente["delito_estandar"] = puente["delito_estandar"].apply(limpiar_para_match)
    puente["objetivo_ministerio"] = puente["objetivo_ministerio"].apply(limpiar_para_match)

    # agrega¡ el nomenclador oficial por descripcion limpia
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

    # df a puente usando como key el delito estandar
    df["delito_estandar_key"] = df["delito_estandar"].apply(limpiar_para_match)

    puente_dedup = puente[
        ["delito_estandar", "objetivo_ministerio", "criterio_match"]
    ].drop_duplicates(subset=["delito_estandar"])

    df = df.merge(
        puente_dedup,
        left_on="delito_estandar_key",
        right_on="delito_estandar",
        how="left",
        suffixes=("", "_dicmin"),
        validate="m:1",
    )

    # df a nomenclador agregado
    df["objetivo_ministerio_limpio"] = df["objetivo_ministerio"].apply(limpiar_para_match)

    df = df.merge(
        nom_agg,
        left_on="objetivo_ministerio_limpio",
        right_on="delito_ministerio_limpio",
        how="left",
        validate="m:1",
    )

    # estado del match
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

    # validacion de shape
    assert len(df) == filas_inicial, (
        f"cruzar_ministerio cambió la cantidad de filas: {filas_inicial} → {len(df)}"
    )

    logger.info(
        "Cruce ministerial completado. Distribución: %s",
        df["estado_match_ministerio"].value_counts().to_dict(),
    )
    return df


# normalizacion de tramites


def _aplicar_reglas_residuales_tramite(df: pd.DataFrame) -> pd.DataFrame:
    # overrides locales al tipo_tramite_estandar después del merge

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
    """

    aca se normaliza el tipo de tramite con diccionario local + reglas

    1. Limpieza textual del trámite con `limpiar_tramite`
    2. Reemplazo de faltantes por NA
    3. Merge con diccionario local
    4. Fallback: si no hay match, queda el `tipo_tramite_limpio`
    5. Reglas residuales por lo que se usa en el juzgado (elevacion, competencia,
       declinatoria).
    """
    filas_inicial = len(df)
    df = df.copy()

    df["tipo_tramite_limpio"] = df["tipo_tramite_raw"].apply(limpiar_tramite)
    df["tipo_tramite_limpio"] = df["tipo_tramite_limpio"].replace(list(FALTANTES_TRAMITE), pd.NA)

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
        f"normalizar_tramites cambió la cantidad de filas: {filas_inicial} → {len(df)}"
    )
    logger.info("Trámites normalizados: %d filas", len(df))
    return df


# columnas finales

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
    # pasa el DataFrame al conjunto de columnas finales
    faltantes = [c for c in COLUMNAS_FINALES if c not in df.columns]
    if faltantes:
        raise ValueError(f"Faltan columnas para el dataset final: {faltantes}")
    if "responsable" not in df.columns:
        df = df.copy()
        df["responsable"] = pd.NA
    return df[list(COLUMNAS_FINALES)].copy()
