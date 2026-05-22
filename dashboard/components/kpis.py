"""Fila de KPIs principales del dashboard."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.data import estadisticas_basicas


def fila_kpis(df: pd.DataFrame) -> None:
    """Renderiza una fila de 4 KPIs principales sobre el DataFrame filtrado."""
    stats = estadisticas_basicas(df)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Total de causas",
            value=f"{stats['total']:,}".replace(",", "."),
        )
    with col2:
        st.metric(
            label="% en tentativa",
            value=f"{stats['pct_tentativa']:.1f}%",
        )
    with col3:
        st.metric(
            label="% agravadas",
            value=f"{stats['pct_agravado']:.1f}%",
        )
    with col4:
        st.metric(
            label="% sin equivalencia ministerial",
            value=f"{stats['pct_sin_match']:.1f}%",
            help="Causas donde el cruce con el nomenclador oficial no es jurídicamente prudente."
        )
