"""Tests del módulo de resoluciones.

Dos niveles:
- Unitarios con fixtures sintéticas (no requieren los Excel reales).
- Aceptación contra los archivos reales (auto-skip si faltan).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from src.config import BACKFILL_RESOLUCIONES, RAW_RESOLUCIONES
from src.resoluciones import (
    _aplicar_diccionario,
    _explotar_multi_resolucion,
    _normalizar_columnas,
    _normalizar_ipp_y_fechas,
    _sha256,
    _slug_token,
    _split_resolucion,
    cargar_resoluciones,
)

# --- Tests del split de multi-resoluciones --------------------------------

class TestSplitResolucion:
    def test_single_devuelve_lista_de_uno(self) -> None:
        assert _split_resolucion("sobreseimiento") == ["sobreseimiento"]

    def test_separador_coma(self) -> None:
        partes = _split_resolucion("sobreseimiento, derivacion")
        assert partes == ["sobreseimiento", "derivacion"]

    def test_separador_slash_con_espacios(self) -> None:
        partes = _split_resolucion("competencia / sobreseimiento")
        assert partes == ["competencia", "sobreseimiento"]

    def test_separador_guion_con_espacios(self) -> None:
        partes = _split_resolucion("allanamiento - secuestro")
        assert partes == ["allanamiento", "secuestro"]

    def test_separador_y(self) -> None:
        partes = _split_resolucion("rebeldia y captura")
        assert partes == ["rebeldia", "captura"]

    def test_s_barra_no_es_separador(self) -> None:
        """'s/' es abreviatura de 'sin', NO un separador. Esta fila es 1 sola
        resolución, no 2."""
        partes = _split_resolucion("Rebeldia s/ efecto")
        assert partes == ["Rebeldia s/ efecto"]

    def test_triple_tema(self) -> None:
        partes = _split_resolucion("rebeldia, captura, sobreseimiento")
        assert len(partes) == 3

    def test_vacio_devuelve_lista_vacia(self) -> None:
        assert _split_resolucion("") == []
        assert _split_resolucion(None) == []
        assert _split_resolucion(pd.NA) == []

    def test_trim_de_partes(self) -> None:
        partes = _split_resolucion("  sobreseimiento  ,   derivacion  ")
        assert partes == ["sobreseimiento", "derivacion"]


# --- Tests del slug ------------------------------------------------------

class TestSlugToken:
    def test_lowercase_y_trim(self) -> None:
        assert _slug_token("  Sobreseimiento  ") == "sobreseimiento"

    def test_quita_tildes(self) -> None:
        assert _slug_token("Elevación") == "elevacion"

    def test_colapsa_espacios(self) -> None:
        assert _slug_token("acepta   competencia") == "acepta competencia"

    def test_nulo(self) -> None:
        assert _slug_token(None) is None
        assert _slug_token("") is None
        assert _slug_token(pd.NA) is None


# --- Tests del flujo completo de transformaciones (sin I/O) ---------------

class TestPipelineTransformaciones:
    """Encadena las transformaciones puras sobre el fixture sintético."""

    def test_normaliza_columnas_renombra(self, df_resoluciones_raw_sint) -> None:
        df = _normalizar_columnas(df_resoluciones_raw_sint)
        assert "ipp_original" in df.columns
        assert "resolucion_raw" in df.columns
        assert "ipp_normalizada_fuente" in df.columns

    def test_explode_multiplica_filas_por_multi(self, df_resoluciones_raw_sint) -> None:
        df = _normalizar_columnas(df_resoluciones_raw_sint)
        df = _explotar_multi_resolucion(df)
        # El fixture tiene 8 filas originales con:
        # 5 single + 3 multi (de 2 partes c/u: sobreseimiento+derivación,
        # rebeldia+captura, allanamiento+secuestro, competencia+sobreseimiento) = 4 multi
        # Wait: "frase rara no en diccionario" single, "Rebeldia s/ efecto" single (no es separador real)
        # Singles: 0 (sobre), 2 (eleva), 6 (frase rara), 7 (rebeldia s/ efecto) = 4
        # Multis: 1 (sobr+deriv), 3 (rebel+capt), 4 (allan+secu), 5 (comp+sobr) = 4 multis x 2 = 8
        # Total = 4 + 8 = 12
        assert len(df) == 12

    def test_explode_marca_flag(self, df_resoluciones_raw_sint) -> None:
        df = _normalizar_columnas(df_resoluciones_raw_sint)
        df = _explotar_multi_resolucion(df)
        # 4 filas originales eran multi, cada una se explotó a 2 → 8 filas con flag True
        assert df["multi_resolucion_origen"].sum() == 8

    def test_aplica_diccionario(
        self,
        df_resoluciones_raw_sint,
        diccionario_resoluciones_sint,
    ) -> None:
        df = _normalizar_columnas(df_resoluciones_raw_sint)
        df = _explotar_multi_resolucion(df)
        # Preparar diccionario tal como lo espera _aplicar_diccionario.
        dic = diccionario_resoluciones_sint.copy()
        dic["token_lookup"] = dic["token_normalizado"].apply(_slug_token)
        dic = dic[["token_lookup", "resolucion_canonica", "categoria", "validar"]]
        df = _aplicar_diccionario(df, dic)
        # La fila "frase rara no en diccionario" no debe matchear.
        frase_rara = df[df["resolucion_raw"].str.contains("frase rara", na=False)]
        assert (frase_rara["categoria_resolucion"] == "sin_match").all()
        # "sobreseimiento" sí debe matchear a "cierre de proceso".
        sobre = df[df["resolucion_parte"].str.lower() == "sobreseimiento"]
        assert (sobre["categoria_resolucion"] == "cierre de proceso").all()

    def test_fechas_raw1_solo_anio(
        self, df_resoluciones_raw_solo_anio_sint,
    ) -> None:
        """Verifica que cuando Año es int (RAW1), fecha_resolucion queda NaT
        pero anio_resolucion conserva el año correcto."""
        df = df_resoluciones_raw_solo_anio_sint.copy()
        df["fuente_raw"] = "backfill_2017_2019"
        df = _normalizar_columnas(df)
        df = _explotar_multi_resolucion(df)
        df = _normalizar_ipp_y_fechas(df)
        assert df["fecha_resolucion"].isna().all()
        assert df["anio_resolucion"].notna().all()
        assert sorted(df["anio_resolucion"].dropna().unique().tolist()) == [2017, 2018, 2019]

    def test_fechas_raw2_con_datetime(
        self, df_resoluciones_raw_sint,
    ) -> None:
        df = df_resoluciones_raw_sint.copy()
        df["fuente_raw"] = "backfill_2020_2023a"
        df = _normalizar_columnas(df)
        df = _explotar_multi_resolucion(df)
        df = _normalizar_ipp_y_fechas(df)
        assert df["fecha_resolucion"].notna().all()
        assert df["mes_resolucion"].notna().all()
        assert (df["anio_resolucion"] == 2024).all()


# --- Tests de seguridad: checksums ----------------------------------------

class TestChecksums:
    def test_sha256_es_determinista(self, tmp_path: Path) -> None:
        archivo = tmp_path / "test.txt"
        archivo.write_text("contenido fijo")
        hash1 = _sha256(archivo)
        hash2 = _sha256(archivo)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex digest

    def test_sha256_cambia_con_contenido(self, tmp_path: Path) -> None:
        a = tmp_path / "a.txt"
        a.write_text("X")
        b = tmp_path / "b.txt"
        b.write_text("Y")
        assert _sha256(a) != _sha256(b)


# --- Tests de aceptación contra archivos reales --------------------------

pytestmark_archivos_reales = pytest.mark.skipif(
    not (
        all(p.exists() for p in BACKFILL_RESOLUCIONES)
        and RAW_RESOLUCIONES.exists()
    ),
    reason="Archivos de resoluciones no disponibles en data/",
)


@pytestmark_archivos_reales
class TestAceptacionArchivosReales:
    """Tests contra los 3 archivos reales de resoluciones."""

    def test_pipeline_corre_end_to_end(self) -> None:
        df = cargar_resoluciones()
        assert len(df) > 2000  # Esperamos ~2950 filas

    def test_cumple_schema(self) -> None:
        from src.schema import schema_resoluciones
        df = cargar_resoluciones()
        schema_resoluciones.validate(df)

    def test_tres_fuentes_presentes(self) -> None:
        df = cargar_resoluciones()
        assert set(df["fuente_raw"].unique()) == {
            "backfill_2017_2019",
            "backfill_2020_2023a",
            "raw_2023b_2026",
        }

    def test_raw1_no_tiene_fecha_exacta(self) -> None:
        """Las filas de backfill_2017_2019 NO deben tener fecha_resolucion."""
        df = cargar_resoluciones()
        raw1 = df[df["fuente_raw"] == "backfill_2017_2019"]
        assert raw1["fecha_resolucion"].isna().all()
        assert raw1["anio_resolucion"].notna().all()

    def test_raw2_y_raw3_si_tienen_fecha(self) -> None:
        """RAW2 y RAW3 deben tener fecha_resolucion completa."""
        df = cargar_resoluciones()
        modernos = df[df["fuente_raw"].isin(["backfill_2020_2023a", "raw_2023b_2026"])]
        assert modernos["fecha_resolucion"].notna().all()

    def test_explode_aumenta_filas(self) -> None:
        """El pipeline debe producir más filas que la suma de los 3 originales,
        por la explosión de multi-resoluciones."""
        df = cargar_resoluciones()
        # 794 + 936 + 841 = 2571 originales; con multi-explode esperamos +200 al menos
        assert len(df) >= 2700

    def test_cobertura_diccionario_alta(self) -> None:
        """El diccionario debe cubrir >95% de las resoluciones."""
        df = cargar_resoluciones()
        sin_match = (df["categoria_resolucion"] == "sin_match").mean()
        assert sin_match < 0.05, (
            f"Cobertura del diccionario insuficiente: {sin_match * 100:.1f}% "
            f"sin match (esperado <5%)"
        )

    def test_checksums_json_se_genera_y_es_valido(self, tmp_path: Path) -> None:
        from scripts.refresh_checksums import sha256 as _sha

        # Verificar que cada archivo registrado tiene un hash válido.
        from src.config import BACKFILL_CHECKSUMS
        if not BACKFILL_CHECKSUMS.exists():
            pytest.skip("checksums.json no existe; correr `make refresh-checksums`.")
        registro = json.loads(BACKFILL_CHECKSUMS.read_text())
        for archivo in BACKFILL_RESOLUCIONES:
            assert archivo.name in registro
            assert registro[archivo.name]["sha256"] == _sha(archivo)
