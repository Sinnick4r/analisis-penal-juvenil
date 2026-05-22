"""Tests de integración del pipeline completo.

Estos tests NO usan el Excel real ni los CSVs de producción: corren sobre
los fixtures sintéticos del `conftest.py`. Permiten validar que la cadena
completa funciona end-to-end y que el contrato pandera se cumple.
"""
from __future__ import annotations

import pandas as pd
import pandera.errors as pa_errors
import pytest
from src.normalizacion import (
    COLUMNAS_FINALES,
    cruzar_ministerio,
    normalizar_delitos,
    normalizar_tramites,
    seleccionar_columnas_finales,
)
from src.schema import schema_dataset_final


@pytest.fixture
def df_final_sintetico(
    df_causas_sinteticas,
    dict_delitos_local_sint,
    dict_delitos_ministerio_sint,
    dict_tramites_sint,
    nomenclador_sint,
) -> pd.DataFrame:
    """Aplica la cadena completa de normalización al fixture sintético."""
    df = normalizar_delitos(df_causas_sinteticas, dict_delitos_local_sint)
    df = cruzar_ministerio(df, dict_delitos_ministerio_sint, nomenclador_sint)
    df = normalizar_tramites(df, dict_tramites_sint)
    return seleccionar_columnas_finales(df)


class TestPipelineEndToEnd:
    """Validan el contrato y comportamiento del dataset final."""

    def test_tiene_todas_las_columnas_esperadas(self, df_final_sintetico) -> None:
        assert set(df_final_sintetico.columns) == set(COLUMNAS_FINALES)

    def test_conserva_la_cantidad_de_filas(
        self, df_final_sintetico, df_causas_sinteticas
    ) -> None:
        assert len(df_final_sintetico) == len(df_causas_sinteticas)

    def test_cumple_el_schema_pandera(self, df_final_sintetico) -> None:
        # No debe lanzar SchemaError.
        validado = schema_dataset_final.validate(df_final_sintetico)
        assert len(validado) == len(df_final_sintetico)

    def test_estado_match_ministerio_solo_categorias_validas(
        self, df_final_sintetico
    ) -> None:
        estados_validos = {
            "match_univoco", "match_ambiguo", "sin_equivalencia_definida",
            "proceso_especial", "sin_delito_informado", "sin_match",
        }
        assert set(df_final_sintetico["estado_match_ministerio"].unique()).issubset(
            estados_validos
        )

    def test_delito_informado_solo_si_o_no(self, df_final_sintetico) -> None:
        assert set(df_final_sintetico["delito_informado"].unique()).issubset({"si", "no"})

    def test_anio_dentro_de_rango_razonable(self, df_final_sintetico) -> None:
        assert df_final_sintetico["anio"].min() >= 2020
        assert df_final_sintetico["anio"].max() <= 2030

    def test_delito_estandar_no_es_null(self, df_final_sintetico) -> None:
        # Mínimo "delito_no_informado" cuando no hay info, pero nunca null.
        assert df_final_sintetico["delito_estandar"].notna().all()


class TestSchemaDetectaCorrupciones:
    """El schema debe fallar cuando el dataset se corrompe (DATA-01)."""

    def test_falla_con_anio_invalido(self, df_final_sintetico) -> None:
        corrupto = df_final_sintetico.copy()
        corrupto.loc[0, "anio"] = 1999  # fuera de rango
        with pytest.raises(pa_errors.SchemaError):
            schema_dataset_final.validate(corrupto)

    def test_falla_con_estado_match_invalido(self, df_final_sintetico) -> None:
        corrupto = df_final_sintetico.copy()
        corrupto.loc[0, "estado_match_ministerio"] = "estado_inexistente"
        with pytest.raises(pa_errors.SchemaError):
            schema_dataset_final.validate(corrupto)

    def test_falla_con_delito_informado_invalido(self, df_final_sintetico) -> None:
        corrupto = df_final_sintetico.copy()
        corrupto.loc[0, "delito_informado"] = "tal vez"
        with pytest.raises(pa_errors.SchemaError):
            schema_dataset_final.validate(corrupto)
