"""Pipeline de resoluciones del juzgado.

Tres fuentes:
- 2 archivos de backfill inmutables en `data/backfill/`
- 1 archivo vigente en `data/raw/` que se actualiza mensualmente

Output: un único CSV consolidado con `fuente_raw` como audit trail,
multi-resoluciones explotadas a una fila por resolución canónica.

Safety net: checksum SHA-256 sobre cada backfill, verificado en cada
corrida. Si un archivo de backfill cambió, log warning ruidoso.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

from src import config
from src.logging_setup import get_logger
from src.normalizar_ipp import (
    clasificar_ipp,
    normalizar_ipp,
    requiere_revision_ipp,
)

logger = get_logger(__name__)

# --- Constantes -----------------------------------------------------------

# Mapeo de archivo → identificador `fuente_raw` para audit trail.
# Las claves son los nombres de archivo esperados; los valores son los
# strings del enum del schema.
FUENTES_RAW: dict[str, str] = {
    "resoluciones_2017_2019.xlsx": "backfill_2017_2019",
    "resoluciones_2020_2023a.xlsx": "backfill_2020_2023a",
    "resoluciones_2023b_2026.xlsx": "raw_2023b_2026",
}

# Separadores de multi-resolución detectados en los 3 RAWs.
# Orden importa: regex compilado con todos al mismo tiempo.
SEPARADORES_MULTI: re.Pattern[str] = re.compile(
    r"\s*,\s*|\s+/\s+|\s+-\s+|\s+y\s+",
    flags=re.IGNORECASE,
)

# Patología conocida: "s/" como abreviatura de "sin", NO separador.
# Lo capturo antes del split para no fragmentar "Rebeldia s/ efecto".
# NO consume espacios siguientes — esos son parte de la palabra que sigue.
SLASH_FALSO_POSITIVO: re.Pattern[str] = re.compile(
    r"\bs/",
    flags=re.IGNORECASE,
)


# --- Carga + safety net (I/O) ---------------------------------------------


def cargar_resoluciones(
    backfill_paths: list[Path] | None = None,
    raw_path: Path | None = None,
    verificar_checksums: bool = True,
) -> pd.DataFrame:
    """Pipeline completo de resoluciones: carga + normalización + concat.

    Args:
        backfill_paths: lista de archivos backfill. Default: `config.BACKFILL_RESOLUCIONES`.
        raw_path: archivo raw vigente. Default: `config.RAW_RESOLUCIONES`.
        verificar_checksums: si True, valida que los backfills no hayan
            cambiado desde la última corrida.

    Returns:
        DataFrame consolidado con columnas:
        `ipp_original`, `ipp_canonico`, `tipo_ipp`, `fecha_resolucion`,
        `anio_resolucion`, `mes_resolucion`, `resolucion_raw`,
        `resolucion_canonica`, `categoria_resolucion`,
        `multi_resolucion_origen`, `requiere_validacion`, `fuente_raw`.
    """
    bpaths = backfill_paths if backfill_paths is not None else config.BACKFILL_RESOLUCIONES
    rpath = raw_path if raw_path is not None else config.RAW_RESOLUCIONES

    if verificar_checksums:
        _verificar_checksums_backfill(bpaths)

    dfs_crudos: list[pd.DataFrame] = []
    for path in [*bpaths, rpath]:
        if not path.exists():
            raise FileNotFoundError(f"No se encontró el archivo de resoluciones: {path}")
        df_raw = pd.read_excel(path, sheet_name=0, header=0)
        fuente = FUENTES_RAW.get(path.name)
        if fuente is None:
            raise ValueError(
                f"Archivo de resoluciones con nombre inesperado: {path.name}. "
                f"Esperados: {list(FUENTES_RAW.keys())}"
            )
        df_raw["fuente_raw"] = fuente
        dfs_crudos.append(df_raw)
        logger.info("Cargado %s: %d filas", fuente, len(df_raw))

    df = pd.concat(dfs_crudos, ignore_index=True)

    # Cargar diccionario de resoluciones (token → canónica + categoría).
    diccionario = _cargar_diccionario_resoluciones()

    # Pipeline de transformaciones puras.
    df = _normalizar_columnas(df)
    df = _explotar_multi_resolucion(df)
    df = _aplicar_diccionario(df, diccionario)
    df = _normalizar_ipp_y_fechas(df)
    df = _construir_dataset_final(df)

    logger.info(
        "Pipeline resoluciones OK: %d filas (post-explode), %d IPPs únicas",
        len(df),
        df["ipp_canonico"].nunique(),
    )
    return df


# --- Checksums de backfill (safety net) -----------------------------------


def _sha256(path: Path) -> str:
    """Calcula SHA-256 del archivo en bloques (memoria-eficiente)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()


def _verificar_checksums_backfill(paths: list[Path]) -> None:
    """Compara checksums actuales contra los registrados.

    No falla si no coinciden — solo logea warning ruidoso. La decisión de
    qué hacer queda al humano (puede ser una corrección legítima).
    """
    checksums_file = config.BACKFILL_CHECKSUMS
    if not checksums_file.exists():
        logger.warning(
            "No existe %s. Si esta es la primera corrida, regeneralo con "
            "`make refresh-checksums-backfill`.",
            checksums_file,
        )
        return

    registrados = json.loads(checksums_file.read_text())
    for path in paths:
        if path.name not in registrados:
            logger.warning(
                "Backfill no registrado en checksums.json: %s. "
                "Regenerá los checksums si es un archivo nuevo legítimo.",
                path.name,
            )
            continue
        actual = _sha256(path)
        esperado = registrados[path.name]["sha256"]
        if actual != esperado:
            logger.warning(
                "El archivo de backfill '%s' CAMBIÓ desde la última corrida. "
                "Si fue intencional, regenerá los checksums con "
                "`make refresh-checksums-backfill`. Si no, restaurá el archivo.",
                path.name,
            )
        else:
            logger.info("Checksum OK: %s", path.name)


# --- Normalización de columnas (puro) -------------------------------------


def _normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza nombres de columnas a snake_case.

    Quirk a manejar: la columna 'IPP  Normalizada' tiene doble espacio.
    """
    df = df.copy()
    rename = {
        "Año": "fecha_o_anio",
        "IPP": "ipp_original",
        "RESOLUCION": "resolucion_raw",
        "IPP  Normalizada": "ipp_normalizada_fuente",  # doble espacio en el original
        "IPP Normalizada": "ipp_normalizada_fuente",  # tolerancia a single space
    }
    df = df.rename(columns=rename)

    # Asegurar tipos string para texto.
    for col in ("ipp_original", "resolucion_raw", "ipp_normalizada_fuente"):
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()

    return df


# --- Explosión de multi-resoluciones --------------------------------------


def _split_resolucion(texto: str | None) -> list[str]:
    """Divide una resolución en sus partes constituyentes.

    Maneja los 4 separadores observados en los RAWs (`,`, ` / `, ` - `,
    ` y `) y un falso positivo (`s/` como "sin").

    Returns:
        Lista de strings. Si la entrada no contiene separadores, lista
        de 1 elemento. Si es None/NaN/vacío, lista vacía.
    """
    if texto is None or pd.isna(texto):
        return []
    s = str(texto).strip()
    if not s:
        return []

    # Proteger "s/" antes del split (placeholder único reemplazable).
    s_protegido = SLASH_FALSO_POSITIVO.sub("__SLASH_SIN__", s)
    partes = SEPARADORES_MULTI.split(s_protegido)
    partes = [p.replace("__SLASH_SIN__", "s/").strip() for p in partes]
    partes = [p for p in partes if p]  # descarta vacíos
    return partes


def _explotar_multi_resolucion(df: pd.DataFrame) -> pd.DataFrame:
    """Explota filas multi-resolución a una fila por resolución.

    Agrega:
    - `partes_resolucion`: lista de strings (temporal, se descarta).
    - `multi_resolucion_origen`: True si la fila original tenía >1 parte.

    La salida tiene más filas que la entrada cuando hay multi-resolución.
    """
    df = df.copy()
    df["partes_resolucion"] = df["resolucion_raw"].apply(_split_resolucion)
    df["multi_resolucion_origen"] = df["partes_resolucion"].apply(lambda lst: len(lst) > 1)

    # Explode: cada parte de la lista se vuelve su propia fila.
    df = df.explode("partes_resolucion", ignore_index=True)
    df = df.rename(columns={"partes_resolucion": "resolucion_parte"})

    # Filas que originalmente eran vacías quedan con NaN en resolucion_parte.
    df["resolucion_parte"] = df["resolucion_parte"].astype("string")

    return df


# --- Aplicación del diccionario -------------------------------------------


def _slug_token(texto: str | None) -> str | None:
    """Normaliza una resolución para matching con el diccionario.

    Replica las reglas del diccionario: lower + sin tildes + espacios
    colapsados. NO descarta paréntesis ni signos (eso lo manejaría una
    versión más agresiva).
    """
    if texto is None or pd.isna(texto):
        return None
    s = str(texto).strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\s+", " ", s)
    return s if s else None


def _cargar_diccionario_resoluciones() -> pd.DataFrame:
    """Carga el diccionario y prepara el índice de lookup."""
    path = config.DICT_RESOLUCIONES
    if not path.exists():
        raise FileNotFoundError(f"Falta diccionario de resoluciones: {path}")
    dic = pd.read_csv(path)
    # El token_normalizado del CSV ya está en formato lower-sin-tildes.
    # Normalizamos por las dudas para tolerar inconsistencias.
    dic["token_lookup"] = dic["token_normalizado"].apply(_slug_token)
    # Quedarnos con la primera entrada por token (defensa contra duplicados).
    dic = dic.drop_duplicates(subset=["token_lookup"], keep="first")
    return dic[["token_lookup", "resolucion_canonica", "categoria", "validar"]]


def _aplicar_diccionario(df: pd.DataFrame, diccionario: pd.DataFrame) -> pd.DataFrame:
    """Joinea cada parte de resolución con el diccionario.

    Filas sin match en el diccionario quedan con `resolucion_canonica=NaN`
    y `categoria_resolucion='sin_match'`.
    """
    df = df.copy()
    df["token_lookup"] = df["resolucion_parte"].apply(_slug_token)

    df = df.merge(
        diccionario,
        on="token_lookup",
        how="left",
        validate="m:1",
    )

    df["categoria_resolucion"] = df["categoria"].fillna("sin_match")
    df["requiere_validacion_dic"] = df["validar"].fillna("no").eq("si") | df["categoria"].eq(
        "descarte"
    )

    return df.drop(columns=["token_lookup", "categoria", "validar"])


# --- Normalización del IPP y fechas ---------------------------------------


def _normalizar_ipp_y_fechas(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica clasificador/normalizador del IPP y construye fechas tipadas.

    RAW1 tiene `Año` como int (solo año); RAW2 y RAW3 como datetime.
    Manejamos ambos casos por separado para evitar que `pd.to_datetime`
    interprete los ints como nanosegundos desde epoch (devolvería 1970).
    """
    df = df.copy()

    # Preferir la IPP normalizada de fuente si existe (RAW2/RAW3 la traen).
    # Fallback al ipp_original (RAW1 a veces sólo tiene esa).
    fuente_ipp = df["ipp_normalizada_fuente"].fillna(df["ipp_original"])
    df["tipo_ipp"] = fuente_ipp.apply(clasificar_ipp)
    df["ipp_canonico"] = fuente_ipp.apply(normalizar_ipp).astype("string")

    # Detectar si el valor de fecha_o_anio es datetime real o solo año (int).
    # Estrategia: parsear como datetime SOLO los valores que no son ints
    # puros entre 2000 y 2100 (rango razonable de años).
    fecha_serie: pd.Series = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    anio_serie: pd.Series = pd.Series(pd.NA, index=df.index, dtype="Int64")

    for idx, val in df["fecha_o_anio"].items():
        if pd.isna(val):
            continue
        if isinstance(val, (int, np.integer)) and 2000 <= int(val) <= 2100:
            # Es solo el año, no una fecha (caso RAW1).
            anio_serie.loc[idx] = int(val)
        else:
            # Es un datetime o convertible (caso RAW2/RAW3).
            try:
                ts = pd.to_datetime(val, errors="coerce")
                if pd.notna(ts):
                    fecha_serie.loc[idx] = ts
                    anio_serie.loc[idx] = ts.year
            except (ValueError, TypeError):
                pass

    df["fecha_resolucion"] = fecha_serie
    df["anio_resolucion"] = anio_serie
    df["mes_resolucion"] = fecha_serie.dt.month.astype("Int64")

    return df


# --- Dataset final --------------------------------------------------------

COLUMNAS_FINALES: tuple[str, ...] = (
    "ipp_original",
    "ipp_canonico",
    "tipo_ipp",
    "fecha_resolucion",
    "anio_resolucion",
    "mes_resolucion",
    "resolucion_raw",
    "resolucion_canonica",
    "categoria_resolucion",
    "multi_resolucion_origen",
    "requiere_validacion",
    "fuente_raw",
)


def _construir_dataset_final(df: pd.DataFrame) -> pd.DataFrame:
    """Consolida flags de validación y filtra a las columnas finales."""
    df = df.copy()

    # Flag global de validación combinando dos criterios:
    # - el diccionario marcó validar=si o categoria=descarte
    # - el IPP es pp_malformada (typo no resuelto)
    df["requiere_validacion"] = df["requiere_validacion_dic"] | df["tipo_ipp"].apply(
        requiere_revision_ipp
    )

    # Asegurar las columnas finales y tipos.
    for col in COLUMNAS_FINALES:
        if col not in df.columns:
            df[col] = pd.NA

    return df[list(COLUMNAS_FINALES)].copy()


# --- Persistencia ---------------------------------------------------------


def correr_pipeline_resoluciones(
    output_csv: Path | None = None,
) -> pd.DataFrame:
    """Pipeline orquestador: carga, valida con schema y persiste a CSV.

    Args:
        output_csv: ruta del CSV de salida. Default: `config.OUTPUT_RESOLUCIONES_CSV`.

    Returns:
        DataFrame final validado.
    """
    from src.schema import schema_resoluciones  # import diferido para evitar ciclos

    df = cargar_resoluciones()
    logger.info("Validando schema sobre %d filas", len(df))
    df = schema_resoluciones.validate(df)

    out = output_csv if output_csv is not None else config.OUTPUT_RESOLUCIONES_CSV
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    logger.info("CSV exportado: %s (%d filas)", out, len(df))
    return df


def main() -> int:
    """Entry point CLI. `python -m src.resoluciones`."""
    try:
        correr_pipeline_resoluciones()
    except FileNotFoundError as exc:
        logger.error("Archivo faltante: %s", exc)
        return 1
    except Exception:
        logger.exception("Error inesperado en el pipeline de resoluciones")
        return 1
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
