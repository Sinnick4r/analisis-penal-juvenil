"""Setup de logging estructurado para el pipeline.

Cumple LOG-01 del guideline: logging en bordes operativos con
timestamp, nivel, componente y outcome.
"""
from __future__ import annotations

import logging

from src import config


def configurar_logging(nivel: int | None = None) -> None:
    """Configura el root logger del pipeline.

    Idempotente: si ya hay handlers configurados, no agrega duplicados.

    Args:
        nivel: nivel de logging. Si es None, usa el de `config.LOG_LEVEL`.
    """
    root = logging.getLogger()
    if root.handlers:  # ya configurado
        return

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(config.LOG_FORMAT))
    root.addHandler(handler)
    root.setLevel(nivel if nivel is not None else config.LOG_LEVEL)


def get_logger(name: str) -> logging.Logger:
    """Devuelve un logger nombrado, asegurando el setup global."""
    configurar_logging()
    return logging.getLogger(name)
