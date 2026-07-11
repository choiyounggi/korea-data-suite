import datetime
import logging
import os

from app.apis.realestate import molit, regions, store
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _target_months(today: datetime.date) -> list[str]:
    """Current month + previous month, as 'YYYY-MM' (re-ingested daily)."""
    current = f"{today.year:04d}-{today.month:02d}"
    prev_last = today.replace(day=1) - datetime.timedelta(days=1)
    previous = f"{prev_last.year:04d}-{prev_last.month:02d}"
    return [current, previous]


def _target_regions() -> list[str]:
    raw = os.environ.get("KDS_RE_REGIONS", "")
    if raw.strip():
        codes = [c.strip() for c in raw.split(",") if c.strip()]
    else:
        codes = sorted(regions.REGIONS.keys())
    valid: list[str] = []
    for c in codes:
        if regions.is_valid_region(c):
            valid.append(c)
        else:
            logger.warning("skipping unknown region_code in KDS_RE_REGIONS: %s", c)
    return valid


def sync_realestate() -> int:
    settings = get_settings()
    if not settings.data_go_kr_key:
        logger.info("KDS_DATA_GO_KR_KEY not set — skipping MOLIT sync")
        return 0
    store.init_db(settings.db_path)
    months = _target_months(datetime.date.today())
    total = 0
    for region in _target_regions():
        for month in months:
            try:
                rows = molit.fetch_apt_trades(region, month, settings.data_go_kr_key)
                # empty = fetch failure or genuinely no deals; either way don't wipe
                # the existing partition with an empty replace
                if rows:
                    total += store.replace_partition(
                        settings.db_path, "apartment", "sale", region, month, rows
                    )
            except Exception as exc:  # noqa: BLE001 — one region must not stop the run
                logger.warning(
                    "MOLIT sync failed for region=%s month=%s: %s", region, month, exc
                )
    logger.info("MOLIT sync upserted %s rows", total)
    return total
