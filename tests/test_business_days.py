import datetime

import pytest

from app.apis.holidays import service


def d(s: str) -> datetime.date:
    return datetime.date.fromisoformat(s)


def test_add_friday_to_monday(db_path):
    assert service.add_business_days(db_path, d("2026-07-10"), 1) == d("2026-07-13")


def test_add_year_rollover(db_path):
    # 12/31(목) +1 → 1/1 신정(금) 스킵, 1/2(토)·1/3(일) 스킵 → 1/4(월)
    assert service.add_business_days(db_path, d("2026-12-31"), 1) == d("2027-01-04")


def test_add_skips_substitute(db_path):
    # 5/22(금) +1 → 5/23(토)·5/24(일=부처님오신날)·5/25(월=대체공휴일) 스킵 → 5/26(화)
    assert service.add_business_days(db_path, d("2026-05-22"), 1) == d("2026-05-26")


def test_add_days_out_of_range_raises(db_path):
    with pytest.raises(ValueError):
        service.add_business_days(db_path, d("2026-07-10"), 0)
    with pytest.raises(ValueError):
        service.add_business_days(db_path, d("2026-07-10"), service.MAX_ADD_DAYS + 1)


def test_count_chuseok_week(db_path):
    # 9/21(월)~9/27(일): 21·22·23 영업일, 24·25 추석연휴, 26(토)·27(일)
    assert service.count_business_days(db_path, d("2026-09-21"), d("2026-09-27")) == 3


def test_count_single_day_boundary(db_path):
    assert service.count_business_days(db_path, d("2026-07-10"), d("2026-07-10")) == 1
    assert service.count_business_days(db_path, d("2026-03-02"), d("2026-03-02")) == 0


def test_count_invalid_range_raises(db_path):
    with pytest.raises(ValueError):
        service.count_business_days(db_path, d("2026-07-11"), d("2026-07-10"))
    with pytest.raises(ValueError):
        service.count_business_days(
            db_path, d("2020-01-01"), d("2020-01-01") + datetime.timedelta(days=service.MAX_COUNT_SPAN_DAYS + 1)
        )


def test_is_business_day(db_path):
    assert service.is_business_day(db_path, d("2026-07-10")) is True
    assert service.is_business_day(db_path, d("2026-07-11")) is False  # Saturday
    assert service.is_business_day(db_path, d("2026-03-02")) is False  # substitute holiday
