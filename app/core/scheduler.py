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
            total += store.upsert_holidays(settings.db_path, holidays, source="kasi")
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
