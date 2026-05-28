"""Tab 5 — Gestión.

Visualiza las métricas derivadas del cruce causas ↔ resoluciones (Iteración C).
Requiere el output de `make cruce-causas-resoluciones`. Si no está disponible,
muestra un mensaje informativo en vez de fallar.

Charts:
- KPIs específicos de gestión (4 métricas).
- Modalidad resolutiva: cómo terminan las causas.
- Duración procesal: distribución de días desde ingreso hasta primera resolución.
- Tiempo de proceso por tipo de delito: top N con más volumen.
- Cohorte por año de ingreso: causas resueltas vs sin resolución registrada.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from dashboard.data import tiene_metricas_cruce
from dashboard.theme import ACENTO, GRIS_CLARO, GRIS_MEDIO, GRIS_OSCURO

# --- KPI row del tab -----------------------------------------------------


def _fila_kpis(df: pd.DataFrame) -> None:
    """KPIs específicos del tab. 4 columnas en una fila."""
    con_res = df["tiene_resoluciones"].sum()
    pct_con_res = con_res / len(df) * 100 if len(df) else 0

    # Métricas temporales: excluir días negativos (causas reingresadas,
    # IPPs con resoluciones previas). No son errores, pero distorsionan
    # la mediana del flujo "normal" del juzgado.
    temporales = df[
        df["dias_hasta_primera_resolucion"].notna() & (df["dias_hasta_primera_resolucion"] >= 0)
    ]
    mediana_primera = (
        int(temporales["dias_hasta_primera_resolucion"].median()) if len(temporales) else 0
    )
    mediana_proceso = int(temporales["dias_proceso"].median()) if len(temporales) else 0
    pct_cierre = df["tiene_cierre_proceso"].mean() * 100 if len(df) else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Causas con resoluciones", f"{con_res:,}", f"{pct_con_res:.1f}% del total")
    c2.metric("Días hasta primera resolución", f"{mediana_primera}", "mediana")
    c3.metric("Días de proceso total", f"{mediana_proceso}", "mediana")
    c4.metric("Causas con cierre de proceso", f"{pct_cierre:.1f}%", "sobreseimiento u otros")


# --- Chart 1: Modalidad resolutiva ---------------------------------------

# Mapeo flag → nombre legible para el eje.
_MODALIDADES = {
    "tiene_cierre_proceso": "Cierre de proceso",
    "tiene_competencia": "Competencia (transfiere)",
    "tiene_derivacion_servicio_local": "Derivación a servicio local",
    "tiene_salida_alternativa": "Salida alternativa",
    "tiene_medida_coercion": "Medida de coerción",
    "tiene_elevacion_juicio": "Elevación a juicio",
    "tiene_rebeldia": "Rebeldía",
}


def _modalidad_resolutiva_chart(df: pd.DataFrame) -> alt.Chart:
    """Bar horizontal con % de causas que tuvieron al menos 1 resolución de cada tipo.

    Acento Knaflic en la barra más alta; el resto en gris.
    """
    total = len(df)
    if total == 0:
        return alt.Chart(pd.DataFrame({"modalidad": [], "pct": []})).mark_bar()

    filas = []
    for flag, nombre in _MODALIDADES.items():
        if flag in df.columns:
            filas.append({"modalidad": nombre, "pct": df[flag].sum() / total * 100})
    datos = pd.DataFrame(filas).sort_values("pct", ascending=False)
    # Marcar la más alta para acento.
    datos["destacar"] = [True] + [False] * (len(datos) - 1)

    bars = (
        alt.Chart(datos)
        .mark_bar()
        .encode(
            y=alt.Y("modalidad:N", sort="-x", title=None, axis=alt.Axis(labelLimit=300)),
            x=alt.X(
                "pct:Q",
                title="% de causas",
                scale=alt.Scale(domain=[0, max(datos["pct"].max() * 1.1, 10)]),
            ),
            color=alt.Color(
                "destacar:N",
                scale=alt.Scale(domain=[True, False], range=[ACENTO, GRIS_MEDIO]),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("modalidad:N", title="Modalidad"),
                alt.Tooltip("pct:Q", title="% causas", format=".1f"),
            ],
        )
    )
    etiquetas = (
        alt.Chart(datos)
        .mark_text(align="left", baseline="middle", dx=4, color=GRIS_OSCURO, fontSize=11)
        .encode(
            y=alt.Y("modalidad:N", sort="-x"),
            x="pct:Q",
            text=alt.Text("pct:Q", format=".1f"),
        )
    )
    return (bars + etiquetas).properties(height=max(220, len(datos) * 32))


# --- Chart 2: Duración procesal ------------------------------------------

# Bins en escala log-amigable. Más resolución en los rangos cortos donde
# se concentra la mediana (11 días), menos en la cola larga.
_BINS_DURACION = [
    (0, 7, "0-7 días"),
    (8, 30, "8-30 días"),
    (31, 90, "31-90 días"),
    (91, 180, "91-180 días"),
    (181, 365, "181-365 días"),
    (366, 10_000, "Más de 1 año"),
]


def _duracion_procesal_chart(df: pd.DataFrame) -> alt.Chart:
    """Histograma con la distribución de días hasta primera resolución."""
    # Solo causas con métrica válida y no negativa (las negativas son outliers
    # explicables — reingresos, jurisdicción externa — y van aparte).
    datos = df[
        df["dias_hasta_primera_resolucion"].notna() & (df["dias_hasta_primera_resolucion"] >= 0)
    ]["dias_hasta_primera_resolucion"]

    if len(datos) == 0:
        return alt.Chart(pd.DataFrame({"rango": [], "causas": []})).mark_bar()

    conteos = []
    for lo, hi, label in _BINS_DURACION:
        n = ((datos >= lo) & (datos <= hi)).sum()
        conteos.append({"rango": label, "causas": int(n), "orden": lo})
    bins_df = pd.DataFrame(conteos)

    # El bin más alto es el acento, el resto gris.
    max_idx = bins_df["causas"].idxmax()
    bins_df["destacar"] = bins_df.index == max_idx

    return (
        alt.Chart(bins_df)
        .mark_bar()
        .encode(
            x=alt.X(
                "rango:N", sort=alt.SortField("orden"), title="Tiempo hasta primera resolución"
            ),
            y=alt.Y("causas:Q", title="Cantidad de causas"),
            color=alt.Color(
                "destacar:N",
                scale=alt.Scale(domain=[True, False], range=[ACENTO, GRIS_MEDIO]),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("rango:N", title="Rango"),
                alt.Tooltip("causas:Q", title="Causas", format=","),
            ],
        )
        .properties(height=280)
    )


# --- Chart 3: Tiempo de proceso por tipo de delito -----------------------


def _tiempo_por_delito_chart(df: pd.DataFrame, top_n: int = 10) -> alt.Chart:
    """Mediana de días de proceso por delito, top N por volumen.

    Solo considera causas con métrica temporal válida (positiva).
    Filtra delitos con menos de 5 casos para evitar conclusiones de poca evidencia.
    """
    datos = df[
        df["dias_proceso"].notna() & (df["dias_proceso"] >= 0) & df["delito_estandar"].notna()
    ].copy()

    if len(datos) == 0:
        return alt.Chart(pd.DataFrame({"delito": [], "dias": []})).mark_bar()

    por_delito = (
        datos.groupby("delito_estandar")
        .agg(
            mediana_dias=("dias_proceso", "median"),
            n_causas=("dias_proceso", "size"),
        )
        .reset_index()
    )
    # Robustez estadística: descartar delitos con < 5 causas.
    por_delito = por_delito[por_delito["n_causas"] >= 5]
    por_delito = por_delito.sort_values("n_causas", ascending=False).head(top_n)

    if len(por_delito) == 0:
        return alt.Chart(pd.DataFrame({"delito": [], "dias": []})).mark_bar()

    # Los 2 delitos con proceso más largo y los 2 más cortos van en acento.
    por_delito_ord = por_delito.sort_values("mediana_dias")
    extremos_ids = set(list(por_delito_ord.head(2).index) + list(por_delito_ord.tail(2).index))
    por_delito["destacar"] = por_delito.index.isin(extremos_ids)

    return (
        alt.Chart(por_delito)
        .mark_bar()
        .encode(
            y=alt.Y("delito_estandar:N", sort="-x", title=None, axis=alt.Axis(labelLimit=400)),
            x=alt.X("mediana_dias:Q", title="Mediana de días de proceso"),
            color=alt.Color(
                "destacar:N",
                scale=alt.Scale(domain=[True, False], range=[ACENTO, GRIS_MEDIO]),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("delito_estandar:N", title="Delito"),
                alt.Tooltip("mediana_dias:Q", title="Mediana días", format=".0f"),
                alt.Tooltip("n_causas:Q", title="Cantidad de causas", format=","),
            ],
        )
        .properties(height=max(280, len(por_delito) * 28))
    )


# --- Chart 4: Cohorte por año --------------------------------------------


def _cohorte_anual_chart(df: pd.DataFrame) -> alt.Chart:
    """Barras apiladas: causas con vs sin resolución registrada, por año de ingreso.

    Permite ver el efecto cohorte: causas recientes naturalmente tienen menor
    tasa de resolución (todavía están en trámite).
    """
    if "anio" not in df.columns or len(df) == 0:
        return alt.Chart(pd.DataFrame({"anio": [], "estado": [], "causas": []})).mark_bar()

    datos = df.copy()
    datos["estado"] = datos["tiene_resoluciones"].map(
        {True: "Con resoluciones", False: "Sin resoluciones"}
    )
    por_anio = datos.groupby(["anio", "estado"], observed=True).size().reset_index(name="causas")

    return (
        alt.Chart(por_anio)
        .mark_bar()
        .encode(
            x=alt.X("anio:O", title="Año de ingreso"),
            y=alt.Y("causas:Q", title="Cantidad de causas", stack=True),
            color=alt.Color(
                "estado:N",
                scale=alt.Scale(
                    domain=["Con resoluciones", "Sin resoluciones"],
                    range=[ACENTO, GRIS_CLARO],
                ),
                legend=alt.Legend(title=None, orient="bottom"),
            ),
            tooltip=[
                alt.Tooltip("anio:O", title="Año"),
                alt.Tooltip("estado:N", title="Estado"),
                alt.Tooltip("causas:Q", title="Causas", format=","),
            ],
        )
        .properties(height=300)
    )


# --- Entry point del tab -------------------------------------------------


def render(df: pd.DataFrame) -> None:
    """Renderiza el tab Gestión. Degrada gracefully si no hay datos del cruce."""
    if not tiene_metricas_cruce(df):
        st.info(
            "El tab **Gestión** requiere el dataset cruzado. "
            "Para habilitarlo, corré:\n\n"
            "```\nmake pipeline\nmake pipeline-resoluciones\nmake cruce-causas-resoluciones\n```\n\n"
            "Después recargá esta página."
        )
        return

    if len(df) == 0:
        st.warning("No hay causas con los filtros actuales.")
        return

    # KPI row
    _fila_kpis(df)
    st.divider()

    # Chart 1
    st.subheader("Cómo terminan las causas")
    st.caption(
        "Una misma causa puede tener varias modalidades a lo largo de su trámite; "
        "los porcentajes no suman 100%."
    )
    st.altair_chart(_modalidad_resolutiva_chart(df), use_container_width=True)

    st.divider()

    # Chart 2
    st.subheader("Cuánto tarda la primera resolución")
    st.caption(
        "Distribución de días entre el ingreso de la causa y su primera "
        "resolución registrada. Excluye causas sin métrica temporal disponible."
    )
    st.altair_chart(_duracion_procesal_chart(df), use_container_width=True)

    st.divider()

    # Chart 3
    st.subheader("Tiempo de proceso por tipo de delito")
    st.caption(
        "Mediana de días desde el ingreso hasta la última resolución, "
        "para los delitos con al menos 5 causas."
    )
    st.altair_chart(_tiempo_por_delito_chart(df), use_container_width=True)

    st.divider()

    # Chart 4
    st.subheader("Resoluciones registradas por año de ingreso")
    st.caption(
        "Las causas recientes naturalmente tienen menor proporción de "
        "resoluciones registradas — siguen en trámite. Las causas viejas sin "
        "resoluciones son mayormente acumuladas a una causa principal."
    )
    st.altair_chart(_cohorte_anual_chart(df), use_container_width=True)
