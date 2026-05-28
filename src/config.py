"""Configuración centralizada del pipeline.

Fuente única de paths y parámetros. Modificar valores acá en lugar de
hardcodearlos en los módulos. Cumple con la regla CFG-01 del guideline
(pyproject + módulo de config como fuente primaria).
"""

from __future__ import annotations

import logging
from pathlib import Path

# --- Paths del proyecto ---------------------------------------------------

ROOT: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = ROOT / "data"
RAW_DIR: Path = DATA_DIR / "raw"
BACKFILL_DIR: Path = DATA_DIR / "backfill"
DICT_DIR: Path = DATA_DIR / "diccionarios"
EXTERNAL_DIR: Path = DATA_DIR / "external"
OUTPUT_DIR: Path = ROOT / "outputs"

# --- Archivos de entrada --------------------------------------------------

RAW_FILE: Path = RAW_DIR / "registro_ingreso_causas_2020_2026.xlsx"
RAW_SHEET: str = "Registro"
RAW_USECOLS: str = "A:F"

DICT_DELITOS_LOCAL: Path = DICT_DIR / "diccionario_delitos_local.csv"
DICT_DELITOS_MINISTERIO: Path = DICT_DIR / "diccionario_delitos_ministerio.csv"
DICT_TRAMITES: Path = DICT_DIR / "diccionario_tramites.csv"
DICT_RESOLUCIONES: Path = DICT_DIR / "diccionario_resoluciones.csv"
DICT_PREFIJOS_IPP: Path = DICT_DIR / "prefijos_ipp.csv"

# Resoluciones: 2 archivos inmutables en backfill/ + 1 vigente en raw/.
# La separación refleja el ciclo de vida operativo: backfill se carga una
# vez (con checksums como safety net), raw se actualiza mensualmente.
BACKFILL_RESOLUCIONES: list[Path] = [
    BACKFILL_DIR / "resoluciones_2017_2019.xlsx",
    BACKFILL_DIR / "resoluciones_2020_2023a.xlsx",
]
RAW_RESOLUCIONES: Path = RAW_DIR / "resoluciones_2023b_2026.xlsx"
BACKFILL_CHECKSUMS: Path = BACKFILL_DIR / "checksums.json"

# Nomenclador oficial del Ministerio de Justicia de la Nación.
# Se descarga con `python scripts/descargar_nomenclador.py`.
MINISTERIO_CSV: Path = EXTERNAL_DIR / "codificacion-delitos-codigo-penal-argentino-20191011.csv"
MINISTERIO_URL: str = (
    "https://datos.jus.gob.ar/dataset/d4a7a48d-d5c5-48e3-b820-0bc308d57e3c/"
    "resource/1bb19ad9-1429-41ce-8ddf-e745a4aa2395/download/"
    "codificacion-delitos-codigo-penal-argentino-20191011.csv"
)

# Indicadores mensuales del juzgado provistos por el Departamento de
# Estadística del Poder Judicial. Formato long, una fila por (mes, indicador).
INDICADORES_FILE: Path = EXTERNAL_DIR / "indicadores_jgj3si.xlsx"

# --- Archivos de salida ---------------------------------------------------

OUTPUT_CSV: Path = OUTPUT_DIR / "causas_penal_juvenil_2020_2026_limpio_diccionarios.csv"
OUTPUT_XLSX: Path = OUTPUT_DIR / "causas_penal_juvenil_2020_2026_limpio_diccionarios.xlsx"
OUTPUT_RESOLUCIONES_CSV: Path = OUTPUT_DIR / "resoluciones_2017_2026_consolidado.csv"
OUTPUT_CRUCE_CSV: Path = OUTPUT_DIR / "causas_con_metricas_resoluciones.csv"

# --- Parámetros del pipeline ----------------------------------------------

ANIO_MINIMO: int = 2020
ANIO_MAXIMO_VALIDO: int = 2030  # cota laxa para el schema

# Columnas clave que deben tener al menos un valor para conservar la fila.
COLUMNAS_CLAVE: list[str] = [
    "fecha_ingreso",
    "ipp",
    "tipo_tramite",
    "caratula_anonimizada",
    "delito",
]

# --- Logging --------------------------------------------------------------

LOG_LEVEL: int = logging.INFO
LOG_FORMAT: str = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
