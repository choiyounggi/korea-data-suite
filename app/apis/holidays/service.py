import datetime

from app.apis.holidays import store

WEEKEND = (5, 6)  # Saturday, Sunday
MAX_ADD_DAYS = 500
MAX_COUNT_SPAN_DAYS = 1827  # ~5 years


def _holiday_set(db_path: str, start_year: int, end_year: int) -> set[str]:
    return store.holiday_dates(db_path, list(range(start_year, end_year + 1)))


def _ensure_coverage(db_path: str, start_year: int, end_year: int) -> None:
    covered = store.covered_years(db_path)
    missing = [y for y in range(start_year, end_year + 1) if y not in covered]
    if missing:
        raise ValueError(
            f"no holiday data for year(s) {missing}; covered years: {sorted(covered)}"
        )


def is_business_day(db_path: str, day: datetime.date) -> bool:
    _ensure_coverage(db_path, day.year, day.year)
    if day.weekday() in WEEKEND:
        return False
    return day.isoformat() not in _holiday_set(db_path, day.year, day.year)


def add_business_days(db_path: str, start: datetime.date, days: int) -> datetime.date:
    if days < 1 or days > MAX_ADD_DAYS:
        raise ValueError(f"days must be between 1 and {MAX_ADD_DAYS}")
    holidays = _holiday_set(db_path, start.year, start.year + (days // 200) + 1)
    current = start
    remaining = days
    while remaining > 0:
        current += datetime.timedelta(days=1)
        if current.weekday() in WEEKEND or current.isoformat() in holidays:
            continue
        remaining -= 1
    # 계산이 지나간 모든 연도에 데이터가 있어야 결과를 신뢰할 수 있다
    _ensure_coverage(db_path, start.year, current.year)
    return current


def count_business_days(db_path: str, start: datetime.date, end: datetime.date) -> int:
    if end < start:
        raise ValueError("end must be on or after start")
    if (end - start).days > MAX_COUNT_SPAN_DAYS:
        raise ValueError(f"range must be at most {MAX_COUNT_SPAN_DAYS} days")
    _ensure_coverage(db_path, start.year, end.year)
    holidays = _holiday_set(db_path, start.year, end.year)
    count = 0
    current = start
    while current <= end:
        if current.weekday() not in WEEKEND and current.isoformat() not in holidays:
            count += 1
        current += datetime.timedelta(days=1)
    return count
