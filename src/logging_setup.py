# Config de logging estructurado para el pipeline

from __future__ import annotations

import logging

from src import config


def configurar_logging(nivel: int | None = None) -> None:

    root = logging.getLogger()
    if root.handlers: 
        return

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(config.LOG_FORMAT))
    root.addHandler(handler)
    root.setLevel(nivel if nivel is not None else config.LOG_LEVEL)


def get_logger(name: str) -> logging.Logger:

    configurar_logging()
    return logging.getLogger(name)
