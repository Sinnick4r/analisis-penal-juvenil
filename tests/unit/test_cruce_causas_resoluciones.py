"""Tests del módulo de cruce causas ↔ resoluciones.

Dos niveles:
- Unitarios con fixtures sintéticos.
- Aceptación contra los CSVs reales (auto-skip si no existen).
"""

from __future__ import annotations

import pandas as pd
import pytest
from src.config import OUTPUT_CSV, OUTPUT_RESOLUCIONES_CSV
from src.cruce_causas_resoluciones import (
    CATEGORIAS_PRINCIPALES,
    SLUGS_CATEGORIAS,
    _slug_categoria,
    calcular_metricas_por_ipp,
    cargar_causas_con_canonico,
    cruzar,
    reporte_auditoria,
)

# --- Tests de funciones puras ---------------------------------------------


class TestSlugCategoria:
    @pytest.mark.parametrize(
        "entrada,esperado",
        [
            ("cierre de proceso", "cierre_proceso"),
            ("elevacion a juicio", "elevacion_juicio"),
            ("salida alternativa", "salida_alternativa"),
            ("derivacion a servicio local", "derivacion_servicio_local"),
            ("medida de coercion", "medida_coercion"),
            ("competencia", "competencia"),
        ],
    )
    def test_slug(self, entrada: str, esperado: str) -> None:
        assert _slug_categoria(entrada) == esperado


class TestCatalogoCoherente:
    def test_todas_las_principales_tienen_slug(self) -> None:
        for cat in CATEGORIAS_PRINCIPALES:
            assert cat in SLUGS_CATEGORIAS

    def test_slugs_son_unicos(self) -> None:
        """Defensa contra slugs colisionados (dos categorías con mismo slug)."""
        slugs = list(SLUGS_CATEGORIAS.values())
        assert len(slugs) == len(set(slugs))


# --- Tests de cálculo de métricas (puros) ---------------------------------


class TestCalcularMetricasPorIpp:
    def test_input_vacio(self) -> None:
        vacio = pd.DataFrame(
            columns=[
                "ipp_canonico",
                "fecha_resolucion",
                "categoria_resolucion",
            ]
        )
        out = calcular_metricas_por_ipp(vacio)
        assert len(out) == 0
        # Las columnas esperadas deben existir.
        for slug in SLUGS_CATEGORIAS.values():
            assert f"tiene_{slug}" in out.columns

    def test_conteo_por_ipp(self, df_resoluciones_para_cruce_sint) -> None:
        metricas = calcular_metricas_por_ipp(df_resoluciones_para_cruce_sint)
        ipp_3 = metricas[metricas["ipp_canonico"] == "14-04-002648-24/01"].iloc[0]
        assert ipp_3["n_resoluciones"] == 3

    def test_fecha_primera_y_ultima(self, df_resoluciones_para_cruce_sint) -> None:
        metricas = calcular_metricas_por_ipp(df_resoluciones_para_cruce_sint)
        ipp_3 = metricas[metricas["ipp_canonico"] == "14-04-002648-24/01"].iloc[0]
        assert ipp_3["fecha_primera_resolucion"] == pd.Timestamp("2024-01-25")
        assert ipp_3["fecha_ultima_resolucion"] == pd.Timestamp("2024-04-10")

    def test_flags_booleanos_correctos(self, df_resoluciones_para_cruce_sint) -> None:
        metricas = calcular_metricas_por_ipp(df_resoluciones_para_cruce_sint)
        # IPP 14-04-002648-24/01 tiene: medida de coercion, competencia, cierre
        ipp_3 = metricas[metricas["ipp_canonico"] == "14-04-002648-24/01"].iloc[0]
        assert ipp_3["tiene_medida_coercion"] is True or ipp_3["tiene_medida_coercion"]
        assert ipp_3["tiene_competencia"]
        assert ipp_3["tiene_cierre_proceso"]
        assert not ipp_3["tiene_elevacion_juicio"]

    def test_categorias_concatenadas_ordenadas(self, df_resoluciones_para_cruce_sint) -> None:
        metricas = calcular_metricas_por_ipp(df_resoluciones_para_cruce_sint)
        ipp_3 = metricas[metricas["ipp_canonico"] == "14-04-002648-24/01"].iloc[0]
        # Las 3 categorías únicas, ordenadas alfabéticamente, separadas por " | "
        assert (
            ipp_3["categorias_resolucion"] == "cierre de proceso | competencia | medida de coercion"
        )

    def test_raw1_sin_fecha_da_nat(self, df_resoluciones_para_cruce_sint) -> None:
        """IPP cuya única resolución es de RAW1 (sin fecha exacta) debe tener
        fecha_primera y fecha_ultima como NaT."""
        metricas = calcular_metricas_por_ipp(df_resoluciones_para_cruce_sint)
        ipp_raw1 = metricas[metricas["ipp_canonico"] == "14-03-001393-22/00"].iloc[0]
        assert pd.isna(ipp_raw1["fecha_primera_resolucion"])
        assert pd.isna(ipp_raw1["fecha_ultima_resolucion"])


# --- Tests del cruce -----------------------------------------------------


class TestCruzar:
    @pytest.fixture
    def causas_con_canonico(self, df_causas_para_cruce_sint) -> pd.DataFrame:
        from src.normalizar_ipp import clasificar_ipp, normalizar_ipp

        df = df_causas_para_cruce_sint.copy()
        df["tipo_ipp"] = df["ipp"].apply(clasificar_ipp)
        df["ipp_canonico"] = df["ipp"].apply(normalizar_ipp)
        return df

    def test_preserva_cantidad_de_filas(
        self,
        causas_con_canonico,
        df_resoluciones_para_cruce_sint,
    ) -> None:
        cruce = cruzar(causas_con_canonico, df_resoluciones_para_cruce_sint)
        assert len(cruce) == len(causas_con_canonico)

    def test_causa_sin_resoluciones_tiene_defaults(
        self,
        causas_con_canonico,
        df_resoluciones_para_cruce_sint,
    ) -> None:
        cruce = cruzar(causas_con_canonico, df_resoluciones_para_cruce_sint)
        # PP-14-05-003482-25/00 no tiene resoluciones en el fixture.
        sin_res = cruce[cruce["ipp_canonico"] == "14-05-003482-25/00"].iloc[0]
        assert sin_res["n_resoluciones"] == 0
        assert sin_res["tiene_resoluciones"] is False or not sin_res["tiene_resoluciones"]
        assert sin_res["categorias_resolucion"] == ""
        for slug in SLUGS_CATEGORIAS.values():
            assert sin_res[f"tiene_{slug}"] is False or not sin_res[f"tiene_{slug}"]
        assert pd.isna(sin_res["fecha_primera_resolucion"])

    def test_causa_con_multiples_resoluciones(
        self,
        causas_con_canonico,
        df_resoluciones_para_cruce_sint,
    ) -> None:
        cruce = cruzar(causas_con_canonico, df_resoluciones_para_cruce_sint)
        con_res = cruce[cruce["ipp_canonico"] == "14-04-002648-24/01"].iloc[0]
        assert con_res["n_resoluciones"] == 3
        assert con_res["tiene_resoluciones"]

    def test_causa_institucional_matchea(
        self,
        causas_con_canonico,
        df_resoluciones_para_cruce_sint,
    ) -> None:
        """IPP institucional AM- debe matchear con la resolución correspondiente."""
        cruce = cruzar(causas_con_canonico, df_resoluciones_para_cruce_sint)
        am = cruce[cruce["ipp_canonico"] == "AM-14-00-000012-24/00"].iloc[0]
        assert am["n_resoluciones"] == 1
        assert am["tiene_salida_alternativa"]

    def test_causa_malformada_sin_match(
        self,
        causas_con_canonico,
        df_resoluciones_para_cruce_sint,
    ) -> None:
        """El PP-J-... no debe matchear con nada (no está en resoluciones)."""
        cruce = cruzar(causas_con_canonico, df_resoluciones_para_cruce_sint)
        malf = cruce[cruce["ipp_canonico"] == "PP-J-01-00013167-5/23"].iloc[0]
        assert malf["n_resoluciones"] == 0

    def test_metricas_temporales_solo_con_fecha(
        self,
        causas_con_canonico,
        df_resoluciones_para_cruce_sint,
    ) -> None:
        """dias_hasta_primera_resolucion debe ser NA cuando la primera
        resolución no tiene fecha exacta (caso RAW1)."""
        cruce = cruzar(causas_con_canonico, df_resoluciones_para_cruce_sint)
        raw1 = cruce[cruce["ipp_canonico"] == "14-03-001393-22/00"].iloc[0]
        # Tiene 1 resolución pero sin fecha → métricas temporales NA
        assert raw1["n_resoluciones"] == 1
        assert pd.isna(raw1["dias_hasta_primera_resolucion"])

    def test_dias_calculados_correctamente(
        self,
        causas_con_canonico,
        df_resoluciones_para_cruce_sint,
    ) -> None:
        """Para una causa con fecha de ingreso y primera resolución con fecha,
        el cálculo de días debe ser exacto."""
        cruce = cruzar(causas_con_canonico, df_resoluciones_para_cruce_sint)
        # PP-14-04-002648-24/01 ingresó 2024-01-10, primera resolución 2024-01-25
        # → 15 días
        c = cruce[cruce["ipp_canonico"] == "14-04-002648-24/01"].iloc[0]
        assert c["dias_hasta_primera_resolucion"] == 15
        # Última resolución 2024-04-10 → días_proceso = 91
        assert c["dias_proceso"] == 91


# --- Tests de auditoría --------------------------------------------------


class TestReporteAuditoria:
    def test_audit_completo(
        self,
        df_causas_para_cruce_sint,
        df_resoluciones_para_cruce_sint,
    ) -> None:
        from src.normalizar_ipp import normalizar_ipp

        causas = df_causas_para_cruce_sint.copy()
        causas["ipp_canonico"] = causas["ipp"].apply(normalizar_ipp)

        audit = reporte_auditoria(causas, df_resoluciones_para_cruce_sint)

        assert audit["causas_total"] == 5
        # Causas con IPP canónico válido: las 5 (incluso PP-J-)
        assert audit["causas_ipp_canonico_unicas"] == 5
        # IPPs únicos en resoluciones: 4 (14-03..., 14-04..., AM-..., 14-99...)
        assert audit["resoluciones_ipp_canonico_unicas"] == 4
        # Intersección: 14-03..., 14-04..., AM-... = 3
        assert audit["ipps_en_ambos_datasets"] == 3
        # Solo en causas: PP-14-05... y PP-J-... = 2
        assert audit["causas_sin_resoluciones_unicas"] == 2
        # Huérfanas: solo 14-99-999999-99/99 = 1
        assert audit["resoluciones_huerfanas_ipps_unicas"] == 1


# --- Tests de aceptación contra archivos reales --------------------------

pytestmark_archivos_reales = pytest.mark.skipif(
    not (OUTPUT_CSV.exists() and OUTPUT_RESOLUCIONES_CSV.exists()),
    reason="Outputs de causas y/o resoluciones no disponibles en outputs/",
)


@pytestmark_archivos_reales
class TestAceptacionArchivosReales:
    def test_pipeline_corre_end_to_end(self) -> None:
        from src.cruce_causas_resoluciones import correr_cruce

        cruce = correr_cruce()
        # Debe haber 1267 causas (output de Iteración A).
        assert len(cruce) == 1267

    def test_cumple_schema(self) -> None:
        from src.cruce_causas_resoluciones import correr_cruce
        from src.schema import schema_causas_con_resoluciones

        cruce = correr_cruce()
        schema_causas_con_resoluciones.validate(cruce)

    def test_overlap_alto(self) -> None:
        """Al menos 70% de las causas deben tener resoluciones registradas."""
        causas = cargar_causas_con_canonico()
        resoluciones = pd.read_csv(OUTPUT_RESOLUCIONES_CSV)
        audit = reporte_auditoria(causas, resoluciones)
        overlap_pct = audit["ipps_en_ambos_datasets"] / audit["causas_ipp_canonico_unicas"]
        assert overlap_pct >= 0.70, f"Overlap esperado >= 70%, observado: {overlap_pct * 100:.1f}%"

    def test_metricas_temporales_son_razonables(self) -> None:
        """Mediana de días hasta primera resolución debe ser positiva y
        razonable (entre 0 y 365)."""
        from src.cruce_causas_resoluciones import correr_cruce

        cruce = correr_cruce()
        con_dias = cruce[cruce["dias_hasta_primera_resolucion"].notna()]
        mediana = con_dias["dias_hasta_primera_resolucion"].median()
        assert 0 <= mediana <= 365, f"Mediana fuera de rango: {mediana}"
