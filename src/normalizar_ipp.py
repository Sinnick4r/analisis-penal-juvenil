"""Clasificacion y normalización del IPP (Investigación Penal Preparatoria).

El pdoer judicial de la Pcia. de Bs. As. usa 8 numeros con prefijo PP.

Aca se va a

1. clasificar ua IPP en una de las 12 categorías de `TIPO_IPP_VALIDOS`.
2. devolver la forma canonica que sirve como join key:
   - Para IPPs estándar: quita el prefijo "PP-" o "PP " y devuelve
     "14-XX-NNNNNN-YY/ZZ"
   - Para otros proceos (AM, HC, OE, etc.): preserva tal cual
     porque el sistema de resoluciones también las registra con prefijo
   - Para  causas de otra jurisdicción, se deja el numero original
   - Para IPPs malformados (typos no reconstruibles): preserva tal cual con
     flag de revision
"""

from __future__ import annotations

import re

import pandas as pd

# categorías de causas

TIPO_IPP_VALIDOS: tuple[str, ...] = (
    "estandar",  # PP-NN-NN-NNNNNN-NN/NN (Proceso Penal)
    "oficio_exhorto",  # OE-...
    "amparo",  # AM-...
    "querella",  # QU-...
    "habeas_corpus",  # HC-...
    "faltas_contravenciones",  # FC-...
    "apelacion_contravencional",  # AC-...
    "habeas_data",  # HD-...
    "dictamen_civil",  # DC-...
    "externa",  # IPP de otra jurisdicción, formato libre
    "pp_malformada",  # empieza con PP pero no matchea canónico (typo no resuelto)
    "nulo",  # ausencia de valor
)

# mapeo prefijo de otros procesos validos

PREFIJOS_INSTITUCIONALES: dict[str, str] = {
    "OE": "oficio_exhorto",
    "AM": "amparo",
    "QU": "querella",
    "HC": "habeas_corpus",
    "FC": "faltas_contravenciones",
    "AC": "apelacion_contravencional",
    "HD": "habeas_data",
    "DC": "dictamen_civil",
}

# formato de IPP estándar
PATRON_CANONICO: re.Pattern[str] = re.compile(r"^\d{2}-\d{2}-\d{6}-\d{2}/\d{2}$")
PREFIJO_PP: re.Pattern[str] = re.compile(r"^PP[-\s]+")

# clasificacion de ipps


def clasificar_ipp(ipp: str | None | float) -> str:
    """lasifica las IPP

    no modifica el string, solamente  lo clasifica para que el caller sepa
    qie hacer

    """
    if ipp is None:
        return "nulo"
    # pd.isna() reconoce None, np.nan, pd.NA, NaT.
    if not isinstance(ipp, str):
        try:
            if pd.isna(ipp):
                return "nulo"
        except (TypeError, ValueError):
            pass

    s = str(ipp).strip()

    if not s or s.lower() == "nan":
        return "nulo"

    s = str(ipp).strip()
    if not s or s.lower() == "nan":
        return "nulo"

    if len(s) >= 3 and s[:2].upper() in PREFIJOS_INSTITUCIONALES and s[2] == "-":
        return PREFIJOS_INSTITUCIONALES[s[:2].upper()]

    if PREFIJO_PP.match(s):
        sin_pp = PREFIJO_PP.sub("", s)
        if PATRON_CANONICO.match(sin_pp):
            return "estandar"
        return "pp_malformada"

    if PATRON_CANONICO.match(s):
        return "estandar"

    return "externa"


def normalizar_ipp(ipp: str | None | float) -> str | None:
    """Devuelve la forma canónica da la IPP qqeu voy a usar como join key

    Reglas:
    - estandar -> "14-XX-NNNNNN-YY/ZZ" (sin prefijo PP)
    - otros procesos-> (AM, HC, OE, etc.) -> string tal cual (con prefijo)
    - externa, pp_malformada -> string tal cual, trimeado
    - nulo -> None

    ejemplos basado en casso detectados:
        >>> normalizar_ipp("PP-14-03-001393-20/00")
        '14-03-001393-20/00'
        >>> normalizar_ipp("PP 14-03-001393-20/00")
        '14-03-001393-20/00'
        >>> normalizar_ipp("AM-14-00-000012-21/00")
        'AM-14-00-000012-21/00'
        >>> normalizar_ipp("Causa 41820")
        'Causa 41820'
        >>> normalizar_ipp(None) is None
        True
    """
    tipo = clasificar_ipp(ipp)
    if tipo == "nulo":
        return None

    s = str(ipp).strip()
    if tipo == "estandar":
        return PREFIJO_PP.sub("", s)

    return s


def requiere_revision_ipp(tipo: str) -> bool:
    return tipo == "pp_malformada"
