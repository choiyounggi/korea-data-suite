from app.core.config import get_settings
from scripts import backfill


def test_months_range():
    assert backfill._months((2025, 11), (2026, 2)) == ["2025-11", "2025-12", "2026-01", "2026-02"]
    assert backfill._months((2026, 7), (2026, 7)) == ["2026-07"]


def test_parse_ym_validation():
    assert backfill._parse_ym("2025-9") == (2025, 9)  # non-zero-padded accepted
    assert backfill._parse_ym("2025-13") is None  # month out of range
    assert backfill._parse_ym("2025-00") is None
    assert backfill._parse_ym("2025") is None  # malformed
    assert backfill._parse_ym("abc-01") is None


def test_from_after_to_returns_exit_2():
    assert backfill.main(["--from", "2026-03", "--to", "2026-01"]) == 2


def test_non_padded_range_not_falsely_rejected(tmp_path, monkeypatch):
    # "2025-9" <= "2025-12" numerically, but lexically "2025-9" > "2025-12" (the old bug)
    monkeypatch.setenv("KDS_DATA_GO_KR_KEY", "test-key")
    monkeypatch.setenv("KDS_DB_PATH", str(tmp_path / "re.db"))
    get_settings.cache_clear()
    monkeypatch.setattr(backfill.time, "sleep", lambda s: None)
    calls = []
    monkeypatch.setattr(backfill.sync, "ingest_slice", lambda db, key, ds, r, m: (calls.append(m), 0)[1])
    rc = backfill.main(["--from", "2025-9", "--to", "2025-12", "--regions", "11680", "--datasets", "apt_trade", "--yes"])
    assert rc == 0
    assert calls == ["2025-09", "2025-10", "2025-11", "2025-12"]  # 4 months, not rejected
    get_settings.cache_clear()


def test_invalid_month_returns_exit_2():
    assert backfill.main(["--from", "2025-13", "--to", "2025-14"]) == 2


def test_no_key_returns_exit_2(tmp_path, monkeypatch):
    monkeypatch.setenv("KDS_DATA_GO_KR_KEY", "")
    monkeypatch.setenv("KDS_DB_PATH", str(tmp_path / "re.db"))
    get_settings.cache_clear()
    assert backfill.main(["--from", "2025-01", "--to", "2025-01", "--regions", "11680"]) == 2
    get_settings.cache_clear()


def test_runs_ingest_for_each_slice(tmp_path, monkeypatch):
    monkeypatch.setenv("KDS_DATA_GO_KR_KEY", "test-key")
    monkeypatch.setenv("KDS_DB_PATH", str(tmp_path / "re.db"))
    get_settings.cache_clear()
    monkeypatch.setattr(backfill.time, "sleep", lambda s: None)
    calls = []
    monkeypatch.setattr(backfill.sync, "ingest_slice", lambda db, key, dataset, region, month: (calls.append((dataset[0], region, month)), 0)[1])
    rc = backfill.main(["--from", "2025-01", "--to", "2025-02", "--regions", "11680", "--datasets", "apt_trade", "--yes"])
    assert rc == 0
    assert calls == [("apt_trade", "11680", "2025-01"), ("apt_trade", "11680", "2025-02")]
    get_settings.cache_clear()
