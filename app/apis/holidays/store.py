import json
from contextlib import closing
from pathlib import Path

from app.apis.holidays.models import Holiday
from app.core.db import connect as _conn
from app.core.db import enable_wal

SEED_PATH = Path(__file__).parent / "seed.json"

DDL = """
CREATE TABLE IF NOT EXISTS holidays (
    date TEXT NOT NULL,
    name_ko TEXT NOT NULL,
    name_en TEXT,
    type TEXT NOT NULL,
    source TEXT NOT NULL,
    PRIMARY KEY (date, name_ko)
)
"""

_UPSERT_SQL = """INSERT INTO holidays (date, name_ko, name_en, type, source)
   VALUES (?, ?, ?, ?, ?)
   ON CONFLICT(date, name_ko) DO UPDATE
   SET name_en = excluded.name_en, type = excluded.type, source = excluded.source"""


def init_db(db_path: str) -> None:
    enable_wal(db_path)
    with closing(_conn(db_path)) as conn, conn:
        conn.execute(DDL)


def upsert_holidays(db_path: str, holidays: list[Holiday], source: str) -> int:
    with closing(_conn(db_path)) as conn, conn:
        for h in holidays:
            conn.execute(_UPSERT_SQL, (h.date, h.name_ko, h.name_en, h.type, source))
    return len(holidays)


def replace_year(db_path: str, year: int, holidays: list[Holiday], source: str) -> int:
    """Atomically replace all rows of a year — the sync source is authoritative.

    Upserting synced rows on top of seed rows would duplicate dates whenever the
    upstream uses different names (e.g. seed '성탄절' vs KASI '기독탄신일').
    """
    with closing(_conn(db_path)) as conn, conn:
        conn.execute("DELETE FROM holidays WHERE date LIKE ?", (f"{year:04d}-%",))
        for h in holidays:
            conn.execute(_UPSERT_SQL, (h.date, h.name_ko, h.name_en, h.type, source))
    return len(holidays)


def load_seed(db_path: str) -> int:
    rows = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    return upsert_holidays(db_path, [Holiday(**r) for r in rows], source="seed")


def get_holidays(db_path: str, year: int, month: int | None = None) -> list[Holiday]:
    prefix = f"{year:04d}-{month:02d}-%" if month else f"{year:04d}-%"
    with closing(_conn(db_path)) as conn:
        rows = conn.execute(
            "SELECT date, name_ko, name_en, type FROM holidays WHERE date LIKE ? ORDER BY date, name_ko",
            (prefix,),
        ).fetchall()
    return [Holiday(**dict(r)) for r in rows]


def holiday_dates(db_path: str, years: list[int]) -> set[str]:
    if not years:
        return set()
    clauses = " OR ".join(["date LIKE ?"] * len(years))
    params = [f"{y:04d}-%" for y in years]
    with closing(_conn(db_path)) as conn:
        rows = conn.execute(
            f"SELECT DISTINCT date FROM holidays WHERE {clauses}", params
        ).fetchall()
    return {r["date"] for r in rows}


def covered_years(db_path: str) -> set[int]:
    with closing(_conn(db_path)) as conn:
        rows = conn.execute("SELECT DISTINCT substr(date, 1, 4) AS y FROM holidays").fetchall()
    return {int(r["y"]) for r in rows}


def names_on(db_path: str, date: str) -> list[str]:
    with closing(_conn(db_path)) as conn:
        rows = conn.execute(
            "SELECT name_ko FROM holidays WHERE date = ? ORDER BY name_ko", (date,)
        ).fetchall()
    return [r["name_ko"] for r in rows]
