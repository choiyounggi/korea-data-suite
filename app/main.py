from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.apis.holidays import store
from app.core.config import get_settings
from app.core.scheduler import start_scheduler

APP_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    store.init_db(settings.db_path)
    store.load_seed(settings.db_path)
    scheduler = None
    if settings.enable_scheduler:
        scheduler = start_scheduler()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="Korea Data Suite",
    version=APP_VERSION,
    description="Korean public data APIs: holidays, business days, and more.",
    lifespan=lifespan,
)


@app.get("/v1/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": APP_VERSION}
