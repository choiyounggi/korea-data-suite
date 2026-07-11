import logging
from contextlib import closing

from app.apis.realestate.models import Transaction
from app.core.db import connect as _conn
from app.core.db import enable_wal

logger = logging.getLogger(__name__)

DDL_TABLE = """
CREATE TABLE IF NOT EXISTS property_transactions (
    id INTEGER PRIMARY KEY,
    property_type TEXT NOT NULL CHECK (property_type IN ('apartment','officetel','land')),
    trade_type TEXT NOT NULL CHECK (trade_type IN ('sale','jeonse','monthly_rent')),
    region_code TEXT NOT NULL,
    neighborhood TEXT,
    building_name TEXT,
    traded_on TEXT NOT NULL,
    price_won INTEGER,
    deposit_won INTEGER,
    monthly_rent_won INTEGER,
    area_m2 REAL,
    floor INTEGER,
    built_year INTEGER
)
"""

DDL_INDEX = """
CREATE INDEX IF NOT EXISTS idx_property_transactions_region_code_traded_on
    ON property_transactions (region_code, traded_on)
"""

_INSERT_SQL = """INSERT INTO property_transactions
    (property_type, trade_type, region_code, neighborhood, building_name,
     traded_on, price_won, deposit_won, monthly_rent_won, area_m2, floor, built_year)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

_SELECT_COLS = (
    "id, property_type, trade_type, region_code, neighborhood, building_name, "
    "traded_on, price_won, deposit_won, monthly_rent_won, area_m2, floor, built_year"
)


def init_db(db_path: str) -> None:
    enable_wal(db_path)
    with closing(_conn(db_path)) as conn, conn:
        conn.execute(DDL_TABLE)
        conn.execute(DDL_INDEX)


def replace_partition(
    db_path: str,
    property_type: str,
    trade_type: str,
    region_code: str,
    deal_ym: str,
    rows: list[Transaction],
) -> int:
    """Atomically replace one (property_type, trade_type, region, month) partition.

    MOLIT rows carry no stable per-row id, so idempotent re-ingestion is a
    delete-by-natural-scope + insert in one transaction (absolute set, not upsert).

    Rows whose traded_on falls outside deal_ym are dropped: DELETE is scoped to the
    partition, so inserting out-of-scope rows would accumulate them across re-runs
    (they are never deleted), breaking idempotency. They belong to another month's
    partition and are ingested when that month is queried.
    """
    scoped = [t for t in rows if t.traded_on.startswith(f"{deal_ym}-")]
    dropped = len(rows) - len(scoped)
    if dropped:
        logger.warning(
            "replace_partition: dropped %s row(s) with traded_on outside %s",
            dropped, deal_ym,
        )
    with closing(_conn(db_path)) as conn, conn:
        conn.execute(
            """DELETE FROM property_transactions
               WHERE property_type = ? AND trade_type = ? AND region_code = ?
                 AND traded_on LIKE ?""",
            (property_type, trade_type, region_code, f"{deal_ym}-%"),
        )
        for t in scoped:
            conn.execute(
                _INSERT_SQL,
                (
                    t.property_type,
                    t.trade_type,
                    t.region_code,
                    t.neighborhood,
                    t.building_name,
                    t.traded_on,
                    t.price_won,
                    t.deposit_won,
                    t.monthly_rent_won,
                    t.area_m2,
                    t.floor,
                    t.built_year,
                ),
            )
    return len(scoped)


def query_transactions(
    db_path: str,
    region_code: str,
    property_type: str | None,
    trade_type: str | None,
    date_from: str | None,
    date_to: str | None,
    limit: int,
    cursor: tuple[str, int] | None,
) -> list[dict]:
    clauses = ["region_code = ?"]
    params: list = [region_code]
    if property_type is not None:
        clauses.append("property_type = ?")
        params.append(property_type)
    if trade_type is not None:
        clauses.append("trade_type = ?")
        params.append(trade_type)
    if date_from is not None:
        clauses.append("traded_on >= ?")
        params.append(date_from)
    if date_to is not None:
        clauses.append("traded_on <= ?")
        params.append(date_to)
    if cursor is not None:
        # keyset: DESC walk continues strictly before the last-seen (traded_on, id)
        clauses.append("(traded_on, id) < (?, ?)")
        params.extend([cursor[0], cursor[1]])
    where = " AND ".join(clauses)
    sql = (
        f"SELECT {_SELECT_COLS} FROM property_transactions WHERE {where} "
        "ORDER BY traded_on DESC, id DESC LIMIT ?"
    )
    params.append(limit)
    with closing(_conn(db_path)) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def count_by_partition(
    db_path: str, property_type: str, trade_type: str, region_code: str, deal_ym: str
) -> int:
    with closing(_conn(db_path)) as conn:
        row = conn.execute(
            """SELECT count(*) AS n FROM property_transactions
               WHERE property_type = ? AND trade_type = ? AND region_code = ?
                 AND traded_on LIKE ?""",
            (property_type, trade_type, region_code, f"{deal_ym}-%"),
        ).fetchone()
    return row["n"]
