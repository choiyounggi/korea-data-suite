from app.apis.holidays import kasi


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _payload(items):
    return {"response": {"body": {"items": {"item": items}}}}


def test_fetch_year_parses_and_filters(monkeypatch):
    items = [
        {"locdate": 20260217, "dateName": "설날", "isHoliday": "Y"},
        {"locdate": 20260302, "dateName": "대체공휴일", "isHoliday": "Y"},
        {"locdate": 20260401, "dateName": "기념일", "isHoliday": "N"},
    ]
    monkeypatch.setattr(kasi.httpx, "get", lambda *a, **k: FakeResponse(_payload(items)))
    out = kasi.fetch_year(2026, "dummy-key")
    assert [(h.date, h.type) for h in out] == [("2026-02-17", "public"), ("2026-03-02", "substitute")]
    assert out[0].name_en == "Seollal (Korean New Year)"


def test_fetch_year_single_item_dict(monkeypatch):
    single = {"locdate": 20260101, "dateName": "1월1일", "isHoliday": "Y"}
    monkeypatch.setattr(kasi.httpx, "get", lambda *a, **k: FakeResponse(_payload(single)))
    out = kasi.fetch_year(2026, "dummy-key")
    assert len(out) == 1 and out[0].date == "2026-01-01"


def test_fetch_year_without_key_returns_empty(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network must not be called without key")

    monkeypatch.setattr(kasi.httpx, "get", boom)
    assert kasi.fetch_year(2026, "") == []


def test_fetch_year_retries_then_empty(monkeypatch):
    calls = {"n": 0}

    def failing(*a, **k):
        calls["n"] += 1
        raise kasi.httpx.ConnectError("down")

    monkeypatch.setattr(kasi.httpx, "get", failing)
    monkeypatch.setattr(kasi.time, "sleep", lambda s: None)
    assert kasi.fetch_year(2026, "dummy-key") == []
    assert calls["n"] == 3


def test_fetch_year_excludes_non_public_holidays(monkeypatch):
    # KASI는 노동절·제헌절도 isHoliday=Y로 주지만 관공서 공휴일이 아니므로 제외 (실측 2026)
    items = [
        {"locdate": 20260501, "dateName": "노동절", "isHoliday": "Y"},
        {"locdate": 20260717, "dateName": "제헌절", "isHoliday": "Y"},
        {"locdate": 20261009, "dateName": "한글날", "isHoliday": "Y"},
    ]
    monkeypatch.setattr(kasi.httpx, "get", lambda *a, **k: FakeResponse(_payload(items)))
    out = kasi.fetch_year(2026, "dummy-key")
    assert [h.name_ko for h in out] == ["한글날"]
    assert kasi.EXCLUDE_NAMES == frozenset({"노동절", "제헌절"})
