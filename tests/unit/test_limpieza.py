"""Tests unitarios para `src.limpieza`.

Cubren cada función pura con casos felices y casos borde (NA, vacíos,
caracteres raros, espacios múltiples).
"""
from __future__ import annotations

import pandas as pd
import pytest
from src.limpieza import (
    REGLAS_DELITOS,
    aplicar_reglas_regex,
    limpiar_para_match,
    limpiar_texto,
    limpiar_tramite,
    normalizar_nombre_columna,
    quitar_tildes,
)

# --- normalizar_nombre_columna -------------------------------------------

class TestNormalizarNombreColumna:
    def test_lower_y_sin_tildes(self) -> None:
        assert normalizar_nombre_columna("Fecha de Ingrésó") == "fecha de ingreso"

    def test_grado_se_reemplaza_por_n(self) -> None:
        assert normalizar_nombre_columna("IPP n°") == "ipp nn"

    def test_espacios_multiples_colapsan(self) -> None:
        assert normalizar_nombre_columna("  tipo    tramite  ") == "tipo tramite"

    def test_acepta_no_string(self) -> None:
        assert normalizar_nombre_columna(123) == "123"


# --- quitar_tildes --------------------------------------------------------

class TestQuitarTildes:
    @pytest.mark.parametrize("entrada,esperado", [
        ("agresión", "agresion"),
        ("año", "ano"),
        ("ñandú", "nandu"),
        ("Juan Pérez", "Juan Perez"),
        ("sin acentos", "sin acentos"),
        ("", ""),
    ])
    def test_quita_diacriticos(self, entrada: str, esperado: str) -> None:
        assert quitar_tildes(entrada) == esperado


# --- limpiar_texto --------------------------------------------------------

class TestLimpiarTexto:
    def test_lower_y_trim(self) -> None:
        assert limpiar_texto("  HURTO  ") == "hurto"

    def test_remueve_tildes(self) -> None:
        assert limpiar_texto("Agresión") == "agresion"

    def test_normaliza_espacios_internos(self) -> None:
        assert limpiar_texto("robo    en   tentativa") == "robo en tentativa"

    def test_remueve_parentesis_y_corchetes(self) -> None:
        assert limpiar_texto("robo (en tentativa)") == "robo en tentativa"

    def test_remueve_comillas(self) -> None:
        assert limpiar_texto("hurto \"agravado\"") == "hurto agravado"

    def test_colapsa_puntos_multiples(self) -> None:
        # tres puntos seguidos colapsan a uno, luego se separa por espacio
        assert limpiar_texto("hurto... agravado") == "hurto. agravado"

    def test_strip_de_bordes_especiales(self) -> None:
        assert limpiar_texto(",,hurto..") == "hurto"

    def test_na_pasa(self) -> None:
        assert pd.isna(limpiar_texto(pd.NA))
        assert pd.isna(limpiar_texto(None))

    def test_vacio_post_limpieza_devuelve_na(self) -> None:
        assert pd.isna(limpiar_texto("..."))

    def test_acepta_int(self) -> None:
        # str(123) → '123' no se reduce, pasa la limpieza
        assert limpiar_texto(123) == "123"


# --- limpiar_para_match ---------------------------------------------------

class TestLimpiarParaMatch:
    def test_mas_conservador_que_limpiar_texto(self) -> None:
        # limpiar_para_match preserva paréntesis/signos internos
        assert limpiar_para_match("Robo (Agravado)") == "robo (agravado)"

    def test_quita_tildes(self) -> None:
        assert limpiar_para_match("Á É Í Ó Ú") == "a e i o u"

    def test_na_pasa(self) -> None:
        assert pd.isna(limpiar_para_match(pd.NA))


# --- aplicar_reglas_regex -------------------------------------------------

class TestAplicarReglasRegex:
    def test_corrige_typo_simple(self) -> None:
        reglas = [(r"\blesioens\b", " lesiones ")]
        assert aplicar_reglas_regex("lesioens leves", reglas) == "lesiones leves"

    def test_aplica_reglas_en_orden(self) -> None:
        # La segunda regla depende del output de la primera
        reglas = [(r"\bhuto\b", "hurto"), (r"\bhurto\b", "hurto simple")]
        assert aplicar_reglas_regex("huto", reglas) == "hurto simple"

    def test_na_pasa(self) -> None:
        assert pd.isna(aplicar_reglas_regex(pd.NA, REGLAS_DELITOS))

    def test_reglas_reales_corrigen_typos_frecuentes(self) -> None:
        # Caso real del fixture: lesioens leves → lesiones leves
        assert aplicar_reglas_regex("lesioens leves", REGLAS_DELITOS) == "lesiones leves"

    def test_reglas_reales_expanden_tva(self) -> None:
        assert "tentativa" in aplicar_reglas_regex("robo en tva.", REGLAS_DELITOS)


# --- limpiar_tramite ------------------------------------------------------

class TestLimpiarTramite:
    def test_lower_y_trim(self) -> None:
        assert limpiar_tramite("  ARCHIVO  ") == "archivo"

    def test_preserva_slash_con_espacios(self) -> None:
        # los nombres de trámite del juzgado usan / como separador
        assert limpiar_tramite("remite a / radicacion") == "remite a / radicacion"

    def test_na_pasa(self) -> None:
        assert pd.isna(limpiar_tramite(pd.NA))


# --- Reglas regex del dominio --------------------------------------------

class TestReglasDelitosCubrenTyposFrecuentes:
    """Verifica que las reglas regex cubran los typos documentados en el notebook."""

    @pytest.mark.parametrize("entrada,esperado_contiene", [
        ("lesioens", "lesiones"),
        ("amanazas", "amenazas"),
        ("agrabado", "agravado"),
        ("agvdo", "agravado"),
        ("desobedencia", "desobediencia"),
        ("estupef", "estupefacientes"),
    ])
    def test_correccion_typo(self, entrada: str, esperado_contiene: str) -> None:
        resultado = aplicar_reglas_regex(entrada, REGLAS_DELITOS)
        assert esperado_contiene in resultado
