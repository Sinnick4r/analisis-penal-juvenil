"""Tab 3 — Trámites de ingreso.

Charts:
- Top 10 trámites (barras horizontales, top destacado).
- Heatmap top trámites × top delitos.
- Tabla descargable del cruce completo.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from dashboard.theme import ACENTO, ACENTO_SUAVE, GRIS_MEDIO, GRIS_OSCURO


def _top_tramites_chart(df: pd.DataFrame, top_n: int = 10) -> alt.Chart:
    """Bar chart horizontal de los top N trámites."""
    top = df["tipo_tramite_estandar"].dropna().value_counts().head(top_n).reset_index()
    top.columns = ["tramite", "causas"]
    top["es_top"] = [True] + [False] * (len(top) - 1)

    bars = (
        alt.Chart(top)
        .mark_bar()
        .encode(
            y=alt.Y(
                "tramite:N",
                sort="-x",
                title=None,
                axis=alt.Axis(labelLimit=400),
            ),
            x=alt.X("causas:Q", title="Cantidad de causas"),
            color=alt.Color(
                "es_top:N",
                scale=alt.Scale(domain=[True, False], range=[ACENTO, GRIS_MEDIO]),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("tramite:N", title="Trámite"),
                alt.Tooltip("causas:Q", title="Causas", format=","),
            ],
        )
    )
    etiquetas = (
        alt.Chart(top)
        .mark_text(align="left", baseline="middle", dx=4, color=GRIS_OSCURO, fontSize=11)
        .encode(
            y=alt.Y("tramite:N", sort="-x"),
            x="causas:Q",
            text=alt.Text("causas:Q", format=","),
        )
    )
    return (bars + etiquetas).properties(height=max(280, top_n * 28))


def _heatmap_tramite_delito(
    df: pd.DataFrame, top_tramites: int = 5, top_delitos: int = 8
) -> alt.Chart:
    """Heatmap del cruce top trámites × top delitos."""
    top_tr = df["tipo_tramite_estandar"].dropna().value_counts().head(top_tramites).index.tolist()
    top_de = df["delito_estandar"].value_counts().head(top_delitos).index.tolist()

    cruce = (
        df[df["tipo_tramite_estandar"].isin(top_tr) & df["delito_estandar"].isin(top_de)]
        .groupby(["tipo_tramite_estandar", "delito_estandar"])
        .size()
        .reset_index(name="causas")
    )

    base = alt.Chart(cruce).encode(
        x=alt.X(
            "tipo_tramite_estandar:N",
            title=None,
            sort=top_tr,
            axis=alt.Axis(labelAngle=-30, labelLimit=200),
        ),
        y=alt.Y("delito_estandar:N", title=None, sort=top_de, axis=alt.Axis(labelLimit=300)),
    )

    rectangulos = base.mark_rect().encode(
        color=alt.Color(
            "causas:Q",
            scale=alt.Scale(range=["#EEF4F8", ACENTO_SUAVE, ACENTO]),
            legend=alt.Legend(title="Causas"),
        ),
        tooltip=[
            alt.Tooltip("tipo_tramite_estandar:N", title="Trámite"),
            alt.Tooltip("delito_estandar:N", title="Delito"),
            alt.Tooltip("causas:Q", title="Causas"),
        ],
    )

    texto = base.mark_text(fontSize=11).encode(
        text=alt.Text("causas:Q", format=","),
        color=alt.condition(
            "datum.causas > " + str(int(cruce["causas"].max() / 2) if len(cruce) > 0 else 0),
            alt.value("white"),
            alt.value(GRIS_OSCURO),
        ),
    )

    return (rectangulos + texto).properties(
        height=max(260, top_delitos * 32),
    )


def render(df: pd.DataFrame) -> None:
    if len(df) == 0:
        st.info("No hay causas que cumplan los filtros seleccionados.")
        return

    # --- Top trámites --------------------------------------------------
    top_tram = df["tipo_tramite_estandar"].dropna().value_counts()
    if len(top_tram) > 0:
        nombre = top_tram.index[0]
        pct = top_tram.iloc[0] / len(df) * 100
        st.subheader(f'El trámite "{nombre}" representa el {pct:.1f}% del ingreso')
    else:
        st.subheader("Top de trámites de ingreso")

    st.altair_chart(_top_tramites_chart(df), use_container_width=True)

    # --- Cruce trámites × delitos -------------------------------------
    st.markdown("")
    st.subheader("Cruce de los principales trámites con los principales delitos")
    st.markdown(
        f"<small style='color:{GRIS_OSCURO}'>"
        "Lectura: cuántas causas combinan cada par (trámite × delito). "
        "Los rectángulos oscuros marcan combinaciones predominantes."
        "</small>",
        unsafe_allow_html=True,
    )
    st.altair_chart(_heatmap_tramite_delito(df), use_container_width=True)

    # --- Tabla descargable del cruce completo --------------------------
    with st.expander("Ver tabla completa de combinaciones trámite × delito"):
        cruce_full = (
            df.dropna(subset=["tipo_tramite_estandar"])
            .groupby(["tipo_tramite_estandar", "delito_estandar"])
            .size()
            .reset_index(name="causas")
            .sort_values("causas", ascending=False)
        )
        st.dataframe(cruce_full, hide_index=True, use_container_width=True)
