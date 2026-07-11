import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from app.apis.holidays import store
from app.apis.holidays.router import router as holidays_router
from app.apis.realestate import store as re_store
from app.apis.realestate.router import router as realestate_router
from app.core.auth import require_api_key
from app.core.config import get_settings
from app.core.scheduler import start_scheduler

logger = logging.getLogger(__name__)

APP_VERSION = "0.1.0"

# Security response headers applied to every response (defense-in-depth for a
# JSON API that will be exposed externally; TLS/HSTS is terminated at the edge).
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",  # no MIME sniffing of JSON as HTML/JS
    "X-Frame-Options": "DENY",  # never framed (clickjacking)
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cache-Control": "no-store",  # auth'd data must not sit in shared caches
    "Server": "kds",  # overwrite the uvicorn version/tech disclosure
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.dev_mode:
        logger.warning("KDS_DEV_MODE is ON — API-key auth is DISABLED. Never set this in production.")
    store.init_db(settings.db_path)
    store.load_seed(settings.db_path)
    re_store.init_db(settings.db_path)  # so the realestate API works before the first sync
    scheduler = None
    if settings.enable_scheduler:
        scheduler = start_scheduler()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


_docs_on = get_settings().enable_docs
app = FastAPI(
    title="Korea Data Suite",
    version=APP_VERSION,
    description="Korean public data APIs: holidays, business days, and more.",
    lifespan=lifespan,
    docs_url="/docs" if _docs_on else None,
    redoc_url="/redoc" if _docs_on else None,
    openapi_url="/openapi.json" if _docs_on else None,
)


def _with_security_headers(response):
    for name, value in _SECURITY_HEADERS.items():
        response.headers[name] = value
    return response


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    return _with_security_headers(await call_next(request))


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    # 500s bypass the middleware (ServerErrorMiddleware is outermost), so apply the
    # headers here too — never leak stack traces / internals / Server version on 5xx.
    logger.error("unhandled error on %s %s: %s", request.method, request.url.path, exc)
    return _with_security_headers(
        JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
    )


app.include_router(holidays_router, dependencies=[Depends(require_api_key)])
app.include_router(realestate_router, dependencies=[Depends(require_api_key)])


@app.get("/v1/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": APP_VERSION}
