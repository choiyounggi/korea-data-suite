import logging
import random
import time
import xml.etree.ElementTree as ET

import httpx
from pydantic import BaseModel

from app.apis.realestate.models import Transaction
from app.core.logsafe import redact

logger = logging.getLogger(__name__)

BASE_URLS = {
    "apt_trade": "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade",
}

NUM_OF_ROWS = 1000
MAX_PAGES = 30


class RawAptTrade(BaseModel):
    sggCd: str
    umdNm: str | None = None
    aptNm: str | None = None
    jeonyongAr: float | None = None
    dealYear: int
    dealMonth: int
    dealDay: int
    dealAmount: str
    floor: int | None = None
    buildYear: int | None = None
    cdealType: str | None = None


def _parse_amount_manwon(raw: str) -> int:
    """MOLIT amounts are in 만원 (10k KRW) with thousands commas → integer won."""
    cleaned = raw.replace(",", "").replace(" ", "")
    value = int(cleaned)
    if value < 0:
        raise ValueError(f"negative amount: {raw!r}")
    return value * 10000


def _item_to_dict(item: ET.Element) -> dict:
    return {child.tag: (child.text or "").strip() for child in item}


def _fetch_one_page(url: str, params: dict, retries: int) -> tuple[list[dict], int]:
    """One page with retry/backoff. 4xx raises immediately (no retry); exhausted
    attempts raise RuntimeError. Returns (raw item dicts, totalCount)."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = httpx.get(url, params=params, timeout=10.0)
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
            result_code = root.findtext("./header/resultCode")
            if result_code != "000":
                raise RuntimeError(f"MOLIT resultCode={result_code}")
            items = [_item_to_dict(it) for it in root.findall("./body/items/item")]
            total = int(root.findtext("./body/totalCount") or "0")
            return items, total
        except httpx.HTTPStatusError as exc:
            if 400 <= exc.response.status_code < 500:
                raise  # client error — the same request will fail again
            last_error = exc
        except Exception as exc:  # noqa: BLE001 — retry transient, raise after budget
            last_error = exc
        if attempt < retries:
            time.sleep(random.uniform(0, min(30, 2**attempt)))
    raise RuntimeError(f"exhausted {retries} attempts: {last_error}")


def _normalize_apt_trade(raw: RawAptTrade, region_code: str) -> Transaction:
    return Transaction(
        property_type="apartment",
        trade_type="sale",
        region_code=region_code,
        neighborhood=raw.umdNm,
        building_name=raw.aptNm,
        traded_on=f"{raw.dealYear:04d}-{raw.dealMonth:02d}-{raw.dealDay:02d}",
        price_won=_parse_amount_manwon(raw.dealAmount),
        area_m2=raw.jeonyongAr,
        floor=raw.floor,
        built_year=raw.buildYear,
    )


def fetch_apt_trades(
    region_code: str, deal_ym: str, service_key: str, retries: int = 3
) -> list[Transaction]:
    """Fetch all apartment-sale transactions for one (region, month).

    Returns [] on any fetch failure (so a caller replacing a partition skips it
    rather than overwriting good data with a partial/empty result)."""
    if not service_key:
        return []
    deal_ymd = deal_ym.replace("-", "")
    url = BASE_URLS["apt_trade"]
    out: list[Transaction] = []
    page_no = 1
    try:
        while page_no <= MAX_PAGES:
            params = {
                "serviceKey": service_key,
                "LAWD_CD": region_code,
                "DEAL_YMD": deal_ymd,
                "pageNo": str(page_no),
                "numOfRows": str(NUM_OF_ROWS),
            }
            items, total = _fetch_one_page(url, params, retries)
            for raw_dict in items:
                try:
                    raw = RawAptTrade.model_validate(raw_dict)
                    if raw.cdealType:  # cancelled deal
                        continue
                    tx = _normalize_apt_trade(raw, region_code)  # amount parse may raise
                except Exception as exc:  # noqa: BLE001 — skip one bad row, keep the rest
                    logger.warning("skipping unparseable MOLIT apt_trade item: %s", exc)
                    continue
                out.append(tx)
            if page_no * NUM_OF_ROWS >= total:
                break
            page_no += 1
    except Exception as exc:  # noqa: BLE001 — total fetch failure → empty, log cause
        logger.warning(
            "MOLIT apt_trade fetch failed for region=%s ym=%s: %s",
            region_code, deal_ym, redact(str(exc)),
        )
        return []
    return out
