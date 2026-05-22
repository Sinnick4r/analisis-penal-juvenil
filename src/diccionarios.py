"""Carga y preparación de diccionarios de equivalencias.

Encapsula la I/O de los 3 diccionarios locales más el nomenclador oficial
del Ministerio de Justicia. Cumple PY-05 del guideline (separar I/O de la
transformación).
"""
from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import TypedDict

import pandas as pd

from src import config
from src.logging_setup import get_logger

logger = get_logger(__name__)


class Diccionarios(TypedDict):
    """Contenedor tipado de los 3 diccionarios locales del proyecto."""
    delitos_local: pd.DataFrame
    delitos_ministerio: pd.DataFrame
    tramites: pd.DataFrame


def cargar_diccionarios(
    dict_dir: Path | None = None,
) -> Diccionarios:
    """Carga los 3 diccionarios locales como DataFrames.

    Args:
        dict_dir: directorio donde están los CSVs. Si es None, usa `config.DICT_DIR`.

    Returns:
        Diccionario tipado con 3 DataFrames.

    Raises:
        FileNotFoundError: si falta alguno de los CSVs esperados.
    """
    base = dict_dir if dict_dir is not None else config.DICT_DIR

    paths = {
        "delitos_local": base / "diccionario_delitos_local.csv",
        "delitos_ministerio": base / "diccionario_delitos_ministerio.csv",
        "tramites": base / "diccionario_tramites.csv",
    }

    faltantes = [str(p) for p in paths.values() if not p.exists()]
    if faltantes:
        raise FileNotFoundError(
            f"Faltan archivos de diccionarios: {faltantes}"
        )

    dicts: Diccionarios = {
        "delitos_local": pd.read_csv(paths["delitos_local"]),
        "delitos_ministerio": pd.read_csv(paths["delitos_ministerio"]),
        "tramites": pd.read_csv(paths["tramites"]),
    }

    logger.info(
        "Diccionarios cargados: delitos_local=%d, delitos_ministerio=%d, tramites=%d",
        len(dicts["delitos_local"]),
        len(dicts["delitos_ministerio"]),
        len(dicts["tramites"]),
    )
    return dicts


def cargar_nomenclador_ministerio(
    path: Path | None = None,
    solo_vigentes: bool = True,
) -> pd.DataFrame:
    """Carga el nomenclador oficial del Ministerio de Justicia.

    Aplica la misma normalización de columnas que el notebook original:
    minúsculas, sin tildes, espacios reemplazados por guión bajo.

    Args:
        path: ruta al CSV oficial. Si es None, usa `config.MINISTERIO_CSV`.
        solo_vigentes: si True (default), filtra `vigente == 'SI'`.

    Returns:
        DataFrame con columnas estandarizadas. Garantiza la presencia de
        `delito_descripcion`; las columnas `delito_articulo`, `codigo_delito`
        y `tipo` se aseguran (creando vacías si no existen) para que el
        cruce posterior no falle.

    Raises:
        FileNotFoundError: si el archivo no existe.
        ValueError: si falta la columna esencial `delito_descripcion`.
    """
    fuente = path if path is not None else config.MINISTERIO_CSV
    if not fuente.exists():
        raise FileNotFoundError(
            f"No se encontró el nomenclador del Ministerio en {fuente}. "
            "Descargalo con: python scripts/descargar_nomenclador.py"
        )

    df = pd.read_csv(fuente)
    df.columns = [
        unicodedata.normalize("NFKD", str(c).strip().lower())
        .encode("ascii", "ignore")
        .decode("utf-8")
        .replace(" ", "_")
        for c in df.columns
    ]

    if solo_vigentes and "vigente" in df.columns:
        df["vigente"] = df["vigente"].astype("string").str.strip().str.upper()
        df = df[df["vigente"] == "SI"].copy()
        logger.info("Nomenclador filtrado por vigente=SI: %d filas", len(df))

    if "delito_descripcion" not in df.columns:
        raise ValueError(
            "El nomenclador no tiene la columna obligatoria 'delito_descripcion'."
        )

    # Asegurar columnas opcionales: si vienen con otro nombre, renombrar;
    # si faltan, crear vacías.
    if "delito_articulo" not in df.columns:
        for c in df.columns:
            if "articulo" in c:
                df = df.rename(columns={c: "delito_articulo"})
                break
        else:
            df["delito_articulo"] = pd.NA

    if "codigo_delito" not in df.columns:
        df["codigo_delito"] = pd.NA

    if "tipo" not in df.columns:
        df["tipo"] = pd.NA

    df["delito_articulo"] = df["delito_articulo"].astype("string").str.strip()

    return df
