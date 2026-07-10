import pytest

from app.apis.holidays import store


@pytest.fixture()
def db_path(tmp_path) -> str:
    path = str(tmp_path / "test.db")
    store.init_db(path)
    store.load_seed(path)
    return path
