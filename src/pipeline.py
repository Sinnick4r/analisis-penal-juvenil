"""Orquestador del pipeline ETL completo.

Ejecutable como módulo:

    python -m src.pipeline

Encadena:
1. Carga de datos crudos (Excel).
2. Carga de diccionarios y nomenclador.
3. Normalización de delitos.
4. Cruce con ministerio.
5. Normalización de trámites.
6. Selección de columnas finales y validación de schema.
7. Exportación a CSV (y opcionalmente XLSX).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from src import config
from src.diccionarios import cargar_diccionarios, cargar_nomenclador_ministerio
from src.logging_setup import get_logger
from src.normalizacion import (
    cargar_datos_raw,
    cruzar_ministerio,
    normalizar_delitos,
    normalizar_tramites,
    seleccionar_columnas_finales,
)
from src.schema import schema_dataset_final

logger = get_logger(__name__)


def correr_pipeline(
    raw_path: Path | None = None,
    output_csv: Path | None = None,
    output_xlsx: Path | None = None,
    exportar_xlsx: bool = True,
) -> pd.DataFrame:
    """Ejecuta el pipeline completo y persiste el dataset final.

    Args:
        raw_path: ruta al Excel de causas. Si es None, usa `config.RAW_FILE`.
        output_csv: ruta de salida CSV. Si es None, usa `config.OUTPUT_CSV`.
        output_xlsx: ruta de salida XLSX. Si es None, usa `config.OUTPUT_XLSX`.
        exportar_xlsx: si True, también exporta a XLSX.

    Returns:
        DataFrame final validado y persistido.

    Raises:
        FileNotFoundError: si falta el Excel, los diccionarios o el nomenclador.
        pandera.errors.SchemaError: si el output no cumple el contrato.
    """
    logger.info("=== Pipeline iniciado ===")

    # 1. Datos crudos.
    df = cargar_datos_raw(path=raw_path)

    # 2. Diccionarios + nomenclador.
    dicts = cargar_diccionarios()
    nomenclador = cargar_nomenclador_ministerio()

    # 3. Normalización de delitos.
    df = normalizar_delitos(df, dicts["delitos_local"])

    # 4. Cruce con ministerio.
    df = cruzar_ministerio(df, dicts["delitos_ministerio"], nomenclador)

    # 5. Normalización de trámites.
    df = normalizar_tramites(df, dicts["tramites"])

    # 6. Selección de columnas finales + validación de schema.
    df_final = seleccionar_columnas_finales(df)
    logger.info("Validando schema sobre %d filas y %d columnas",
                len(df_final), len(df_final.columns))
    df_final = schema_dataset_final.validate(df_final)

    # 7. Persistencia.
    out_csv = output_csv if output_csv is not None else config.OUTPUT_CSV
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df_final.to_csv(out_csv, index=False)
    logger.info("CSV exportado: %s (%d filas)", out_csv, len(df_final))

    if exportar_xlsx:
        out_xlsx = output_xlsx if output_xlsx is not None else config.OUTPUT_XLSX
        df_final.to_excel(out_xlsx, index=False)
        logger.info("XLSX exportado: %s", out_xlsx)

    logger.info("=== Pipeline completado ===")
    return df_final


def main() -> int:
    """Entry point CLI. Devuelve código de salida (0 OK, 1 error)."""
    try:
        correr_pipeline()
    except FileNotFoundError as exc:
        logger.error("Archivo faltante: %s", exc)
        return 1
    except Exception:
        logger.exception("Error inesperado en el pipeline")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
