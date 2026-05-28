#Carga del df final desde el CSV generado por el pipeline

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
from src import config


@st.cache_data(show_spinner="Cargando dataset…")
def cargar_dataset(path: Path | None = None) -> pd.DataFrame:

    fuente = path if path is not None else config.OUTPUT_CSV
    if not fuente.exists():
        raise FileNotFoundError(
            f"No se encontró el dataset en {fuente}. "
            "Corré `make pipeline` para generarlo."
        )

    df = pd.read_csv(fuente)
    df["fecha_ingreso"] = pd.to_datetime(df["fecha_ingreso"], errors="coerce")

    # asegurar dtype int para anio (a veces se carga como float si hay NaN)
    df["anio"] = df["anio"].astype("Int64")

    return df


def estadisticas_basicas(df: pd.DataFrame) -> dict:
    #calculo de KPIs
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
