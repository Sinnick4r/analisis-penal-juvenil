# validacion cruzada del pipeline contra los indicadores oficiales del juzgado.
"""
Cruza las metricas calculadas del pipeline contra el archivo del Departamento
de Estadistica (indicadores_jgj3si.xlsx), que es la fuente que el area audita.

El cruce tiene tres niveles, porque no todos los indicadores se validan igual:

- nivel_validacion (Causas Ingresadas): el unico indicador con match de NIVEL.
  El oficial es auto-generado y cuenta tramites que no son ingresos reales; el
  pipeline cuenta los ingresos manuales validados por funcionario. El gap es
  metodologico (universo) y estable a nivel ANUAL (~0,92). A nivel mensual la
  atribucion temporal difiere (el sistema data el ingreso al entrar el tramite,
  el registro manual al asignarlo) y el ratio es ruido: se reporta, no se valida.

- consistencia_interna (Tasa de resolucion): se verifica que la tasa publicada =
  finalizadas_oficial / ingresadas_oficial * 100, dentro de +-0,5 por redondeo.
  No interviene el pipeline: valida que entendemos la formula del oficial.

- caracterizacion (Finalizadas, Tramites de Resoluciones): NO matchean a nivel.
  El consolidado captura ~50% del universo resolutivo que cuenta el oficial.
  Se reporta ratio + correlacion mensual, no tolerancia: el pipeline sigue la
  tendencia oficial (corr ~0,82) como muestra parcial, no como recuento total.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pandera.pandas as pa

from src import config
from src.indicadores import (
    SLUG_CAUSAS_FINALIZADAS,
    SLUG_CAUSAS_INGRESADAS,
    SLUG_TASA_RESOLUCION,
    SLUG_TRAMITES_RESOLUCIONES,
    cargar_indicadores,
    pivot_a_wide,
)
from src.logging_setup import get_logger

logger = get_logger(__name__)


# Categorias del consolidado que cuentan como egreso/finalizacion del proceso.
# Es el conjunto que mejor aproxima "tramites de finalizacion" del oficial.
# Ajustable: la validacion de finalizadas es caracterizacion, no match exacto.
CATEGORIAS_FINALIZACION: frozenset[str] = frozenset(
    {
        "cierre de proceso",
        "salida alternativa",
        "elevacion a juicio",
        "competencia",
        "medida de seguridad",
        "medidas alternativas",
    }
)

# Banda de ratio anual aceptada para ingresadas (pipeline/oficial).
# Permisiva a proposito; observado 0,89-0,94. Endurecer cuando haya mas años.
BANDA_INGRESADAS: tuple[float, float] = (0.85, 0.95)

# Tolerancia de la tasa publicada vs recalculada (redondeo a entero del oficial).
TOL_TASA: float = 0.5

# Clasificaciones posibles de cada fila del reporte.
CLASIFICACIONES: frozenset[str] = frozenset(
    {
        "metodologica_universo",
        "ruido_atribucion_temporal",
        "consistencia_interna_ok",
        "consistencia_interna_revisar",
        "cobertura_parcial",
        "anomalia_revisar",
    }
)


# -- series del lado pipeline --


def _periodo(fechas: pd.Series) -> pd.Series:
    # fecha -> "YYYY-MM"
    return pd.to_datetime(fechas, errors="coerce").dt.to_period("M").astype(str)


def cargar_series_pipeline(
    causas_csv: Path | None = None,
    resoluciones_csv: Path | None = None,
) -> dict[str, pd.Series]:
    """Series mensuales del pipeline indexadas por periodo "YYYY-MM".

    Devuelve un dict con las claves-slug que matchean al oficial:
    causas_ingresadas, causas_finalizadas, tramites_de_resoluciones.
    """
    causas = pd.read_csv(causas_csv or config.OUTPUT_CSV)
    res = pd.read_csv(resoluciones_csv or config.OUTPUT_RESOLUCIONES_CSV)

    # ingresadas: una causa por fecha_ingreso
    ing = causas.assign(periodo=_periodo(causas["fecha_ingreso"])).groupby("periodo").size()

    # resoluciones datadas (el backfill 2017-2019 viene sin fecha y queda fuera)
    res = res[res["fecha_resolucion"].notna()].copy()
    res["periodo"] = _periodo(res["fecha_resolucion"])

    tramites = res.groupby("periodo").size()
    fin = res[res["categoria_resolucion"].isin(CATEGORIAS_FINALIZACION)].groupby("periodo").size()

    return {
        SLUG_CAUSAS_INGRESADAS: ing,
        SLUG_CAUSAS_FINALIZADAS: fin,
        SLUG_TRAMITES_RESOLUCIONES: tramites,
    }


# -- helpers de reporte --


def _periodos_wide(wide_oficial: pd.DataFrame) -> pd.Series:
    # "YYYY-MM" alineado a cada fila del wide (no asume orden ni indice)
    return (
        wide_oficial["anio"].astype(int).astype(str)
        + "-"
        + wide_oficial["mes"].astype(int).astype(str).str.zfill(2)
    )


def _ventana(wide_oficial: pd.DataFrame) -> pd.Index:
    # periodos cubiertos por el oficial, ordenados; define la ventana de cruce
    return pd.Index(sorted(_periodos_wide(wide_oficial).tolist()))


def _serie_oficial(wide_oficial: pd.DataFrame, slug: str) -> pd.Series:
    # serie del oficial indexada por periodo, robusta al orden de filas
    return pd.Series(wide_oficial[slug].to_numpy(), index=_periodos_wide(wide_oficial))


def _alinear(
    serie_oficial: pd.Series, serie_pipeline: pd.Series, ventana: pd.Index
) -> pd.DataFrame:
    # alinea ambas series a la ventana, 0 donde no hay dato
    d = pd.DataFrame(
        {
            "valor_oficial": serie_oficial.reindex(ventana),
            "valor_pipeline": serie_pipeline.reindex(ventana),
        }
    ).fillna(0.0)
    d["diff"] = d["valor_pipeline"] - d["valor_oficial"]
    d["ratio"] = np.where(d["valor_oficial"] != 0, d["valor_pipeline"] / d["valor_oficial"], np.nan)
    return d


def _correlacion(a: pd.Series, b: pd.Series) -> float:
    # corr de Pearson; NaN si alguna serie es constante (corr indefinida)
    if a.nunique() <= 1 or b.nunique() <= 1:
        return np.nan
    return a.corr(b)


def _fila(nivel, granularidad, slug, periodo, oficial, pipeline, clasif, banda=pd.NA, corr=np.nan):
    diff = pipeline - oficial
    ratio = pipeline / oficial if oficial != 0 else np.nan
    return {
        "nivel": nivel,
        "granularidad": granularidad,
        "indicador_slug": slug,
        "periodo": periodo,
        "valor_oficial": float(oficial),
        "valor_pipeline": float(pipeline),
        "diff": float(diff),
        "ratio": ratio,
        "dentro_banda": banda,
        "correlacion": corr,
        "clasificacion": clasif,
    }


# -- construccion de cada nivel --


def _validar_ingresadas(wide, series, ventana) -> list[dict]:
    # nivel: mensual (ruido, informativo) + anual y agregado (validacion real)
    serie_of = _serie_oficial(wide, SLUG_CAUSAS_INGRESADAS)
    d = _alinear(serie_of, series[SLUG_CAUSAS_INGRESADAS], ventana)
    filas = []

    # mensual: solo se reporta; el ratio mensual es atribucion temporal
    for per, r in d.iterrows():
        filas.append(
            _fila(
                "nivel_validacion",
                "mensual",
                SLUG_CAUSAS_INGRESADAS,
                per,
                r["valor_oficial"],
                r["valor_pipeline"],
                "ruido_atribucion_temporal",
            )
        )

    # anual: aca vive el criterio de aceptacion
    d["anio"] = [p[:4] for p in d.index]
    lo, hi = BANDA_INGRESADAS
    for anio, g in d.groupby("anio"):
        of, pl = g["valor_oficial"].sum(), g["valor_pipeline"].sum()
        ratio = pl / of if of else np.nan
        dentro = bool(lo <= ratio <= hi and pl <= of)
        clasif = "metodologica_universo" if dentro else "anomalia_revisar"
        filas.append(
            _fila(
                "nivel_validacion",
                "anual",
                SLUG_CAUSAS_INGRESADAS,
                anio,
                of,
                pl,
                clasif,
                banda=dentro,
            )
        )

    # agregado de la ventana completa
    of, pl = d["valor_oficial"].sum(), d["valor_pipeline"].sum()
    ratio = pl / of
    dentro = bool(lo <= ratio <= hi and pl <= of)
    filas.append(
        _fila(
            "nivel_validacion",
            "agregado",
            SLUG_CAUSAS_INGRESADAS,
            f"{ventana[0]}_{ventana[-1]}",
            of,
            pl,
            "metodologica_universo" if dentro else "anomalia_revisar",
            banda=dentro,
        )
    )
    return filas


def _validar_consistencia_tasa(wide, ventana) -> list[dict]:
    # tasa publicada vs recalculada con las propias columnas del oficial
    sub = wide.dropna(
        subset=[SLUG_CAUSAS_INGRESADAS, SLUG_CAUSAS_FINALIZADAS, SLUG_TASA_RESOLUCION]
    )
    filas = []
    for _, row in sub.iterrows():
        ing, fin, tasa_pub = (
            row[SLUG_CAUSAS_INGRESADAS],
            row[SLUG_CAUSAS_FINALIZADAS],
            row[SLUG_TASA_RESOLUCION],
        )
        if ing == 0:
            continue
        periodo = f"{int(row['anio'])}-{int(row['mes']):02d}"
        tasa_calc = fin / ing * 100
        clasif = (
            "consistencia_interna_ok"
            if abs(tasa_pub - tasa_calc) <= TOL_TASA
            else "consistencia_interna_revisar"
        )
        filas.append(
            _fila(
                "consistencia_interna",
                "mensual",
                SLUG_TASA_RESOLUCION,
                periodo,
                oficial=tasa_pub,
                pipeline=tasa_calc,
                clasif=clasif,
            )
        )
    return filas


def _caracterizar(wide, series, ventana, slug) -> list[dict]:
    # finalizadas / tramites: ratio + correlacion, sin tolerancia
    serie_of = _serie_oficial(wide, slug)
    d = _alinear(serie_of, series[slug], ventana)
    corr = _correlacion(d["valor_oficial"], d["valor_pipeline"])
    filas = [
        _fila(
            "caracterizacion",
            "mensual",
            slug,
            per,
            r["valor_oficial"],
            r["valor_pipeline"],
            "cobertura_parcial",
        )
        for per, r in d.iterrows()
    ]
    of, pl = d["valor_oficial"].sum(), d["valor_pipeline"].sum()
    filas.append(
        _fila(
            "caracterizacion",
            "agregado",
            slug,
            f"{ventana[0]}_{ventana[-1]}",
            of,
            pl,
            "cobertura_parcial",
            corr=corr,
        )
    )
    return filas


# -- schema y orquestador --

schema_reporte = pa.DataFrameSchema(
    {
        "nivel": pa.Column(
            str, pa.Check.isin(["nivel_validacion", "consistencia_interna", "caracterizacion"])
        ),
        "granularidad": pa.Column(str, pa.Check.isin(["mensual", "anual", "agregado"])),
        "indicador_slug": pa.Column(str),
        "periodo": pa.Column(str),
        "valor_oficial": pa.Column(float),
        "valor_pipeline": pa.Column(float),
        "diff": pa.Column(float),
        "ratio": pa.Column(float, nullable=True),
        "dentro_banda": pa.Column("boolean", nullable=True),
        "correlacion": pa.Column(float, nullable=True),
        "clasificacion": pa.Column(str, pa.Check.isin(list(CLASIFICACIONES))),
    },
    strict=True,
    coerce=True,
)


def construir_validacion(
    wide_oficial: pd.DataFrame,
    series_pipeline: dict[str, pd.Series],
) -> pd.DataFrame:
    # arma el reporte tidy combinando los tres niveles
    ventana = _ventana(wide_oficial)
    filas: list[dict] = []
    filas += _validar_ingresadas(wide_oficial, series_pipeline, ventana)
    filas += _validar_consistencia_tasa(wide_oficial, ventana)
    filas += _caracterizar(wide_oficial, series_pipeline, ventana, SLUG_CAUSAS_FINALIZADAS)
    filas += _caracterizar(wide_oficial, series_pipeline, ventana, SLUG_TRAMITES_RESOLUCIONES)

    df = pd.DataFrame(filas)
    df["dentro_banda"] = df["dentro_banda"].astype("boolean")
    return schema_reporte.validate(df).reset_index(drop=True)


def validar(
    indicadores_path: Path | None = None,
    causas_csv: Path | None = None,
    resoluciones_csv: Path | None = None,
    salida: Path | None = None,
) -> pd.DataFrame:
    # corre el cruce end-to-end y exporta el CSV
    wide = pivot_a_wide(cargar_indicadores(indicadores_path))
    series = cargar_series_pipeline(causas_csv, resoluciones_csv)
    reporte = construir_validacion(wide, series)

    destino = salida or config.OUTPUT_VALIDACION_CSV
    destino.parent.mkdir(parents=True, exist_ok=True)
    reporte.to_csv(destino, index=False)

    _log_resumen(reporte)
    logger.info("Validacion exportada a %s (%d filas)", destino, len(reporte))
    return reporte


def _log_resumen(reporte: pd.DataFrame) -> None:
    # resumen legible de los hallazgos clave
    agg = reporte[reporte.granularidad == "agregado"].set_index("indicador_slug")
    ing = agg.loc[SLUG_CAUSAS_INGRESADAS]
    logger.info(
        "INGRESADAS agregado: oficial=%.0f pipeline=%.0f ratio=%.3f dentro_banda=%s",
        ing.valor_oficial,
        ing.valor_pipeline,
        ing.ratio,
        ing.dentro_banda,
    )
    tasa = reporte[reporte.indicador_slug == SLUG_TASA_RESOLUCION]
    ok = (tasa.clasificacion == "consistencia_interna_ok").sum()
    logger.info("TASA consistencia interna: %d/%d meses OK (+-%.1f)", ok, len(tasa), TOL_TASA)
    for slug in (SLUG_CAUSAS_FINALIZADAS, SLUG_TRAMITES_RESOLUCIONES):
        row = agg.loc[slug]
        logger.info("%s caracterizacion: ratio=%.3f corr=%.3f", slug, row.ratio, row.correlacion)


if __name__ == "__main__":
    validar()
