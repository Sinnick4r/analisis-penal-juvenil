"""Tab 1 — Evolución temporal de las causas.

Charts:
- Causas por año (barras, año pico destacado).
- Tendencia mensual completa (línea).
"""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from dashboard.theme import ACENTO, GRIS_MEDIO, GRIS_OSCURO


def _causas_por_anio(df: pd.DataFrame) -> alt.Chart:
    """Bar chart de causas por año con el año pico destacado."""
    por_anio = (
        df.dropna(subset=["anio"])
        .groupby("anio")
        .size()
        .reset_index(name="causas")
    )
    if len(por_anio) == 0:
        return alt.Chart(pd.DataFrame({"anio": [], "causas": []})).mark_bar()

    anio_pico = int(por_anio.loc[por_anio["causas"].idxmax(), "anio"])
    por_anio["es_pico"] = por_anio["anio"] == anio_pico
    por_anio["anio_str"] = por_anio["anio"].astype(int).astype(str)

    bars = (
        alt.Chart(por_anio)
        .mark_bar(size=40)
        .encode(
            x=alt.X("anio_str:N", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("causas:Q", title="Cantidad de causas"),
            color=alt.Color(
                "es_pico:N",
                scale=alt.Scale(domain=[True, False], range=[ACENTO, GRIS_MEDIO]),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("anio_str:N", title="Año"),
                alt.Tooltip("causas:Q", title="Causas", format=","),
            ],
        )
    )

    etiquetas = (
        alt.Chart(por_anio)
        .mark_text(dy=-8, color=GRIS_OSCURO, fontSize=11)
        .encode(
            x="anio_str:N",
            y="causas:Q",
            text=alt.Text("causas:Q", format=","),
        )
    )

    return (bars + etiquetas).properties(height=320)


def _tendencia_mensual(df: pd.DataFrame) -> alt.Chart:
    """Línea de causas por mes a lo largo de todo el período."""
    df_t = df.dropna(subset=["fecha_ingreso"]).copy()
    if len(df_t) == 0:
        return alt.Chart(pd.DataFrame({"mes": [], "causas": []})).mark_line()

    df_t["mes"] = df_t["fecha_ingreso"].dt.to_period("M").dt.to_timestamp()
    por_mes = df_t.groupby("mes").size().reset_index(name="causas")

    return (
        alt.Chart(por_mes)
        .mark_line(color=ACENTO, strokeWidth=2, point=alt.OverlayMarkDef(color=ACENTO, size=20))
        .encode(
            x=alt.X("mes:T", title=None),
            y=alt.Y("causas:Q", title="Causas por mes"),
            tooltip=[
                alt.Tooltip("mes:T", title="Mes", format="%B %Y"),
                alt.Tooltip("causas:Q", title="Causas"),
            ],
        )
        .properties(height=280)
    )


def render(df: pd.DataFrame) -> None:
    """Renderiza el contenido del tab temporal."""
    if len(df) == 0:
        st.info("No hay causas que cumplan los filtros seleccionados.")
        return

    # --- Anual ---------------------------------------------------------
    por_anio = df.dropna(subset=["anio"]).groupby("anio").size()
    if len(por_anio) > 0:
        anio_pico = int(por_anio.idxmax())
        causas_pico = int(por_anio.max())
        st.subheader(
            f"El pico del período se registró en {anio_pico} con {causas_pico:,} causas".replace(",", ".")
        )
    else:
        st.subheader("Causas por año")

    st.altair_chart(_causas_por_anio(df), use_container_width=True)

    # --- Mensual -------------------------------------------------------
    st.markdown("")
    st.subheader("Evolución mes a mes")
    st.markdown(
        f"<small style='color:{GRIS_OSCURO}'>"
        "Cada punto representa un mes calendario. Útil para detectar estacionalidad "
        "y cambios bruscos en el flujo de ingreso."
        "</small>",
        unsafe_allow_html=True,
    )
    st.altair_chart(_tendencia_mensual(df), use_container_width=True)
