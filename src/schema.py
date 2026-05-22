"""Contrato pandera del dataset analítico final.

Implementa la regla DATA-01 del guideline: "todo dataset crítico MUST tener
contrato explícito". Define columnas requeridas, dtypes, nullabilidad y
categorías válidas. Si una corrida produce un output que no cumple el
contrato, el pipeline falla con `SchemaError`.
"""
from __future__ import annotations

import pandera.pandas as pa
from pandera.pandas import Check, Column

from src import config

# Estados válidos del cruce con el nomenclador ministerial.
# Los dos últimos son auxiliares para casos no aplicables (no match positivo
# ni negativo); se preservan tal como aparecen en el notebook original.
ESTADOS_MATCH_VALIDOS: list[str] = [
    "match_univoco",
    "match_ambiguo",
    "sin_equivalencia_definida",
    "proceso_especial",
    "sin_delito_informado",
    "sin_match",
]


# Schema del dataset final. Se aplica con `schema.validate(df)`.
schema_dataset_final = pa.DataFrameSchema(
    columns={
        # Identificación temporal
        "fecha_ingreso": Column("datetime64[ns]", nullable=True),
        "anio": Column(
            int,
            checks=Check.in_range(config.ANIO_MINIMO, config.ANIO_MAXIMO_VALIDO),
            nullable=False,
            coerce=True,
        ),

        # Identificadores administrativos
        "ipp": Column(str, nullable=True),
        "caratula_anonimizada": Column(str, nullable=True),
        "responsable": Column(str, nullable=True),

        # Trámite
        "tipo_tramite_raw": Column(str, nullable=True),
        "tipo_tramite_limpio": Column(str, nullable=True),
        "tipo_tramite_estandar": Column(str, nullable=True),

        # Delito
        "delito_raw": Column(str, nullable=True),
        "delito_limpio": Column(str, nullable=True),
        "delito_sin_tentativa": Column(str, nullable=True),
        "delito_estandar": Column(str, nullable=False),
        "delito_informado": Column(str, checks=Check.isin(["si", "no"])),

        # Flags jurídicos
        "tentativa": Column(bool),
        "es_proceso_especial": Column(bool),
        "agravado_flag": Column(bool),
        "agravante_poblado_banda": Column(bool),
        "agravante_arma": Column(bool),
        "agravante_escalamiento": Column(bool),
        "agravante_efraccion": Column(bool),
        "agravante_vehiculo_via_publica": Column(bool),
        "agravante_no_especificado": Column(bool),
        "posible_delito_multiple": Column(bool),

        # Cruce ministerial
        "objetivo_ministerio": Column(str, nullable=True),
        "descripcion_ministerio": Column(str, nullable=True),
        "articulo_ministerio": Column(str, nullable=True),
        "codigo_delito_ministerio": Column(str, nullable=True),
        "estado_match_ministerio": Column(
            str,
            checks=Check.isin(ESTADOS_MATCH_VALIDOS),
        ),
    },
    strict="filter",  # tolera columnas extra (las filtra silenciosamente)
    coerce=True,
)


# --- Schemas de indicadores -----------------------------------------------

# Schema del DataFrame de indicadores en formato long (post-carga).
schema_indicadores_long = pa.DataFrameSchema(
    columns={
        "departamento": Column(str, nullable=True),
        "dependencia": Column(str, nullable=True),
        "anio": Column(
            int,
            checks=Check.in_range(config.ANIO_MINIMO, config.ANIO_MAXIMO_VALIDO),
            coerce=True,
        ),
        "mes": Column(int, checks=Check.in_range(1, 12), coerce=True),
        "dimension": Column(str, nullable=True),
        "indicador": Column(str, nullable=True),
        "indicador_slug": Column(str, nullable=False),
        "valor": Column(float, nullable=True, coerce=True),
    },
    strict="filter",
    coerce=True,
)


# Schema del DataFrame de indicadores en formato wide (post-pivot).
# Mucho más laxo: cada mes tiene distintos indicadores disponibles, así que
# las columnas indicador permiten NaN. Solo se valida la clave temporal.
schema_indicadores_wide = pa.DataFrameSchema(
    columns={
        "anio": Column(int, checks=Check.in_range(
            config.ANIO_MINIMO, config.ANIO_MAXIMO_VALIDO,
        ), coerce=True),
        "mes": Column(int, checks=Check.in_range(1, 12), coerce=True),
        "fecha_mes": Column("datetime64[ns]"),
    },
    strict=False,  # acepta columnas indicador adicionales
    coerce=True,
)
