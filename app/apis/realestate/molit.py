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
    "apt_rent": "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent",
    "offi_trade": "https://apis.data.go.kr/1613000/RTMSDataSvcOffiTrade/getRTMSDataSvcOffiTrade",
    "offi_rent": "https://apis.data.go.kr/1613000/RTMSDataSvcOffiRent/getRTMSDataSvcOffiRent",
    "land_trade": "https://apis.data.go.kr/1613000/RTMSDataSvcLandTrade/getRTMSDataSvcLandTrade",
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


def _normalize_apt_trade(raw: RawAptTrade, region_code: str) -> Transaction | None:
    if raw.cdealType:  # cancelled deal
        return None
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


def _fetch_pages(
    dataset_key: str, region_code: str, deal_ym: str, service_key: str, retries: int = 3
) -> list[dict]:
    """Fetch every page of one (dataset, region, month) as raw {tag: text} dicts.

    Returns [] on empty key or any fetch failure (so a caller skips the partition
    rather than overwriting good data with a partial/empty result)."""
    if not service_key:
        return []
    deal_ymd = deal_ym.replace("-", "")
    url = BASE_URLS[dataset_key]
    raw_items: list[dict] = []
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
            raw_items.extend(items)
            if page_no * NUM_OF_ROWS >= total:
                break
            page_no += 1
    except Exception as exc:  # noqa: BLE001 — total fetch failure → empty, log cause
        logger.warning(
            "MOLIT %s fetch failed for region=%s ym=%s: %s",
            dataset_key, region_code, deal_ym, redact(str(exc)),
        )
        return []
    return raw_items


def _collect(dataset_key, region_code, deal_ym, service_key, retries, model, normalize):
    """Fetch → per-row validate+normalize, skipping (not discarding all on) bad rows."""
    out: list[Transaction] = []
    for raw_dict in _fetch_pages(dataset_key, region_code, deal_ym, service_key, retries):
        try:
            raw = model.model_validate(raw_dict)
            tx = normalize(raw, region_code)
            if tx is None:  # cancelled deal
                continue
        except Exception as exc:  # noqa: BLE001 — skip one bad row, keep the rest
            logger.warning("skipping unparseable MOLIT %s item: %s", dataset_key, exc)
            continue
        out.append(tx)
    return out


# ── apartment sale ──
def fetch_apt_trades(
    region_code: str, deal_ym: str, service_key: str, retries: int = 3
) -> list[Transaction]:
    return _collect(
        "apt_trade", region_code, deal_ym, service_key, retries,
        RawAptTrade, _normalize_apt_trade,
    )


# ── apartment rent (jeonse / monthly) ──
class RawAptRent(BaseModel):
    umdNm: str | None = None
    aptNm: str | None = None
    excluUseAr: float | None = None
    dealYear: int
    dealMonth: int
    dealDay: int
    deposit: str
    monthlyRent: str
    floor: int | None = None
    buildYear: int | None = None


def _normalize_rent(
    raw, region_code: str, property_type: str, name: str | None, area: float | None
) -> Transaction:
    monthly_won = _parse_amount_manwon(raw.monthlyRent)  # rent is also in 만원
    if monthly_won == 0:
        trade_type, monthly_rent_won = "jeonse", None
    else:
        trade_type, monthly_rent_won = "monthly_rent", monthly_won
    return Transaction(
        property_type=property_type,
        trade_type=trade_type,
        region_code=region_code,
        neighborhood=raw.umdNm,
        building_name=name,
        traded_on=f"{raw.dealYear:04d}-{raw.dealMonth:02d}-{raw.dealDay:02d}",
        deposit_won=_parse_amount_manwon(raw.deposit),
        monthly_rent_won=monthly_rent_won,
        area_m2=area,
        floor=raw.floor,
        built_year=raw.buildYear,
    )


def fetch_apt_rents(
    region_code: str, deal_ym: str, service_key: str, retries: int = 3
) -> list[Transaction]:
    return _collect(
        "apt_rent", region_code, deal_ym, service_key, retries,
        RawAptRent, lambda r, rc: _normalize_rent(r, rc, "apartment", r.aptNm, r.excluUseAr),
    )


# ── officetel sale / rent ──
class RawOffiTrade(BaseModel):
    umdNm: str | None = None
    offiNm: str | None = None
    excluUseAr: float | None = None
    dealYear: int
    dealMonth: int
    dealDay: int
    dealAmount: str
    floor: int | None = None
    buildYear: int | None = None
    cdealType: str | None = None


def _normalize_offi_trade(raw: RawOffiTrade, region_code: str) -> Transaction | None:
    if raw.cdealType:
        return None
    return Transaction(
        property_type="officetel",
        trade_type="sale",
        region_code=region_code,
        neighborhood=raw.umdNm,
        building_name=raw.offiNm,
        traded_on=f"{raw.dealYear:04d}-{raw.dealMonth:02d}-{raw.dealDay:02d}",
        price_won=_parse_amount_manwon(raw.dealAmount),
        area_m2=raw.excluUseAr,
        floor=raw.floor,
        built_year=raw.buildYear,
    )


class RawOffiRent(BaseModel):
    umdNm: str | None = None
    offiNm: str | None = None
    excluUseAr: float | None = None
    dealYear: int
    dealMonth: int
    dealDay: int
    deposit: str
    monthlyRent: str
    floor: int | None = None
    buildYear: int | None = None


def fetch_offi_trades(
    region_code: str, deal_ym: str, service_key: str, retries: int = 3
) -> list[Transaction]:
    return _collect(
        "offi_trade", region_code, deal_ym, service_key, retries,
        RawOffiTrade, _normalize_offi_trade,
    )


def fetch_offi_rents(
    region_code: str, deal_ym: str, service_key: str, retries: int = 3
) -> list[Transaction]:
    return _collect(
        "offi_rent", region_code, deal_ym, service_key, retries,
        RawOffiRent, lambda r, rc: _normalize_rent(r, rc, "officetel", r.offiNm, r.excluUseAr),
    )


# ── land sale ──
class RawLandTrade(BaseModel):
    umdNm: str | None = None
    dealYear: int
    dealMonth: int
    dealDay: int
    dealAmount: str
    dealArea: float | None = None
    cdealType: str | None = None


def _normalize_land_trade(raw: RawLandTrade, region_code: str) -> Transaction | None:
    if raw.cdealType:
        return None
    return Transaction(
        property_type="land",
        trade_type="sale",
        region_code=region_code,
        neighborhood=raw.umdNm,
        building_name=None,
        traded_on=f"{raw.dealYear:04d}-{raw.dealMonth:02d}-{raw.dealDay:02d}",
        price_won=_parse_amount_manwon(raw.dealAmount),
        area_m2=raw.dealArea,
        floor=None,
        built_year=None,
    )


def fetch_land_trades(
    region_code: str, deal_ym: str, service_key: str, retries: int = 3
) -> list[Transaction]:
    return _collect(
        "land_trade", region_code, deal_ym, service_key, retries,
        RawLandTrade, _normalize_land_trade,
    )
