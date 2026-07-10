from fastapi import HTTPException, Request

from app.core.config import get_settings

_KEY_HEADERS = ("x-api-key", "x-rapidapi-proxy-secret", "x-proxy-secret")


def require_api_key(request: Request) -> None:
    settings = get_settings()
    if settings.dev_mode:
        return
    allowed = settings.allowed_keys
    for header in _KEY_HEADERS:
        value = request.headers.get(header, "")
        if value and value in allowed:
            return
    raise HTTPException(status_code=401, detail="Invalid or missing API key")
