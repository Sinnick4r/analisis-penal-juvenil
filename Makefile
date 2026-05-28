# Makefile: comandos de conveniencia para el pipeline y el dashboard.
# Uso: make <target>
#
# Detecta automáticamente el Python a usar:
# - .venv/bin/python si existe (Linux/macOS)
# - .venv/Scripts/python.exe si existe (Windows + Git Bash)
# - el `python` del PATH si no hay venv

ifneq (,$(wildcard .venv/bin/python))
    PYTHON := .venv/bin/python
else ifneq (,$(wildcard .venv/Scripts/python.exe))
    PYTHON := .venv/Scripts/python.exe
else
    PYTHON := python
endif

.PHONY: help setup install pipeline pipeline-resoluciones cruce-causas-resoluciones \
        refresh-checksums-backfill test test-cov \
        lint format dashboard clean nomenclador

help:
	@echo "Targets disponibles:"
	@echo "  setup                          crea .venv e instala deps dev + dashboard"
	@echo "  install                        instala el paquete en modo editable + extras"
	@echo "  nomenclador                    descarga el nomenclador del Ministerio"
	@echo "  pipeline                       corre el ETL de causas (registro de ingreso)"
	@echo "  pipeline-resoluciones          corre el ETL de resoluciones (3 RAWs + diccionario)"
	@echo "  cruce-causas-resoluciones      cruza causas con resoluciones, produce métricas por causa"
	@echo "  refresh-checksums-backfill     regenera checksums de archivos en data/backfill/"
	@echo "  dashboard                      abre el dashboard Streamlit"
	@echo "  test                           corre la suite de tests con pytest"
	@echo "  test-cov                       corre tests con reporte de cobertura"
	@echo "  lint                           valida estilo con ruff"
	@echo "  format                         aplica ruff format y autofix"
	@echo "  clean                          limpia caches"

setup:
	python -m venv .venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev,dashboard]"

install:
	$(PYTHON) -m pip install -e ".[dev,dashboard]"

nomenclador:
	$(PYTHON) scripts/descargar_nomenclador.py

pipeline:
	$(PYTHON) -m src.pipeline

pipeline-resoluciones:
	$(PYTHON) -m src.resoluciones

cruce-causas-resoluciones:
	$(PYTHON) -m src.cruce_causas_resoluciones

refresh-checksums-backfill:
	$(PYTHON) scripts/refresh_checksums.py

dashboard:
	$(PYTHON) -m streamlit run dashboard/app.py

test:
	$(PYTHON) -m pytest tests/

test-cov:
	$(PYTHON) -m pytest tests/ --cov=src --cov=dashboard --cov-report=term-missing

lint:
	$(PYTHON) -m ruff check src/ dashboard/ tests/ scripts/

format:
	$(PYTHON) -m ruff format src/ dashboard/ tests/ scripts/
	$(PYTHON) -m ruff check --fix src/ dashboard/ tests/ scripts/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
