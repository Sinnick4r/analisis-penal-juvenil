"""Entry point del dashboard Streamlit.

Correr con:
    streamlit run dashboard/app.py
o:
    make dashboard

Requiere que el pipeline haya generado el CSV en `outputs/`. Si no existe,
mostramos un mensaje con instrucciones.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Permite ejecutar `streamlit run dashboard/app.py` desde la raíz del proyecto
# sin necesidad de instalar el paquete en modo editable.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from dashboard.components.filtros import (  # noqa: E402
    aplicar_filtros,
    boton_descarga,
    sidebar_filtros,
)
from dashboard.components.kpis import fila_kpis  # noqa: E402
from dashboard.data import cargar_dataset  # noqa: E402
from dashboard.tabs import calidad, delitos, gestion, temporal, tramites  # noqa: E402
from dashboard.theme import CSS_GLOBAL, aplicar_tema_altair  # noqa: E402

# --- Configuración de página ---------------------------------------------

st.set_page_config(
    page_title="Causas penal juvenil — 2020-2026",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

aplicar_tema_altair()
st.markdown(CSS_GLOBAL, unsafe_allow_html=True)


# --- Carga del dataset ---------------------------------------------------

try:
    df = cargar_dataset()
except FileNotFoundError as exc:
    st.title("Causas del fuero penal juvenil")
    st.error(str(exc))
    st.markdown(
        "**Cómo generar el dataset:**\n\n"
        "1. Colocá el Excel anonimizado en `data/raw/`.\n"
        "2. Descargá el nomenclador con `make nomenclador`.\n"
        "3. Corré `make pipeline`.\n"
        "4. Volvé a abrir este dashboard."
    )
    st.stop()


# --- Sidebar + filtros ---------------------------------------------------

filtros = sidebar_filtros(df)
df_f = aplicar_filtros(df, filtros)

boton_descarga(df_f, nombre_archivo="causas_filtradas.csv")

st.sidebar.markdown("---")
st.sidebar.markdown(
    "<small style='color:#666'>"
    "Dataset producido por el pipeline reproducible en `src/`. "
    "Última actualización: ver fecha de modificación del CSV en `outputs/`."
    "</small>",
    unsafe_allow_html=True,
)


# --- Cabecera + KPIs -----------------------------------------------------

st.title("Causas del fuero penal juvenil — 2020-2026")
st.markdown(
    "<p style='color:#4A4A4A; margin-top:-0.5rem'>"
    "Buenos Aires · Pipeline reproducible con normalización jurídica y cruce "
    "con el nomenclador del Ministerio de Justicia."
    "</p>",
    unsafe_allow_html=True,
)

fila_kpis(df_f)

st.markdown("")  # separador suave


# --- Tabs ----------------------------------------------------------------

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "Evolución temporal",
        "Delitos",
        "Trámites",
        "Gestión",
        "Calidad de datos",
    ]
)

with tab1:
    temporal.render(df_f)

with tab2:
    delitos.render(df_f)

with tab3:
    tramites.render(df_f)

with tab4:
    gestion.render(df_f)

with tab5:
    calidad.render(df_f)
