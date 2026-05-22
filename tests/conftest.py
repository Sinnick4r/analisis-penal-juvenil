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
