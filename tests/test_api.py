def test_requires_api_key(client):
    assert client.get("/v1/holidays?year=2026").status_code == 401


def test_proxy_secret_header_accepted(client):
    r = client.get("/v1/holidays?year=2026", headers={"X-RapidAPI-Proxy-Secret": "proxy-secret"})
    assert r.status_code == 200


def test_health_open_without_key(client):
    assert client.get("/v1/health").status_code == 200


def test_holidays_2026_contains_substitutes(client):
    r = client.get("/v1/holidays?year=2026", headers={"X-API-Key": "test-key"})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 20
    subs = {h["date"] for h in body["holidays"] if h["type"] == "substitute"}
    assert subs == {"2026-03-02", "2026-05-25", "2026-08-17", "2026-10-05"}


def test_holidays_month_filter(client):
    r = client.get("/v1/holidays?year=2026&month=9", headers={"X-API-Key": "test-key"})
    assert [h["date"] for h in r.json()["holidays"]] == ["2026-09-24", "2026-09-25", "2026-09-26"]


def test_check_substitute_holiday(client):
    r = client.get("/v1/holidays/check?date=2026-03-02", headers={"X-API-Key": "test-key"})
    body = r.json()
    assert body["is_holiday"] is True
    assert body["is_business_day"] is False
    assert body["names"] == ["대체공휴일(삼일절)"]


def test_add_endpoint_year_rollover(client):
    r = client.get("/v1/business-days/add?date=2026-12-31&days=1", headers={"X-API-Key": "test-key"})
    assert r.json()["result"] == "2027-01-04"


def test_count_endpoint(client):
    r = client.get(
        "/v1/business-days/count?start=2026-09-21&end=2026-09-27", headers={"X-API-Key": "test-key"}
    )
    assert r.json()["business_days"] == 3


def test_invalid_date_returns_422(client):
    r = client.get("/v1/holidays/check?date=2026-13-01", headers={"X-API-Key": "test-key"})
    assert r.status_code == 422


def test_days_zero_returns_422(client):
    r = client.get("/v1/business-days/add?date=2026-07-10&days=0", headers={"X-API-Key": "test-key"})
    assert r.status_code == 422


def test_count_reversed_range_returns_422(client):
    r = client.get(
        "/v1/business-days/count?start=2026-07-11&end=2026-07-10", headers={"X-API-Key": "test-key"}
    )
    assert r.status_code == 422
