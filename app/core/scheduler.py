import datetime
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.apis.holidays import kasi, store
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def sync_holidays() -> int:
    settings = get_settings()
    if not settings.data_go_kr_key:
        logger.info("KDS_DATA_GO_KR_KEY not set — skipping KASI sync (seed data only)")
        return 0
    today = datetime.date.today()
    total = 0
    for year in (today.year, today.year + 1):
        holidays = kasi.fetch_year(year, settings.data_go_kr_key)
        if holidays:
            # upsert가 아니라 연도 교체 — 시드와 KASI의 이름이 다르면(성탄절 vs 기독탄신일)
            # upsert는 같은 날짜에 중복 행을 만든다. 동기화 소스가 그 연도의 정본.
            total += store.replace_year(settings.db_path, year, holidays, source="kasi")
    logger.info("KASI sync upserted %s rows", total)
    return total


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    scheduler.add_job(
        sync_holidays,
        CronTrigger(day_of_week="mon", hour=3, minute=0, timezone="Asia/Seoul"),
        id="kasi-weekly-sync",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        sync_holidays,
        id="kasi-initial-sync",
        next_run_time=datetime.datetime.now(),
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    return scheduler
