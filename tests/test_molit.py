import httpx

from app.apis.realestate import molit


def _xml(items: list[dict], total: int | None = None) -> str:
    if total is None:
        total = len(items)
    item_xml = ""
    for it in items:
        cells = "".join(f"<{k}>{v}</{k}>" for k, v in it.items())
        item_xml += f"<item>{cells}</item>"
    return (
        "<response><header><resultCode>000</resultCode><resultMsg>OK</resultMsg></header>"
        f"<body><items>{item_xml}</items><totalCount>{total}</totalCount></body></response>"
    )


def _resp(text: str, status: int = 200) -> httpx.Response:
    return httpx.Response(status, text=text, request=httpx.Request("GET", "http://x"))


def test_fetch_apt_trades_parses(monkeypatch):
    items = [
        {"sggCd": "11680", "umdNm": "역삼동", "aptNm": "래미안", "jeonyongAr": "84.5",
         "dealYear": "2026", "dealMonth": "7", "dealDay": "1", "dealAmount": "82,500",
         "floor": "10", "buildYear": "2015"},
        {"sggCd": "11680", "umdNm": "삼성동", "aptNm": "아이파크", "jeonyongAr": "120.0",
         "dealYear": "2026", "dealMonth": "7", "dealDay": "3", "dealAmount": "150,000",
         "floor": "20", "buildYear": "2018"},
    ]
    monkeypatch.setattr(molit.httpx, "get", lambda *a, **k: _resp(_xml(items)))
    out = molit.fetch_apt_trades("11680", "2026-07", "key")
    assert len(out) == 2
    assert out[0].price_won == 825_000_000  # 82,500만원
    assert out[0].traded_on == "2026-07-01"
    assert out[0].building_name == "래미안"
    assert out[0].area_m2 == 84.5
    assert out[1].price_won == 1_500_000_000


def test_fetch_apt_trades_skips_cancelled(monkeypatch):
    items = [
        {"sggCd": "11680", "dealYear": "2026", "dealMonth": "7", "dealDay": "1", "dealAmount": "50,000"},
        {"sggCd": "11680", "dealYear": "2026", "dealMonth": "7", "dealDay": "2", "dealAmount": "60,000",
         "cdealType": "O"},
    ]
    monkeypatch.setattr(molit.httpx, "get", lambda *a, **k: _resp(_xml(items)))
    out = molit.fetch_apt_trades("11680", "2026-07", "key")
    assert len(out) == 1
    assert out[0].traded_on == "2026-07-01"


def test_fetch_apt_trades_paginates(monkeypatch):
    monkeypatch.setattr(molit, "NUM_OF_ROWS", 2)
    calls = {"n": 0}

    def fake_get(url, params=None, **k):
        calls["n"] += 1
        page = int(params["pageNo"])
        if page == 1:
            items = [
                {"sggCd": "11680", "dealYear": "2026", "dealMonth": "7", "dealDay": str(d),
                 "dealAmount": "10,000"} for d in (1, 2)
            ]
        else:
            items = [{"sggCd": "11680", "dealYear": "2026", "dealMonth": "7", "dealDay": "3",
                      "dealAmount": "10,000"}]
        return _resp(_xml(items, total=3))

    monkeypatch.setattr(molit.httpx, "get", fake_get)
    out = molit.fetch_apt_trades("11680", "2026-07", "key")
    assert len(out) == 3
    assert calls["n"] == 2


def test_fetch_apt_trades_4xx_stops(monkeypatch):
    calls = {"n": 0}

    def fake_get(*a, **k):
        calls["n"] += 1
        return _resp("bad request", status=400)

    monkeypatch.setattr(molit.httpx, "get", fake_get)
    monkeypatch.setattr(molit.time, "sleep", lambda s: None)
    out = molit.fetch_apt_trades("11680", "2026-07", "key")
    assert out == []
    assert calls["n"] == 1  # client error is not retried


def test_fetch_apt_trades_retries_then_empty(monkeypatch):
    calls = {"n": 0}

    def failing(*a, **k):
        calls["n"] += 1
        raise molit.httpx.ConnectError("down")

    monkeypatch.setattr(molit.httpx, "get", failing)
    monkeypatch.setattr(molit.time, "sleep", lambda s: None)
    monkeypatch.setattr(molit.random, "uniform", lambda a, b: 0)
    out = molit.fetch_apt_trades("11680", "2026-07", "key")
    assert out == []
    assert calls["n"] == 3


def test_fetch_apt_trades_no_key(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("must not call network without a key")

    monkeypatch.setattr(molit.httpx, "get", boom)
    assert molit.fetch_apt_trades("11680", "2026-07", "") == []


def test_fetch_apt_trades_bad_amount_skips_only_that_row(monkeypatch):
    # BUG-A regression: one bad dealAmount must not discard the whole region-month
    items = [
        {"sggCd": "11680", "dealYear": "2026", "dealMonth": "7", "dealDay": "1", "dealAmount": "50,000"},
        {"sggCd": "11680", "dealYear": "2026", "dealMonth": "7", "dealDay": "2", "dealAmount": ""},
        {"sggCd": "11680", "dealYear": "2026", "dealMonth": "7", "dealDay": "3", "dealAmount": "-5,000"},
        {"sggCd": "11680", "dealYear": "2026", "dealMonth": "7", "dealDay": "4", "dealAmount": "60,000"},
    ]
    monkeypatch.setattr(molit.httpx, "get", lambda *a, **k: _resp(_xml(items)))
    out = molit.fetch_apt_trades("11680", "2026-07", "key")
    assert [t.traded_on for t in out] == ["2026-07-01", "2026-07-04"]  # 2 good rows survive
