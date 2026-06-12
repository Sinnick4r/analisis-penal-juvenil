# descarga el nomenclador oficial de delitos del Ministerio de Justicia.

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config
from src.logging_setup import get_logger

logger = get_logger(__name__)


def descargar(destino: Path, url: str, force: bool = False) -> Path:
    if destino.exists() and not force:
        logger.info("Ya existe %s (usar --force para sobrescribir)", destino)
        return destino

    destino.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Descargando %s → %s", url, destino)
    urllib.request.urlretrieve(url, destino)
    logger.info("Descarga completa: %d bytes", destino.stat().st_size)
    return destino


def main() -> int:
    parser = argparse.ArgumentParser(description="Descarga el nomenclador oficial del Ministerio.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Sobrescribe el archivo si ya existe.",
    )
    args = parser.parse_args()

    try:
        descargar(config.MINISTERIO_CSV, config.MINISTERIO_URL, args.force)
    except Exception:
        logger.exception("Error descargando el nomenclador")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
