import datetime

import pytest

from app.apis.realestate import sync
from app.apis.realestate.models import Transaction
from app.core.config import get_settings


def _sale(region: str, month: str, pt: str = "apartment") -> Transaction:
    return Transaction(
        property_type=pt, trade_type="sale", region_code=region,
        traded_on=f"{month}-01", price_won=1,
    )


def _rent(region: str, month: str, tt: str) -> Transaction:
    return Transaction(
        property_type="apartment", trade_type=tt, region_code=region,
        traded_on=f"{month}-01", deposit_won=1000,
        monthly_rent_won=(50 if tt == "monthly_rent" else None),
    )


@pytest.fixture()
def synced_env(tmp_path, monkeypatch):
    monkeypatch.setenv("KDS_DATA_GO_KR_KEY", "test-key")
    monkeypatch.setenv("KDS_DB_PATH", str(tmp_path / "re.db"))
    monkeypatch.setenv("KDS_RE_REGIONS", "11680,11650")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _record_replace(monkeypatch):
    calls = []
    monkeypatch.setattr(
        sync.store, "replace_partition",
        lambda db, pt, tt, region, month, rows: (calls.append((pt, tt, region, month)), len(rows))[1],
    )
    return calls


def test_sync_replaces_each_partition(synced_env, monkeypatch):
    monkeypatch.setenv("KDS_RE_DATASETS", "apt_trade")
    monkeypatch.setattr(sync.molit, "fetch_apt_trades", lambda region, month, key, retries=3: [_sale(region, month)])
    calls = _record_replace(monkeypatch)
    total = sync.sync_realestate()
    assert len(calls) == 4  # 2 regions × 2 months
    assert total == 4


def test_sync_empty_fetch_skips_replace(synced_env, monkeypatch):
    monkeypatch.setenv("KDS_RE_DATASETS", "apt_trade")
    monkeypatch.setattr(sync.molit, "fetch_apt_trades", lambda *a, **k: [])
    calls = _record_replace(monkeypatch)
    assert sync.sync_realestate() == 0
    assert calls == []


def test_sync_region_error_continues(synced_env, monkeypatch):
    monkeypatch.setenv("KDS_RE_DATASETS", "apt_trade")

    def fake(region, month, key, retries=3):
        if region == "11680":
            raise RuntimeError("boom")
        return [_sale(region, month)]

    monkeypatch.setattr(sync.molit, "fetch_apt_trades", fake)
    monkeypatch.setattr(sync.store, "replace_partition", lambda db, pt, tt, r, m, rows: len(rows))
    assert sync.sync_realestate() == 2  # only 11650 × 2 months


def test_sync_rent_splits_into_two_partitions(synced_env, monkeypatch):
    monkeypatch.setenv("KDS_RE_DATASETS", "apt_rent")
    monkeypatch.setenv("KDS_RE_REGIONS", "11680")

    def fake_rents(region, month, key, retries=3):
        return [_rent(region, month, "jeonse"), _rent(region, month, "monthly_rent"), _rent(region, month, "jeonse")]

    monkeypatch.setattr(sync.molit, "fetch_apt_rents", fake_rents)
    calls = _record_replace(monkeypatch)
    total = sync.sync_realestate()
    # 1 region × 2 months × 2 partitions (jeonse+monthly) = 4 replace calls
    tt_calls = sorted({(tt, month) for _, tt, _, month in calls})
    assert ("jeonse", "2026-06") in tt_calls and ("monthly_rent", "2026-06") in tt_calls
    assert total == 2 * (2 + 1)  # per month: 2 jeonse + 1 monthly


def test_sync_dataset_filter(synced_env, monkeypatch):
    monkeypatch.setenv("KDS_RE_DATASETS", "land_trade")
    used = {"apt": 0, "land": 0}
    monkeypatch.setattr(sync.molit, "fetch_apt_trades", lambda *a, **k: (used.__setitem__("apt", used["apt"] + 1), [])[1])
    monkeypatch.setattr(sync.molit, "fetch_land_trades", lambda region, month, key, retries=3: (used.__setitem__("land", used["land"] + 1), [_sale(region, month, "land")])[1])
    _record_replace(monkeypatch)
    sync.sync_realestate()
    assert used["apt"] == 0  # filtered out
    assert used["land"] == 4  # 2 regions × 2 months


def test_sync_no_key(tmp_path, monkeypatch):
    monkeypatch.setenv("KDS_DATA_GO_KR_KEY", "")
    monkeypatch.setenv("KDS_DB_PATH", str(tmp_path / "re.db"))
    get_settings.cache_clear()
    called = {"n": 0}
    monkeypatch.setattr(sync.molit, "fetch_apt_trades", lambda *a, **k: (called.__setitem__("n", called["n"] + 1), [])[1])
    assert sync.sync_realestate() == 0
    assert called["n"] == 0
    get_settings.cache_clear()


def test_target_months_january_boundary():
    assert sync._target_months(datetime.date(2027, 1, 15)) == ["2027-01", "2026-12"]
    assert sync._target_months(datetime.date(2026, 7, 11)) == ["2026-07", "2026-06"]


def test_rent_jeonse_only_does_not_wipe_monthly(monkeypatch, tmp_path):
    # MED bug regression: a jeonse-only fetch must not wipe an existing monthly partition
    from app.apis.realestate import store
    db = str(tmp_path / "wipe.db")
    monkeypatch.setenv("KDS_DATA_GO_KR_KEY", "test-key")
    monkeypatch.setenv("KDS_DB_PATH", db)
    get_settings.cache_clear()
    store.init_db(db)
    # seed an existing monthly_rent row for the partition
    store.replace_partition(db, "apartment", "monthly_rent", "11680", "2026-07", [_rent("11680", "2026-07", "monthly_rent")])
    # a jeonse-only fetch for the same partition
    monkeypatch.setattr(sync.molit, "fetch_apt_rents", lambda region, month, key, retries=3: [_rent(region, month, "jeonse")])
    sync.ingest_slice(db, "key", ("apt_rent", "apartment", "rent", "fetch_apt_rents"), "11680", "2026-07")
    assert store.count_by_partition(db, "apartment", "monthly_rent", "11680", "2026-07") == 1  # preserved, not wiped
    assert store.count_by_partition(db, "apartment", "jeonse", "11680", "2026-07") == 1  # jeonse written
    get_settings.cache_clear()
