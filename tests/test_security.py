"""Hacker-perspective test cases for external exposure. Each asserts the SECURE
behavior; a failure here is a real attack surface, not a style nit."""
import base64

import pytest
from fastapi.testclient import TestClient

from app.apis.holidays import store as h_store
from app.apis.realestate import store as re_store
from app.apis.realestate.models import Transaction
from app.core.config import get_settings

KEY = "test-key"
H = {"X-API-Key": KEY}


def _tx(region: str, day: str, price: int = 100000000) -> Transaction:
    return Transaction(property_type="apartment", trade_type="sale", region_code=region,
                       traded_on=day, price_won=price)


@pytest.fixture()
def sec_client(tmp_path, monkeypatch):
    db = str(tmp_path / "sec.db")
    h_store.init_db(db)
    re_store.init_db(db)
    re_store.replace_partition(db, "apartment", "sale", "11680", "2026-07",
                               [_tx("11680", f"2026-07-{d:02d}") for d in range(1, 6)])
    re_store.replace_partition(db, "apartment", "sale", "11650", "2026-07",
                               [_tx("11650", "2026-07-01", price=999)])
    monkeypatch.setenv("KDS_DEV_MODE", "false")
    monkeypatch.setenv("KDS_API_KEYS", KEY)
    monkeypatch.setenv("KDS_PROXY_SECRETS", "proxy-secret")
    monkeypatch.setenv("KDS_DB_PATH", db)
    monkeypatch.setenv("KDS_ENABLE_SCHEDULER", "false")
    get_settings.cache_clear()
    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    get_settings.cache_clear()


# ── A. Authentication ──
def test_no_key_rejected(sec_client):
    assert sec_client.get("/v1/realestate/transactions?region=11680").status_code == 401


def test_wrong_key_rejected(sec_client):
    assert sec_client.get("/v1/realestate/transactions?region=11680", headers={"X-API-Key": "wrong"}).status_code == 401


def test_empty_key_rejected(sec_client):
    assert sec_client.get("/v1/realestate/transactions?region=11680", headers={"X-API-Key": ""}).status_code == 401


def test_key_as_query_param_rejected(sec_client):
    # a key smuggled as a query param must NOT authenticate (URLs are logged/cached)
    assert sec_client.get(f"/v1/realestate/transactions?region=11680&api_key={KEY}").status_code == 401
    assert sec_client.get(f"/v1/realestate/transactions?region=11680&serviceKey={KEY}").status_code == 401


def test_valid_key_variants_accepted(sec_client):
    assert sec_client.get("/v1/realestate/transactions?region=11680", headers={"X-API-Key": KEY}).status_code == 200
    assert sec_client.get("/v1/realestate/transactions?region=11680",
                          headers={"X-RapidAPI-Proxy-Secret": "proxy-secret"}).status_code == 200


def test_health_open_without_key(sec_client):
    assert sec_client.get("/v1/health").status_code == 200


def test_docs_and_schema_disabled_by_default(sec_client):
    # secure-by-default: the origin serves no schema/docs for an attacker to map
    assert sec_client.get("/openapi.json").status_code == 404
    assert sec_client.get("/docs").status_code == 404
    assert sec_client.get("/redoc").status_code == 404


# ── B. SQL injection ──
@pytest.mark.parametrize("payload", [
    "11680' OR '1'='1",
    "'; DROP TABLE property_transactions;--",
    "11680) UNION SELECT * FROM property_transactions--",
    "11680 OR 1=1",
])
def test_sql_injection_in_region_rejected(sec_client, payload):
    assert sec_client.get("/v1/realestate/transactions", params={"region": payload}, headers=H).status_code == 422


def test_table_survives_injection_attempt(sec_client):
    sec_client.get("/v1/realestate/transactions",
                   params={"region": "'; DROP TABLE property_transactions;--"}, headers=H)
    # table intact: a legitimate query still returns rows
    assert sec_client.get("/v1/realestate/transactions?region=11680", headers=H).json()["data"]


def test_sql_injection_in_cursor_rejected(sec_client):
    bad = base64.urlsafe_b64encode(b"2026-07-01' OR '1'='1:1").decode()
    assert sec_client.get(f"/v1/realestate/transactions?region=11680&cursor={bad}", headers=H).status_code == 400


# ── C. DoS / input validation ──
@pytest.mark.parametrize("limit", ["0", "-1", "-999", "abc", "1e9"])
def test_bad_limit_rejected(sec_client, limit):
    assert sec_client.get(f"/v1/realestate/transactions?region=11680&limit={limit}", headers=H).status_code == 422


def test_huge_limit_capped_not_honored(sec_client):
    body = sec_client.get("/v1/realestate/transactions?region=11680&limit=1000000", headers=H).json()
    assert body["limit"] == 100  # coerced down, request not honored


def test_oversized_region_rejected(sec_client):
    assert sec_client.get("/v1/realestate/transactions", params={"region": "1" * 10000}, headers=H).status_code == 422


def test_oversized_cursor_rejected(sec_client):
    assert sec_client.get("/v1/realestate/transactions",
                          params={"region": "11680", "cursor": "A" * 5000}, headers=H).status_code == 422


def test_unicode_fullwidth_region_rejected(sec_client):
    # fullwidth digits must not normalize-bypass the ASCII-digit pattern
    assert sec_client.get("/v1/realestate/transactions", params={"region": "１１６８０"}, headers=H).status_code == 422


# ── D. HTTP method ──
@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
def test_non_get_methods_rejected(sec_client, method):
    assert sec_client.request(method, "/v1/realestate/transactions?region=11680", headers=H).status_code == 405


# ── E. Information disclosure / security headers ──
def test_security_headers_present_on_success(sec_client):
    h = sec_client.get("/v1/realestate/transactions?region=11680", headers=H).headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert h["cache-control"] == "no-store"
    assert "default-src 'none'" in h["content-security-policy"]
    assert h.get("server") == "kds"  # uvicorn version/tech disclosure overwritten


def test_security_headers_present_on_error(sec_client):
    h = sec_client.get("/v1/realestate/transactions?region=11680").headers  # 401
    assert h["x-content-type-options"] == "nosniff"


def test_errors_are_json(sec_client):
    r = sec_client.get("/v1/realestate/transactions?region=99999", headers=H)  # 422 unknown region
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/json")


def test_500_returns_generic_body_no_internals(sec_client, monkeypatch):
    from app.apis.realestate import router as re_router

    def boom(*a, **k):
        raise RuntimeError("SECRET /Users/x/data/kds.db internal detail")

    monkeypatch.setattr(re_router.store, "query_transactions", boom)
    r = sec_client.get("/v1/realestate/transactions?region=11680", headers=H)
    assert r.status_code == 500
    assert r.json() == {"detail": "Internal Server Error"}
    assert "SECRET" not in r.text and "RuntimeError" not in r.text and "Traceback" not in r.text


# ── F. IDOR / scope escape via cursor tampering ──
def test_cursor_cannot_escape_region_filter(sec_client):
    # a cursor derived from region 11680 must not leak 11680 rows into an 11650 query
    first = sec_client.get("/v1/realestate/transactions?region=11680&limit=2", headers=H).json()
    cursor = first["next_cursor"]
    assert cursor  # 11680 has 5 rows → there is a next page
    other = sec_client.get(f"/v1/realestate/transactions?region=11650&cursor={cursor}", headers=H).json()
    assert other["data"], "the 11650 row (2026-07-01) is before the cursor, so it should return"
    assert all(row["region_code"] == "11650" for row in other["data"])  # region param stays authoritative


# ── L1: 5xx hardening (from independent pentest) ──
def test_far_future_date_is_422_not_500(sec_client):
    # date arithmetic must not overflow into an unhandled 500 (L1a)
    r = sec_client.get("/v1/business-days/add?date=9999-12-30&days=500", headers=H)
    assert r.status_code == 422


def test_security_headers_present_on_500(sec_client, monkeypatch):
    # 500 responses bypass the middleware; the exception handler must still add headers (L1b)
    from app.apis.realestate import router as re_router

    def boom(*a, **k):
        raise RuntimeError("internal")

    monkeypatch.setattr(re_router.store, "query_transactions", boom)
    r = sec_client.get("/v1/realestate/transactions?region=11680", headers=H)
    assert r.status_code == 500
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers.get("server") == "kds"  # no uvicorn version disclosure on 5xx
