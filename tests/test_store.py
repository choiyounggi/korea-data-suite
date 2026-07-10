from app.apis.holidays import store
from app.apis.holidays.models import Holiday


def test_seed_loads_all_rows(db_path):
    assert len(store.get_holidays(db_path, 2025)) + len(store.get_holidays(db_path, 2026)) + len(
        store.get_holidays(db_path, 2027)
    ) == 61


def test_get_holidays_year_and_month_filter(db_path):
    y2026 = store.get_holidays(db_path, 2026)
    assert len(y2026) == 20
    feb = store.get_holidays(db_path, 2026, month=2)
    assert [h.date for h in feb] == ["2026-02-16", "2026-02-17", "2026-02-18"]


def test_get_holidays_unknown_year_returns_empty(db_path):
    assert store.get_holidays(db_path, 1999) == []


def test_duplicate_date_two_holidays_preserved(db_path):
    names = store.names_on(db_path, "2025-05-05")
    assert names == ["부처님오신날", "어린이날"]


def test_upsert_updates_existing_row(db_path):
    updated = Holiday(date="2026-02-17", name_ko="설날", name_en="Lunar New Year", type="public")
    n = store.upsert_holidays(db_path, [updated], source="kasi")
    assert n == 1
    row = [h for h in store.get_holidays(db_path, 2026, month=2) if h.date == "2026-02-17"][0]
    assert row.name_en == "Lunar New Year"


def test_holiday_dates_multi_year(db_path):
    dates = store.holiday_dates(db_path, [2026, 2027])
    assert "2026-03-02" in dates and "2027-02-09" in dates
    assert not any(d.startswith("2025-") for d in dates)
    assert store.holiday_dates(db_path, []) == set()


def test_replace_year_removes_stale_names(db_path):
    # KASI가 다른 이름(기독탄신일)으로 주면 연도 교체 후 시드 이름(성탄절)이 사라져야 한다
    kasi_rows = [
        Holiday(date="2026-12-25", name_ko="기독탄신일", name_en="Christmas Day", type="public"),
        Holiday(date="2026-01-01", name_ko="1월1일", name_en="New Year's Day", type="public"),
    ]
    store.replace_year(db_path, 2026, kasi_rows, source="kasi")
    y2026 = store.get_holidays(db_path, 2026)
    assert len(y2026) == 2  # 연도 전체가 교체됨 — 중복/잔존 없음
    assert store.names_on(db_path, "2026-12-25") == ["기독탄신일"]
    # 다른 연도는 불변
    assert len(store.get_holidays(db_path, 2027)) == 20


def test_covered_years(db_path):
    assert store.covered_years(db_path) == {2025, 2026, 2027}
