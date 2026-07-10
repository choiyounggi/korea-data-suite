import pytest
from fastapi.testclient import TestClient

from app.apis.holidays import store
from app.core.config import get_settings


@pytest.fixture()
def db_path(tmp_path) -> str:
    path = str(tmp_path / "test.db")
    store.init_db(path)
    store.load_seed(path)
    return path


@pytest.fixture()
def client(db_path, monkeypatch):
    monkeypatch.setenv("KDS_DEV_MODE", "false")
    monkeypatch.setenv("KDS_API_KEYS", "test-key")
    monkeypatch.setenv("KDS_PROXY_SECRETS", "proxy-secret")
    monkeypatch.setenv("KDS_DB_PATH", db_path)
    monkeypatch.setenv("KDS_ENABLE_SCHEDULER", "false")
    get_settings.cache_clear()
    from app.main import app

    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()
