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


# --- Schema de resoluciones -----------------------------------------------

# Categorías reconocidas de IPP. Espejo de `TIPO_IPP_VALIDOS` en
# `src.normalizar_ipp`. Si se actualiza una lista, actualizar la otra.
TIPO_IPP_VALIDOS_SCHEMA: list[str] = [
    "estandar", "oficio_exhorto", "amparo", "querella", "habeas_corpus",
    "faltas_contravenciones", "apelacion_contravencional",
    "habeas_data", "dictamen_civil", "externa", "pp_malformada", "nulo",
]

# Identificadores de fuente raw del audit trail.
FUENTES_RAW_VALIDAS: list[str] = [
    "backfill_2017_2019",
    "backfill_2020_2023a",
    "raw_2023b_2026",
]

# Año mínimo de resoluciones (el primer backfill arranca en 2017).
ANIO_MINIMO_RESOLUCIONES: int = 2017


schema_resoluciones = pa.DataFrameSchema(
    columns={
        # IPP y clasificación
        "ipp_original": Column(str, nullable=True),
        "ipp_canonico": Column(str, nullable=True),
        "tipo_ipp": Column(str, checks=Check.isin(TIPO_IPP_VALIDOS_SCHEMA)),

        # Fechas: RAW1 solo tiene año; RAW2/3 tienen fecha completa.
        # Por eso `fecha_resolucion` y `mes_resolucion` son nullable.
        "fecha_resolucion": Column("datetime64[ns]", nullable=True),
        "anio_resolucion": Column(
            "Int64",
            checks=Check.in_range(ANIO_MINIMO_RESOLUCIONES, config.ANIO_MAXIMO_VALIDO),
            coerce=True,
        ),
        "mes_resolucion": Column(
            "Int64", nullable=True, checks=Check.in_range(1, 12), coerce=True,
        ),

        # Resolución cruda y normalizada
        "resolucion_raw": Column(str, nullable=True),
        "resolucion_canonica": Column(str, nullable=True),
        "categoria_resolucion": Column(str, nullable=False),

        # Flags
        "multi_resolucion_origen": Column(bool, coerce=True),
        "requiere_validacion": Column(bool, coerce=True),

        # Audit trail
        "fuente_raw": Column(str, checks=Check.isin(FUENTES_RAW_VALIDAS)),
    },
    strict="filter",
    coerce=True,
)


# --- Schema del cruce causas x resoluciones -------------------------------

# Schema laxo (strict=False): valida las columnas NUEVAS introducidas por
# el cruce, pero preserva las columnas heredadas de `schema_dataset_final`
# (causas) sin re-validarlas. La idea es que cada schema sea responsable
# de su capa: causas valida lo suyo, resoluciones lo suyo, el cruce solo
# valida lo que agrega.
schema_causas_con_resoluciones = pa.DataFrameSchema(
    columns={
        # IPP canónico calculado localmente en el cruce (deuda técnica:
        # eventualmente debería ser columna nativa de causas).
        "ipp_canonico": Column(str, nullable=True),
        "tipo_ipp": Column(str, checks=Check.isin(TIPO_IPP_VALIDOS_SCHEMA)),

        # Métricas de conteo
        "n_resoluciones": Column(int, checks=Check.ge(0), coerce=True),
        "tiene_resoluciones": Column(bool, coerce=True),

        # Métricas temporales (nullable: causas sin resoluciones o solo
        # con resoluciones de RAW1 sin fecha exacta).
        "fecha_primera_resolucion": Column("datetime64[ns]", nullable=True),
        "fecha_ultima_resolucion": Column("datetime64[ns]", nullable=True),
        "dias_hasta_primera_resolucion": Column("Int64", nullable=True, coerce=True),
        "dias_proceso": Column("Int64", nullable=True, coerce=True),

        # Flags por categoría (7 más frecuentes).
        "tiene_cierre_proceso": Column(bool, coerce=True),
        "tiene_elevacion_juicio": Column(bool, coerce=True),
        "tiene_salida_alternativa": Column(bool, coerce=True),
        "tiene_competencia": Column(bool, coerce=True),
        "tiene_medida_coercion": Column(bool, coerce=True),
        "tiene_derivacion_servicio_local": Column(bool, coerce=True),
        "tiene_rebeldia": Column(bool, coerce=True),

        # Audit: todas las categorías concatenadas (no solo las 7 principales).
        "categorias_resolucion": Column(str, nullable=True),
    },
    strict=False,  # preserva columnas heredadas de causas
    coerce=True,
)
