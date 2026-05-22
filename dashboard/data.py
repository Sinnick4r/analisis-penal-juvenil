"""Carga del dataset final desde el CSV generado por el pipeline.

Usa `st.cache_data` para evitar releer el archivo en cada interacción.
La cache se invalida cuando cambia el mtime del archivo.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
from src import config


@st.cache_data(show_spinner="Cargando dataset…")
def cargar_dataset(path: Path | None = None) -> pd.DataFrame:
    """Carga el CSV final del pipeline.

    Args:
        path: ruta al CSV. Si es None, usa `config.OUTPUT_CSV`.

    Returns:
        DataFrame con las 28 columnas del contrato pandera.

    Raises:
        FileNotFoundError: si no existe el CSV (correr `make pipeline` primero).
    """
    fuente = path if path is not None else config.OUTPUT_CSV
    if not fuente.exists():
        raise FileNotFoundError(
            f"No se encontró el dataset en {fuente}. "
            "Corré `make pipeline` para generarlo."
        )

    df = pd.read_csv(fuente)
    df["fecha_ingreso"] = pd.to_datetime(df["fecha_ingreso"], errors="coerce")

    # Asegurar dtype int para anio (a veces se carga como float si hay NaN)
    df["anio"] = df["anio"].astype("Int64")

    return df


def estadisticas_basicas(df: pd.DataFrame) -> dict:
    """Calcula KPIs principales sobre un DataFrame (sin filtros)."""
    if len(df) == 0:
        return {
            "total": 0,
            "pct_tentativa": 0.0,
            "pct_agravado": 0.0,
            "pct_sin_match": 0.0,
        }
    return {
        "total": len(df),
        "pct_tentativa": df["tentativa"].mean() * 100,
        "pct_agravado": df["agravado_flag"].mean() * 100,
        "pct_sin_match": df["estado_match_ministerio"].eq(
            "sin_equivalencia_definida"
        ).mean() * 100,
    }
