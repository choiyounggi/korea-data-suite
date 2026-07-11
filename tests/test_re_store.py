import pytest

from app.apis.realestate import store
from app.apis.realestate.models import Transaction


@pytest.fixture()
def re_db(tmp_path) -> str:
    path = str(tmp_path / "re.db")
    store.init_db(path)
    return path


def _tx(region: str, day: str, trade_type: str = "sale", price: int = 100000000) -> Transaction:
    return Transaction(
        property_type="apartment",
        trade_type=trade_type,
        region_code=region,
        traded_on=day,
        price_won=price,
    )


def test_replace_partition_idempotent(re_db):
    rows = [_tx("11680", "2026-07-01"), _tx("11680", "2026-07-15")]
    store.replace_partition(re_db, "apartment", "sale", "11680", "2026-07", rows)
    store.replace_partition(re_db, "apartment", "sale", "11680", "2026-07", rows)
    assert store.count_by_partition(re_db, "apartment", "sale", "11680", "2026-07") == 2


def test_replace_partition_scoped(re_db):
    store.replace_partition(re_db, "apartment", "sale", "11680", "2026-06", [_tx("11680", "2026-06-10")])
    store.replace_partition(re_db, "apartment", "sale", "11650", "2026-07", [_tx("11650", "2026-07-10")])
    # replacing 강남구 7월 must not touch 강남구 6월 or 서초구 7월
    store.replace_partition(re_db, "apartment", "sale", "11680", "2026-07", [_tx("11680", "2026-07-20")])
    assert store.count_by_partition(re_db, "apartment", "sale", "11680", "2026-06") == 1
    assert store.count_by_partition(re_db, "apartment", "sale", "11650", "2026-07") == 1
    assert store.count_by_partition(re_db, "apartment", "sale", "11680", "2026-07") == 1


def test_query_keyset_no_skip_no_repeat(re_db):
    rows = [_tx("11680", "2026-07-01"), _tx("11680", "2026-07-01"), _tx("11680", "2026-07-01")]
    rows += [_tx("11680", "2026-07-02"), _tx("11680", "2026-07-03"), _tx("11680", "2026-07-04")]
    rows += [_tx("11680", "2026-07-05")]
    store.replace_partition(re_db, "apartment", "sale", "11680", "2026-07", rows)

    seen: list[int] = []
    cursor = None
    for _ in range(10):  # bounded loop guard
        page = store.query_transactions(re_db, "11680", None, None, None, None, 3, cursor)
        if not page:
            break
        seen.extend(r["id"] for r in page)
        last = page[-1]
        cursor = (last["traded_on"], last["id"])
    assert len(seen) == 7
    assert len(set(seen)) == 7  # no repeats


def test_query_filters(re_db):
    store.replace_partition(re_db, "apartment", "sale", "11680", "2026-07", [_tx("11680", "2026-07-10")])
    store.replace_partition(
        re_db, "apartment", "jeonse", "11680", "2026-07",
        [_tx("11680", "2026-07-11", trade_type="jeonse", price=0)],
    )
    store.replace_partition(re_db, "apartment", "sale", "11680", "2026-08", [_tx("11680", "2026-08-05")])

    sales = store.query_transactions(re_db, "11680", "apartment", "sale", None, None, 50, None)
    assert {r["traded_on"] for r in sales} == {"2026-07-10", "2026-08-05"}

    july = store.query_transactions(re_db, "11680", None, None, "2026-07-01", "2026-07-31", 50, None)
    assert {r["traded_on"] for r in july} == {"2026-07-10", "2026-07-11"}

    jeonse = store.query_transactions(re_db, "11680", None, "jeonse", None, None, 50, None)
    assert [r["traded_on"] for r in jeonse] == ["2026-07-11"]


def test_query_empty_region_returns_empty(re_db):
    store.replace_partition(re_db, "apartment", "sale", "11680", "2026-07", [_tx("11680", "2026-07-10")])
    assert store.query_transactions(re_db, "11110", None, None, None, None, 50, None) == []


def test_replace_partition_drops_out_of_month_rows(re_db):
    # BUG-C regression: rows outside deal_ym must not accumulate across re-runs
    rows = [_tx("11680", "2026-07-10"), _tx("11680", "2026-08-01")]  # second is out of 2026-07
    n1 = store.replace_partition(re_db, "apartment", "sale", "11680", "2026-07", rows)
    n2 = store.replace_partition(re_db, "apartment", "sale", "11680", "2026-07", rows)
    assert n1 == 1 and n2 == 1  # only the in-month row is inserted, counts stable
    assert store.count_by_partition(re_db, "apartment", "sale", "11680", "2026-07") == 1
    # the out-of-month row never landed anywhere in this partition's writes
    all_rows = store.query_transactions(re_db, "11680", None, None, None, None, 50, None)
    assert [r["traded_on"] for r in all_rows] == ["2026-07-10"]
