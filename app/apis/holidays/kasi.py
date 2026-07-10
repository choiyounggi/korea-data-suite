import logging
import time

import httpx

from app.apis.holidays.models import Holiday

logger = logging.getLogger(__name__)

BASE_URL = "http://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo"

NAME_EN = {
    "1월1일": "New Year's Day",
    "신정": "New Year's Day",
    "설날": "Seollal (Korean New Year)",
    "삼일절": "Independence Movement Day",
    "어린이날": "Children's Day",
    "부처님오신날": "Buddha's Birthday",
    "석가탄신일": "Buddha's Birthday",
    "현충일": "Memorial Day",
    "광복절": "Liberation Day",
    "추석": "Chuseok (Korean Thanksgiving)",
    "개천절": "National Foundation Day",
    "한글날": "Hangeul Day",
    "기독탄신일": "Christmas Day",
    "성탄절": "Christmas Day",
}


def _classify(name: str) -> str:
    if "대체" in name:
        return "substitute"
    if "임시" in name:
        return "temporary"
    if "선거" in name:
        return "election"
    return "public"


def _name_en(name: str) -> str | None:
    if "대체" in name:
        return "Substitute Holiday"
    if "선거" in name:
        return "Election Day"
    if "임시" in name:
        return "Temporary Public Holiday"
    for ko, en in NAME_EN.items():
        if ko in name:
            return en
    return None


def fetch_year(year: int, service_key: str, retries: int = 3) -> list[Holiday]:
    if not service_key:
        return []
    params = {
        "solYear": str(year),
        "ServiceKey": service_key,
        "_type": "json",
        "numOfRows": "100",
    }
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = httpx.get(BASE_URL, params=params, timeout=10.0)
            resp.raise_for_status()
            body = resp.json()["response"]["body"]
            items = body.get("items") or {}
            raw = items.get("item") or []
            if isinstance(raw, dict):
                raw = [raw]
            out: list[Holiday] = []
            for it in raw:
                if it.get("isHoliday") != "Y":
                    continue
                d = str(it["locdate"])
                name = str(it["dateName"]).strip()
                out.append(
                    Holiday(
                        date=f"{d[0:4]}-{d[4:6]}-{d[6:8]}",
                        name_ko=name,
                        name_en=_name_en(name),
                        type=_classify(name),
                    )
                )
            return out
        except Exception as exc:  # noqa: BLE001 — 실패 시 빈 결과 폴백, 원인은 로그 보존
            last_error = exc
            if attempt < retries:
                time.sleep(2**attempt)
    logger.warning("KASI sync failed for year=%s after %s attempts: %s", year, retries, last_error)
    return []
