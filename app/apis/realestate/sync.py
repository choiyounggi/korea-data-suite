import datetime
import logging
import os

from app.apis.realestate import molit, regions, store
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# (dataset key, property_type, "sale"|"rent", molit fetch-fn name). "rent" is
# split into jeonse / monthly_rent partitions by each row's own trade_type.
# The fetch fn is named (not referenced) so it resolves via getattr at call time.
DATASETS = [
    ("apt_trade", "apartment", "sale", "fetch_apt_trades"),
    ("apt_rent", "apartment", "rent", "fetch_apt_rents"),
    ("offi_trade", "officetel", "sale", "fetch_offi_trades"),
    ("offi_rent", "officetel", "rent", "fetch_offi_rents"),
    ("land_trade", "land", "sale", "fetch_land_trades"),
]


def _target_datasets():
    raw = os.environ.get("KDS_RE_DATASETS", "")
    if not raw.strip():
        return DATASETS
    wanted = {k.strip() for k in raw.split(",") if k.strip()}
    known = {d[0] for d in DATASETS}
    for k in sorted(wanted - known):
        logger.warning("skipping unknown dataset key in KDS_RE_DATASETS: %s", k)
    return [d for d in DATASETS if d[0] in wanted]


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


def ingest_slice(db: str, key: str, dataset, region: str, month: str) -> int:
    """Fetch + partition-replace one (dataset, region, month). Shared by the daily
    scheduler and the backfill CLI so both use one ingest path.

    Empty fetch (failure or genuinely no deals) skips the replace, so a transient
    API failure never wipes an existing partition. For a successful rent fetch,
    each trade_type is replaced separately (an empty sublist genuinely means zero
    of that type that month, so its partition is correctly emptied)."""
    _key, property_type, kind, fetch_name = dataset
    fetch = getattr(molit, fetch_name)  # late-bound so tests can monkeypatch
    rows = fetch(region, month, key)
    if not rows:
        return 0
    if kind == "sale":
        return store.replace_partition(db, property_type, "sale", region, month, rows)
    # rent → jeonse / monthly_rent. An empty sub-list skips its replace (same
    # empty-guard as sale): a fetch that yields only jeonse must not wipe an
    # existing monthly partition (and vice-versa). _fetch_pages is all-or-nothing
    # (partial pages → []), so a non-empty side is a complete slice for that type.
    jeonse = [t for t in rows if t.trade_type == "jeonse"]
    monthly = [t for t in rows if t.trade_type == "monthly_rent"]
    n = 0
    if jeonse:
        n += store.replace_partition(db, property_type, "jeonse", region, month, jeonse)
    if monthly:
        n += store.replace_partition(db, property_type, "monthly_rent", region, month, monthly)
    return n


def sync_realestate() -> int:
    settings = get_settings()
    if not settings.data_go_kr_key:
        logger.info("KDS_DATA_GO_KR_KEY not set — skipping MOLIT sync")
        return 0
    store.init_db(settings.db_path)
    months = _target_months(datetime.date.today())
    total = 0
    for dataset in _target_datasets():
        for region in _target_regions():
            for month in months:
                try:
                    total += ingest_slice(settings.db_path, settings.data_go_kr_key, dataset, region, month)
                except Exception as exc:  # noqa: BLE001 — one slice must not stop the run
                    logger.warning(
                        "MOLIT sync failed for dataset=%s region=%s month=%s: %s",
                        dataset[0], region, month, exc,
                    )
    logger.info("MOLIT sync upserted %s rows", total)
    return total
