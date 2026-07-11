"""Backfill MOLIT real-estate transactions for a past month range.

Usage:
    uv run python scripts/backfill.py --from 2025-01 --to 2025-12 \
        [--regions 11680,11650] [--datasets apt_trade,apt_rent] [--yes]
"""
import argparse
import sys
import time
from pathlib import Path

# run as `python scripts/backfill.py` puts scripts/ on sys.path, not the repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.apis.realestate import regions, store, sync  # noqa: E402 — after sys.path fix
from app.core.config import get_settings  # noqa: E402

CALL_SLEEP_SECONDS = 0.2  # be polite to the gateway
DAILY_QUOTA = 10000


def _parse_ym(s: str) -> tuple[int, int] | None:
    """Parse 'YYYY-M' / 'YYYY-MM' → (year, month), or None if malformed / month out of 1-12."""
    parts = s.split("-")
    if len(parts) != 2:
        return None
    try:
        y, m = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (1 <= m <= 12) or not (2000 <= y <= 2100):
        return None
    return (y, m)


def _months(start: tuple[int, int], end: tuple[int, int]) -> list[str]:
    out: list[str] = []
    y, m = start
    while (y, m) <= end:
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Backfill MOLIT real-estate transactions.")
    p.add_argument("--from", dest="start", required=True, help="start month, YYYY-MM")
    p.add_argument("--to", dest="end", required=True, help="end month (inclusive), YYYY-MM")
    p.add_argument("--regions", default="", help="comma LAWD codes; default all seeded regions")
    p.add_argument("--datasets", default="", help="comma dataset keys; default all datasets")
    p.add_argument("--yes", action="store_true", help="skip the call-count confirmation")
    args = p.parse_args(argv)

    start, end = _parse_ym(args.start), _parse_ym(args.end)
    if start is None or end is None:
        print("error: --from/--to must be YYYY-MM with month 01-12", file=sys.stderr)
        return 2
    if start > end:
        print(f"error: --from ({args.start}) must be <= --to ({args.end})", file=sys.stderr)
        return 2

    months = _months(start, end)
    region_codes = [c.strip() for c in args.regions.split(",") if c.strip()] or sorted(regions.REGIONS.keys())
    region_codes = [c for c in region_codes if regions.is_valid_region(c)]
    if args.datasets.strip():
        wanted = {k.strip() for k in args.datasets.split(",") if k.strip()}
        datasets = [d for d in sync.DATASETS if d[0] in wanted]
    else:
        datasets = list(sync.DATASETS)

    if not region_codes or not datasets:
        print("error: no valid regions or datasets selected", file=sys.stderr)
        return 2

    settings = get_settings()
    if not settings.data_go_kr_key:
        print("error: KDS_DATA_GO_KR_KEY not set (put it in .env)", file=sys.stderr)
        return 2

    slices = len(datasets) * len(region_codes) * len(months)
    print(
        f"planned fetch slices: {slices} "
        f"({len(datasets)} datasets x {len(region_codes)} regions x {len(months)} months); "
        f"each slice is 1+ paginated API calls"
    )
    if slices > DAILY_QUOTA and not args.yes:
        reply = input(f"exceeds {DAILY_QUOTA}/day dev quota (and each may paginate) — continue? [y/N] ")
        if reply.strip().lower() != "y":
            print("aborted.")
            return 0

    store.init_db(settings.db_path)
    inserted = 0
    for dataset in datasets:
        for region in region_codes:
            for month in months:
                try:
                    n = sync.ingest_slice(settings.db_path, settings.data_go_kr_key, dataset, region, month)
                    if n:
                        inserted += n
                        print(f"{dataset[0]} {region} {month}: +{n}")
                except Exception as exc:  # noqa: BLE001 — one slice must not stop the backfill
                    print(f"{dataset[0]} {region} {month}: FAILED ({type(exc).__name__})", file=sys.stderr)
                time.sleep(CALL_SLEEP_SECONDS)
    print(f"done. inserted {inserted} rows across {slices} slices.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
