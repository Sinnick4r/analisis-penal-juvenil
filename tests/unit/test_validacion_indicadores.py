# tests del cruce contra indicadores oficiales
import numpy as np
import pandas as pd
import pytest
from src import config
from src.validacion_indicadores import (
    BANDA_INGRESADAS,
    CATEGORIAS_FINALIZACION,
    cargar_series_pipeline,
    construir_validacion,
    schema_reporte,
    validar,
)

SLUG_ING = "causas_ingresadas"
SLUG_FIN = "causas_finalizadas"
SLUG_TASA = "tasa_de_resolucion"
SLUG_TR = "tramites_de_resoluciones"


# -- fixtures sinteticas --


def _wide(filas: list[dict]) -> pd.DataFrame:
    # arma un wide minimo desordenado a proposito (robustez de indice)
    df = pd.DataFrame(filas)
    return df.sample(frac=1, random_state=0).reset_index(drop=True)


def _series(ing=None, fin=None, tr=None) -> dict:
    def s(d):
        return pd.Series(d, dtype=float) if d else pd.Series(dtype=float)

    return {SLUG_ING: s(ing or {}), SLUG_FIN: s(fin or {}), SLUG_TR: s(tr or {})}


@pytest.fixture
def causas_csv(tmp_path):
    df = pd.DataFrame(
        {
            "fecha_ingreso": ["2021-01-10", "2021-01-25", "2021-02-03", "2021-03-15"],
            "ipp": ["a", "b", "c", "d"],
        }
    )
    p = tmp_path / "causas.csv"
    df.to_csv(p, index=False)
    return p


@pytest.fixture
def resoluciones_csv(tmp_path):
    df = pd.DataFrame(
        {
            "fecha_resolucion": ["2021-01-20", "2021-01-22", "2021-02-10", np.nan],
            "categoria_resolucion": [
                "cierre de proceso",  # finalizacion
                "medida de coercion",  # interlocutoria, NO finaliza
                "salida alternativa",  # finalizacion
                "cierre de proceso",  # sin fecha -> se excluye
            ],
        }
    )
    p = tmp_path / "resoluciones.csv"
    df.to_csv(p, index=False)
    return p


# -- series del pipeline --


def test_ingresadas_se_cuentan_por_mes(causas_csv, resoluciones_csv):
    series = cargar_series_pipeline(causas_csv, resoluciones_csv)
    ing = series[SLUG_ING]
    assert ing["2021-01"] == 2
    assert ing["2021-02"] == 1
    assert ing["2021-03"] == 1


def test_finalizadas_solo_cuenta_categorias_de_egreso(causas_csv, resoluciones_csv):
    series = cargar_series_pipeline(causas_csv, resoluciones_csv)
    fin = series[SLUG_FIN]
    # enero: 1 cierre (la coercion no cuenta); febrero: 1 salida alternativa
    assert fin["2021-01"] == 1
    assert fin["2021-02"] == 1


def test_resoluciones_sin_fecha_quedan_fuera(causas_csv, resoluciones_csv):
    series = cargar_series_pipeline(causas_csv, resoluciones_csv)
    # 3 datadas en total (la 4ta sin fecha se excluye)
    assert series[SLUG_TR].sum() == 3


def test_categorias_finalizacion_son_subconjunto_de_egreso():
    assert "cierre de proceso" in CATEGORIAS_FINALIZACION
    assert "medida de coercion" not in CATEGORIAS_FINALIZACION


# -- construccion del reporte --


def _wide_un_anio(ing, fin, tasa, tr):
    # un año con 12 meses identicos para sumas anuales limpias
    return _wide(
        [
            {"anio": 2021, "mes": m, SLUG_ING: ing, SLUG_FIN: fin, SLUG_TASA: tasa, SLUG_TR: tr}
            for m in range(1, 13)
        ]
    )


def test_reporte_pasa_schema():
    wide = _wide_un_anio(10, 5, 50.0, 8)
    series = _series(
        ing={f"2021-{m:02d}": 9 for m in range(1, 13)},
        fin={f"2021-{m:02d}": 3 for m in range(1, 13)},
        tr={f"2021-{m:02d}": 4 for m in range(1, 13)},
    )
    rep = construir_validacion(wide, series)
    # no levanta = pasa schema; ademas validamos explicito
    schema_reporte.validate(rep)
    assert set(rep.nivel) == {"nivel_validacion", "consistencia_interna", "caracterizacion"}


def test_ingresadas_dentro_de_banda_es_metodologica():
    # ratio anual 9/10 = 0.9 -> dentro de banda
    wide = _wide_un_anio(10, 5, 50.0, 8)
    series = _series(ing={f"2021-{m:02d}": 9 for m in range(1, 13)})
    rep = construir_validacion(wide, series)
    anual = rep[(rep.indicador_slug == SLUG_ING) & (rep.granularidad == "anual")].iloc[0]
    assert anual.dentro_banda is True or anual.dentro_banda == True  # noqa: E712
    assert anual.clasificacion == "metodologica_universo"
    assert BANDA_INGRESADAS[0] <= anual.ratio <= BANDA_INGRESADAS[1]


def test_ingresadas_pipeline_mayor_que_oficial_es_anomalia():
    # pipeline (12) > oficial (10) viola la invariante estructural
    wide = _wide_un_anio(10, 5, 50.0, 8)
    series = _series(ing={f"2021-{m:02d}": 12 for m in range(1, 13)})
    rep = construir_validacion(wide, series)
    anual = rep[(rep.indicador_slug == SLUG_ING) & (rep.granularidad == "anual")].iloc[0]
    assert bool(anual.dentro_banda) is False
    assert anual.clasificacion == "anomalia_revisar"


def test_consistencia_tasa_ok_y_revisar():
    # mes 1: tasa pub 50 vs calc 50.0 (ok); mes 2: pub 99 vs calc 50.0 (revisar)
    wide = _wide(
        [
            {"anio": 2021, "mes": 1, SLUG_ING: 10, SLUG_FIN: 5, SLUG_TASA: 50.0, SLUG_TR: 8},
            {"anio": 2021, "mes": 2, SLUG_ING: 10, SLUG_FIN: 5, SLUG_TASA: 99.0, SLUG_TR: 8},
        ]
    )
    rep = construir_validacion(wide, _series())
    tasa = rep[rep.nivel == "consistencia_interna"].set_index("periodo")
    assert tasa.loc["2021-01"].clasificacion == "consistencia_interna_ok"
    assert tasa.loc["2021-02"].clasificacion == "consistencia_interna_revisar"


def test_caracterizacion_reporta_correlacion():
    # oficial variable mes a mes para que la correlacion este definida
    wide = _wide(
        [
            {"anio": 2021, "mes": m, SLUG_ING: 10, SLUG_FIN: m * 2, SLUG_TASA: 50.0, SLUG_TR: m * 3}
            for m in range(1, 13)
        ]
    )
    series = _series(
        fin={f"2021-{m:02d}": m for m in range(1, 13)},
        tr={f"2021-{m:02d}": m for m in range(1, 13)},
    )
    rep = construir_validacion(wide, series)
    agg = rep[(rep.granularidad == "agregado") & (rep.nivel == "caracterizacion")]
    assert agg["correlacion"].notna().all()


# -- aceptacion sobre datos reales (se saltea si no estan los CSV) --


@pytest.mark.skipif(
    not (
        config.INDICADORES_FILE.exists()
        and config.OUTPUT_CSV.exists()
        and config.OUTPUT_RESOLUCIONES_CSV.exists()
    ),
    reason="archivos reales no presentes (causa-por-causa fuera del repo)",
)
def test_aceptacion_datos_reales(tmp_path):
    rep = validar(salida=tmp_path / "val.csv")

    ing_agg = rep[(rep.indicador_slug == SLUG_ING) & (rep.granularidad == "agregado")].iloc[0]
    assert bool(ing_agg.dentro_banda) is True
    assert BANDA_INGRESADAS[0] <= ing_agg.ratio <= BANDA_INGRESADAS[1]

    # ingresadas: pipeline <= oficial todos los años (invariante de universo)
    anual = rep[(rep.indicador_slug == SLUG_ING) & (rep.granularidad == "anual")]
    assert (anual.valor_pipeline <= anual.valor_oficial).all()

    # tasa: consistencia interna en todos los meses
    tasa = rep[rep.nivel == "consistencia_interna"]
    assert (tasa.clasificacion == "consistencia_interna_ok").all()
