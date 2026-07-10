import json
import sqlite3
from pathlib import Path

from app.apis.holidays.models import Holiday

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


def _conn(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    with _conn(db_path) as conn:
        conn.execute(DDL)


def upsert_holidays(db_path: str, holidays: list[Holiday], source: str) -> int:
    with _conn(db_path) as conn:
        for h in holidays:
            conn.execute(
                """INSERT INTO holidays (date, name_ko, name_en, type, source)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(date, name_ko) DO UPDATE
                   SET name_en = excluded.name_en, type = excluded.type, source = excluded.source""",
                (h.date, h.name_ko, h.name_en, h.type, source),
            )
    return len(holidays)


def load_seed(db_path: str) -> int:
    rows = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    return upsert_holidays(db_path, [Holiday(**r) for r in rows], source="seed")


def get_holidays(db_path: str, year: int, month: int | None = None) -> list[Holiday]:
    prefix = f"{year:04d}-{month:02d}-%" if month else f"{year:04d}-%"
    with _conn(db_path) as conn:
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
    with _conn(db_path) as conn:
        rows = conn.execute(
            f"SELECT DISTINCT date FROM holidays WHERE {clauses}", params
        ).fetchall()
    return {r["date"] for r in rows}


def names_on(db_path: str, date: str) -> list[str]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT name_ko FROM holidays WHERE date = ? ORDER BY name_ko", (date,)
        ).fetchall()
    return [r["name_ko"] for r in rows]
