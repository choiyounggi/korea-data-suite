import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.apis.holidays import store
from app.apis.holidays.router import router as holidays_router
from app.apis.realestate import store as re_store
from app.apis.realestate.router import router as realestate_router
from app.core.auth import require_api_key
from app.core.config import get_settings
from app.core.scheduler import start_scheduler

logger = logging.getLogger(__name__)

APP_VERSION = "0.1.0"

# Security response headers for the JSON API (defense-in-depth for an externally
# exposed API; TLS/HSTS is terminated at the edge). Locked all the way down.
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",  # no MIME sniffing of JSON as HTML/JS
    "X-Frame-Options": "DENY",  # never framed (clickjacking)
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cache-Control": "no-store",  # auth'd data must not sit in shared caches
    "Server": "kds",  # overwrite the uvicorn version/tech disclosure
}

# Headers for the generated SEO marketing site (static HTML at non-API paths). It
# must render inline <style> and be cacheable — so it needs its own, still-safe
# policy rather than the API's locked-down one. No user input is ever reflected
# (every value is HTML-escaped at generation), so 'unsafe-inline' for style is low
# risk here; scripts remain fully blocked.
_SITE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'none'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
    "Cache-Control": "public, max-age=300",  # public data, refreshed at most daily
    "Server": "kds",
}

# Docs (when enabled) are an API concern; everything under /v1 is the API. All
# other paths are the static marketing site.
_API_PATHS = ("/docs", "/redoc", "/openapi.json")


def _is_api_path(path: str) -> bool:
    return path.startswith("/v1") or path in _API_PATHS


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


def _with_security_headers(response, path: str = ""):
    headers = _SECURITY_HEADERS if _is_api_path(path) else _SITE_HEADERS
    for name, value in headers.items():
        response.headers[name] = value
    return response


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    return _with_security_headers(await call_next(request), request.url.path)


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    # 500s bypass the middleware (ServerErrorMiddleware is outermost), so apply the
    # headers here too — never leak stack traces / internals / Server version on 5xx.
    logger.error("unhandled error on %s %s: %s", request.method, request.url.path, exc)
    return _with_security_headers(
        JSONResponse(status_code=500, content={"detail": "Internal Server Error"}),
        request.url.path,
    )


app.include_router(holidays_router, dependencies=[Depends(require_api_key)])
app.include_router(realestate_router, dependencies=[Depends(require_api_key)])


@app.get("/v1/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": APP_VERSION}


# The generated SEO marketing site is served at all non-API paths. Mounted LAST so
# every /v1 route and /health takes precedence; check_dir=False lets the app boot
# even before the site is generated (those paths simply 404). Files are read from
# disk per request, so regenerating the site goes live without an app restart.
app.mount(
    "/",
    StaticFiles(directory=get_settings().site_dir, html=True, check_dir=False),
    name="site",
)
