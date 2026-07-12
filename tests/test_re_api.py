import pytest
from fastapi.testclient import TestClient

from app.apis.holidays import store as h_store
from app.apis.realestate import store as re_store
from app.apis.realestate.models import Transaction
from app.core.config import get_settings

H = {"X-API-Key": "test-key"}


def _tx(day: str, price: int = 100000000) -> Transaction:
    return Transaction(
        property_type="apartment", trade_type="sale", region_code="11680",
        traded_on=day, price_won=price,
    )


@pytest.fixture()
def re_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "re_api.db")
    h_store.init_db(db_path)
    re_store.init_db(db_path)
    rows = [_tx(f"2026-07-{d:02d}") for d in (1, 1, 1, 2, 3, 4, 5)]  # 3 share 07-01
    re_store.replace_partition(db_path, "apartment", "sale", "11680", "2026-07", rows)
    monkeypatch.setenv("KDS_DEV_MODE", "false")
    monkeypatch.setenv("KDS_API_KEYS", "test-key")
    monkeypatch.setenv("KDS_DB_PATH", db_path)
    monkeypatch.setenv("KDS_ENABLE_SCHEDULER", "false")
    get_settings.cache_clear()
    from app.main import app

    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def test_requires_api_key(re_client):
    assert re_client.get("/v1/realestate/transactions?region=11680").status_code == 401


def test_normal_page(re_client):
    r = re_client.get("/v1/realestate/transactions?region=11680&limit=50", headers=H)
    assert r.status_code == 200
    body = r.json()
    assert body["limit"] == 50
    assert body["has_more"] is False
    assert body["next_cursor"] is None
    assert len(body["data"]) == 7
    assert "id" not in body["data"][0]  # internal key stripped


def test_cursor_pagination_no_skip_no_repeat(re_client):
    seen: list[str] = []
    cursor = None
    for _ in range(10):
        url = "/v1/realestate/transactions?region=11680&limit=3"
        if cursor:
            url += f"&cursor={cursor}"
        body = re_client.get(url, headers=H).json()
        seen.extend(f"{row['traded_on']}:{row['price_won']}" for row in body["data"])
        cursor = body["next_cursor"]
        if not cursor:
            break
    assert len(seen) == 7  # all rows, no repeats across pages


def test_limit_coerced_down(re_client):
    body = re_client.get("/v1/realestate/transactions?region=11680&limit=500", headers=H).json()
    assert body["limit"] == 100  # forced down to MAX_LIMIT and reported


def test_invalid_cursor_400(re_client):
    r = re_client.get("/v1/realestate/transactions?region=11680&cursor=@@@bad", headers=H)
    assert r.status_code == 400
    assert r.json()["detail"] == "invalid_cursor"


def test_unknown_region_422(re_client):
    r = re_client.get("/v1/realestate/transactions?region=99999", headers=H)
    assert r.status_code == 422


def test_regions_endpoint(re_client):
    from app.apis.realestate import regions

    body = re_client.get("/v1/realestate/regions", headers=H).json()
    assert body["count"] == len(regions.REGIONS)
    assert body["count"] >= 200  # nationwide coverage, not Seoul-only
    gangnam = [x for x in body["regions"] if x["code"] == "11680"][0]
    assert gangnam["name_en"] == "Seoul Gangnam-gu"
    # a non-Seoul sigungu is present (nationwide, disambiguated by sido)
    haeundae = [x for x in body["regions"] if x["code"] == "26350"][0]
    assert haeundae["name_ko"] == "부산광역시 해운대구"


def test_oversized_cursor_returns_400(re_client):
    import base64
    big = base64.urlsafe_b64encode(b"2026-01-01:99999999999999999999").decode()
    r = re_client.get(f"/v1/realestate/transactions?region=11680&cursor={big}", headers=H)
    assert r.status_code == 400  # BUG-B: was 500 (SQLite OverflowError)
    assert r.json()["detail"] == "invalid_cursor"


def test_impossible_date_returns_422(re_client):
    r = re_client.get("/v1/realestate/transactions?region=11680&date_from=2026-13-99", headers=H)
    assert r.status_code == 422  # date type rejects impossible dates


def test_realestate_api_works_before_any_sync(client):
    # lifespan must create the table so the API returns empty (200), not 500
    r = client.get("/v1/realestate/transactions?region=11680", headers=H)
    assert r.status_code == 200
    assert r.json()["data"] == []
