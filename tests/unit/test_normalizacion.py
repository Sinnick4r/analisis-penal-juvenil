"""Tests unitarios para `src.normalizacion`.

Cubren cada paso de la pipeline lógica con el fixture sintético:
- Detección de tentativa.
- Cálculo de flags jurídicos (agravado, sub-agravantes, agravante_no_especificado).
- Excepciones de delitos múltiples.
- Estados del cruce ministerial.
- Normalización de trámites + reglas residuales.
"""
from __future__ import annotations

from src.normalizacion import (
    EXCEPCIONES_NO_MULTIPLES,
    cruzar_ministerio,
    normalizar_delitos,
    normalizar_tramites,
)


class TestNormalizarDelitos:
    """Tests sobre la cadena completa de normalización de delitos."""

    def test_no_pierde_filas(self, df_causas_sinteticas, dict_delitos_local_sint):
        df = normalizar_delitos(df_causas_sinteticas, dict_delitos_local_sint)
        assert len(df) == len(df_causas_sinteticas)

    def test_detecta_tentativa_de_abreviatura_tva(
        self, df_causas_sinteticas, dict_delitos_local_sint
    ):
        df = normalizar_delitos(df_causas_sinteticas, dict_delitos_local_sint)
        # Fila 1: "robo en tva." → debe ser tentativa
        assert df.iloc[1]["tentativa"]

    def test_no_marca_tentativa_donde_no_corresponde(
        self, df_causas_sinteticas, dict_delitos_local_sint
    ):
        df = normalizar_delitos(df_causas_sinteticas, dict_delitos_local_sint)
        # Fila 0: "lesiones leves" no es tentativa
        assert not df.iloc[0]["tentativa"]

    def test_corrige_typo_lesioens(self, df_causas_sinteticas, dict_delitos_local_sint):
        df = normalizar_delitos(df_causas_sinteticas, dict_delitos_local_sint)
        # Fila 11: "lesioens leves" → "lesiones leves"
        assert df.iloc[11]["delito_estandar"] == "lesiones leves"

    def test_delito_no_informado_para_vacio(
        self, df_causas_sinteticas, dict_delitos_local_sint
    ):
        df = normalizar_delitos(df_causas_sinteticas, dict_delitos_local_sint)
        # Fila 8: "" → "delito_no_informado"
        assert df.iloc[8]["delito_estandar"] == "delito_no_informado"
        assert df.iloc[8]["delito_informado"] == "no"

    def test_marca_proceso_especial(
        self, df_causas_sinteticas, dict_delitos_local_sint
    ):
        df = normalizar_delitos(df_causas_sinteticas, dict_delitos_local_sint)
        # Fila 7: "amparo" → es proceso especial
        assert df.iloc[7]["es_proceso_especial"]

    def test_flag_agravado_se_activa(
        self, df_causas_sinteticas, dict_delitos_local_sint
    ):
        df = normalizar_delitos(df_causas_sinteticas, dict_delitos_local_sint)
        # Fila 3: "robo agravado por el uso de arma" → agravado_flag True
        assert df.iloc[3]["agravado_flag"]
        # Y específicamente con sub-flag de arma
        assert df.iloc[3]["agravante_arma"]

    def test_sub_agravante_escalamiento(
        self, df_causas_sinteticas, dict_delitos_local_sint
    ):
        df = normalizar_delitos(df_causas_sinteticas, dict_delitos_local_sint)
        # Fila 4: "hurto agravado por escalamiento"
        assert df.iloc[4]["agravado_flag"]
        assert df.iloc[4]["agravante_escalamiento"]

    def test_agravante_no_especificado(
        self, df_causas_sinteticas, dict_delitos_local_sint
    ):
        df = normalizar_delitos(df_causas_sinteticas, dict_delitos_local_sint)
        # Fila 6: "robo agravado" — agravado pero sin sub-tipo específico
        assert df.iloc[6]["agravado_flag"]
        assert df.iloc[6]["agravante_no_especificado"]

    def test_posible_delito_multiple_se_marca(
        self, df_causas_sinteticas, dict_delitos_local_sint
    ):
        df = normalizar_delitos(df_causas_sinteticas, dict_delitos_local_sint)
        # Fila 5: "lesiones leves y amenazas" → múltiple
        assert df.iloc[5]["posible_delito_multiple"]

    def test_excepcion_no_marca_multiple(
        self, df_causas_sinteticas, dict_delitos_local_sint
    ):
        df = normalizar_delitos(df_causas_sinteticas, dict_delitos_local_sint)
        # Fila 10: "robo agravado en poblado y en banda" → es excepción, NO múltiple
        assert df.iloc[10]["delito_estandar"] in EXCEPCIONES_NO_MULTIPLES
        assert not df.iloc[10]["posible_delito_multiple"]
        # Y debe marcar el sub-agravante de poblado y banda
        assert df.iloc[10]["agravante_poblado_banda"]


class TestCruzarMinisterio:
    """Tests sobre el cruce con el nomenclador del Ministerio."""

    def test_no_pierde_filas(
        self, df_causas_sinteticas, dict_delitos_local_sint,
        dict_delitos_ministerio_sint, nomenclador_sint,
    ):
        df = normalizar_delitos(df_causas_sinteticas, dict_delitos_local_sint)
        df = cruzar_ministerio(df, dict_delitos_ministerio_sint, nomenclador_sint)
        assert len(df) == len(df_causas_sinteticas)

    def test_proceso_especial_marca_estado(
        self, df_causas_sinteticas, dict_delitos_local_sint,
        dict_delitos_ministerio_sint, nomenclador_sint,
    ):
        df = normalizar_delitos(df_causas_sinteticas, dict_delitos_local_sint)
        df = cruzar_ministerio(df, dict_delitos_ministerio_sint, nomenclador_sint)
        # Fila 7: amparo → proceso_especial
        assert df.iloc[7]["estado_match_ministerio"] == "proceso_especial"

    def test_sin_delito_informado_marca_estado(
        self, df_causas_sinteticas, dict_delitos_local_sint,
        dict_delitos_ministerio_sint, nomenclador_sint,
    ):
        df = normalizar_delitos(df_causas_sinteticas, dict_delitos_local_sint)
        df = cruzar_ministerio(df, dict_delitos_ministerio_sint, nomenclador_sint)
        # Fila 8: vacío → sin_delito_informado
        assert df.iloc[8]["estado_match_ministerio"] == "sin_delito_informado"

    def test_match_ambiguo_cuando_nomenclador_tiene_dos_codigos(
        self, df_causas_sinteticas, dict_delitos_local_sint,
        dict_delitos_ministerio_sint, nomenclador_sint,
    ):
        df = normalizar_delitos(df_causas_sinteticas, dict_delitos_local_sint)
        df = cruzar_ministerio(df, dict_delitos_ministerio_sint, nomenclador_sint)
        # Fila 6: "robo agravado" en nomenclador aparece 2 veces → ambiguo
        assert df.iloc[6]["estado_match_ministerio"] == "match_ambiguo"

    def test_sin_equivalencia_definida_se_respeta(
        self, df_causas_sinteticas, dict_delitos_local_sint,
        dict_delitos_ministerio_sint, nomenclador_sint,
    ):
        df = normalizar_delitos(df_causas_sinteticas, dict_delitos_local_sint)
        df = cruzar_ministerio(df, dict_delitos_ministerio_sint, nomenclador_sint)
        # Fila 5: "lesiones leves y amenazas" tiene criterio_match=sin_equivalencia
        assert df.iloc[5]["estado_match_ministerio"] == "sin_equivalencia_definida"

    def test_solo_estados_validos(
        self, df_causas_sinteticas, dict_delitos_local_sint,
        dict_delitos_ministerio_sint, nomenclador_sint,
    ):
        df = normalizar_delitos(df_causas_sinteticas, dict_delitos_local_sint)
        df = cruzar_ministerio(df, dict_delitos_ministerio_sint, nomenclador_sint)
        estados_validos = {
            "match_univoco", "match_ambiguo", "sin_equivalencia_definida",
            "proceso_especial", "sin_delito_informado", "sin_match",
        }
        assert set(df["estado_match_ministerio"].unique()).issubset(estados_validos)


class TestNormalizarTramites:
    """Tests sobre la normalización de trámites."""

    def test_no_pierde_filas(
        self, df_causas_sinteticas, dict_tramites_sint,
    ):
        df = normalizar_tramites(df_causas_sinteticas, dict_tramites_sint)
        assert len(df) == len(df_causas_sinteticas)

    def test_elevacion_aplica_regla_residual(
        self, df_causas_sinteticas, dict_tramites_sint,
    ):
        df = normalizar_tramites(df_causas_sinteticas, dict_tramites_sint)
        # Fila 0: "elevacion a juicio" → mapea a elevacion_a_juicio
        assert df.iloc[0]["tipo_tramite_estandar"] == "elevacion_a_juicio"

    def test_elevacion_con_sjp(
        self, df_causas_sinteticas, dict_tramites_sint,
    ):
        df = normalizar_tramites(df_causas_sinteticas, dict_tramites_sint)
        # Fila 3: "elevacion a juicio (ofrece SJP)" → elevacion_a_juicio_ofrece_sjp
        assert df.iloc[3]["tipo_tramite_estandar"] == "elevacion_a_juicio_ofrece_sjp"

    def test_remite_a_se_mapea_a_competencia(
        self, df_causas_sinteticas, dict_tramites_sint,
    ):
        df = normalizar_tramites(df_causas_sinteticas, dict_tramites_sint)
        # Fila 1: "Remite a Departamental" → competencia
        assert df.iloc[1]["tipo_tramite_estandar"] == "competencia"

    def test_declinatoria_normalizada(
        self, df_causas_sinteticas, dict_tramites_sint,
    ):
        df = normalizar_tramites(df_causas_sinteticas, dict_tramites_sint)
        # Fila 4: "declinatoria de competencia" → declinatoria_de_competencia
        assert df.iloc[4]["tipo_tramite_estandar"] == "declinatoria_de_competencia"

    def test_typo_delinatoria_tambien_se_normaliza(
        self, df_causas_sinteticas, dict_tramites_sint,
    ):
        df = normalizar_tramites(df_causas_sinteticas, dict_tramites_sint)
        # Fila 9: "delinatoria de competencia" (con typo) → declinatoria_de_competencia
        assert df.iloc[9]["tipo_tramite_estandar"] == "declinatoria_de_competencia"
