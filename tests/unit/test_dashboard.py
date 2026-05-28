"""Smoke tests del dashboard.

No levantan el server de Streamlit ni renderizan UI: solo verifican que
las funciones que NO dependen de `st.*` funcionan con un DataFrame válido.

Las funciones que sí dependen de Streamlit (sidebar, render de tabs)
quedan cubiertas indirectamente: si rompen al importar, el test falla.
"""

from __future__ import annotations

import pandas as pd
import pytest
from dashboard.components.filtros import Filtros, aplicar_filtros
from dashboard.data import estadisticas_basicas
from dashboard.tabs.calidad import _construir_cola_revision, _motivos_revision
from dashboard.tabs.delitos import _resumen_flags

# --- Fixture: DataFrame con la forma del dataset final --------------------


@pytest.fixture
def df_dataset_completo() -> pd.DataFrame:
    """DataFrame con todas las columnas del schema, varias filas representativas."""
    return pd.DataFrame(
        {
            "fecha_ingreso": pd.to_datetime(
                [
                    "2022-03-15",
                    "2023-04-10",
                    "2024-05-20",
                    "2024-08-08",
                    "2025-01-15",
                    "2025-06-18",
                ]
            ),
            "anio": pd.array([2022, 2023, 2024, 2024, 2025, 2025], dtype="Int64"),
            "ipp": pd.array(["1-1", "1-2", "1-3", "1-4", "1-5", "1-6"], dtype="string"),
            "tipo_tramite_raw": pd.array(["archivo"] * 6, dtype="string"),
            "tipo_tramite_limpio": pd.array(["archivo"] * 6, dtype="string"),
            "tipo_tramite_estandar": pd.array(
                [
                    "archivo",
                    "elevacion_a_juicio",
                    "archivo",
                    "competencia",
                    "archivo",
                    "elevacion_a_juicio",
                ],
                dtype="string",
            ),
            "caratula_anonimizada": pd.array(["XXX"] * 6, dtype="string"),
            "responsable": pd.array(["op1"] * 6, dtype="string"),
            "delito_raw": pd.array(
                [
                    "robo simple",
                    "lesiones leves",
                    "robo agravado",
                    "amparo",
                    "",
                    "lesiones leves y amenazas",
                ],
                dtype="string",
            ),
            "delito_limpio": pd.array(
                [
                    "robo simple",
                    "lesiones leves",
                    "robo agravado",
                    "amparo",
                    pd.NA,
                    "lesiones leves y amenazas",
                ],
                dtype="string",
            ),
            "delito_sin_tentativa": pd.array(
                [
                    "robo simple",
                    "lesiones leves",
                    "robo agravado",
                    "amparo",
                    pd.NA,
                    "lesiones leves y amenazas",
                ],
                dtype="string",
            ),
            "delito_estandar": [
                "robo simple",
                "lesiones leves",
                "robo agravado",
                "amparo",
                "delito_no_informado",
                "lesiones leves y amenazas",
            ],
            "delito_informado": ["si", "si", "si", "si", "no", "si"],
            "tentativa": [False, False, False, False, False, False],
            "es_proceso_especial": [False, False, False, True, False, False],
            "agravado_flag": [False, False, True, False, False, False],
            "agravante_poblado_banda": [False, False, False, False, False, False],
            "agravante_arma": [False, False, False, False, False, False],
            "agravante_escalamiento": [False, False, False, False, False, False],
            "agravante_efraccion": [False, False, False, False, False, False],
            "agravante_vehiculo_via_publica": [False, False, False, False, False, False],
            "agravante_no_especificado": [False, False, True, False, False, False],
            "posible_delito_multiple": [False, False, False, False, False, True],
            "objetivo_ministerio": pd.array(
                [
                    "robo simple",
                    "lesiones leves",
                    "robo agravado",
                    pd.NA,
                    pd.NA,
                    pd.NA,
                ],
                dtype="string",
            ),
            "descripcion_ministerio": pd.array(
                [
                    "Robo simple",
                    "Lesiones leves",
                    "Robo agravado",
                    pd.NA,
                    pd.NA,
                    pd.NA,
                ],
                dtype="string",
            ),
            "articulo_ministerio": pd.array(
                [
                    "Art. 164",
                    "Art. 89",
                    "Art. 166 | Art. 167",
                    pd.NA,
                    pd.NA,
                    pd.NA,
                ],
                dtype="string",
            ),
            "codigo_delito_ministerio": pd.array(
                [
                    "CP.164.0.00.00.00",
                    "CP.089.0.00.00.00",
                    "CP.166.0.00.00.00 | CP.167.0.00.00.00",
                    pd.NA,
                    pd.NA,
                    pd.NA,
                ],
                dtype="string",
            ),
            "estado_match_ministerio": [
                "match_univoco",
                "match_univoco",
                "match_ambiguo",
                "proceso_especial",
                "sin_delito_informado",
                "sin_equivalencia_definida",
            ],
        }
    )


# --- Tests ----------------------------------------------------------------


class TestEstadisticasBasicas:
    def test_calcula_kpis_correctos(self, df_dataset_completo):
        stats = estadisticas_basicas(df_dataset_completo)
        assert stats["total"] == 6
        assert stats["pct_tentativa"] == 0.0  # ninguna tentativa
        assert stats["pct_agravado"] == pytest.approx(100 * 1 / 6, abs=0.01)

    def test_dataframe_vacio_no_rompe(self):
        stats = estadisticas_basicas(
            pd.DataFrame(
                columns=[
                    "tentativa",
                    "agravado_flag",
                    "estado_match_ministerio",
                ]
            )
        )
        assert stats["total"] == 0
        assert stats["pct_tentativa"] == 0.0


class TestAplicarFiltros:
    def test_filtro_por_anio(self, df_dataset_completo):
        filtros = Filtros(anios=[2024], delitos=[], estados_match=[])
        out = aplicar_filtros(df_dataset_completo, filtros)
        assert len(out) == 2
        assert out["anio"].unique().tolist() == [2024]

    def test_filtro_por_delito(self, df_dataset_completo):
        filtros = Filtros(anios=[], delitos=["robo simple"], estados_match=[])
        out = aplicar_filtros(df_dataset_completo, filtros)
        assert len(out) == 1
        assert out.iloc[0]["delito_estandar"] == "robo simple"

    def test_filtro_combinado(self, df_dataset_completo):
        filtros = Filtros(
            anios=[2024, 2025],
            delitos=[],
            estados_match=["match_univoco"],
        )
        out = aplicar_filtros(df_dataset_completo, filtros)
        # 2024+2025 = 4 filas; de esas, ninguna es match_univoco
        # (las dos de 2024 son match_ambiguo y proceso_especial)
        assert all(out["anio"].isin([2024, 2025]))
        assert all(out["estado_match_ministerio"] == "match_univoco")

    def test_filtros_vacios_devuelven_todo(self, df_dataset_completo):
        filtros = Filtros(anios=[], delitos=[], estados_match=[])
        out = aplicar_filtros(df_dataset_completo, filtros)
        assert len(out) == len(df_dataset_completo)


class TestColaRevision:
    def test_incluye_sin_delito_informado(self, df_dataset_completo):
        cola = _construir_cola_revision(df_dataset_completo)
        # La fila 4 tiene sin_delito_informado → debe estar
        assert "1-5" in cola["ipp"].values

    def test_incluye_posible_multiple(self, df_dataset_completo):
        cola = _construir_cola_revision(df_dataset_completo)
        # La fila 5 tiene posible_delito_multiple=True → debe estar
        assert "1-6" in cola["ipp"].values

    def test_incluye_agravante_no_especificado(self, df_dataset_completo):
        cola = _construir_cola_revision(df_dataset_completo)
        # La fila 2 tiene agravante_no_especificado=True → debe estar
        assert "1-3" in cola["ipp"].values

    def test_no_incluye_filas_limpias(self, df_dataset_completo):
        cola = _construir_cola_revision(df_dataset_completo)
        # Filas 0 y 1: match_univoco sin flags problemáticos → fuera
        assert "1-1" not in cola["ipp"].values
        assert "1-2" not in cola["ipp"].values

    def test_motivos_son_descriptivos(self, df_dataset_completo):
        cola = _construir_cola_revision(df_dataset_completo)
        cola["motivos"] = cola.apply(_motivos_revision, axis=1)
        # La fila con sin_delito_informado debe mencionar ese motivo
        fila = cola[cola["ipp"] == "1-5"].iloc[0]
        assert "delito no informado" in fila["motivos"]


class TestResumenFlags:
    def test_tabla_tiene_filas_y_porcentajes(self, df_dataset_completo):
        tabla = _resumen_flags(df_dataset_completo)
        assert "Indicador" in tabla.columns
        assert "Cantidad" in tabla.columns
        assert "% sobre el total" in tabla.columns
        assert len(tabla) > 0


# --- Smoke test de imports ------------------------------------------------


class TestImports:
    """Verifica que todos los módulos del dashboard importan sin errores."""

    def test_dashboard_app_es_importable(self):
        # Importar app.py ejecuta st.set_page_config — no podemos hacerlo
        # fuera de un contexto de Streamlit. Pero sí podemos verificar que
        # los módulos auxiliares importan.
        from dashboard import data, theme  # noqa: F401
        from dashboard.components import filtros, kpis  # noqa: F401
        from dashboard.tabs import calidad, delitos, gestion, temporal, tramites  # noqa: F401

    def test_theme_aplica_sin_error(self):
        from dashboard.theme import aplicar_tema_altair

        # Debe ser idempotente
        aplicar_tema_altair()
        aplicar_tema_altair()


# --- Tab Gestión: tests con/sin métricas del cruce ----------------------


class TestTabGestion:
    """Smoke tests del tab Gestión. Valida que cada chart se construya sin error."""

    @pytest.fixture
    def df_con_cruce(self) -> pd.DataFrame:
        """DataFrame mínimo con las columnas del cruce que el tab necesita."""
        return pd.DataFrame(
            {
                "anio": pd.array([2023, 2024, 2024, 2025], dtype="Int64"),
                "fecha_ingreso": pd.to_datetime(
                    [
                        "2023-01-15",
                        "2024-03-10",
                        "2024-06-20",
                        "2025-02-01",
                    ]
                ),
                "delito_estandar": ["robo simple", "lesiones leves", "robo simple", "hurto"],
                "tentativa": [False, False, True, False],
                "agravado_flag": [False, False, False, False],
                "estado_match_ministerio": ["match_unico"] * 4,
                # Columnas del cruce:
                "n_resoluciones": [2, 1, 0, 1],
                "tiene_resoluciones": [True, True, False, True],
                "fecha_primera_resolucion": pd.to_datetime(
                    [
                        "2023-01-25",
                        "2024-04-05",
                        None,
                        "2025-02-15",
                    ]
                ),
                "fecha_ultima_resolucion": pd.to_datetime(
                    [
                        "2023-02-10",
                        "2024-04-05",
                        None,
                        "2025-02-15",
                    ]
                ),
                "dias_hasta_primera_resolucion": pd.array([10, 26, None, 14], dtype="Int64"),
                "dias_proceso": pd.array([26, 26, None, 14], dtype="Int64"),
                "tiene_cierre_proceso": [True, True, False, False],
                "tiene_elevacion_juicio": [False, False, False, True],
                "tiene_salida_alternativa": [False, False, False, False],
                "tiene_competencia": [True, False, False, False],
                "tiene_medida_coercion": [False, False, False, False],
                "tiene_derivacion_servicio_local": [False, False, False, False],
                "tiene_rebeldia": [False, False, False, False],
                "categorias_resolucion": [
                    "cierre de proceso | competencia",
                    "cierre de proceso",
                    "",
                    "elevacion a juicio",
                ],
            }
        )

    def test_modalidad_resolutiva_se_construye(self, df_con_cruce):
        from dashboard.tabs.gestion import _modalidad_resolutiva_chart

        chart = _modalidad_resolutiva_chart(df_con_cruce)
        # Debe ser un chart de altair (no None, no Exception)
        assert chart is not None

    def test_duracion_procesal_se_construye(self, df_con_cruce):
        from dashboard.tabs.gestion import _duracion_procesal_chart

        chart = _duracion_procesal_chart(df_con_cruce)
        assert chart is not None

    def test_tiempo_por_delito_se_construye(self, df_con_cruce):
        from dashboard.tabs.gestion import _tiempo_por_delito_chart

        chart = _tiempo_por_delito_chart(df_con_cruce)
        assert chart is not None

    def test_cohorte_anual_se_construye(self, df_con_cruce):
        from dashboard.tabs.gestion import _cohorte_anual_chart

        chart = _cohorte_anual_chart(df_con_cruce)
        assert chart is not None

    def test_charts_no_fallan_con_df_vacio(self):
        """Defensa contra filtros que dejan el DataFrame vacío."""
        from dashboard.tabs.gestion import (
            _cohorte_anual_chart,
            _duracion_procesal_chart,
            _modalidad_resolutiva_chart,
            _tiempo_por_delito_chart,
        )

        df_vacio = pd.DataFrame(
            {
                "anio": pd.array([], dtype="Int64"),
                "tiene_resoluciones": pd.array([], dtype=bool),
                "dias_hasta_primera_resolucion": pd.array([], dtype="Int64"),
                "dias_proceso": pd.array([], dtype="Int64"),
                "delito_estandar": pd.array([], dtype="object"),
                **{
                    f: pd.array([], dtype=bool)
                    for f in (
                        "tiene_cierre_proceso",
                        "tiene_elevacion_juicio",
                        "tiene_salida_alternativa",
                        "tiene_competencia",
                        "tiene_medida_coercion",
                        "tiene_derivacion_servicio_local",
                        "tiene_rebeldia",
                    )
                },
            }
        )
        # Ninguno debe lanzar excepción
        for chart_fn in (
            _modalidad_resolutiva_chart,
            _duracion_procesal_chart,
            _tiempo_por_delito_chart,
            _cohorte_anual_chart,
        ):
            assert chart_fn(df_vacio) is not None


class TestDataResolverFuente:
    """Tests del nuevo helper de carga que prefiere el cruce sobre causas."""

    def test_tiene_metricas_cruce_true_con_columna(self):
        from dashboard.data import tiene_metricas_cruce

        df = pd.DataFrame({"n_resoluciones": [1, 2, 3]})
        assert tiene_metricas_cruce(df)

    def test_tiene_metricas_cruce_false_sin_columna(self):
        from dashboard.data import tiene_metricas_cruce

        df = pd.DataFrame({"anio": [2024, 2025]})
        assert not tiene_metricas_cruce(df)
