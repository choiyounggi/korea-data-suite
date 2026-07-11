"""Standalone sync entrypoint — the single writer, run as its own process by a
scheduled launchd job (not inside the API server). Keeping the heavy daily
ingest out of the API process means it never competes with request handling for
the GIL, and lets the API run multiple read-only workers.

    uv run python scripts/sync.py
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.apis.realestate.sync import sync_realestate  # noqa: E402
from app.core.scheduler import sync_holidays  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("kds.sync")


def main() -> int:
    logger.info("sync start")
    holidays = sync_holidays()
    realestate = sync_realestate()
    logger.info("sync done: holidays=%s realestate=%s", holidays, realestate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
