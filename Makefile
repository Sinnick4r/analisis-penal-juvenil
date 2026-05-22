# Makefile: comandos de conveniencia para el pipeline y el dashboard.
# Uso: make <target>
#
# Detecta automáticamente el Python a usar:
# - .venv/bin/python si existe (Linux/macOS)
# - .venv/Scripts/python.exe si existe (Windows + Git Bash)
# - el `python` del PATH si no hay venv
#
# Esto evita el problema de "hay que activar el venv primero" en Linux/macOS.

ifneq (,$(wildcard .venv/bin/python))
    PYTHON := .venv/bin/python
else ifneq (,$(wildcard .venv/Scripts/python.exe))
    PYTHON := .venv/Scripts/python.exe
else
    PYTHON := python
endif

.PHONY: help setup install pipeline test test-cov lint format dashboard clean nomenclador

help:
	@echo "Targets disponibles:"
	@echo "  setup        crea .venv e instala dependencias dev + dashboard"
	@echo "  install      instala el paquete en modo editable + extras dev/dashboard"
	@echo "  nomenclador  descarga el nomenclador oficial del Ministerio"
	@echo "  pipeline     corre el ETL completo (requiere Excel en data/raw/)"
	@echo "  dashboard    abre el dashboard Streamlit en el browser"
	@echo "  test         corre la suite de tests con pytest"
	@echo "  test-cov     corre tests con reporte de cobertura"
	@echo "  lint         valida estilo con ruff (no modifica)"
	@echo "  format       aplica ruff format y autofix"
	@echo "  clean        limpia caches y archivos temporales"

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

dashboard:
	$(PYTHON) -m streamlit run dashboard/app.py

test:
	$(PYTHON) -m pytest tests/

test-cov:
	$(PYTHON) -m pytest tests/ --cov=src --cov=dashboard --cov-report=term-missing

lint:
	$(PYTHON) -m ruff check src/ dashboard/ tests/

format:
	$(PYTHON) -m ruff format src/ dashboard/ tests/
	$(PYTHON) -m ruff check --fix src/ dashboard/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
