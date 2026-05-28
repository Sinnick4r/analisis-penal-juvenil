"""Tests del clasificador y normalizador de IPP."""

from __future__ import annotations

import pandas as pd
import pytest
from src.normalizar_ipp import (
    PREFIJOS_INSTITUCIONALES,
    TIPO_IPP_VALIDOS,
    clasificar_ipp,
    normalizar_ipp,
    requiere_revision_ipp,
)


class TestClasificarIpp:
    """Cubre las 12 categorías del enum TIPO_IPP_VALIDOS."""

    @pytest.mark.parametrize(
        "ipp,esperado",
        [
            # Estándar: con prefijo PP- o PP+espacio, o ya canónico
            ("PP-14-03-001393-20/00", "estandar"),
            ("PP 14-03-001393-20/00", "estandar"),  # quirk: PP+espacio
            ("14-03-001393-20/00", "estandar"),  # canónico sin prefijo (RAW de resoluciones)
            # Institucionales
            ("AM-14-00-000012-21/00", "amparo"),
            ("HC-14-00-000077-22/00", "habeas_corpus"),
            ("OE-14-00-000087-22/00", "oficio_exhorto"),
            ("QU-14-00-000001-25/00", "querella"),
            ("FC-14-00-000005-23/00", "faltas_contravenciones"),
            ("AC-14-00-000010-24/00", "apelacion_contravencional"),
            ("HD-14-00-000020-22/00", "habeas_data"),
            ("DC-14-00-000003-25/00", "dictamen_civil"),
            # Externa
            ("Causa 41820", "externa"),
            ("CCC 15203/2024", "externa"),
            ("10391324-2024", "externa"),
            # PP malformada
            ("PP-J-01-00013167-5/22", "pp_malformada"),
            # Nulo
            (None, "nulo"),
            ("", "nulo"),
            ("nan", "nulo"),
            ("   ", "nulo"),
        ],
    )
    def test_clasificacion(self, ipp, esperado: str) -> None:
        assert clasificar_ipp(ipp) == esperado

    def test_resultado_siempre_en_enum_valido(self) -> None:
        """Cualquier input debe devolver un valor del enum."""
        casos_borde = [
            "casi-canonico-pero-no",
            "PP",
            "PPP-...",
            "12345",
            "X" * 100,
            "🎉",
        ]
        for caso in casos_borde:
            assert clasificar_ipp(caso) in TIPO_IPP_VALIDOS

    def test_prefijo_case_insensitive(self) -> None:
        """Los prefijos institucionales deben reconocerse en mayúscula y minúscula."""
        assert clasificar_ipp("am-14-00-000012-21/00") == "amparo"
        assert clasificar_ipp("Am-14-00-000012-21/00") == "amparo"

    def test_nan_de_pandas(self) -> None:
        """pd.NA y float('nan') deben caer como nulo."""
        assert clasificar_ipp(pd.NA) == "nulo"
        assert clasificar_ipp(float("nan")) == "nulo"


class TestNormalizarIpp:
    """Verifica que la normalización produzca claves de join consistentes."""

    def test_estandar_quita_prefijo_pp_guion(self) -> None:
        assert normalizar_ipp("PP-14-03-001393-20/00") == "14-03-001393-20/00"

    def test_estandar_quita_prefijo_pp_espacio(self) -> None:
        """Tolera el quirk de PP+espacio."""
        assert normalizar_ipp("PP 14-03-001393-20/00") == "14-03-001393-20/00"

    def test_canonico_sin_prefijo_se_preserva(self) -> None:
        """Las IPPs Normalizadas de los RAWs vienen ya sin PP- y eso es válido."""
        assert normalizar_ipp("14-03-001393-20/00") == "14-03-001393-20/00"

    def test_institucional_se_preserva_completo(self) -> None:
        """AM-, HC-, OE- etc. NO pierden su prefijo (es parte del identificador)."""
        assert normalizar_ipp("AM-14-00-000012-21/00") == "AM-14-00-000012-21/00"
        assert normalizar_ipp("HC-14-00-000077-22/00") == "HC-14-00-000077-22/00"
        assert normalizar_ipp("OE-14-00-000087-22/00") == "OE-14-00-000087-22/00"

    def test_externa_se_preserva(self) -> None:
        assert normalizar_ipp("Causa 41820") == "Causa 41820"
        assert normalizar_ipp("CCC 15203/2024") == "CCC 15203/2024"

    def test_pp_malformada_se_preserva(self) -> None:
        """No intentamos corregir typos automáticamente — se conservan tal cual."""
        assert normalizar_ipp("PP-J-01-00013167-5/22") == "PP-J-01-00013167-5/22"

    def test_nulo_devuelve_none(self) -> None:
        assert normalizar_ipp(None) is None
        assert normalizar_ipp("") is None
        assert normalizar_ipp(pd.NA) is None

    def test_idempotente_para_estandar(self) -> None:
        """Aplicar normalizar dos veces no cambia el resultado."""
        original = "PP-14-03-001393-20/00"
        una_vez = normalizar_ipp(original)
        dos_veces = normalizar_ipp(una_vez)
        assert una_vez == dos_veces


class TestRequiereRevision:
    def test_pp_malformada_requiere_revision(self) -> None:
        assert requiere_revision_ipp("pp_malformada") is True

    @pytest.mark.parametrize(
        "tipo",
        [
            "estandar",
            "amparo",
            "oficio_exhorto",
            "externa",
            "nulo",
        ],
    )
    def test_resto_no_requiere(self, tipo: str) -> None:
        assert requiere_revision_ipp(tipo) is False


class TestCatalogoCoherente:
    """Verifica que los enums se mantengan coherentes con sus fuentes."""

    def test_todos_los_prefijos_institucionales_en_enum(self) -> None:
        """Cada tipo del mapeo PREFIJOS_INSTITUCIONALES debe estar en TIPO_IPP_VALIDOS."""
        for tipo in PREFIJOS_INSTITUCIONALES.values():
            assert tipo in TIPO_IPP_VALIDOS, f"Tipo '{tipo}' del mapeo no está en TIPO_IPP_VALIDOS"

    def test_categorias_especiales_estan_en_enum(self) -> None:
        for tipo in ("estandar", "externa", "pp_malformada", "nulo"):
            assert tipo in TIPO_IPP_VALIDOS
