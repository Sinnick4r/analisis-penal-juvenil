"""Tests del módulo `src.indicadores`.

Dos niveles:
- Tests unitarios con DataFrame sintético (no requieren el Excel real).
- Tests de aceptación contra el archivo real (auto-skip si no está disponible,
  útil para CI sin datos).
"""

from __future__ import annotations

import pandas as pd
import pytest
from src.config import INDICADORES_FILE
from src.indicadores import (
    SLUG_CAUSAS_FINALIZADAS,
    SLUG_CAUSAS_INGRESADAS,
    SLUG_TASA_RESOLUCION,
    SLUGS_PRINCIPALES,
    _normalizar,
    _slug,
    calcular_ratios,
    cargar_indicadores,
    pivot_a_wide,
    serie_temporal,
)

# --- Tests del slug --------------------------------------------------------


class TestSlug:
    @pytest.mark.parametrize(
        "entrada,esperado",
        [
            ("Causas Ingresadas", "causas_ingresadas"),
            ("Tasa de resolución", "tasa_de_resolucion"),
            ("Causas finalizadas (trámites de finalización)", "causas_finalizadas"),
            ("Detenidos al final del periodo", "detenidos_al_final_del_periodo"),
            ("Días asistencia en periodo", "dias_asistencia_en_periodo"),
            ("ÁREA con TILDES", "area_con_tildes"),
        ],
    )
    def test_slug_produce_lo_esperado(self, entrada: str, esperado: str) -> None:
        assert _slug(entrada) == esperado

    def test_descarta_contenido_de_parentesis(self) -> None:
        assert _slug("Algo (con paréntesis)") == "algo"

    def test_idempotente(self) -> None:
        # Aplicar dos veces no cambia el resultado.
        s = "Causas Ingresadas"
        assert _slug(_slug(s)) == _slug(s)


# --- Tests de normalización (puros, sin I/O) ------------------------------


class TestNormalizar:
    def test_estructura_de_columnas(self, df_indicadores_raw_sint) -> None:
        df = _normalizar(df_indicadores_raw_sint)
        cols_esperadas = {
            "departamento",
            "dependencia",
            "anio",
            "mes",
            "dimension",
            "indicador",
            "indicador_slug",
            "valor",
        }
        assert set(df.columns) == cols_esperadas

    def test_tipos_correctos(self, df_indicadores_raw_sint) -> None:
        df = _normalizar(df_indicadores_raw_sint)
        # anio y mes deben ser enteros, valor float
        assert pd.api.types.is_integer_dtype(df["anio"])
        assert pd.api.types.is_integer_dtype(df["mes"])
        assert pd.api.types.is_float_dtype(df["valor"])

    def test_dimension_sin_tildes_y_minusculas(self, df_indicadores_raw_sint) -> None:
        df = _normalizar(df_indicadores_raw_sint)
        # "Respuesta del Órgano" → "respuesta del organo"
        assert "respuesta del organo" in df["dimension"].values
        # No debe haber tildes en dimension
        assert not df["dimension"].str.contains("ó|á|é|í|ú", regex=True).any()

    def test_slug_se_calcula(self, df_indicadores_raw_sint) -> None:
        df = _normalizar(df_indicadores_raw_sint)
        # "Causas Ingresadas" → "causas_ingresadas"
        causas = df[df["indicador"] == "Causas Ingresadas"]
        assert (causas["indicador_slug"] == "causas_ingresadas").all()

    def test_no_pierde_filas_validas(self, df_indicadores_raw_sint) -> None:
        df = _normalizar(df_indicadores_raw_sint)
        assert len(df) == len(df_indicadores_raw_sint)


# --- Tests de pivot long → wide -------------------------------------------


class TestPivotAWide:
    def test_estructura_wide(self, df_indicadores_raw_sint) -> None:
        df_long = _normalizar(df_indicadores_raw_sint)
        df_wide = pivot_a_wide(df_long)
        # Hay 4 meses únicos en el fixture
        assert len(df_wide) == 4
        # Columnas mínimas: anio, mes, fecha_mes
        assert {"anio", "mes", "fecha_mes"}.issubset(df_wide.columns)

    def test_pivot_crea_columnas_por_slug(self, df_indicadores_raw_sint) -> None:
        df_long = _normalizar(df_indicadores_raw_sint)
        df_wide = pivot_a_wide(df_long)
        # Los slugs del fixture deben aparecer como columnas
        for slug in ["causas_ingresadas", "causas_finalizadas", "tasa_de_resolucion"]:
            assert slug in df_wide.columns

    def test_pivot_preserva_valores(self, df_indicadores_raw_sint) -> None:
        df_long = _normalizar(df_indicadores_raw_sint)
        df_wide = pivot_a_wide(df_long)
        # 2024/01: ingresadas debía ser 20
        fila = df_wide[(df_wide["anio"] == 2024) & (df_wide["mes"] == 1)].iloc[0]
        assert fila["causas_ingresadas"] == 20

    def test_orden_temporal(self, df_indicadores_raw_sint) -> None:
        df_long = _normalizar(df_indicadores_raw_sint)
        df_wide = pivot_a_wide(df_long)
        fechas = df_wide["fecha_mes"].tolist()
        assert fechas == sorted(fechas)

    def test_input_vacio_no_rompe(self) -> None:
        vacio = pd.DataFrame(
            columns=[
                "anio",
                "mes",
                "indicador_slug",
                "valor",
            ]
        )
        out = pivot_a_wide(vacio)
        assert len(out) == 0


# --- Tests de ratios calculados -------------------------------------------


class TestCalcularRatios:
    def test_tasa_calculada_coincide_con_publicada(self, df_indicadores_raw_sint) -> None:
        """Caso del fixture: la tasa publicada coincide exacta con la fórmula."""
        df_long = _normalizar(df_indicadores_raw_sint)
        df_wide = pivot_a_wide(df_long)
        df_r = calcular_ratios(df_wide)
        # El fixture usa valores que dan tasas redondas exactas
        diff = (df_r[SLUG_TASA_RESOLUCION] - df_r["tasa_resolucion_calculada"]).abs()
        assert (diff < 0.001).all()

    def test_delta_ingreso_finalizacion(self, df_indicadores_raw_sint) -> None:
        df_long = _normalizar(df_indicadores_raw_sint)
        df_wide = pivot_a_wide(df_long)
        df_r = calcular_ratios(df_wide)
        # 2024/01: ingresadas=20, finalizadas=30 → delta = -10 (resuelve más de lo que ingresa)
        fila = df_r[(df_r["anio"] == 2024) & (df_r["mes"] == 1)].iloc[0]
        assert fila["delta_ingreso_finalizacion"] == -10

    def test_divide_by_zero_da_nan(self) -> None:
        """Si ingresadas es 0, los ratios deben ser NaN (no inf)."""
        df = pd.DataFrame(
            {
                "anio": [2024],
                "mes": [1],
                "fecha_mes": [pd.Timestamp("2024-01-01")],
                SLUG_CAUSAS_INGRESADAS: [0.0],
                SLUG_CAUSAS_FINALIZADAS: [5.0],
            }
        )
        out = calcular_ratios(df)
        assert pd.isna(out.iloc[0]["tasa_resolucion_calculada"])
        assert pd.isna(out.iloc[0]["ratio_finalizacion"])

    def test_columnas_faltantes_no_rompe(self) -> None:
        """Si no hay causas_ingresadas o finalizadas, no agrega columnas."""
        df = pd.DataFrame(
            {
                "anio": [2024],
                "mes": [1],
                "fecha_mes": [pd.Timestamp("2024-01-01")],
                "tramites_totales": [100.0],
            }
        )
        out = calcular_ratios(df)
        assert "tasa_resolucion_calculada" not in out.columns


# --- Tests de serie_temporal ----------------------------------------------


class TestSerieTemporal:
    def test_devuelve_serie_ordenada(self, df_indicadores_raw_sint) -> None:
        df_long = _normalizar(df_indicadores_raw_sint)
        serie = serie_temporal(df_long, "causas_ingresadas")
        assert "fecha_mes" in serie.columns
        fechas = serie["fecha_mes"].tolist()
        assert fechas == sorted(fechas)

    def test_slug_inexistente_levanta_keyerror(self, df_indicadores_raw_sint) -> None:
        df_long = _normalizar(df_indicadores_raw_sint)
        with pytest.raises(KeyError, match="slug_inventado"):
            serie_temporal(df_long, "slug_inventado")


# --- Tests de aceptación contra el archivo real ---------------------------

# Estos tests verifican propiedades del archivo real cuando está disponible.
# En CI sin datos, se skipean automáticamente.
pytestmark_archivo_real = pytest.mark.skipif(
    not INDICADORES_FILE.exists(),
    reason="Archivo de indicadores no disponible en data/external/",
)


@pytestmark_archivo_real
class TestAceptacionArchivoReal:
    """Tests contra el archivo real provisto por el área de Estadística."""

    def test_cumple_schema_long(self) -> None:
        from src.schema import schema_indicadores_long

        df = cargar_indicadores()
        schema_indicadores_long.validate(df)

    def test_cumple_schema_wide(self) -> None:
        from src.schema import schema_indicadores_wide

        df = cargar_indicadores()
        wide = pivot_a_wide(df)
        schema_indicadores_wide.validate(wide)

    def test_slugs_principales_aparecen_todos(self) -> None:
        """Si un slug declarado en SLUGS_PRINCIPALES no aparece en los datos,
        algo cambió en la fuente y hay que actualizar el catálogo."""
        df = cargar_indicadores()
        observados = set(df["indicador_slug"].unique())
        faltantes = [k for k in SLUGS_PRINCIPALES if k not in observados]
        assert faltantes == [], (
            f"Slugs declarados pero ausentes en el archivo: {faltantes}. "
            f"Probablemente estadística renombró un indicador."
        )

    def test_tasa_publicada_consistente_con_formula(self) -> None:
        """Test de aceptación duro: la tasa publicada debe ser igual a
        finalizadas/ingresadas*100 con tolerancia de redondeo (<1.0)."""
        df = cargar_indicadores()
        wide = pivot_a_wide(df)
        wide_r = calcular_ratios(wide)
        m = wide_r[
            wide_r[SLUG_TASA_RESOLUCION].notna() & wide_r["tasa_resolucion_calculada"].notna()
        ]
        if len(m) == 0:
            pytest.skip("No hay meses con ambas tasas disponibles.")
        diff = (m[SLUG_TASA_RESOLUCION] - m["tasa_resolucion_calculada"]).abs()
        assert diff.max() < 1.0, (
            f"La tasa publicada divergió >1 punto de la recalculada en "
            f"{(diff >= 1.0).sum()} meses. La fórmula puede haber cambiado."
        )
