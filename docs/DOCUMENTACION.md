# Documentación técnica

Detalle de arquitectura, metodología, schemas y pipelines del proyecto.
Para una vista general y el quickstart, ver el `README.md`.

## Arquitectura

Paquete Python con capa de I/O, capa de transformación pura y orquestador CLI.
El pipeline corre sin Jupyter ni Colab.

```
analitica-judicial-penal-juvenil/
├── pyproject.toml              fuente primaria de config y dependencias
├── Makefile                    comandos de conveniencia
├── .gitignore                  data/raw/ y outputs/ nunca al repo
├── .github/workflows/ci.yml    CI: lint + tests en cada push
├── .streamlit/config.toml      tema persistente del dashboard
│
├── src/
│   ├── config.py               paths y parámetros
│   ├── limpieza.py             funciones puras de limpieza textual
│   ├── normalizacion.py        normalización jurídica + cruces
│   ├── diccionarios.py         carga de diccionarios y nomenclador
│   ├── indicadores.py          indicadores mensuales del juzgado
│   ├── normalizar_ipp.py       clasificador IPP (12 categorías)
│   ├── resoluciones.py         pipeline de resoluciones (3 RAWs)
│   ├── cruce_causas_resoluciones.py   join causas/resoluciones + métricas
│   ├── pipeline.py             orquestador CLI de causas
│   ├── schema.py               contratos pandera
│   └── logging_setup.py        logging estructurado
│
├── dashboard/                  Streamlit + Altair
│   ├── app.py, theme.py, data.py
│   ├── components/             sidebar, KPIs
│   └── tabs/                   temporal, delitos, trámites, calidad, gestión
│
├── tests/                      unitarios + integración + dashboard
├── data/
│   ├── raw/                    Excel fuente + RAW vigente (gitignored)
│   ├── backfill/               históricos inmutables + checksums.json
│   ├── diccionarios/           CSVs versionados
│   └── external/               nomenclador + indicadores estadística
├── outputs/                    CSV/XLSX generados (gitignored)
├── scripts/descargar_nomenclador.py
└── docs/metodologia.md
```

## Metodología de normalización

Resumen de etapas en `docs/metodologia.md`. Puntos clave:

**Protección de datos.** El archivo original con nombres no se usa en el repo. El
análisis corre sobre una copia anonimizada; la carátula original no se publica.

**Delitos.** Capa operativa con limpieza textual, 45 reglas regex de typos frecuentes,
diccionario local de equivalencias verificadas en el juzgado y flags jurídicos
(tentativa, agravado, 5 subtipos de agravantes, agravante no especificado, posible
delito múltiple). Ejemplos de reglas: `robo` a `robo simple`; `lesiones` a `lesiones
leves` cuando no se especifica; `agravado/calificado` sin detalle queda como categoría
agravada no especificada.

**Cruce con nomenclador oficial.** Referencia: [Codificación de delitos del Código
Penal Argentino](https://datos.jus.gob.ar/dataset/d4a7a48d-d5c5-48e3-b820-0bc308d57e3c/resource/1bb19ad9-1429-41ce-8ddf-e745a4aa2395/download/codificacion-delitos-codigo-penal-argentino-20191011.csv).
Estados del match: `match_univoco`, `match_ambiguo`, `sin_equivalencia_definida`, más
`proceso_especial` (amparo, habeas corpus) y `sin_delito_informado`. No se fuerzan
matches cuando la fuente o el nomenclador no permiten una identificación unívoca.

**Trámites.** Se estandarizan con diccionario local más reglas residuales por
operatoria del juzgado (elevación a juicio con/sin SJP, declinatoria de competencia, etc.).

## Schema del dataset de causas (28 columnas)

Validado en runtime con `pandera`. Si el output viola el contrato, el pipeline falla
con `SchemaError`.

| Columna | Tipo | Notas |
|---------|------|-------|
| `fecha_ingreso`, `anio`, `ipp` | datetime / int / str | Identificación temporal |
| `caratula_anonimizada`, `responsable` | str | Identificación administrativa |
| `tipo_tramite_raw` / `_limpio` / `_estandar` | str | Trámite en 3 capas |
| `delito_raw` / `_limpio` / `_sin_tentativa` / `_estandar` | str | Delito en 4 capas |
| `delito_informado` | enum: si / no | |
| `tentativa`, `es_proceso_especial` | bool | |
| `agravado_flag` + 5 subflags + `agravante_no_especificado` | bool | |
| `posible_delito_multiple` | bool | |
| `objetivo_ministerio`, `descripcion_ministerio`, `articulo_ministerio`, `codigo_delito_ministerio` | str | Cruce con nomenclador |
| `estado_match_ministerio` | enum: 6 valores | |

## Calidad del código

- Suite de tests con fixtures sintéticas (unitarios + integración + dashboard +
  indicadores + resoluciones + cruce). El número exacto lo da `make test`.
- CI: lint + tests en cada push (GitHub Actions).
- Lint/format: `ruff` configurado en `pyproject.toml`.
- Type hints en firmas públicas de `src/`.
- Contratos de datos con `pandera`.
- Todos los `merge()` declaran `validate="m:1"` (regla DATA-02 del guideline interno).

## Dashboard

Streamlit con Altair, siguiendo *Storytelling with Data* (Knaflic): títulos
narrativos calculados sobre los filtros activos, un único color de acento, sin
chart-junk. Requiere que el pipeline haya generado el CSV en `outputs/`.

Tabs: **temporal** (evolución anual + mensual), **delitos** (top 10 + evolución +
flags jurídicos), **trámites** (top 10 + heatmap trámite x delito), **calidad**
(distribución del match + cola de revisión descargable), **gestión** (consume el
cruce causas-resoluciones).

El tab **Calidad de datos** funciona como herramienta operativa: produce una cola de
revisión descargable con causas que requieren atención humana (sin cruce ministerial,
posibles delitos múltiples, agravantes sin especificar, delitos no informados),
para enriquecer los diccionarios locales de forma iterativa.

### Tab Gestión

Consume el output del cruce y muestra:

1. KPIs: % de causas con resoluciones, mediana de días hasta primera resolución,
   mediana de días de proceso, % que termina en cierre de proceso.
2. Cómo terminan las causas: distribución porcentual por modalidad resolutiva.
3. Cuánto tarda la primera resolución: histograma por bins de tiempo, excluyendo
   métricas temporales anómalas (días negativos por reingresos o IPPs de otra jurisdicción).
4. Tiempo de proceso por tipo de delito: mediana de días, top N por volumen, umbral
   de 5 causas mínimas para descartar ruido.
5. Cohorte por año de ingreso: barras apiladas con resolución vs sin resolución, para
   leer el efecto cohorte (causas recientes tienen menor tasa de resolución).

Si el output del cruce no está disponible, el tab muestra los comandos para generarlo.

### Deploy en Streamlit Community Cloud

1. Push del repo a GitHub manteniendo `data/raw/` afuera.
2. Subir el CSV anonimizado de `outputs/` al repo o a un bucket accesible.
3. En [share.streamlit.io](https://share.streamlit.io) conectar el repo y apuntar a
   `dashboard/app.py`.

## Indicadores mensuales del juzgado

Indicadores agregados del Departamento de Estadística del Poder Judicial, en formato
long (una fila por mes-indicador).

```python
from src.indicadores import cargar_indicadores, pivot_a_wide, calcular_ratios

df = cargar_indicadores()            # long: 1011 filas, 21 indicadores, 54 meses
wide = pivot_a_wide(df)              # una fila por mes
wide_ratios = calcular_ratios(wide)  # + tasa_resolucion_calculada, delta, ratio
```

El archivo va en `data/external/indicadores_jgj3si.xlsx`. La carga valida un schema
pandera y, contra el archivo real, un test de aceptación verifica que la
`tasa_de_resolucion` publicada coincida con `finalizadas / ingresadas * 100`
(tolerancia <1.0). Los slugs estables están en `src.indicadores.SLUGS_PRINCIPALES`.

## Pipeline de resoluciones

Carga el registro causa-por-causa de resoluciones desde tres archivos con ciclos de
vida distintos:

```
data/
├── backfill/                            inmutable, checksums versionados
│   ├── resoluciones_2017_2019.xlsx      RAW1, solo año
│   ├── resoluciones_2020_2023a.xlsx     RAW2, fecha completa
│   └── checksums.json
└── raw/
    └── resoluciones_2023b_2026.xlsx     RAW3, vigente, se actualiza mensual
```

```bash
make pipeline-resoluciones   # produce outputs/resoluciones_2017_2026_consolidado.csv
```

El pipeline:

1. Verifica checksums SHA-256 de los backfills (warning ruidoso si cambiaron).
2. Concatena los 3 archivos con `fuente_raw` como audit trail.
3. Explota multi-resoluciones: `"sobreseimiento, derivación"` se vuelve 2 filas, cada
   una con `multi_resolucion_origen=True`.
4. Clasifica cada IPP en 12 categorías (`tipo_ipp`): estándar, oficio_exhorto, amparo,
   querella, habeas_corpus, faltas_contravenciones, apelacion_contravencional,
   habeas_data, dictamen_civil, externa, pp_malformada, nulo.
5. Normaliza el IPP a `ipp_canonico` (clave de join con causas).
6. Aplica el diccionario de resoluciones (424 tokens a 99 canónicas en 20 categorías).
7. Valida el output contra schema pandera.

### Safety net de backfills

Los archivos en `data/backfill/` son inmutables. Un cambio accidental se detecta en la
próxima corrida. Si el cambio es intencional:

```bash
make refresh-checksums-backfill
git add data/backfill/checksums.json
git commit -m "data: actualización legítima de backfill"
```

Sin regenerar los checksums, el pipeline logea un warning pero no falla (sigue idempotente).

### Schema del consolidado (12 columnas)

| Columna | Tipo | Notas |
|---------|------|-------|
| `ipp_original`, `ipp_canonico` | str | El canónico es la clave de join con causas |
| `tipo_ipp` | enum | 12 categorías |
| `fecha_resolucion` | datetime \| NaT | NaT en RAW1 (solo año) |
| `anio_resolucion` | Int64 | Siempre presente |
| `mes_resolucion` | Int64 \| NA | NA en RAW1 |
| `resolucion_raw` / `_canonica` / `categoria_resolucion` | str | 3 capas |
| `multi_resolucion_origen` | bool | True si salió de explotar multi |
| `requiere_validacion` | bool | Cola de revisión |
| `fuente_raw` | enum | backfill_2017_2019 / backfill_2020_2023a / raw_2023b_2026 |

## Cruce causas-resoluciones

`src/cruce_causas_resoluciones.py` produce un dataset con un row por causa enriquecido
con métricas del join por IPP canónico.

```bash
make cruce-causas-resoluciones   # produce outputs/causas_con_metricas_resoluciones.csv
```

LEFT JOIN desde causas (preserva las 1.267 filas) que agrega 14 columnas:

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `ipp_canonico`, `tipo_ipp` | str | Clasificación del IPP |
| `n_resoluciones` | int | Total de resoluciones del IPP |
| `tiene_resoluciones` | bool | True si al menos 1 |
| `fecha_primera_resolucion`, `fecha_ultima_resolucion` | datetime, NaT | NaT si solo hay RAW1 |
| `dias_hasta_primera_resolucion`, `dias_proceso` | Int64, NA | NA si no computable |
| `tiene_cierre_proceso`, `tiene_elevacion_juicio`, ... (7 flags) | bool | Una por categoría |
| `categorias_resolucion` | str | Concat de categorías únicas (audit) |

**Auditoría.** Cada corrida logea causas con/sin resoluciones (esperado ~77% con,
~23% sin) y resoluciones huérfanas (IPPs en resoluciones que no aparecen en causas,
esperables por ser causas anteriores a 2020).

**Deuda técnica.** El dataset de causas no tiene `ipp_canonico` ni `tipo_ipp` nativos;
el cruce los calcula localmente con `normalizar_ipp`. Pendiente incorporarlos al
pipeline de causas para que el cruce los consuma directo.
