# Analítica de causas del fuero penal juvenil (2020-2026)
 
Pipeline reproducible que convierte una planilla administrativa cargada a mano por
varios operadores en un dataset analítico versionado, anonimizado y validado.
Limpia el texto, normaliza delitos y trámites con diccionarios locales, los cruza
con el nomenclador oficial del Ministerio de Justicia de la Republica Argentina 
y exporta tablas listas para BI.
 
## Qué resuelve
 
Los registros de ingreso de causas tienen typos, criterios de carga distintos por
operador y delitos escritos en lenguaje libre. Eso hace imposible cualquier análisis
de gestión confiable. El proyecto produce un dataset estable (28 columnas, contrato
validado en runtime) sobre el que sí se puede medir volumen, tipo de delito, trámite,
tiempos procesales y resoluciones.
 
## Estructura
 
`src/` pipeline (limpieza, normalización jurídica, cruces) · `dashboard/` Streamlit + Altair ·
`tests/` fixtures sintéticas · `data/` (`raw/` gitignored, `diccionarios/` y `backfill/` versionados) ·
`docs/` metodología y schema completo.
 
## Quickstart
 
```bash
make setup          # crea .venv e instala dependencias dev
make nomenclador    # descarga el nomenclador del Ministerio
make pipeline       # genera el dataset en outputs/
make test           # corre los tests (no requieren datos reales)
make dashboard      # abre el dashboard Streamlit
```
 
Antes de `make pipeline` necesitás el Excel anonimizado de causas en
`data/raw/registro_ingreso_causas_2020_2026.xlsx` (ese archivo no va al repo).
Los diccionarios locales ya están versionados en `data/diccionarios/`.

 
Salida principal en `outputs/`:
`causas_penal_juvenil_2020_2026_limpio_diccionarios.csv` (y su `.xlsx`).
 
## Stack
 
Python 3.11+ · pandas / numpy / openpyxl · pandera (contratos de datos) ·
pytest / ruff (calidad) · Streamlit + Altair (dashboard) · compatible con Power BI.
 
## Privacidad
 
El repo no publica la base original identificada. El analisis corre sobre una copia
anonimizada; `data/raw/` permanece en `.gitignore` sin excepciones. Cualquier muestra
de datos incluida tiene que estar anonimizada y revisada contra reidentificación.
 
## Documentación técnica
 
Schema completo del dataset, metodología de normalización, pipeline de resoluciones,
cruce causas-resoluciones, tabs del dashboard y deploy en `docs/DOCUMENTACION.md`.
