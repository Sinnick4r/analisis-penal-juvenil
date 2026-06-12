# Carga del df final desde el CSV generado por el pipeline
# Estrategia: prefiere el CSV del cruce (44 cols) si existe; si no, cae al de causas (28 cols)
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
from src import config


@st.cache_data(show_spinner="Cargando dataset…")
def cargar_dataset(path: Path | None = None) -> pd.DataFrame:
    fuente = _resolver_fuente(path)
    df = pd.read_csv(fuente)

    # fechas: las del cruce son nullable (NaT permitido)
    df["fecha_ingreso"] = pd.to_datetime(df["fecha_ingreso"], errors="coerce")
    if "fecha_primera_resolucion" in df.columns:
        df["fecha_primera_resolucion"] = pd.to_datetime(
            df["fecha_primera_resolucion"], errors="coerce"
        )
    if "fecha_ultima_resolucion" in df.columns:
        df["fecha_ultima_resolucion"] = pd.to_datetime(
            df["fecha_ultima_resolucion"], errors="coerce"
        )

    # anio nullable Int64 (tolerante a NaN ocasional)
    df["anio"] = df["anio"].astype("Int64")

    return df


def _resolver_fuente(path: Path | None) -> Path:
    # orden de precedencia: path explícito > output del cruce > output de causas
    if path is not None:
        if not path.exists():
            raise FileNotFoundError(f"No se encontró {path}.")
        return path

    cruce = config.OUTPUT_CRUCE_CSV
    causas = config.OUTPUT_CSV

    if cruce.exists():
        return cruce
    if causas.exists():
        return causas

    raise FileNotFoundError(
        f"No se encontró ni el dataset cruzado ({cruce}) ni el de causas ({causas}). "
        "Corré `make pipeline` (y opcionalmente `make cruce-causas-resoluciones`)."
    )


def tiene_metricas_cruce(df: pd.DataFrame) -> bool:
    # True si el df incluye las columnas que agrega el cruce
    return "n_resoluciones" in df.columns


def estadisticas_basicas(df: pd.DataFrame) -> dict:
    # calculo de KPIs
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
        "pct_sin_match": df["estado_match_ministerio"].eq("sin_equivalencia_definida").mean() * 100,
    }
