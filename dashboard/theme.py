#tema visual del dashboard: paleta + config base de Altair

from __future__ import annotations

import altair as alt

# paleta de colores
ACENTO = "#1F4E79"
ACENTO_SUAVE = "#7BA7C9"
GRIS_CLARO = "#D9D9D9"
GRIS_MEDIO = "#B8B8B8"
GRIS_OSCURO = "#4A4A4A"
GRIS_TEXTO = "#262626"
ALERTA = "#C0392B"
EXITO = "#2E7D32"
PALETA_CUALITATIVA = ["#1F4E79", "#7BA7C9", "#B8B8B8", "#4A4A4A", "#9C9C9C"]


# -config de Altair

def _config_base() -> dict:
    return {
        "config": {
            "view": {
                "stroke": "transparent", 
            },
            "axis": {
                "domain": False,
                "grid": False,
                "ticks": False,
                "labelColor": GRIS_TEXTO,
                "labelFontSize": 12,
                "titleColor": GRIS_TEXTO,
                "titleFontSize": 12,
                "titleFontWeight": "normal",
            },
            "axisY": {
                "labelPadding": 6,
            },
            "legend": {
                "labelColor": GRIS_TEXTO,
                "titleColor": GRIS_TEXTO,
                "labelFontSize": 11,
                "titleFontSize": 11,
                "titleFontWeight": "normal",
            },
            "title": {
                "color": GRIS_TEXTO,
                "fontSize": 14,
                "fontWeight": "normal",
                "anchor": "start", 
            },
            "range": {
                "category": PALETA_CUALITATIVA,
            },
        }
    }


def aplicar_tema_altair() -> None:
    #registra y activa el tema custom en Altair. Idempotente
    if hasattr(alt, "theme"):
        # Altair >= 5.5: register devuelve un decorator.
        api = alt.theme
        if "judicial" not in api.names():
            api.register("judicial", enable=True)(_config_base)
        else:
            api.enable("judicial")
    else:
        # Altair < 5.5: legacy API.
        api = alt.themes
        if "judicial" not in api.names():
            api.register("judicial", _config_base)
        api.enable("judicial")


# helpers de color

def color_destacado(es_destacado, acento: str = ACENTO, base: str = GRIS_MEDIO) -> alt.Color:

    return alt.Color(
        f"{es_destacado}:N",
        scale=alt.Scale(domain=[True, False], range=[acento, base]),
        legend=None,
    )


# overrides

CSS_GLOBAL = """
<style>
    /* Esconder marca de Streamlit y el menú hamburguesa */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Tipografía más compacta para títulos */
    h1 { font-size: 1.8rem !important; font-weight: 500; }
    h2 { font-size: 1.3rem !important; font-weight: 500; margin-top: 1.5rem; }
    h3 { font-size: 1.05rem !important; font-weight: 500; color: #4A4A4A; }

    /* KPI cards con borde sutil en lugar del default */
    [data-testid="stMetric"] {
        background-color: #FAFAFA;
        padding: 12px 16px;
        border-left: 3px solid #1F4E79;
        border-radius: 4px;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.85rem;
        color: #4A4A4A;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.6rem;
        font-weight: 500;
    }

    /* Compactar tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        padding-top: 6px;
        padding-bottom: 6px;
    }
</style>
"""
