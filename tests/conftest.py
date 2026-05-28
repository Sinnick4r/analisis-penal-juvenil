"""Fixtures compartidas para los tests del pipeline.

Construyen un dataset sintético pequeño (~10-15 filas) que cubre todos
los casos jurídicamente relevantes: tentativa, agravantes, procesos
especiales, delitos múltiples, ambigüedad ministerial y delito no informado.

No usa el Excel real ni los CSVs del Ministerio: todo se arma en memoria,
así los tests corren en CI sin datos sensibles ni dependencias externas.
"""
from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture
def df_causas_sinteticas() -> pd.DataFrame:
    """DataFrame de causas que cubre los casos jurídicos relevantes.

    Las columnas y dtypes imitan la salida de `cargar_datos_raw`.
    """
    return pd.DataFrame({
        "fecha_ingreso": pd.to_datetime([
            "2022-03-15", "2022-04-10", "2023-01-20", "2023-05-05",
            "2024-02-12", "2024-07-08", "2024-09-30", "2025-01-15",
            "2025-06-18", "2025-08-22", "2024-11-03", "2025-03-14",
        ]),
        "anio": [2022, 2022, 2023, 2023, 2024, 2024, 2024, 2025, 2025, 2025, 2024, 2025],
        "ipp": pd.array([
            "1-2022-001", "1-2022-002", "1-2023-003", "1-2023-004",
            "1-2024-005", "1-2024-006", "1-2024-007", "1-2025-008",
            "1-2025-009", "1-2025-010", "1-2024-011", "1-2025-012",
        ], dtype="string"),
        "tipo_tramite": pd.array([
            "elevacion a juicio", "Remite a Departamental",
            "ARCHIVO", "elevacion a juicio (ofrece SJP)",
            "declinatoria de competencia", "ARCHIVO",
            "elevacion a juicio", "Remite a Departamental",
            "ARCHIVO", "delinatoria de competencia",
            "ARCHIVO", "ARCHIVO",
        ], dtype="string"),
        "caratula_anonimizada": pd.array(["XXXX"] * 12, dtype="string"),
        "responsable": pd.array(["op1"] * 12, dtype="string"),
        # Casos cubiertos:
        # 0: lesiones leves — match unívoco, sin tentativa
        # 1: robo en tva. — tentativa, robo simple, match unívoco
        # 2: amenazas — match unívoco
        # 3: robo agravado por el uso de arma — agravado con sub-flag arma, no múltiple
        # 4: hurto agravado por escalamiento — agravante escalamiento, no múltiple (excepción)
        # 5: lesiones leves y amenazas — posible delito múltiple
        # 6: robo agravado — match ambiguo (sin sub-agravante específico)
        # 7: amparo — proceso especial
        # 8: "" — delito no informado
        # 9: hurto — match unívoco
        # 10: robo agravado en poblado y en banda — agravante poblado+banda, no múltiple (excepción)
        # 11: lesioens leves (typo) — debe normalizarse a lesiones leves
        "delito": pd.array([
            "lesiones leves",
            "robo en tva.",
            "amenazas",
            "robo agravado por el uso de arma",
            "hurto agravado por escalamiento",
            "lesiones leves y amenazas",
            "robo agravado",
            "amparo",
            "",
            "hurto",
            "robo agravado en poblado y en banda",
            "lesioens leves",
        ], dtype="string"),
        "delito_raw": pd.array([
            "lesiones leves",
            "robo en tva.",
            "amenazas",
            "robo agravado por el uso de arma",
            "hurto agravado por escalamiento",
            "lesiones leves y amenazas",
            "robo agravado",
            "amparo",
            "",
            "hurto",
            "robo agravado en poblado y en banda",
            "lesioens leves",
        ], dtype="string"),
        "tipo_tramite_raw": pd.array([
            "elevacion a juicio", "Remite a Departamental",
            "ARCHIVO", "elevacion a juicio (ofrece SJP)",
            "declinatoria de competencia", "ARCHIVO",
            "elevacion a juicio", "Remite a Departamental",
            "ARCHIVO", "delinatoria de competencia",
            "ARCHIVO", "ARCHIVO",
        ], dtype="string"),
    })


@pytest.fixture
def dict_delitos_local_sint() -> pd.DataFrame:
    """Diccionario local sintético con los delitos que aparecen en el fixture."""
    return pd.DataFrame({
        "delito_fuente": [
            "robo", "hurto", "lesiones", "lesiones leves",
            "amenazas", "robo agravado", "amparo",
            "robo agravado por el uso de arma",
            "hurto agravado por escalamiento",
            "robo agravado en poblado y en banda",
            "lesiones leves y amenazas",
        ],
        "delito_estandar": [
            "robo simple", "hurto", "lesiones leves", "lesiones leves",
            "amenazas", "robo agravado", "amparo",
            "robo agravado por el uso de arma",
            "hurto agravado por escalamiento",
            "robo agravado en poblado y en banda",
            "lesiones leves y amenazas",
        ],
        "observacion": [""] * 11,
        "fuente_regla": ["local"] * 11,
        "requiere_revision": [False] * 11,
        "activo": [True] * 11,
    })


@pytest.fixture
def dict_delitos_ministerio_sint() -> pd.DataFrame:
    """Puente local→ministerio sintético."""
    return pd.DataFrame({
        "delito_estandar": [
            "robo simple", "hurto", "lesiones leves", "amenazas",
            "robo agravado", "robo agravado por el uso de arma",
            "hurto agravado por escalamiento",
            "robo agravado en poblado y en banda",
            "lesiones leves y amenazas",
        ],
        "objetivo_ministerio": [
            "hurto simple",  # ojo: el plan dice que "robo" se mapea a "robo simple"; aquí simulamos
            "hurto simple",
            "lesiones leves",
            "amenazas",
            "robo agravado",  # ambiguo: dos códigos en el nomenclador
            "robo agravado por el uso de arma",
            "hurto agravado por escalamiento",
            "robo agravado en poblado y en banda",
            "sin_equivalencia_definida",  # explícitamente sin equivalencia
        ],
        "criterio_match": [
            "univoco", "univoco", "univoco", "univoco",
            "ambiguo", "univoco", "univoco", "univoco",
            "sin_equivalencia_definida",
        ],
        "observacion": [""] * 9,
        "activo": [True] * 9,
    })


@pytest.fixture
def dict_tramites_sint() -> pd.DataFrame:
    """Diccionario de trámites sintético."""
    return pd.DataFrame({
        "tramite_fuente": [
            "archivo", "remite a departamental", "elevacion a juicio",
        ],
        "tramite_estandar": [
            "archivo", "competencia", "elevacion_a_juicio",
        ],
        "categoria": ["resolutivo", "competencia", "elevacion"],
        "observacion": [""] * 3,
        "activo": [True] * 3,
    })


@pytest.fixture
def df_indicadores_raw_sint() -> pd.DataFrame:
    """DataFrame con la forma EXACTA del Excel de indicadores (pre-normalización).

    Columnas con tildes y mayúsculas tal como vienen del área de Estadística.
    Cubre las 5 dimensiones y los indicadores más relevantes, con valores
    elegidos para que la verificación `tasa = finalizadas/ingresadas*100`
    funcione exactamente sin redondeo.
    """
    rows: list[dict] = []
    # Dos años, dos meses cada uno = 4 meses con datos completos.
    casos = [
        # (año, mes, ingresadas, finalizadas, tasa_redondeada)
        (2024, 1, 20, 30, 150),  # 30/20*100 = 150 exacto
        (2024, 2, 25, 50, 200),  # 50/25*100 = 200 exacto
        (2025, 1, 10, 15, 150),  # 15/10*100 = 150 exacto
        (2025, 2, 30, 45, 150),  # 45/30*100 = 150 exacto
    ]
    base = {
        "Departamento": "SAN ISIDRO",
        "Dependencia": "JUZGADO DE GARANTIAS DEL JOVEN Nº 3 - SAN ISIDRO",
    }
    for anio, mes, ing, fin, tasa in casos:
        rows.extend([
            {**base, "Año": anio, "Mes": mes, "Dimensión": "Demanda del servicio",
             "indicador": "Causas Ingresadas", "valor": ing},
            {**base, "Año": anio, "Mes": mes, "Dimensión": "Respuesta del Órgano",
             "indicador": "Causas finalizadas (trámites de finalización)", "valor": fin},
            {**base, "Año": anio, "Mes": mes, "Dimensión": "Respuesta del Órgano",
             "indicador": "Tasa de resolución", "valor": tasa},
            {**base, "Año": anio, "Mes": mes, "Dimensión": "Carga Laboral",
             "indicador": "Trámites Totales", "valor": 300 + mes * 10},
            {**base, "Año": anio, "Mes": mes, "Dimensión": "Planta",
             "indicador": "Funcionarios en Dependencia", "valor": 5},
        ])
    return pd.DataFrame(rows)


@pytest.fixture
def nomenclador_sint() -> pd.DataFrame:
    """Nomenclador oficial sintético con los delitos del fixture.

    'Robo agravado' aparece con dos códigos (CP.166 y CP.167) para simular
    el match ambiguo. Los demás son unívocos.
    """
    return pd.DataFrame({
        "delito_descripcion": [
            "Hurto simple",
            "Lesiones leves",
            "Amenazas",
            "Robo agravado", "Robo agravado",  # mismo nombre, dos códigos
            "Robo agravado por el uso de arma",
            "Hurto agravado por escalamiento",
            "Robo agravado en poblado y en banda",
        ],
        "delito_articulo": [
            "Art. 162", "Art. 89", "Art. 149 bis Pár. 1 Parte 1",
            "Art. 166", "Art. 167",
            "Art. 166 Inc. 2", "Art. 163 Inc. 4",
            "Art. 167 Inc. 2",
        ],
        "codigo_delito": [
            "CP.162.0.00.00.00", "CP.089.0.00.00.00", "CP.149.2.01.00.01",
            "CP.166.0.00.00.00", "CP.167.0.00.00.00",
            "CP.166.0.02.00.00", "CP.163.0.04.00.00",
            "CP.167.0.02.00.00",
        ],
        "tipo": ["delito"] * 8,
        "vigente": ["SI"] * 8,
    })


@pytest.fixture
def df_resoluciones_raw_sint() -> pd.DataFrame:
    """DataFrame con la forma EXACTA de los Excel de resoluciones (pre-normalización).

    Imita las 4 columnas (`Año`, `IPP`, `RESOLUCION`, `IPP  Normalizada`) con
    casos que cubren:
    - IPP estándar (PP-...)
    - IPP institucional (AM-, HC-, OE-)
    - IPP externo ("Causa NNNN")
    - IPP malformado (PP-J-...)
    - Resolución single-tema
    - Resolución multi-tema (varios separadores)
    - Resolución no presente en el diccionario
    """
    return pd.DataFrame({
        "Año": pd.to_datetime([
            "2024-03-15", "2024-04-10", "2024-05-20",
            "2024-06-08", "2024-07-15", "2024-08-22",
            "2024-09-30", "2024-10-15",
        ]),
        "IPP": pd.array([
            "PP-14-03-001393-24/00",
            "PP 14-04-002648-24/01",  # espacio en vez de guion
            "AM-14-00-000012-24/00",
            "HC-14-00-000077-24/00",
            "OE-14-00-000087-24/00",
            "Causa 41820",
            "PP-J-01-00013167-5/24",  # malformado
            "PP-14-05-003482-24/00",
        ], dtype="string"),
        "RESOLUCION": pd.array([
            "sobreseimiento",                       # single
            "sobreseimiento, derivacion",           # multi por coma
            "Elevacion a juicio",                   # single
            "rebeldia y captura",                   # multi por " y "
            "allanamiento - secuestro",             # multi por " - "
            "competencia / sobreseimiento",         # multi por " / "
            "frase rara no en diccionario",         # sin match
            "Rebeldia s/ efecto",                   # falso positivo: s/ NO es separador
        ], dtype="string"),
        "IPP  Normalizada": pd.array([        # doble espacio en el original
            "14-03-001393-24/00",
            "14-04-002648-24/01",
            "AM-14-00-000012-24/00",
            "HC-14-00-000077-24/00",
            "OE-14-00-000087-24/00",
            "Causa 41820",
            "PP-J-01-00013167-5/24",
            "14-05-003482-24/00",
        ], dtype="string"),
    })


@pytest.fixture
def df_resoluciones_raw_solo_anio_sint() -> pd.DataFrame:
    """Variante para simular RAW1 (2017-2019): `Año` es int, no datetime."""
    return pd.DataFrame({
        "Año": [2017, 2018, 2019],
        "IPP": pd.array([
            "14-00-005027-16",
            "14-08-001758-16",
            "14-00-006120-16",
        ], dtype="string"),
        "RESOLUCION": pd.array([
            "Autoriza salida",
            "Sobreseimiento",
            "Comp/Sobreseimiento",  # multi por /
        ], dtype="string"),
        "IPP  Normalizada": pd.array([
            "14-00-005027-16/00",
            "14-08-001758-16/00",
            "14-00-006120-16/00",
        ], dtype="string"),
    })


@pytest.fixture
def diccionario_resoluciones_sint() -> pd.DataFrame:
    """Diccionario de resoluciones sintético con los tokens del fixture."""
    return pd.DataFrame({
        "token_normalizado": [
            "sobreseimiento",
            "derivacion",
            "elevacion a juicio",
            "rebeldia",
            "captura",
            "allanamiento",
            "secuestro",
            "competencia",
            "autoriza salida",
            "rebeldia s/ efecto",
        ],
        "resolucion_canonica": [
            "sobreseimiento",
            "derivacion a servicio local",
            "elevacion a juicio",
            "rebeldia",
            "captura",
            "allanamiento",
            "secuestro",
            "acepta competencia",
            "autoriza salida",
            "rebeldia sin efecto",
        ],
        "categoria": [
            "cierre de proceso",
            "derivacion a servicio local",
            "elevacion a juicio",
            "rebeldia",
            "ordenes de detencion/captura/comparendos",
            "allanamiento",
            "allanamiento",
            "competencia",
            "salida alternativa",
            "rebeldia",
        ],
        "validar": [None, None, None, None, None, None, None, None, None, None],
        "observaciones": [None] * 10,
        "frecuencia_total": [100] * 10,
        "datasets_presentes": [3] * 10,
        "ejemplos_raw": [""] * 10,
    })


@pytest.fixture
def df_causas_para_cruce_sint() -> pd.DataFrame:
    """DataFrame mínimo con la forma del output de Iteración A.

    5 causas que cubren los casos del cruce:
    - Causa con 1 resolución de RAW1 (sin fecha exacta)
    - Causa con varias resoluciones de RAW2/3
    - Causa sin resoluciones
    - Causa con IPP institucional (AM)
    - Causa con IPP malformado (sin match con resoluciones)
    """
    return pd.DataFrame({
        "fecha_ingreso": pd.to_datetime([
            "2022-03-15", "2024-01-10", "2025-06-01",
            "2024-05-15", "2023-09-20",
        ]),
        "anio": [2022, 2024, 2025, 2024, 2023],
        "ipp": [
            "PP-14-03-001393-22/00",     # 1 resol RAW1 simulada
            "PP-14-04-002648-24/01",     # múltiples resoluciones
            "PP-14-05-003482-25/00",     # sin resoluciones
            "AM-14-00-000012-24/00",     # institucional
            "PP-J-01-00013167-5/23",     # malformado, sin match
        ],
        "delito_estandar": [
            "robo simple", "lesiones leves", "hurto",
            "amparo", "robo agravado",
        ],
        "delito_informado": ["si"] * 5,
    })


@pytest.fixture
def df_resoluciones_para_cruce_sint() -> pd.DataFrame:
    """DataFrame mínimo con la forma del output de Iteración B (consolidado).

    Sincronizado con `df_causas_para_cruce_sint`:
    - IPP 14-03-001393-22/00: 1 resolución RAW1 (fecha NaT, solo año)
    - IPP 14-04-002648-24/01: 3 resoluciones RAW2/3 con fechas reales
    - AM-14-00-000012-24/00: 1 resolución (institucional)
    - IPP 14-99-999999-99/99: 1 resolución huérfana (sin causa correspondiente)
    """
    return pd.DataFrame({
        "ipp_canonico": [
            "14-03-001393-22/00",          # 1 sola, RAW1
            "14-04-002648-24/01",          # primera de 3
            "14-04-002648-24/01",          # segunda
            "14-04-002648-24/01",          # tercera
            "AM-14-00-000012-24/00",       # institucional, 1 resol
            "14-99-999999-99/99",          # huérfana
        ],
        "fecha_resolucion": pd.to_datetime([
            None,                                       # RAW1 sin fecha
            "2024-01-25", "2024-02-15", "2024-04-10",   # 3 resoluciones RAW2/3
            "2024-06-01",                                # institucional
            "2024-12-30",                                # huérfana
        ]),
        "anio_resolucion": pd.array(
            [2022, 2024, 2024, 2024, 2024, 2024], dtype="Int64",
        ),
        "categoria_resolucion": [
            "cierre de proceso",
            "medida de coercion",
            "competencia",
            "cierre de proceso",
            "salida alternativa",
            "rebeldia",
        ],
        "resolucion_canonica": [
            "sobreseimiento", "prision preventiva", "acepta competencia",
            "sobreseimiento", "suspension de juicio a prueba", "rebeldia",
        ],
        "fuente_raw": [
            "backfill_2017_2019", "backfill_2020_2023a", "raw_2023b_2026",
            "raw_2023b_2026", "raw_2023b_2026", "raw_2023b_2026",
        ],
    })
