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
