"""Sidebar de filtros del dashboard.

Filtros disponibles:
- Año (multiselect)
- Tipo de delito estandarizado (multiselect)
- Estado del match ministerial (multiselect)

Devuelve un dict con los valores seleccionados. Aplicación al DataFrame
con `aplicar_filtros`.
"""
from __future__ import annotations

from typing import TypedDict

import pandas as pd
import streamlit as st


class Filtros(TypedDict):
    anios: list[int]
    delitos: list[str]
    estados_match: list[str]


def sidebar_filtros(df: pd.DataFrame) -> Filtros:
    """Renderiza la sidebar y devuelve los filtros seleccionados."""
    st.sidebar.header("Filtros")

    # Año
    anios_disponibles = sorted(
        [int(a) for a in df["anio"].dropna().unique()]
    )
    anios_sel = st.sidebar.multiselect(
        "Año de ingreso",
        options=anios_disponibles,
        default=anios_disponibles,
        help="Seleccioná uno o más años. Vacío equivale a todos.",
    )

    # Delito estándar
    delitos_disponibles = sorted(df["delito_estandar"].dropna().unique().tolist())
    delitos_sel = st.sidebar.multiselect(
        "Delito estandarizado",
        options=delitos_disponibles,
        default=[],
        help="Vacío = todos los delitos.",
    )

    # Estado del match ministerial
    estados_disponibles = sorted(
        df["estado_match_ministerio"].dropna().unique().tolist()
    )
    estados_sel = st.sidebar.multiselect(
        "Estado del cruce ministerial",
        options=estados_disponibles,
        default=[],
        help="Vacío = todos los estados.",
    )

    st.sidebar.markdown("---")

    return Filtros(
        anios=anios_sel,
        delitos=delitos_sel,
        estados_match=estados_sel,
    )


def aplicar_filtros(df: pd.DataFrame, filtros: Filtros) -> pd.DataFrame:
    """Devuelve el subset del DataFrame que cumple los filtros.

    Listas vacías equivalen a 'sin filtro' (no a 'filtrar todo afuera').
    """
    out = df.copy()
    if filtros["anios"]:
        out = out[out["anio"].isin(filtros["anios"])]
    if filtros["delitos"]:
        out = out[out["delito_estandar"].isin(filtros["delitos"])]
    if filtros["estados_match"]:
        out = out[out["estado_match_ministerio"].isin(filtros["estados_match"])]
    return out


def boton_descarga(df: pd.DataFrame, nombre_archivo: str = "causas_filtradas.csv") -> None:
    """Renderiza un botón de descarga del DataFrame filtrado en la sidebar."""
    csv = df.to_csv(index=False).encode("utf-8")
    st.sidebar.download_button(
        label=f"Descargar CSV ({len(df)} filas)",
        data=csv,
        file_name=nombre_archivo,
        mime="text/csv",
        use_container_width=True,
    )
