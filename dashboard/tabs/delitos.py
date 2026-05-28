"""Tab 2 — Delitos.

Charts:
- Top 10 delitos (barras horizontales, top 2 destacados con narrativa).
- Evolución year-over-year de los top 5 delitos.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from dashboard.theme import ACENTO, GRIS_MEDIO, GRIS_OSCURO, PALETA_CUALITATIVA


def _top_delitos_chart(df: pd.DataFrame, top_n: int = 10, destacar: int = 2) -> alt.Chart:
    """Bar chart horizontal de los top N delitos, con los top `destacar` en acento."""
    top = df["delito_estandar"].value_counts().head(top_n).reset_index()
    top.columns = ["delito", "causas"]
    top["es_top"] = [True] * destacar + [False] * (len(top) - destacar)

    bars = (
        alt.Chart(top)
        .mark_bar()
        .encode(
            y=alt.Y(
                "delito:N",
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
                alt.Tooltip("delito:N", title="Delito"),
                alt.Tooltip("causas:Q", title="Causas", format=","),
            ],
        )
    )

    etiquetas = (
        alt.Chart(top)
        .mark_text(align="left", baseline="middle", dx=4, color=GRIS_OSCURO, fontSize=11)
        .encode(
            y=alt.Y("delito:N", sort="-x"),
            x="causas:Q",
            text=alt.Text("causas:Q", format=","),
        )
    )

    return (bars + etiquetas).properties(height=max(280, top_n * 28))


def _evolucion_top_chart(df: pd.DataFrame, top_n: int = 5) -> alt.Chart:
    """Líneas de evolución anual para los top N delitos del período."""
    top_delitos = df["delito_estandar"].value_counts().head(top_n).index.tolist()
    sub = df[df["delito_estandar"].isin(top_delitos)].dropna(subset=["anio"])
    por_anio = sub.groupby(["anio", "delito_estandar"]).size().reset_index(name="causas")
    por_anio["anio_str"] = por_anio["anio"].astype(int).astype(str)

    return (
        alt.Chart(por_anio)
        .mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=40))
        .encode(
            x=alt.X("anio_str:N", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("causas:Q", title="Causas"),
            color=alt.Color(
                "delito_estandar:N",
                title="Delito",
                scale=alt.Scale(range=PALETA_CUALITATIVA),
                sort=top_delitos,  # mantener orden por frecuencia
            ),
            tooltip=[
                alt.Tooltip("anio_str:N", title="Año"),
                alt.Tooltip("delito_estandar:N", title="Delito"),
                alt.Tooltip("causas:Q", title="Causas"),
            ],
        )
        .properties(height=320)
    )


def _resumen_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula el resumen de flags jurídicos como tabla."""
    total = len(df)
    flags = {
        "Tentativa": int(df["tentativa"].sum()),
        "Agravado (cualquier tipo)": int(df["agravado_flag"].sum()),
        "  — agravante por arma": int(df["agravante_arma"].sum()),
        "  — agravante poblado y banda": int(df["agravante_poblado_banda"].sum()),
        "  — agravante por escalamiento": int(df["agravante_escalamiento"].sum()),
        "  — agravante por efracción": int(df["agravante_efraccion"].sum()),
        "  — agravante vehículo en vía pública": int(df["agravante_vehiculo_via_publica"].sum()),
        "  — agravante no especificado": int(df["agravante_no_especificado"].sum()),
        "Proceso especial (amparo, habeas corpus)": int(df["es_proceso_especial"].sum()),
        "Posible delito múltiple": int(df["posible_delito_multiple"].sum()),
    }
    return pd.DataFrame(
        {
            "Indicador": list(flags.keys()),
            "Cantidad": list(flags.values()),
            "% sobre el total": [
                f"{(v / total * 100):.1f}%" if total > 0 else "—" for v in flags.values()
            ],
        }
    )


def render(df: pd.DataFrame) -> None:
    if len(df) == 0:
        st.info("No hay causas que cumplan los filtros seleccionados.")
        return

    # --- Top delitos ---------------------------------------------------
    top = df["delito_estandar"].value_counts().head(10)
    if len(top) >= 2 and len(df) > 0:
        top2 = top.head(2)
        nombres_top2 = " y ".join(top2.index.tolist())
        pct = top2.sum() / len(df) * 100
        st.subheader(f"{nombres_top2.capitalize()} concentran el {pct:.1f}% de las causas")
    else:
        st.subheader("Top de delitos en el período")

    st.altair_chart(_top_delitos_chart(df), use_container_width=True)

    # --- Evolución ----------------------------------------------------
    st.markdown("")
    st.subheader("Evolución anual de los principales delitos")
    st.markdown(
        f"<small style='color:{GRIS_OSCURO}'>"
        "Cada serie muestra cómo cambia el ingreso anual de cada delito top. "
        "Útil para detectar cambios de patrón delictivo o de criterio de carátula."
        "</small>",
        unsafe_allow_html=True,
    )
    st.altair_chart(_evolucion_top_chart(df), use_container_width=True)

    # --- Resumen de flags ---------------------------------------------
    st.markdown("")
    st.subheader("Resumen de flags jurídicos")
    st.dataframe(
        _resumen_flags(df),
        hide_index=True,
        use_container_width=True,
    )
