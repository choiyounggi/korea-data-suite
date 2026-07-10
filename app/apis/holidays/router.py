import datetime

from fastapi import APIRouter, HTTPException, Query

from app.apis.holidays import service, store
from app.core.config import get_settings

router = APIRouter(prefix="/v1", tags=["holidays"])


@router.get("/holidays")
def list_holidays(
    year: int = Query(ge=2004, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
) -> dict:
    holidays = store.get_holidays(get_settings().db_path, year, month)
    return {
        "year": year,
        "month": month,
        "count": len(holidays),
        "holidays": [h.model_dump() for h in holidays],
    }


@router.get("/holidays/check")
def check_date(date: datetime.date) -> dict:
    db_path = get_settings().db_path
    names = store.names_on(db_path, date.isoformat())
    return {
        "date": date.isoformat(),
        "weekday": date.strftime("%A").lower(),
        "is_holiday": bool(names),
        "is_business_day": service.is_business_day(db_path, date),
        "names": names,
    }


@router.get("/business-days/add")
def business_days_add(
    date: datetime.date,
    days: int = Query(ge=1, le=service.MAX_ADD_DAYS),
) -> dict:
    result = service.add_business_days(get_settings().db_path, date, days)
    return {"start": date.isoformat(), "days": days, "result": result.isoformat()}


@router.get("/business-days/count")
def business_days_count(start: datetime.date, end: datetime.date) -> dict:
    try:
        n = service.count_business_days(get_settings().db_path, start, end)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"start": start.isoformat(), "end": end.isoformat(), "business_days": n}
