from contextlib import asynccontextmanager

from fastapi import FastAPI

APP_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Korea Data Suite",
    version=APP_VERSION,
    description="Korean public data APIs: holidays, business days, and more.",
    lifespan=lifespan,
)


@app.get("/v1/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": APP_VERSION}
