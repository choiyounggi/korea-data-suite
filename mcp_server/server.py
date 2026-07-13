"""Korea Data Suite — MCP server.

Exposes the Korea Data Suite REST API as Model Context Protocol tools so AI agents
(Claude Desktop/Code, Cursor, etc.) can discover and call Korean public-data
endpoints — public holidays, business-day math, and MOLIT real-estate transactions
— directly, without hand-writing HTTP calls.

Run (stdio):
    KDS_API_KEY=<your key> uv run korea-data-mcp

Config (env):
    KDS_API_BASE   API origin (default https://api.korea-data.cloud)
    KDS_API_KEY    your API key (from the RapidAPI listing); sent as X-API-Key
"""
import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

API_BASE = os.environ.get("KDS_API_BASE", "https://api.korea-data.cloud").rstrip("/")
API_KEY = os.environ.get("KDS_API_KEY", "")

mcp = FastMCP("korea-data-suite")


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    """GET the API and return parsed JSON, raising a clear error on failure."""
    headers = {"X-API-Key": API_KEY} if API_KEY else {}
    clean = {k: v for k, v in (params or {}).items() if v is not None}
    with httpx.Client(base_url=API_BASE, headers=headers, timeout=20.0) as client:
        resp = client.get(path, params=clean)
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:  # noqa: BLE001 — non-JSON error body
            detail = resp.text
        hint = " (set KDS_API_KEY to a valid key)" if resp.status_code == 401 else ""
        raise RuntimeError(f"Korea Data Suite API returned {resp.status_code}: {detail}{hint}")
    return resp.json()


@mcp.tool()
def get_holidays(year: int, month: int | None = None) -> dict:
    """대한민국 공휴일 목록을 조회한다 (List Korean public holidays).

    법정공휴일뿐 아니라 대체공휴일·임시공휴일·선거일까지 포함한다. 대부분의 글로벌 공휴일
    API가 놓치는 한국 특유의 대체/임시공휴일을 정확히 반영한다.

    Args:
        year: 조회 연도 (e.g. 2026).
        month: 특정 월(1-12)만 필터링. 생략하면 해당 연도 전체.
    """
    return _get("/v1/holidays", {"year": year, "month": month})


@mcp.tool()
def check_holiday(date: str) -> dict:
    """특정 날짜가 공휴일/영업일인지 확인한다 (Is this date a holiday or a business day?).

    Args:
        date: ISO 날짜 (YYYY-MM-DD).
    """
    return _get("/v1/holidays/check", {"date": date})


@mcp.tool()
def add_business_days(date: str, days: int) -> dict:
    """특정 날짜에 N영업일을 더한 날짜를 계산한다 (주말·공휴일 자동 제외).

    Args:
        date: 기준 날짜 (YYYY-MM-DD).
        days: 더할 영업일 수 (음수면 이전 영업일).
    """
    return _get("/v1/business-days/add", {"date": date, "days": days})


@mcp.tool()
def count_business_days(start: str, end: str) -> dict:
    """기간 내 영업일 수를 센다 (양끝 포함, 주말·공휴일 제외).

    Args:
        start: 시작일 (YYYY-MM-DD).
        end: 종료일 (YYYY-MM-DD, 포함).
    """
    return _get("/v1/business-days/count", {"start": start, "end": end})


@mcp.tool()
def list_real_estate_regions() -> dict:
    """실거래가 조회에 쓰는 지역 코드(LAWD 5자리) 목록을 반환한다.

    각 항목은 code(예: '11680'), name_ko('서울특별시 강남구'), name_en을 가진다.
    get_real_estate_transactions의 region 파라미터에 이 code를 사용한다.
    """
    return _get("/v1/realestate/regions")


@mcp.tool()
def get_real_estate_transactions(
    region: str,
    property_type: str | None = None,
    trade_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> dict:
    """국토교통부(MOLIT) 아파트/오피스텔/토지 실거래가를 정규화된 JSON으로 조회한다.

    Args:
        region: 지역 코드 LAWD 5자리 (예: 강남구 '11680'). list_real_estate_regions 참고.
        property_type: 'apartment' | 'officetel' | 'land' (생략 시 전체).
        trade_type: 'sale'(매매) | 'jeonse'(전세) | 'monthly_rent'(월세) (생략 시 전체).
        date_from: 시작일 필터 (YYYY-MM-DD).
        date_to: 종료일 필터 (YYYY-MM-DD).
        limit: 페이지 크기 (기본 50, 최대 100).
        cursor: 다음 페이지 커서 (이전 응답의 next_cursor 값).
    """
    return _get(
        "/v1/realestate/transactions",
        {
            "region": region,
            "property_type": property_type,
            "trade_type": trade_type,
            "date_from": date_from,
            "date_to": date_to,
            "limit": limit,
            "cursor": cursor,
        },
    )


def main() -> None:
    """Console entry point — run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
