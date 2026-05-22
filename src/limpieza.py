"""Funciones puras de limpieza textual.

Extraídas del notebook 01_limpieza_y_normalizacion.ipynb (celda inicial).
Todas son funciones sin side effects y sin I/O, fácilmente testeables
(cumple PY-05 del guideline: separar transformación de I/O).

Las constantes `REGLAS_DELITOS`, `FALTANTES_DELITO` y `FALTANTES_TRAMITE`
se mantienen como tuplas/frozensets para que sean inmutables.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

import pandas as pd

# --- Constantes -----------------------------------------------------------

# Valores que deben tratarse como "delito ausente" en la columna delito.
FALTANTES_DELITO: frozenset[str] = frozenset({
    "", "nan", "none", "#value!", "#valor!",
    "sin delito", "s/", "s", "/", "n/a", "na",
})

# Valores que deben tratarse como "trámite ausente".
FALTANTES_TRAMITE: frozenset[str] = frozenset({
    "", "nan", "none", "n/a", "na", "s/d", "sd",
})

# Procesos especiales que no son delitos en sentido penal.
PROCESOS_ESPECIALES: frozenset[str] = frozenset({"amparo", "habeas corpus"})

# Reglas de regex para normalización de delitos: corrección de typos,
# expansión de abreviaturas y uniformización de redacciones del juzgado.
# Orden importa: las reglas se aplican secuencialmente.
REGLAS_DELITOS: tuple[tuple[str, str], ...] = (
    # tentativa
    (r"\ben\s+tva\.?\b", " tentativa "),
    (r"\btva\.?\b", " tentativa "),
    (r"\ben\s+grado\s+de\s+tentativa\b", " tentativa "),
    (r"\bgrado\s+de\s+tentativa\b", " tentativa "),

    # abreviaturas comunes
    (r"\bx\b", " por "),
    (r"\bp/\s*", " por "),
    (r"\bres\.?\s*a\s*la\s*autoridad\b", " resistencia a la autoridad "),
    (r"\bau\b", " autoridad "),
    (r"\bdom\b", " domicilio "),
    (r"\bdomic\b", " domicilio "),
    (r"\bvehic\b", " vehiculo "),
    (r"\bvehicul\b", " vehiculo "),
    (r"\bvia publ\b", " via publica "),
    (r"\bvia pub\b", " via publica "),

    # typos frecuentes
    (r"\bhuto\b", " hurto "),
    (r"\bhurto rn\b", " hurto "),
    (r"\bhurto en entativa\b", " hurto en tentativa "),
    (r"\blesioens\b", " lesiones "),
    (r"\blesioes\b", " lesiones "),
    (r"\blesones\b", " lesiones "),
    (r"\blesioens leves\b", " lesiones leves "),
    (r"\blesiones levs\b", " lesiones leves "),
    (r"\blesones leves\b", " lesiones leves "),
    (r"\blesiones leves-amenazas\b", " lesiones leves y amenazas "),
    (r"\bamanazas\b", " amenazas "),
    (r"\bamenanzas\b", " amenazas "),
    (r"\bagrabado\b", " agravado "),
    (r"\bagrabada\b", " agravada "),
    (r"\bagvdo\b", " agravado "),
    (r"\bagdo\b", " agravado "),
    (r"\bpobaldo\b", " poblado "),
    (r"\bpro\b", " por "),
    (r"\bbehiculo\b", " vehiculo "),
    (r"\bpuvlica\b", " publica "),
    (r"\bcomercialiacion\b", " comercializacion "),
    (r"\bestupefefacientes\b", " estupefacientes "),
    (r"\bestupefaciones\b", " estupefacientes "),
    (r"\bdesobedencia\b", " desobediencia "),
    (r"\bexibiciones obsenas\b", " exhibiciones obscenas "),

    # estupefacientes — abreviaturas y expansiones
    (r"\bestupef\b", " estupefacientes "),
    (r"\btenencia estupefacientes\b", " tenencia de estupefacientes "),
    (r"\btenencia de estupefacientes p/ comer\b", " tenencia de estupefacientes con fines de comercializacion "),
    (r"\btenencia de estupefacientes con fines de comerc\b", " tenencia de estupefacientes con fines de comercializacion "),
    (r"\btenencia de estupefacientes con fines de comer\b", " tenencia de estupefacientes con fines de comercializacion "),
    (r"\btenencia de estupefacientes con fines de com\b", " tenencia de estupefacientes con fines de comercializacion "),
)


# --- Funciones de limpieza ------------------------------------------------

def normalizar_nombre_columna(col: Any) -> str:
    """Normaliza el nombre de una columna: minúsculas, sin tildes, espacios colapsados.

    Convierte º y ° a 'n' para evitar caracteres raros en nombres de columnas
    como 'IPP n°'.
    """
    col_str = str(col).strip().lower()
    col_str = unicodedata.normalize("NFKD", col_str)
    col_str = "".join(c for c in col_str if not unicodedata.combining(c))
    col_str = re.sub(r"\s+", " ", col_str)
    col_str = col_str.replace("º", "n").replace("°", "n")
    return col_str.strip()


def quitar_tildes(texto: str) -> str:
    """Quita tildes y diacríticos de un string (NFKD + filtro de combining chars)."""
    texto_norm = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto_norm if not unicodedata.combining(c))


def limpiar_texto(texto: Any) -> Any:
    """Limpieza textual exhaustiva para descripciones de delitos.

    Aplica: lower, sin tildes, colapso de espacios, eliminación de signos de
    puntuación redundantes, normalización de comas/puntos/guiones.

    Args:
        texto: string a limpiar, o NA.

    Returns:
        Texto limpio (str) o pd.NA si la entrada es NA o queda vacía.
    """
    if pd.isna(texto):
        return pd.NA

    s = str(texto).strip().lower()
    s = quitar_tildes(s)

    s = s.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    s = re.sub(r"\s+", " ", s)

    s = s.replace(";", " ")
    s = s.replace(":", " ")
    s = s.replace("{", "")
    s = s.replace("}", "")
    s = s.replace("[", "")
    s = s.replace("]", "")
    s = s.replace("(", " ")
    s = s.replace(")", " ")
    s = re.sub(r"[\"'`´]", "", s)  # noqa: RUF001 — intencional: limpiar ambos acentos

    s = re.sub(r"\.{2,}", ".", s)
    s = re.sub(r",{2,}", ",", s)
    s = re.sub(r"-{2,}", "-", s)

    s = re.sub(r"\s*,\s*", ", ", s)
    s = re.sub(r"\s*\.\s*", ". ", s)
    s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"\s+", " ", s)

    s = s.strip(" .,-_/")
    return s if s else pd.NA


def limpiar_para_match(texto: Any) -> Any:
    """Limpieza más liviana, usada para construir claves de match con diccionarios.

    Más simple que `limpiar_texto`: solo lower, sin tildes, colapso de espacios
    y strip de signos en bordes. Preserva más caracteres para mantener
    coincidencias con los valores de los diccionarios.
    """
    if pd.isna(texto):
        return pd.NA
    s = str(texto).strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\s+", " ", s)
    s = s.strip(" .,-_/")
    return s if s else pd.NA


def aplicar_reglas_regex(texto: Any, reglas: tuple[tuple[str, str], ...] | list[tuple[str, str]]) -> Any:
    """Aplica una secuencia de reglas (patrón_regex, reemplazo) a un texto.

    Las reglas se aplican en orden, lo cual es relevante: una regla puede
    depender de la salida de la anterior.

    Args:
        texto: string a transformar, o NA.
        reglas: secuencia de tuplas (patrón, reemplazo).

    Returns:
        Texto transformado (str), NA si la entrada es NA, o NA si queda vacío.
    """
    if pd.isna(texto):
        return texto
    s = str(texto)
    for patron, reemplazo in reglas:
        s = re.sub(patron, reemplazo, s)
    s = re.sub(r"\s+", " ", s).strip(" .,-_/")
    return s if s else pd.NA


def limpiar_tramite(texto: Any) -> Any:
    """Limpieza específica para tipos de trámite.

    Similar a `limpiar_texto` pero más conservadora con la puntuación: solo
    elimina ; : { } [ ] y normaliza / con espacios alrededor, ya que los
    nombres de trámite del juzgado conservan estructura tipo 'remite a / radicacion'.
    """
    if pd.isna(texto):
        return pd.NA

    s = str(texto).strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    s = re.sub(r"\s+", " ", s)
    s = s.replace(";", " ")
    s = s.replace(":", " ")
    s = s.replace("/", " / ")
    s = re.sub(r"\s+", " ", s)
    s = s.strip(" .,-_/")
    return s if s else pd.NA
