import sqlite3
from contextlib import closing
from pathlib import Path


def connect(db_path: str) -> sqlite3.Connection:
    """Per-request SQLite connection. Only the cheap, per-connection pragma goes
    here — busy_timeout (~0.04ms). journal_mode/synchronous are ~0.4ms each and
    are set once by enable_wal(); WAL persists on the file so readers need not
    re-assert it every request.
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")  # wait for a lock instead of raising 'database is locked'
    return conn


def enable_wal(db_path: str) -> None:
    """Put the database in WAL mode once (call from init_db at startup).

    WAL lets the API keep reading while the sync process writes (and lets multiple
    uvicorn workers read concurrently) — the core requirement for a read-heavy API
    with a background writer. It is a persistent property of the file.
    """
    with closing(connect(db_path)) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")  # safe under WAL, one less fsync per commit
