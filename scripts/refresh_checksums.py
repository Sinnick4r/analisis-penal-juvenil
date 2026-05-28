'''genera o regenera `data/backfill/checksums.json`

es para detectar  cambios en los backfills raw inmutables
'''
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config  # noqa: E402
from src.logging_setup import get_logger  # noqa: E402

logger = get_logger(__name__)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()


def main() -> int:
    if not config.BACKFILL_DIR.exists():
        logger.error("No existe el directorio de backfill: %s", config.BACKFILL_DIR)
        return 1

    archivos = sorted(p for p in config.BACKFILL_DIR.glob("*.xlsx") if p.is_file())
    if not archivos:
        logger.warning("No hay archivos .xlsx en %s", config.BACKFILL_DIR)
        return 0

    ahora = datetime.now(timezone.utc).isoformat()
    registro: dict[str, dict[str, object]] = {}
    for path in archivos:
        registro[path.name] = {
            "sha256": sha256(path),
            "size_bytes": path.stat().st_size,
            "generated_at": ahora,
        }
        logger.info("Registrado %s (%d bytes)", path.name, path.stat().st_size)

    config.BACKFILL_CHECKSUMS.write_text(
        json.dumps(registro, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info("Checksums guardados en %s", config.BACKFILL_CHECKSUMS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
