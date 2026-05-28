# Analítica de causas del fuero penal juvenil (2020–2026)

Pipeline reproducible de limpieza, anonimización, normalización jurídica
y análisis estadístico de causas ingresadas en un juzgado del fuero penal
juvenil de la Provincia de Buenos Aires.

## Qué hace este proyecto

Transforma una planilla administrativa cargada manualmente por múltiples
operadores en un dataset analítico reproducible. El flujo de trabajo incluye:

- desidentificación previa de datos reservados;
- limpieza de texto y corrección de inconsistencias de carga;
- normalización operativa de delitos con diccionario local;
- separación de tentativa, agravantes y posibles delitos múltiples;
- normalización de trámites de ingreso;
- cruce con la codificación oficial de delitos del Ministerio de Justicia de la Nación;
- exportación de tablas listas para BI y análisis de gestión.

## Arquitectura

El proyecto está estructurado como un paquete Python con una capa de I/O,
una capa de transformación pura y un orquestador CLI. No depende de Jupyter
ni de Google Colab para correr el pipeline en producción.

```
analitica-judicial-penal-juvenil/
├── pyproject.toml              ← fuente primaria de config y dependencias
├── Makefile                    ← comandos de conveniencia
├── README.md
├── .gitignore                  ← data/raw/ y outputs/ NUNCA al repo
├── .python-version             ← 3.11
├── .github/workflows/ci.yml    ← CI: lint + tests en cada push
├── .streamlit/config.toml      ← tema persistente del dashboard
│
├── src/                        ← lógica del pipeline
│   ├── config.py               ← paths y parámetros
│   ├── limpieza.py             ← funciones puras de limpieza textual
│   ├── normalizacion.py        ← normalización jurídica + cruces
│   ├── diccionarios.py         ← carga de diccionarios y nomenclador
│   ├── indicadores.py          ← carga indicadores mensuales del juzgado
│   ├── normalizar_ipp.py       ← clasificador IPP (12 categorías)
│   ├── resoluciones.py         ← pipeline de resoluciones (3 RAWs)
│   ├── cruce_causas_resoluciones.py  ← join causas ↔ resoluciones + métricas
│   ├── pipeline.py             ← orquestador CLI de causas
│   ├── schema.py               ← contratos pandera (causas + indicadores + resoluciones + cruce)
│   └── logging_setup.py        ← logging estructurado
│
├── dashboard/                  ← visualización Streamlit + Altair
│   ├── app.py                  ← entry point
│   ├── theme.py                ← paleta + tema Altair (Knaflic)
│   ├── data.py                 ← carga del CSV con cache
│   ├── components/             ← sidebar, KPIs
│   └── tabs/                   ← 4 tabs: temporal, delitos, trámites, calidad
│
├── tests/                      ← 84 tests (unitarios + integración + dashboard)
│   ├── conftest.py             ← fixtures sintéticas (sin datos reales)
│   ├── unit/
│   └── integration/
│
├── data/
│   ├── raw/                    ← Excel fuente + RAW vigente (gitignored)
│   ├── backfill/               ← históricos inmutables + checksums.json
│   ├── diccionarios/           ← 5 CSVs versionados (delitos, trámites, resoluciones, prefijos)
│   └── external/               ← nomenclador del Ministerio + indicadores estadística
│
├── outputs/                    ← CSV/XLSX generados (gitignored)
├── scripts/
│   └── descargar_nomenclador.py
└── docs/
    └── metodologia.md
```

## Quickstart

### 1. Setup del entorno

```bash
make setup     # crea .venv e instala dependencias dev
# o manual:
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Datos requeridos

Necesitás tres cosas antes de correr el pipeline:

1. **Excel de causas anonimizado** en `data/raw/registro_ingreso_causas_2020_2026.xlsx`
   (este archivo NO va al repo).
2. **Diccionarios locales** (ya versionados) en `data/diccionarios/`.
3. **Nomenclador del Ministerio** — descargalo con:
   ```bash
   make nomenclador
   ```

### 3. Correr el pipeline

```bash
make pipeline
# o:
python -m src.pipeline
```

Salida esperada en `outputs/`:
- `causas_penal_juvenil_2020_2026_limpio_diccionarios.csv`
- `causas_penal_juvenil_2020_2026_limpio_diccionarios.xlsx`

### 4. Correr los tests

```bash
make test
```

Los tests usan fixtures sintéticas: no requieren el Excel real ni el
nomenclador descargado.

## Metodología

### 1. Protección de datos

El archivo original con nombres y apellidos no se usa en el repositorio.
El análisis se realiza sobre una copia anonimizada. La carátula original
no se publica. `data/raw/` está en `.gitignore`.

### 2. Normalización de delitos

Capa operativa basada en:

- limpieza textual;
- 45 reglas regex de corrección de typos frecuentes;
- diccionario local de equivalencias verificadas en el juzgado;
- flags jurídicos: tentativa, agravado, 5 sub-tipos de agravantes,
  agravante no especificado, posible delito múltiple.

Ejemplos de reglas locales aplicadas:

- `robo` → `robo simple`;
- `lesiones` → `lesiones leves` cuando no se especifica otra gravedad;
- `captacion` → `grooming` cuando pudo validarse en el sistema fuente;
- `agravado/calificado` sin detalle expreso queda como categoría agravada
  no especificada.

### 3. Cruce con nomenclador oficial

Se utilizó como referencia la [Codificación de delitos del Código Penal
Argentino del Ministerio de Justicia de la Nación](https://datos.jus.gob.ar/dataset/d4a7a48d-d5c5-48e3-b820-0bc308d57e3c/resource/1bb19ad9-1429-41ce-8ddf-e745a4aa2395/download/codificacion-delitos-codigo-penal-argentino-20191011.csv).
El cruce se modeló en tres estados principales:

- `match_univoco`;
- `match_ambiguo`;
- `sin_equivalencia_definida`.

Más dos estados auxiliares: `proceso_especial` (amparo, habeas corpus) y
`sin_delito_informado`. **No se fuerzan matches** cuando la fuente
administrativa o el nomenclador oficial no permiten una identificación
unívoca jurídicamente prudente.

### 4. Normalización de trámites

Los tipos de trámite se estandarizan con un diccionario local más reglas
residuales por operatoria del juzgado (elevación a juicio con/sin SJP,
declinatoria de competencia, etc.).

## Contrato del dataset final (28 columnas)

Validado en runtime con `pandera`:

| Columna | Tipo | Notas |
|---------|------|-------|
| `fecha_ingreso`, `anio`, `ipp` | datetime / int / str | Identificación temporal |
| `caratula_anonimizada`, `responsable` | str | Identificación administrativa |
| `tipo_tramite_raw` / `_limpio` / `_estandar` | str | Trámite en 3 capas |
| `delito_raw` / `_limpio` / `_sin_tentativa` / `_estandar` | str | Delito en 4 capas |
| `delito_informado` | enum: `si` / `no` | |
| `tentativa`, `es_proceso_especial` | bool | |
| `agravado_flag` + 5 sub-flags + `agravante_no_especificado` | bool | |
| `posible_delito_multiple` | bool | |
| `objetivo_ministerio`, `descripcion_ministerio`, `articulo_ministerio`, `codigo_delito_ministerio` | str | Cruce con nomenclador |
| `estado_match_ministerio` | enum: 6 valores | |

Si el output viola el contrato, el pipeline falla con `SchemaError`.

## Calidad del código

- **Tests**: 212 tests (unitarios + integración + dashboard + indicadores + resoluciones + cruce + tab gestión) con fixtures sintéticos.
- **CI**: lint + tests automáticos en cada push (GitHub Actions).
- **Lint/format**: `ruff` configurado en `pyproject.toml`.
- **Type hints**: en firmas públicas de `src/`.
- **Contratos de datos**: `pandera` valida el dataset final.
- **Validación de merges**: todos los `merge()` declaran `validate="m:1"`
  (regla DATA-02 del guideline interno).

## Dashboard

Dashboard Streamlit con visualización interactiva del dataset normalizado.
Sigue principios de *Storytelling with Data* (Knaflic): títulos narrativos
calculados sobre los filtros activos, un único color de acento, sin chart-junk.

### Cómo abrirlo

```bash
make dashboard
# o:
streamlit run dashboard/app.py
```

Requiere que el pipeline haya generado el CSV en `outputs/`. Si no existe,
el dashboard muestra instrucciones de cómo generarlo.

### Estructura

```
dashboard/
├── app.py                  ← entry point (sidebar + KPIs + 4 tabs)
├── theme.py                ← paleta + tema Altair (regla "Knaflic")
├── data.py                 ← carga del CSV con cache
├── components/
│   ├── filtros.py          ← sidebar: año / delito / estado del match
│   └── kpis.py             ← fila de 4 KPIs principales
└── tabs/
    ├── temporal.py         ← evolución anual + mensual
    ├── delitos.py          ← top 10 + evolución + flags jurídicos
    ├── tramites.py         ← top 10 + heatmap trámite × delito
    └── calidad.py          ← distribución del match + cola de revisión
```

### Tab "Calidad de datos"

Funciona como herramienta operativa, no solo informativa: produce una
**cola de revisión descargable** con causas que requieren atención humana
(sin cruce ministerial, posibles delitos múltiples, agravantes sin
especificar, delitos no informados). Permite enriquecer los diccionarios
locales de forma iterativa.

### Deploy en Streamlit Community Cloud

1. Push del repo a GitHub (manteniendo `data/raw/` afuera, ver `.gitignore`).
2. Subir manualmente el CSV anonimizado de `outputs/` al repo o a un bucket
   accesible (cuidando privacidad).
3. En [share.streamlit.io](https://share.streamlit.io), conectar el repo
   y apuntar a `dashboard/app.py`.
4. La app queda en una URL pública sin instalación por parte del equipo judicial.

## Indicadores mensuales del juzgado

El proyecto carga indicadores agregados provistos por el Departamento de
Estadística del Poder Judicial (formato long, una fila por mes-indicador).

```python
from src.indicadores import cargar_indicadores, pivot_a_wide, calcular_ratios

df = cargar_indicadores()                  # long: 1011 filas, 21 indicadores, 54 meses
wide = pivot_a_wide(df)                    # wide: una fila por mes
wide_ratios = calcular_ratios(wide)        # + tasa_resolucion_calculada, delta, ratio
```

El archivo se coloca en `data/external/indicadores_jgj3si.xlsx`. La carga
valida un schema pandera y, contra el archivo real, se ejecuta un test de
aceptación que verifica que la `tasa_de_resolucion` publicada coincide con
`finalizadas / ingresadas * 100` (tolerancia de redondeo <1.0). Si esa
identidad se rompe en una entrega futura, el test alerta.

Los slugs estables de los indicadores principales están en
`src.indicadores.SLUGS_PRINCIPALES` con constantes `SLUG_*` para uso en
código downstream sin depender del wording exacto del Excel.

## Resoluciones del juzgado

El proyecto carga el registro causa-por-causa de **resoluciones** desde tres
archivos con ciclos de vida distintos:

```
data/
├── backfill/              ← inmutable, checksums versionados
│   ├── resoluciones_2017_2019.xlsx       (RAW1, año solo)
│   ├── resoluciones_2020_2023a.xlsx      (RAW2, fecha completa)
│   └── checksums.json                    ← safety net
└── raw/                   ← se actualiza mensualmente
    └── resoluciones_2023b_2026.xlsx      (RAW3, vigente)
```

### Cómo correr

```bash
make pipeline-resoluciones      # produce outputs/resoluciones_2017_2026_consolidado.csv
```

El pipeline:
1. Verifica los checksums SHA-256 de los backfills (warning ruidoso si cambiaron).
2. Concatena los 3 archivos con `fuente_raw` como audit trail.
3. **Explota multi-resoluciones**: una entrada `"sobreseimiento, derivación"`
   se convierte en 2 filas, cada una con `multi_resolucion_origen=True`.
4. Clasifica cada IPP en una de **12 categorías** (`tipo_ipp`):
   estándar, oficio_exhorto, amparo, querella, habeas_corpus,
   faltas_contravenciones, apelacion_contravencional, habeas_data,
   dictamen_civil, externa, pp_malformada, nulo.
5. Normaliza el IPP a `ipp_canonico` (join key para cruce con causas).
6. Aplica el diccionario de resoluciones (424 tokens → 99 canónicas
   en 20 categorías).
7. Valida el output contra un schema pandera.

### Safety net de backfills

Los archivos en `data/backfill/` son históricos inmutables. Cualquier cambio
accidental (alguien sobrescribe un archivo por error) se detecta en la
próxima corrida del pipeline:

```bash
# Si modificás intencionalmente un backfill:
make refresh-checksums-backfill
git add data/backfill/checksums.json
git commit -m "data: actualización legítima de backfill XXX"
```

Si no se regeneran los checksums tras un cambio, el pipeline logea un
warning ruidoso (pero no falla, así sigue siendo idempotente).

### Schema del dataset consolidado (12 columnas)

| Columna | Tipo | Notas |
|---------|------|-------|
| `ipp_original`, `ipp_canonico` | str | El canónico es la clave de join con causas |
| `tipo_ipp` | enum | 12 categorías |
| `fecha_resolucion` | datetime \| NaT | NaT en RAW1 (solo año disponible) |
| `anio_resolucion` | Int64 | Siempre presente |
| `mes_resolucion` | Int64 \| NA | NA en RAW1 |
| `resolucion_raw` / `_canonica` / `categoria_resolucion` | str | 3 capas del diccionario |
| `multi_resolucion_origen` | bool | True si la fila salió de explotar multi |
| `requiere_validacion` | bool | Cola de revisión |
| `fuente_raw` | enum | `backfill_2017_2019` / `backfill_2020_2023a` / `raw_2023b_2026` |

## Cruce causas ↔ resoluciones

Por encima de los pipelines de causas (Iteración A) y resoluciones (Iteración B),
el módulo `src/cruce_causas_resoluciones.py` produce un dataset con un row
por causa enriquecido con métricas derivadas del join por IPP canónico.

### Cómo correr

```bash
make pipeline                       # produce outputs/causas_..._diccionarios.csv
make pipeline-resoluciones          # produce outputs/resoluciones_..._consolidado.csv
make cruce-causas-resoluciones      # produce outputs/causas_con_metricas_resoluciones.csv
```

El cruce hace LEFT JOIN desde causas (preserva las 1.267 filas) y agrega
14 columnas nuevas:

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `ipp_canonico`, `tipo_ipp` | str | Clasificación del IPP (12 categorías) |
| `n_resoluciones` | int | Cantidad total de resoluciones del IPP |
| `tiene_resoluciones` | bool | True si al menos 1 |
| `fecha_primera_resolucion`, `fecha_ultima_resolucion` | datetime, NaT | NaT si solo hay resoluciones de RAW1 |
| `dias_hasta_primera_resolucion`, `dias_proceso` | Int64, NA | NA si la métrica no es computable |
| `tiene_cierre_proceso`, `tiene_elevacion_juicio`, ... (7 flags) | bool | Una por categoría principal de resolución |
| `categorias_resolucion` | str | Concat de todas las categorías únicas (audit) |

### Deuda técnica documentada

El dataset de causas no tiene `ipp_canonico` ni `tipo_ipp` como columnas
nativas. El cruce los calcula localmente aplicando `normalizar_ipp` al
campo `ipp`. En una iteración futura, incorporar esas columnas al pipeline
de causas para que el cruce las consuma directamente.

### Auditoría del cruce

El cruce logea en cada corrida un reporte de auditoría con:
- Causas con/sin resoluciones registradas (esperado: ~77% con, ~23% sin)
- Resoluciones huérfanas (IPPs en resoluciones que no aparecen en causas).
  Esperable: son causas anteriores al período del registro (pre-2020).

## Dashboard: tab Gestión

El tab **Gestión** del dashboard Streamlit consume el output del cruce
(Iteración C) y muestra 4 visualizaciones de gestión judicial:

1. **KPIs**: % de causas con resoluciones, mediana de días hasta primera
   resolución, mediana de días de proceso total, % que termina en cierre
   de proceso.
2. **Cómo terminan las causas**: bar horizontal con la distribución
   porcentual por modalidad resolutiva (cierre, competencia, derivación,
   salida alternativa, etc).
3. **Cuánto tarda la primera resolución**: histograma con bins de tiempo
   (0-7 días, 8-30, 31-90, 91-180, 181-365, +1 año). Excluye causas con
   métrica temporal anómala (días negativos por reingresos o IPPs de
   otra jurisdicción).
4. **Tiempo de proceso por tipo de delito**: mediana de días por delito,
   top N por volumen, con umbral de 5 causas mínimas para descartar
   ruido estadístico.
5. **Cohorte por año de ingreso**: barras apiladas mostrando causas con
   vs sin resolución registrada, por año. Permite leer el efecto cohorte
   (causas recientes naturalmente tienen menor tasa de resolución).

Si el output del cruce no está disponible, el tab muestra un mensaje
informativo con los comandos necesarios para generarlo.

## Próximas etapas

- **Iteración B — Validación cruzada**: módulo `src/validacion.py` que
  compara "Causas Ingresadas" mensual del pipeline contra el área de
  Estadística y reporta divergencias.
- **Iteración C — Tab "Gestión" en el dashboard**: visualización temporal de
  ingresos vs finalizaciones, tasa de resolución, productividad.
- **Resoluciones causa-por-causa** (pendiente del juzgado): permitirá
  cruces detallados delito × resolución y métricas de duración procesal.
- **Estadísticas provinciales** (pendiente de formato): si están en CSV
  abierto, integración directa; si en PDF, evaluación caso por caso.

## Stack

- Python 3.11+
- pandas, numpy, openpyxl
- pandera (contratos de datos)
- pytest, ruff (calidad)
- Streamlit + Altair (dashboard)
- Power BI (compatibilidad con CSV existente)

## Nota sobre privacidad

Este repositorio no publica la base original identificada. Cualquier muestra
de datos incluida debe estar previamente anonimizada y revisada para evitar
reidentificación directa o indirecta. `data/raw/` permanece en `.gitignore`
sin excepciones.
