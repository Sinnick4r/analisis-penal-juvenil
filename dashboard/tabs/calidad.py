"""Tab 4 — Calidad de datos y cola de revisión.

Este tab convierte al dashboard en herramienta operativa: muestra el estado
del cruce ministerial y la cola de causas que conviene revisar para
enriquecer los diccionarios locales.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from dashboard.theme import ACENTO, ALERTA, EXITO, GRIS_MEDIO, GRIS_OSCURO

# Mapeo del estado del match a un color semántico (verde/azul/gris/rojo).
COLORES_ESTADO_MATCH: dict[str, str] = {
    "match_univoco": EXITO,
    "match_ambiguo": ACENTO,
    "sin_equivalencia_definida": GRIS_MEDIO,
    "proceso_especial": GRIS_OSCURO,
    "sin_delito_informado": ALERTA,
    "sin_match": ALERTA,
}


def _distribucion_match_chart(df: pd.DataFrame) -> alt.Chart:
    """Bar chart horizontal de la distribución del estado del match."""
    dist = df["estado_match_ministerio"].value_counts().reset_index()
    dist.columns = ["estado", "causas"]
    dist["pct"] = dist["causas"] / dist["causas"].sum() * 100

    bars = (
        alt.Chart(dist)
        .mark_bar()
        .encode(
            y=alt.Y("estado:N", sort="-x", title=None, axis=alt.Axis(labelLimit=300)),
            x=alt.X("causas:Q", title="Cantidad de causas"),
            color=alt.Color(
                "estado:N",
                scale=alt.Scale(
                    domain=list(COLORES_ESTADO_MATCH.keys()),
                    range=list(COLORES_ESTADO_MATCH.values()),
                ),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("estado:N", title="Estado"),
                alt.Tooltip("causas:Q", title="Causas", format=","),
                alt.Tooltip("pct:Q", title="% del total", format=".1f"),
            ],
        )
    )

    etiquetas = (
        alt.Chart(dist)
        .mark_text(align="left", baseline="middle", dx=4, color=GRIS_OSCURO, fontSize=11)
        .encode(
            y=alt.Y("estado:N", sort="-x"),
            x="causas:Q",
            text=alt.Text("pct:Q", format=".1f"),
        )
    )

    return (bars + etiquetas).properties(height=240)


def _construir_cola_revision(df: pd.DataFrame) -> pd.DataFrame:
    """Filtra el subconjunto de causas que requieren revisión humana.

    Criterios (cualquiera dispara):
    - sin_match: el cruce ministerial no encontró ninguna correspondencia.
    - posible_delito_multiple: puede requerir separación manual.
    - agravante_no_especificado: está marcado como agravado pero sin sub-tipo.
    - sin_delito_informado: la causa no tiene delito cargado.
    """
    mask = (
        (df["estado_match_ministerio"] == "sin_match")
        | (df["estado_match_ministerio"] == "sin_delito_informado")
        | df["posible_delito_multiple"]
        | df["agravante_no_especificado"]
    )
    cols = [
        "anio",
        "ipp",
        "delito_raw",
        "delito_estandar",
        "estado_match_ministerio",
        "posible_delito_multiple",
        "agravante_no_especificado",
    ]
    return df.loc[mask, cols].copy()


def _motivos_revision(fila: pd.Series) -> str:
    """Genera la lista de motivos por los que la fila entró en la cola."""
    motivos = []
    if fila["estado_match_ministerio"] == "sin_match":
        motivos.append("sin cruce ministerial")
    if fila["estado_match_ministerio"] == "sin_delito_informado":
        motivos.append("delito no informado")
    if fila["posible_delito_multiple"]:
        motivos.append("posible múltiple")
    if fila["agravante_no_especificado"]:
        motivos.append("agravante sin especificar")
    return "; ".join(motivos)


def render(df: pd.DataFrame) -> None:
    if len(df) == 0:
        st.info("No hay causas que cumplan los filtros seleccionados.")
        return

    # --- Distribución del estado del match -----------------------------
    pct_univoco = df["estado_match_ministerio"].eq("match_univoco").mean() * 100
    pct_problemas = (
        df["estado_match_ministerio"]
        .isin(["sin_equivalencia_definida", "sin_match", "sin_delito_informado"])
        .mean()
        * 100
    )

    if pct_univoco >= 60:
        st.subheader(f"El {pct_univoco:.1f}% de las causas tiene cruce ministerial unívoco")
    else:
        st.subheader(
            f"El {pct_problemas:.1f}% de las causas presenta algún problema de equivalencia"
        )

    st.altair_chart(_distribucion_match_chart(df), use_container_width=True)

    st.markdown(
        f"<small style='color:{GRIS_OSCURO}'>"
        "<b>match_univoco</b>: el delito tiene una correspondencia unívoca en el nomenclador.<br>"
        "<b>match_ambiguo</b>: el delito mapea a más de un código del nomenclador.<br>"
        "<b>sin_equivalencia_definida</b>: el cruce no es jurídicamente prudente.<br>"
        "<b>proceso_especial</b>: amparo, habeas corpus u otros no clasificables como delito.<br>"
        "<b>sin_delito_informado</b>: la causa no tiene delito cargado en la fuente.<br>"
        "<b>sin_match</b>: el delito no apareció en el diccionario local (revisar)."
        "</small>",
        unsafe_allow_html=True,
    )

    # --- Cola de revisión ---------------------------------------------
    st.markdown("")
    st.subheader("Cola de revisión")
    cola = _construir_cola_revision(df)

    if len(cola) == 0:
        st.success(
            "Ninguna causa del subconjunto filtrado requiere revisión manual. La calidad es buena."
        )
        return

    cola["motivos"] = cola.apply(_motivos_revision, axis=1)
    cola_display = cola[
        [
            "anio",
            "ipp",
            "delito_raw",
            "delito_estandar",
            "estado_match_ministerio",
            "motivos",
        ]
    ].rename(
        columns={
            "anio": "Año",
            "ipp": "IPP",
            "delito_raw": "Delito (raw)",
            "delito_estandar": "Delito normalizado",
            "estado_match_ministerio": "Estado del match",
            "motivos": "Motivos de revisión",
        }
    )

    st.markdown(
        f"<small style='color:{GRIS_OSCURO}'>"
        f"<b>{len(cola)} causas</b> entraron en la cola "
        f"({len(cola) / len(df) * 100:.1f}% del subconjunto filtrado). "
        "Revisar estas filas y, cuando corresponda, agregar la equivalencia faltante "
        "al diccionario local."
        "</small>",
        unsafe_allow_html=True,
    )

    st.dataframe(cola_display, hide_index=True, use_container_width=True, height=380)

    st.download_button(
        label=f"Descargar cola de revisión ({len(cola)} filas)",
        data=cola_display.to_csv(index=False).encode("utf-8"),
        file_name="cola_revision.csv",
        mime="text/csv",
    )
