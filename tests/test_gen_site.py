"""Tests for the programmatic-SEO site generator (scripts/gen_site.py).

Covers the data-quality gate (the whole point — no thin pages), SEO essentials in
rendered pages, sitemap exclusion of skipped regions, and the formatting helpers'
boundary behaviour (empty input, sub-억 values, None).
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import gen_site  # noqa: E402

GANGNAM = "11680"  # real REGIONS codes
JONGNO = "11110"


def _db(tmp_path):
    p = tmp_path / "t.db"
    conn = sqlite3.connect(p)
    conn.execute(
        """CREATE TABLE property_transactions(
            id INTEGER PRIMARY KEY, property_type TEXT, trade_type TEXT, region_code TEXT,
            neighborhood TEXT, building_name TEXT, traded_on TEXT, price_won INTEGER,
            deposit_won INTEGER, monthly_rent_won INTEGER, area_m2 REAL, floor INTEGER,
            built_year INTEGER)"""
    )
    conn.execute("CREATE TABLE holidays(date TEXT, name_ko TEXT, name_en TEXT, type TEXT, source TEXT)")
    conn.executemany(
        "INSERT INTO holidays(date,name_ko,name_en,type,source) VALUES(?,?,'','public','seed')",
        [("2026-01-01", "신정"), ("2026-03-01", "삼일절")],
    )
    return conn, str(p)


def _seed_sales(conn, code, n, price=1_000_000_000, area=84.0):
    conn.executemany(
        """INSERT INTO property_transactions
           (property_type,trade_type,region_code,neighborhood,building_name,traded_on,
            price_won,deposit_won,monthly_rent_won,area_m2,floor,built_year)
           VALUES('apartment','sale',?,?,?,?,?,NULL,NULL,?,?,2015)""",
        [(code, "대치동", f"단지{i}", f"2026-0{(i % 6) + 1}-15", price, area, i % 20 + 1)
         for i in range(n)],
    )
    conn.commit()


# ── formatting helpers: boundary behaviour ──
def test_won_short_boundaries():
    assert gen_site.won_short(None) == "—"          # boundary: None
    assert gen_site.won_short(1_160_000_000) == "11억 6,000만"
    assert gen_site.won_short(85_000_000) == "8,500만"  # sub-억
    assert gen_site.won_short(0) == "0만"


def test_median_and_slugify_boundaries():
    assert gen_site.median([]) is None               # boundary: empty
    assert gen_site.median([2, 4, 6]) == 4
    assert gen_site.slugify("Seoul Gangnam-gu") == "seoul-gangnam-gu"
    assert gen_site.slugify("!!!") == "region"       # boundary: no alnum → fallback


# ── the data-quality gate ──
def test_gate_skips_region_below_threshold(tmp_path):
    conn, _ = _db(tmp_path)
    _seed_sales(conn, JONGNO, gen_site.MIN_SALE_ROWS - 1)  # one short of the gate
    conn.row_factory = sqlite3.Row
    assert gen_site.aggregate_region(conn, JONGNO) is None


def test_gate_passes_and_aggregates(tmp_path):
    conn, _ = _db(tmp_path)
    _seed_sales(conn, GANGNAM, 40, price=2_000_000_000, area=80.0)
    conn.row_factory = sqlite3.Row
    agg = gen_site.aggregate_region(conn, GANGNAM)
    assert agg is not None
    assert agg["sale_count"] == 40
    assert agg["median_price"] == 2_000_000_000
    assert agg["code"] == GANGNAM


# ── rendered page carries SEO essentials ──
def test_region_page_has_seo_essentials(tmp_path, monkeypatch):
    monkeypatch.setattr(gen_site, "SITE_URL", "https://data.test")
    conn, _ = _db(tmp_path)
    _seed_sales(conn, GANGNAM, 40)
    conn.row_factory = sqlite3.Row
    html = gen_site.render_region(gen_site.aggregate_region(conn, GANGNAM))
    assert "<title>" in html and "강남구" in html
    assert '<link rel="canonical" href="https://data.test/realestate/11680-' in html
    assert '"@type": "Dataset"' in html
    assert '"@type": "FAQPage"' in html
    assert "40건" in html  # real count surfaced, not a placeholder


# ── build(): sitemap excludes skipped regions ──
def test_build_excludes_skipped_region_from_sitemap(tmp_path, monkeypatch):
    monkeypatch.setattr(gen_site, "SITE_URL", "https://data.test")
    conn, db_path = _db(tmp_path)
    _seed_sales(conn, GANGNAM, 40)                       # passes gate
    _seed_sales(conn, JONGNO, 5)                          # fails gate
    conn.close()
    out = tmp_path / "dist"
    result = gen_site.build(db_path, str(out))

    sitemap = (out / "sitemap.xml").read_text(encoding="utf-8")
    assert "/realestate/11680-" in sitemap                # generated
    assert "/realestate/11110-" not in sitemap            # skipped
    assert result["regions"] == 1
    assert (out / "holidays" / "index.html").exists()
    assert not (out / "realestate" / "11110-seoul-jongno-gu" / "index.html").exists()
