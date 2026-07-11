import threading

from app.apis.realestate import store
from app.apis.realestate.models import Transaction
from app.core.db import connect


def _rows(n: int) -> list[Transaction]:
    return [
        Transaction(property_type="apartment", trade_type="sale", region_code="11680",
                    traded_on=f"2026-07-{(i % 28) + 1:02d}", price_won=10**8 + i)
        for i in range(n)
    ]


def test_wal_enabled_after_init(tmp_path):
    db = str(tmp_path / "c.db")
    store.init_db(db)
    with connect(db) as c:
        assert c.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"


def test_busy_timeout_set_on_connection(tmp_path):
    db = str(tmp_path / "c.db")
    store.init_db(db)
    with connect(db) as c:
        assert c.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_concurrent_reads_during_writes_no_lock_errors(tmp_path):
    # WAL + busy_timeout: readers proceed during a writer with no 'database is locked'
    db = str(tmp_path / "c.db")
    store.init_db(db)
    store.replace_partition(db, "apartment", "sale", "11680", "2026-07", _rows(500))
    errors: list = []
    stop = threading.Event()

    def writer():
        while not stop.is_set():
            try:
                store.replace_partition(db, "apartment", "sale", "11680", "2026-06", _rows(500))
            except Exception as e:  # noqa: BLE001
                errors.append(("write", type(e).__name__))

    def reader():
        for _ in range(200):
            try:
                store.query_transactions(db, "11680", "apartment", "sale", None, None, 50, None)
            except Exception as e:  # noqa: BLE001
                errors.append(("read", type(e).__name__))

    wt = threading.Thread(target=writer)
    wt.start()
    readers = [threading.Thread(target=reader) for _ in range(4)]
    for t in readers:
        t.start()
    for t in readers:
        t.join()
    stop.set()
    wt.join()
    assert errors == [], f"lock errors under concurrency: {errors[:3]}"
