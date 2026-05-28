"""Cruce causas ↔ resoluciones por IPP canónico.

Toma como entrada los dos outputs ya generados:
- `outputs/causas_penal_juvenil_2020_2026_limpio_diccionarios.csv` (Iteración A)
- `outputs/resoluciones_2017_2026_consolidado.csv` (Iteración B)

Produce un dataset con un row por causa enriquecido con métricas derivadas
del cruce: cantidad de resoluciones, fechas primera/última, días de
proceso, flags booleanos para las 7 categorías de resolución principales.

NOTA DE DEUDA TÉCNICA: el dataset de causas hoy no tiene `ipp_canonico` ni
`tipo_ipp` como columnas nativas. Este módulo los calcula localmente
aplicando `normalizar_ipp` al campo `ipp`. En una iteración futura,
incorporar esas columnas al schema de causas (`src/normalizacion.py`)
para que el cruce las consuma directamente.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from src import config
from src.logging_setup import get_logger
from src.normalizar_ipp import clasificar_ipp, normalizar_ipp

logger = get_logger(__name__)


# --- Constantes -----------------------------------------------------------

# Categorías de resolución que se convierten en flags booleanos en el output.
# Las 7 más frecuentes cubren ~85% del volumen total de resoluciones
# (resto queda como `categorias_resolucion` concatenado para audit).
CATEGORIAS_PRINCIPALES: tuple[str, ...] = (
    "cierre de proceso",
    "elevacion a juicio",
    "salida alternativa",
    "competencia",
    "medida de coercion",
    "derivacion a servicio local",
    "rebeldia",
)


def _slug_categoria(categoria: str) -> str:
    """Convierte una categoría a slug para nombre de columna.

    >>> _slug_categoria("cierre de proceso")
    'cierre_proceso'
    >>> _slug_categoria("derivacion a servicio local")
    'derivacion_servicio_local'
    """
    # Quita conectores comunes ("a", "de") para slugs más concisos.
    palabras = categoria.lower().split()
    palabras = [p for p in palabras if p not in {"a", "de", "del", "la", "el"}]
    return "_".join(palabras)


# Slugs precomputados (estables). Mantener este mapeo si cambiás
# CATEGORIAS_PRINCIPALES — los tests dependen de estos nombres.
SLUGS_CATEGORIAS: dict[str, str] = {cat: _slug_categoria(cat) for cat in CATEGORIAS_PRINCIPALES}


# --- Carga (I/O) ----------------------------------------------------------


def cargar_causas_con_canonico(path: Path | None = None) -> pd.DataFrame:
    """Carga el CSV de causas y agrega `ipp_canonico` + `tipo_ipp`.

    Esta es la deuda técnica documentada arriba: los hace localmente
    aplicando `normalizar_ipp` al campo `ipp` original.
    """
    p = path if path is not None else config.OUTPUT_CSV
    if not p.exists():
        raise FileNotFoundError(
            f"No se encontró el output de causas en {p}. Corré `make pipeline` primero."
        )
    df = pd.read_csv(p)
    df["fecha_ingreso"] = pd.to_datetime(df["fecha_ingreso"], errors="coerce")
    df["tipo_ipp"] = df["ipp"].apply(clasificar_ipp)
    df["ipp_canonico"] = df["ipp"].apply(normalizar_ipp).astype("string")
    return df


def cargar_resoluciones_consolidado(path: Path | None = None) -> pd.DataFrame:
    """Carga el CSV consolidado de resoluciones con dtypes correctos."""
    p = path if path is not None else config.OUTPUT_RESOLUCIONES_CSV
    if not p.exists():
        raise FileNotFoundError(
            f"No se encontró el output de resoluciones en {p}. "
            "Corré `make pipeline-resoluciones` primero."
        )
    df = pd.read_csv(p)
    df["fecha_resolucion"] = pd.to_datetime(df["fecha_resolucion"], errors="coerce")
    return df


# --- Cálculo de métricas (puro) -------------------------------------------


def calcular_metricas_por_ipp(resoluciones: pd.DataFrame) -> pd.DataFrame:
    """Para cada `ipp_canonico`, calcula las métricas agregadas.

    Args:
        resoluciones: DataFrame de resoluciones consolidado.

    Returns:
        DataFrame con un row por `ipp_canonico` y columnas:
        - `n_resoluciones` (int)
        - `fecha_primera_resolucion`, `fecha_ultima_resolucion` (datetime, NaT
          si todas las resoluciones del IPP son de RAW1 sin fecha exacta)
        - `tiene_<categoria>` x 7 (bool)
        - `categorias_resolucion` (str, concat de categorías únicas con " | ")
    """
    res = resoluciones.dropna(subset=["ipp_canonico"]).copy()
    if len(res) == 0:
        # DataFrame vacío bien tipado.
        cols = [
            "ipp_canonico",
            "n_resoluciones",
            "fecha_primera_resolucion",
            "fecha_ultima_resolucion",
            "categorias_resolucion",
            *[f"tiene_{slug}" for slug in SLUGS_CATEGORIAS.values()],
        ]
        return pd.DataFrame(columns=cols)

    # Agregaciones base.
    metricas = (
        res.groupby("ipp_canonico")
        .agg(
            n_resoluciones=("ipp_canonico", "size"),
            fecha_primera_resolucion=("fecha_resolucion", "min"),
            fecha_ultima_resolucion=("fecha_resolucion", "max"),
            categorias_resolucion=(
                "categoria_resolucion",
                lambda s: " | ".join(sorted(set(s.dropna()))),
            ),
        )
        .reset_index()
    )

    # Flags booleanos por categoría: pivot eficiente vs. groupby+apply.
    crosstab = pd.crosstab(res["ipp_canonico"], res["categoria_resolucion"]) > 0
    # Asegurar que todas las categorías principales tengan una columna,
    # aunque no aparezcan en los datos.
    for cat in CATEGORIAS_PRINCIPALES:
        if cat not in crosstab.columns:
            crosstab[cat] = False
    # Quedarnos solo con las principales y renombrar a tiene_<slug>.
    crosstab = crosstab[list(CATEGORIAS_PRINCIPALES)].copy()
    crosstab.columns = [f"tiene_{SLUGS_CATEGORIAS[c]}" for c in crosstab.columns]
    crosstab = crosstab.reset_index()

    metricas = metricas.merge(crosstab, on="ipp_canonico", how="left", validate="1:1")
    return metricas


# --- Cruce ----------------------------------------------------------------


def cruzar(causas: pd.DataFrame, resoluciones: pd.DataFrame) -> pd.DataFrame:
    """Cruce LEFT desde causas. Preserva todas las causas, anota cuáles
    tienen resoluciones registradas.

    Args:
        causas: DataFrame de causas con `ipp_canonico` ya calculado.
        resoluciones: DataFrame consolidado de resoluciones.

    Returns:
        DataFrame de causas + columnas derivadas. Mismo número de filas
        que `causas`.
    """
    n_inicial = len(causas)

    metricas = calcular_metricas_por_ipp(resoluciones)
    cruce = causas.merge(
        metricas,
        on="ipp_canonico",
        how="left",
        validate="m:1",
    )

    # Validación de shape post-merge (regla DATA-07).
    assert len(cruce) == n_inicial, f"Cruce alteró cantidad de filas: {n_inicial} → {len(cruce)}"

    # Defaults para causas sin resoluciones registradas.
    cruce["n_resoluciones"] = cruce["n_resoluciones"].fillna(0).astype(int)
    cruce["tiene_resoluciones"] = cruce["n_resoluciones"] > 0
    cruce["categorias_resolucion"] = cruce["categorias_resolucion"].fillna("")
    for slug in SLUGS_CATEGORIAS.values():
        col = f"tiene_{slug}"
        cruce[col] = cruce[col].fillna(False).astype(bool)

    # Métricas temporales: diferencia en días entre fechas.
    # Solo válido cuando ambas fechas existen (causas con fecha_ingreso real
    # Y al menos una resolución con fecha exacta de RAW2/RAW3).
    cruce["dias_hasta_primera_resolucion"] = (
        cruce["fecha_primera_resolucion"] - cruce["fecha_ingreso"]
    ).dt.days.astype("Int64")
    cruce["dias_proceso"] = (
        cruce["fecha_ultima_resolucion"] - cruce["fecha_ingreso"]
    ).dt.days.astype("Int64")

    return cruce


# --- Auditoría del cruce --------------------------------------------------


def reporte_auditoria(causas: pd.DataFrame, resoluciones: pd.DataFrame) -> dict:
    """Estadísticas descriptivas del cruce para logging y dashboard de calidad.

    No es un reporte de "errores" — la asimetría entre causas y
    resoluciones es esperable (ver documentación del proyecto):
    - Causas sin resoluciones: acumuladas, archivadas sin mérito, recientes.
    - Resoluciones huérfanas: IPPs de causas anteriores a 2020 (fuera del
      registro de causas), o de otra jurisdicción.
    """
    ipps_causas = set(causas["ipp_canonico"].dropna())
    ipps_res = set(resoluciones["ipp_canonico"].dropna())

    interseccion = ipps_causas & ipps_res
    solo_causas = ipps_causas - ipps_res
    solo_res = ipps_res - ipps_causas

    audit = {
        "causas_total": len(causas),
        "causas_ipp_canonico_unicas": len(ipps_causas),
        "resoluciones_ipp_canonico_unicas": len(ipps_res),
        "ipps_en_ambos_datasets": len(interseccion),
        "causas_sin_resoluciones_unicas": len(solo_causas),
        "resoluciones_huerfanas_ipps_unicas": len(solo_res),
        "resoluciones_huerfanas_filas": int(resoluciones["ipp_canonico"].isin(solo_res).sum()),
    }
    return audit


# --- Orquestador ----------------------------------------------------------


def correr_cruce(
    causas_path: Path | None = None,
    resoluciones_path: Path | None = None,
    output_path: Path | None = None,
) -> pd.DataFrame:
    """Orquestador del cruce. Carga, cruza, valida schema, persiste.

    Returns:
        DataFrame final del cruce, mismo número de filas que el input
        de causas.
    """
    from src.schema import schema_causas_con_resoluciones

    logger.info("=== Cruce causas ↔ resoluciones iniciado ===")

    causas = cargar_causas_con_canonico(causas_path)
    resoluciones = cargar_resoluciones_consolidado(resoluciones_path)

    logger.info(
        "Inputs: %d causas, %d filas de resoluciones",
        len(causas),
        len(resoluciones),
    )

    cruce = cruzar(causas, resoluciones)

    logger.info("Validando schema sobre %d filas", len(cruce))
    cruce = schema_causas_con_resoluciones.validate(cruce)

    audit = reporte_auditoria(causas, resoluciones)
    logger.info("Auditoría del cruce: %s", audit)

    out = output_path if output_path is not None else config.OUTPUT_CRUCE_CSV
    out.parent.mkdir(parents=True, exist_ok=True)
    cruce.to_csv(out, index=False)
    logger.info("CSV del cruce exportado: %s", out)

    logger.info("=== Cruce completado ===")
    return cruce


def main() -> int:
    """Entry point CLI. `python -m src.cruce_causas_resoluciones`."""
    try:
        correr_cruce()
    except FileNotFoundError as exc:
        logger.error("Archivo faltante: %s", exc)
        return 1
    except Exception:
        logger.exception("Error inesperado en el cruce")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
