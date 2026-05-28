# normalizacion de indicadores mensuales del juzgado.
"""
Aca hay tres operaciones:
- `cargar_indicadores`: I/O -> normaliza las cosas del excel
- `pivot_a_wide`: reshape a wide
- `calcular_ratios`: agrega features como ratio_finalizacion.

"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from src import config
from src.limpieza import normalizar_nombre_columna, quitar_tildes
from src.logging_setup import get_logger

logger = get_logger(__name__)


DIMENSIONES_VALIDAS: frozenset[str] = frozenset(
    {
        "carga laboral",
        "demanda del servicio",
        "planta",
        "respuesta del organo",
        "teletrabajo",
    }
)

# solo renombro las columnas de la fuente al snake_case interno
RENAME_COLUMNAS: dict[str, str] = {
    "departamento": "departamento",
    "dependencia": "dependencia",
    "ano": "anio",  # "Año" pierde la ñ al normalizar
    "anio": "anio",
    "mes": "mes",
    "dimension": "dimension",
    "indicador": "indicador",
    "valor": "valor",
}

# Catálogo de slugs principales producidos por `_slug()`. Cada clave es el
# slug EXACTO que sale del algoritmo aplicado al nombre original del Excel.
# Hay un test (`test_slugs_son_consistentes`) que verifica que estos slugs
# efectivamente aparecen al cargar el archivo real.
#
# Si en el futuro estadística renombra un indicador, se ajusta acá y se
# corre el test para detectar la divergencia.
SLUGS_PRINCIPALES: dict[str, str] = {
    # Demanda del servicio
    "causas_ingresadas": "Causas ingresadas",
    "recepcion_de_presentaciones": "Recepción de presentaciones",
    # Respuesta del Órgano
    "causas_finalizadas": "Causas finalizadas (trámites de finalización)",
    "tasa_de_resolucion": "Tasa de resolución",
    "tramites_de_resoluciones": "Trámites de resoluciones",
    "resoluciones_por_funcionario": "Resoluciones por funcionario",
    "resoluciones_por_empleado": "Resoluciones por empleado",
    "medidas_cautelares_en_violencia": "Medidas cautelares en violencia",
    # Carga Laboral
    "actas_de_audiencias": "Actas de audiencias",
    "causas_con_tramitacion": "Causas con tramitación",
    "detenidos_al_final_del_periodo": "Detenidos al final del período",
    "tramites_totales": "Trámites totales",
    # Planta
    "funcionarios_en_dependencia": "Funcionarios en dependencia",
    "empleados_en_dependencia": "Empleados en dependencia",
}

# Aliases canónicos cortos para uso frecuente en código downstream.
# Usar estos constants en vez de strings literales — refactoring centralizado.
SLUG_CAUSAS_INGRESADAS = "causas_ingresadas"
SLUG_CAUSAS_FINALIZADAS = "causas_finalizadas"
SLUG_TASA_RESOLUCION = "tasa_de_resolucion"
SLUG_TRAMITES_TOTALES = "tramites_totales"
SLUG_TRAMITES_RESOLUCIONES = "tramites_de_resoluciones"
SLUG_RESOLUCIONES_POR_FUNCIONARIO = "resoluciones_por_funcionario"
SLUG_CAUSAS_CON_TRAMITACION = "causas_con_tramitacion"
SLUG_DETENIDOS_FIN_PERIODO = "detenidos_al_final_del_periodo"


def _slug(nombre: str) -> str:
    """Convierte un nombre de indicador a slug snake_case estable.

    Reglas:
    - Quita tildes y baja a minúsculas.
    - Descarta paréntesis y su contenido (los usan para notas).
    - Reemplaza no-alfanumérico por _.
    - Strip de _ en los bordes.

    Ejemplos:
        "Causas Ingresadas" → "causas_ingresadas"
        "Causas finalizadas (trámites de finalización)" → "causas_finalizadas"
        "Tasa de resolución" → "tasa_de_resolucion"
    """
    s = quitar_tildes(str(nombre)).lower()
    s = re.sub(r"\([^)]*\)", "", s)
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


# -Aca viene el I/O


def cargar_indicadores(path: Path | None = None) -> pd.DataFrame:
    # carga el xlsx de indicadores en formato long normalizado

    fuente = path if path is not None else config.INDICADORES_FILE
    if not fuente.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de indicadores en {fuente}. "
            "Pedilo al área de Estadística del juzgado y colocalo en data/external/."
        )

    df_raw = pd.read_excel(fuente, sheet_name=0, header=0)
    df = _normalizar(df_raw)
    logger.info(
        "Indicadores cargados: %d filas | %d meses | %d indicadores distintos",
        len(df),
        df.groupby(["anio", "mes"]).ngroups,
        df["indicador_slug"].nunique(),
    )
    return df


def _normalizar(df_raw: pd.DataFrame) -> pd.DataFrame:
    # se ahce la normalizacion al df

    df = df_raw.copy()
    df.columns = [normalizar_nombre_columna(c) for c in df.columns]
    df = df.rename(columns=RENAME_COLUMNAS)

    # Tipos: in para año/mes, float el cvalor
    df["anio"] = pd.to_numeric(df["anio"], errors="coerce").astype("Int64")
    df["mes"] = pd.to_numeric(df["mes"], errors="coerce").astype("Int64")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").astype(float)

    # sacco tildes, paso todo a minuscula
    df["dimension"] = (
        df["dimension"]
        .astype("string")
        .apply(lambda s: quitar_tildes(s).lower() if pd.notna(s) else s)
    )

    # trim
    for col in ("departamento", "dependencia", "indicador"):
        df[col] = df[col].astype("string").str.strip()

    # slug del indicador
    df["indicador_slug"] = df["indicador"].apply(_slug)

    # descarto filas sin fechas
    df = df.dropna(subset=["anio", "mes"]).reset_index(drop=True)

    return df[
        [
            "departamento",
            "dependencia",
            "anio",
            "mes",
            "dimension",
            "indicador",
            "indicador_slug",
            "valor",
        ]
    ]


# reshape


def pivot_a_wide(df_long: pd.DataFrame) -> pd.DataFrame:
    # pivota el df long a wide: una fila por la fecha
    if len(df_long) == 0:
        return pd.DataFrame(columns=["anio", "mes", "fecha_mes"])

    wide = df_long.pivot_table(
        index=["anio", "mes"],
        columns="indicador_slug",
        values="valor",
        aggfunc="first",  # un valor por slug-mes, first detecta dupes
    ).reset_index()

    wide.columns.name = None

    # Fecha al primer dia del mes para los graficos
    wide["fecha_mes"] = pd.to_datetime(
        wide["anio"].astype(str) + "-" + wide["mes"].astype(str).str.zfill(2) + "-01"
    )

    # reorden
    cols_id = ["anio", "mes", "fecha_mes"]
    cols_indicadores = [c for c in wide.columns if c not in cols_id]
    wide = wide[cols_id + sorted(cols_indicadores)]

    return wide.sort_values(["anio", "mes"]).reset_index(drop=True)


# Aca se procesan metricas
def calcular_ratios(df_wide: pd.DataFrame) -> pd.DataFrame:
    """
    metricas calculadas si se puede obvio:
    - `tasa_resolucion_calculada`: finalizadas / ingresadas * 100.
    - `delta_ingreso_finalizacion`: ingresadas - finalizadas.
    - `ratio_finalizacion`: finalizadas / ingresadas (decimal).
    """
    df = df_wide.copy()

    tiene_ing = SLUG_CAUSAS_INGRESADAS in df.columns
    tiene_fin = SLUG_CAUSAS_FINALIZADAS in df.columns

    if tiene_ing and tiene_fin:
        ing = df[SLUG_CAUSAS_INGRESADAS]
        fin = df[SLUG_CAUSAS_FINALIZADAS]
        with np.errstate(divide="ignore", invalid="ignore"):
            df["tasa_resolucion_calculada"] = np.where(
                ing.notna() & (ing != 0) & fin.notna(),
                fin / ing * 100,
                np.nan,
            )
            df["ratio_finalizacion"] = np.where(
                ing.notna() & (ing != 0) & fin.notna(),
                fin / ing,
                np.nan,
            )
        df["delta_ingreso_finalizacion"] = ing - fin

    return df


# utils


def serie_temporal(
    df_long: pd.DataFrame,
    indicador_slug: str,
) -> pd.DataFrame:
    # esta funcion devuelve la serie temporal de un un indicador

    sub = df_long[df_long["indicador_slug"] == indicador_slug].copy()
    if len(sub) == 0:
        slugs_disponibles = sorted(df_long["indicador_slug"].unique().tolist())
        raise KeyError(
            f"Indicador '{indicador_slug}' no encontrado. Disponibles: {slugs_disponibles}"
        )
    sub["fecha_mes"] = pd.to_datetime(
        sub["anio"].astype(str) + "-" + sub["mes"].astype(str).str.zfill(2) + "-01"
    )
    return (
        sub[["anio", "mes", "fecha_mes", "valor"]].sort_values("fecha_mes").reset_index(drop=True)
    )
