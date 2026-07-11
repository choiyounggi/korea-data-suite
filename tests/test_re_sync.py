import datetime

import pytest

from app.apis.realestate import sync
from app.apis.realestate.models import Transaction
from app.core.config import get_settings


def _tx(region: str, month: str) -> Transaction:
    return Transaction(
        property_type="apartment", trade_type="sale", region_code=region,
        traded_on=f"{month}-01", price_won=1,
    )


@pytest.fixture()
def synced_env(tmp_path, monkeypatch):
    monkeypatch.setenv("KDS_DATA_GO_KR_KEY", "test-key")
    monkeypatch.setenv("KDS_DB_PATH", str(tmp_path / "re.db"))
    monkeypatch.setenv("KDS_RE_REGIONS", "11680,11650")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_sync_replaces_each_partition(synced_env, monkeypatch):
    monkeypatch.setattr(sync.molit, "fetch_apt_trades", lambda region, month, key, retries=3: [_tx(region, month)])
    calls = []
    monkeypatch.setattr(
        sync.store, "replace_partition",
        lambda db, pt, tt, region, month, rows: (calls.append((pt, tt, region, month)), len(rows))[1],
    )
    total = sync.sync_realestate()
    assert len(calls) == 4  # 2 regions × 2 months
    assert total == 4


def test_sync_empty_fetch_skips_replace(synced_env, monkeypatch):
    monkeypatch.setattr(sync.molit, "fetch_apt_trades", lambda *a, **k: [])
    called = {"n": 0}
    monkeypatch.setattr(
        sync.store, "replace_partition",
        lambda *a, **k: called.__setitem__("n", called["n"] + 1),
    )
    assert sync.sync_realestate() == 0
    assert called["n"] == 0


def test_sync_region_error_continues(synced_env, monkeypatch):
    def fake_fetch(region, month, key, retries=3):
        if region == "11680":
            raise RuntimeError("boom")
        return [_tx(region, month)]

    monkeypatch.setattr(sync.molit, "fetch_apt_trades", fake_fetch)
    monkeypatch.setattr(sync.store, "replace_partition", lambda db, pt, tt, r, m, rows: len(rows))
    assert sync.sync_realestate() == 2  # only 11650 × 2 months survives


def test_sync_no_key(tmp_path, monkeypatch):
    monkeypatch.setenv("KDS_DATA_GO_KR_KEY", "")
    monkeypatch.setenv("KDS_DB_PATH", str(tmp_path / "re.db"))
    get_settings.cache_clear()
    called = {"n": 0}
    monkeypatch.setattr(
        sync.molit, "fetch_apt_trades",
        lambda *a, **k: (called.__setitem__("n", called["n"] + 1), [])[1],
    )
    assert sync.sync_realestate() == 0
    assert called["n"] == 0
    get_settings.cache_clear()


def test_target_months_january_boundary():
    assert sync._target_months(datetime.date(2027, 1, 15)) == ["2027-01", "2026-12"]
    assert sync._target_months(datetime.date(2026, 7, 11)) == ["2026-07", "2026-06"]
