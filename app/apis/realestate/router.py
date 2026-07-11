import base64
import datetime

from fastapi import APIRouter, HTTPException, Query

from app.apis.realestate import regions, store
from app.core.config import get_settings

router = APIRouter(prefix="/v1/realestate", tags=["realestate"])

MAX_LIMIT = 100


def _encode_cursor(traded_on: str, row_id: int) -> str:
    return base64.urlsafe_b64encode(f"{traded_on}:{row_id}".encode()).decode()


def _decode_cursor(cursor: str) -> tuple[str, int]:
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode()).decode()
        traded_on, id_str = decoded.rsplit(":", 1)
        row_id = int(id_str)
        if not 0 <= row_id < 2**63:  # SQLite INTEGER is signed 64-bit; larger overflows on bind
            raise ValueError("cursor id out of range")
        datetime.date.fromisoformat(traded_on)  # reject non-date sort keys
    except Exception:  # noqa: BLE001 — any malformed cursor is a 400
        raise HTTPException(status_code=400, detail="invalid_cursor")
    return traded_on, row_id


@router.get("/transactions")
def list_transactions(
    region: str,
    property_type: str | None = Query(default=None, pattern="^(apartment|officetel|land)$"),
    trade_type: str | None = Query(default=None, pattern="^(sale|jeonse|monthly_rent)$"),
    date_from: datetime.date | None = None,
    date_to: datetime.date | None = None,
    limit: int = Query(default=50, ge=1),
    cursor: str | None = None,
) -> dict:
    if not regions.is_valid_region(region):
        raise HTTPException(
            status_code=422,
            detail=f"unknown region_code: {region!r} (e.g. 11680 for Gangnam-gu; see /v1/realestate/regions)",
        )
    applied_limit = min(limit, MAX_LIMIT)
    parsed_cursor = _decode_cursor(cursor) if cursor else None
    # fetch one extra row to decide has_more without a count query
    rows = store.query_transactions(
        get_settings().db_path,
        region,
        property_type,
        trade_type,
        date_from.isoformat() if date_from else None,
        date_to.isoformat() if date_to else None,
        applied_limit + 1,
        parsed_cursor,
    )
    has_more = len(rows) > applied_limit
    rows = rows[:applied_limit]
    next_cursor = (
        _encode_cursor(rows[-1]["traded_on"], rows[-1]["id"]) if has_more and rows else None
    )
    data = [{k: v for k, v in r.items() if k != "id"} for r in rows]
    return {"data": data, "limit": applied_limit, "has_more": has_more, "next_cursor": next_cursor}


@router.get("/regions")
def list_regions() -> dict:
    items = [
        {"code": code, "name_ko": info["name_ko"], "name_en": info["name_en"]}
        for code, info in sorted(regions.REGIONS.items())
    ]
    return {"count": len(items), "regions": items}
