"""Generate the programmatic-SEO static marketing site from the live DB.

For every region that has *real* transaction data (gated by MIN_SALE_ROWS, so we
never publish thin/doorway pages), emit one Korean-language landing page backed by
actual MOLIT stats — the query users type ("강남구 아파트 실거래가 API") resolves to a
page with real numbers plus the API call that returns them. Also emits an always-
populated holidays pillar page, a home page, sitemap.xml and robots.txt.

    uv run python scripts/gen_site.py [--out site/dist] [--db data/kds.db]

Site URL / CTA link come from env so the same generator works for any domain:
    KDS_SITE_URL   (e.g. https://data.example.com)   — canonical/sitemap base
    KDS_CTA_URL    (RapidAPI listing URL)             — signup call-to-action
"""
import argparse
import html
import os
import sqlite3
import statistics
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.apis.realestate.regions import REGIONS  # noqa: E402

# A region needs at least this many apartment-sale rows to earn a page. Below it,
# the page would be thin content (Google penalizes mass-produced empty pages), so
# we skip it — quality gate over raw page count.
MIN_SALE_ROWS = 30
RECENT_SAMPLE = 8  # transactions shown in the "recent deals" table

SITE_URL = os.environ.get("KDS_SITE_URL", "https://YOUR-DOMAIN.example").rstrip("/")
CTA_URL = os.environ.get("KDS_CTA_URL", "https://rapidapi.com/")
API_ORIGIN = os.environ.get("KDS_API_ORIGIN", "https://api.YOUR-DOMAIN.example").rstrip("/")


# ─────────────────────────── formatting helpers ───────────────────────────
def slugify(name_en: str) -> str:
    """'Seoul Gangnam-gu' → 'seoul-gangnam-gu' (url-safe, ascii)."""
    out = []
    for ch in name_en.lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in " -_":
            out.append("-")
    slug = "".join(out)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "region"


def median(values: list[float]) -> float | None:
    """Median, or None for an empty input (callers render '—')."""
    return statistics.median(values) if values else None


def won_short(won: float | None) -> str:
    """116_000_0000 → '11.6억', 8_500_0000 → '8,500만'. None → '—'."""
    if won is None:
        return "—"
    won = round(won)
    eok, rest = divmod(won, 100_000_000)
    man = round(rest / 10_000)
    if eok and man:
        return f"{eok}억 {man:,}만"
    if eok:
        return f"{eok}억"
    return f"{man:,}만"


def esc(s) -> str:
    return html.escape(str(s), quote=True)


# ─────────────────────────── data aggregation ───────────────────────────
def _rows(conn, region_code, trade_type):
    return conn.execute(
        """SELECT neighborhood, building_name, traded_on, price_won, deposit_won,
                  monthly_rent_won, area_m2, floor
           FROM property_transactions
           WHERE region_code=? AND property_type='apartment' AND trade_type=?
           ORDER BY traded_on DESC, id DESC""",
        (region_code, trade_type),
    ).fetchall()


def aggregate_region(conn, code: str) -> dict | None:
    """Real stats for one region, or None if it fails the data quality gate."""
    sales = _rows(conn, code, "sale")
    if len(sales) < MIN_SALE_ROWS:
        return None  # gate: not enough real data → no page

    prices = [r["price_won"] for r in sales if r["price_won"]]
    ppm2 = [r["price_won"] / r["area_m2"] for r in sales if r["price_won"] and r["area_m2"]]
    jeonse = _rows(conn, code, "jeonse")
    deposits = [r["deposit_won"] for r in jeonse if r["deposit_won"]]

    # neighborhood breakdown (동별 매매 건수 / 중위가), top by count
    by_hood: dict[str, list[int]] = {}
    for r in sales:
        if r["neighborhood"] and r["price_won"]:
            by_hood.setdefault(r["neighborhood"], []).append(r["price_won"])
    hoods = sorted(
        ({"name": h, "count": len(v), "median": median(v)} for h, v in by_hood.items()),
        key=lambda x: x["count"],
        reverse=True,
    )[:10]

    dates = [r["traded_on"] for r in sales]
    return {
        "code": code,
        "name_ko": REGIONS[code]["name_ko"],
        "name_en": REGIONS[code]["name_en"],
        "slug": slugify(REGIONS[code]["name_en"]),
        "sale_count": len(sales),
        "median_price": median(prices),
        "median_ppm2": median(ppm2),
        "jeonse_count": len(jeonse),
        "median_deposit": median(deposits),
        "date_min": min(dates),
        "date_max": max(dates),
        "recent": sales[:RECENT_SAMPLE],
        "hoods": hoods,
    }


# ─────────────────────────── HTML rendering ───────────────────────────
_CSS = """
:root{--bg:#fff;--fg:#1a1d24;--muted:#5c6470;--line:#e6e8ec;--accent:#2b6cff;--code:#f5f7fa}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;font:16px/1.65 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",Segoe UI,Roboto,sans-serif;color:var(--fg);background:var(--bg)}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
header,main,footer{max-width:880px;margin:0 auto;padding:0 20px}
header{display:flex;align-items:center;justify-content:space-between;height:64px;border-bottom:1px solid var(--line)}
header .brand{font-weight:700;font-size:18px;color:var(--fg)}
.cta{display:inline-block;background:var(--accent);color:#fff;padding:10px 18px;border-radius:8px;font-weight:600}
.cta:hover{text-decoration:none;opacity:.92}
h1{font-size:30px;line-height:1.25;margin:32px 0 8px}h2{font-size:22px;margin:36px 0 12px}
.lede{color:var(--muted);font-size:18px;margin:0 0 8px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:24px 0}
.stat{border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.stat .k{color:var(--muted);font-size:13px}.stat .v{font-size:22px;font-weight:700;margin-top:2px}
table{width:100%;border-collapse:collapse;margin:12px 0;font-size:14px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600}td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.wrap{overflow-x:auto}
pre{background:var(--code);border:1px solid var(--line);border-radius:10px;padding:16px;overflow-x:auto;font-size:13px;line-height:1.5}
code{font-family:"SF Mono",Menlo,Consolas,monospace}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px;margin:16px 0}
.card{border:1px solid var(--line);border-radius:10px;padding:14px}.card .c{color:var(--muted);font-size:13px}
footer{color:var(--muted);font-size:13px;border-top:1px solid var(--line);margin-top:56px;padding-top:24px;padding-bottom:48px}
.faq h3{font-size:16px;margin:18px 0 4px}.faq p{margin:0 0 8px;color:var(--muted)}
"""


def page(title: str, desc: str, canonical: str, body: str, jsonld: list[str]) -> str:
    ld = "\n".join(f'<script type="application/ld+json">{j}</script>' for j in jsonld)
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{esc(canonical)}">
<style>{_CSS}</style>
{ld}
</head>
<body>
<header>
  <a class="brand" href="{esc(SITE_URL)}/">Korea Data Suite</a>
  <a class="cta" href="{esc(CTA_URL)}" rel="nofollow">API 시작하기</a>
</header>
<main>
{body}
</main>
<footer>
  <p>Korea Data Suite — 한국 공공데이터를 개발자 친화적 JSON REST API로. 데이터 출처: 국토교통부 실거래가, 공공데이터포털.</p>
  <p><a href="{esc(SITE_URL)}/">홈</a> · <a href="{esc(SITE_URL)}/holidays/">공휴일·영업일 API</a> · <a href="{esc(CTA_URL)}" rel="nofollow">API 구독</a></p>
</footer>
</body>
</html>
"""


def _jsonld_dataset(agg: dict, url: str) -> str:
    import json
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": f"{agg['name_ko']} 아파트 실거래가 데이터 (JSON API)",
        "description": f"{agg['name_ko']}의 아파트 매매·전세 실거래 정규화 데이터. 최근 {agg['sale_count']}건의 매매 거래 포함.",
        "url": url,
        "keywords": [agg["name_ko"], "실거래가", "아파트", "부동산 API", "MOLIT"],
        "creator": {"@type": "Organization", "name": "Korea Data Suite"},
        "isAccessibleForFree": False,
        "license": "https://www.data.go.kr",
    }, ensure_ascii=False)


def _jsonld_faq(qas: list[tuple[str, str]]) -> str:
    import json
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in qas
        ],
    }, ensure_ascii=False)


def render_region(agg: dict) -> str:
    url = f"{SITE_URL}/realestate/{agg['code']}-{agg['slug']}/"
    ko = agg["name_ko"]
    stat = lambda k, v: f'<div class="stat"><div class="k">{esc(k)}</div><div class="v">{esc(v)}</div></div>'
    stats = "".join([
        stat("매매 거래 건수", f"{agg['sale_count']:,}건"),
        stat("중위 매매가", f"{won_short(agg['median_price'])}원"),
        stat("중위 ㎡당 가격", f"{won_short(agg['median_ppm2'])}원"),
        stat("전세 거래 건수", f"{agg['jeonse_count']:,}건"),
        stat("중위 전세 보증금", f"{won_short(agg['median_deposit'])}원"),
        stat("데이터 기간", f"{agg['date_min']} ~ {agg['date_max']}"),
    ])
    recent = "".join(
        f"<tr><td>{esc(r['neighborhood'] or '')}</td><td>{esc(r['building_name'] or '')}</td>"
        f"<td class='num'>{esc(round(r['area_m2'],1)) if r['area_m2'] else '—'}㎡</td>"
        f"<td class='num'>{esc(r['floor']) if r['floor'] is not None else '—'}층</td>"
        f"<td class='num'>{won_short(r['price_won'])}원</td><td class='num'>{esc(r['traded_on'])}</td></tr>"
        for r in agg["recent"]
    )
    hoods = "".join(
        f"<tr><td>{esc(h['name'])}</td><td class='num'>{h['count']:,}건</td>"
        f"<td class='num'>{won_short(h['median'])}원</td></tr>"
        for h in agg["hoods"]
    )
    curl = (
        f'curl "{API_ORIGIN}/v1/realestate/transactions?region={agg["code"]}'
        f'&property_type=apartment&trade_type=sale" \\\n'
        f'  -H "X-API-Key: YOUR_KEY"'
    )
    qas = [
        (f"{ko} 아파트 실거래가 데이터를 API로 받을 수 있나요?",
         f"네. Korea Data Suite의 실거래가 API에 region={agg['code']} 파라미터로 요청하면 "
         f"{ko}의 아파트 매매·전세 실거래 데이터를 정규화된 JSON으로 받을 수 있습니다. 커서 페이지네이션과 기간 필터를 지원합니다."),
        ("데이터 출처와 갱신 주기는 어떻게 되나요?",
         "국토교통부(MOLIT) 실거래가 공개시스템 원천 데이터를 정규화한 것으로, 매일 자동 동기화됩니다."),
        (f"{ko}의 지역 코드(LAWD)는 무엇인가요?",
         f"{ko}의 법정동 시군구 코드는 {agg['code']}입니다. 이 5자리 코드를 region 파라미터로 사용합니다."),
    ]
    body = f"""
<nav style="font-size:13px;color:#5c6470;margin-top:20px"><a href="{esc(SITE_URL)}/">홈</a> › <a href="{esc(SITE_URL)}/#realestate">실거래가 API</a> › {esc(ko)}</nav>
<h1>{esc(ko)} 아파트 실거래가 API</h1>
<p class="lede">{esc(ko)}(코드 {agg['code']})의 아파트 매매·전세 실거래 데이터를 정규화된 JSON REST API로 조회하세요.
최근 매매 {agg['sale_count']:,}건 · 전세 {agg['jeonse_count']:,}건.</p>
<div class="stats">{stats}</div>

<h2>{esc(ko)} 최근 아파트 매매 실거래</h2>
<div class="wrap"><table>
<thead><tr><th>동</th><th>단지</th><th class="num">전용면적</th><th class="num">층</th><th class="num">거래가</th><th class="num">거래일</th></tr></thead>
<tbody>{recent}</tbody></table></div>

<h2>동별 매매 현황</h2>
<div class="wrap"><table>
<thead><tr><th>법정동</th><th class="num">거래 건수</th><th class="num">중위 매매가</th></tr></thead>
<tbody>{hoods}</tbody></table></div>

<h2>API로 받는 법</h2>
<p>위 데이터 전체를 아래 한 번의 호출로 받을 수 있습니다. 응답은 영문 키의 깔끔한 JSON입니다.</p>
<pre><code>{esc(curl)}</code></pre>
<p><a class="cta" href="{esc(CTA_URL)}" rel="nofollow">무료로 API 키 받기 →</a></p>

<h2 class="faq">자주 묻는 질문</h2>
<div class="faq">
{''.join(f'<h3>{esc(q)}</h3><p>{esc(a)}</p>' for q, a in qas)}
</div>
"""
    desc = (f"{ko} 아파트 실거래가를 JSON API로. 최근 매매 {agg['sale_count']}건, "
            f"중위가 {won_short(agg['median_price'])}원. 국토교통부 정규화 데이터, region={agg['code']}.")
    return page(f"{ko} 아파트 실거래가 API — Korea Data Suite", desc, url, body,
                [_jsonld_dataset(agg, url), _jsonld_faq(qas)])


def render_holidays(conn) -> str:
    url = f"{SITE_URL}/holidays/"
    years = conn.execute(
        "SELECT substr(date,1,4) y, count(*) n FROM holidays GROUP BY y ORDER BY y"
    ).fetchall()
    rows_2026 = conn.execute(
        "SELECT date, name_ko FROM holidays WHERE date LIKE '2026-%' "
        "GROUP BY date, name_ko ORDER BY date"
    ).fetchall()
    table = "".join(f"<tr><td class='num'>{esc(r['date'])}</td><td>{esc(r['name_ko'])}</td></tr>"
                    for r in rows_2026)
    yspan = f"{years[0]['y']}~{years[-1]['y']}" if years else "—"
    curl = (f'curl "{API_ORIGIN}/v1/holidays?year=2026" -H "X-API-Key: YOUR_KEY"\n'
            f'curl "{API_ORIGIN}/v1/business-days/add?date=2026-12-31&days=1" -H "X-API-Key: YOUR_KEY"')
    qas = [
        ("한국 공휴일 API는 대체공휴일도 포함하나요?",
         "네. Korea Data Suite의 공휴일 API는 법정공휴일뿐 아니라 대체공휴일, 임시공휴일, 선거일까지 포함합니다. "
         "대부분의 글로벌 공휴일 API가 한국의 대체·임시공휴일을 놓치는 부분을 정확히 처리합니다."),
        ("영업일(business day) 계산도 되나요?",
         "됩니다. 특정 날짜에 N영업일을 더하거나(주말·공휴일 자동 제외), 기간 내 영업일 수를 세거나, "
         "특정 날짜가 영업일/공휴일인지 확인하는 엔드포인트를 제공합니다."),
    ]
    body = f"""
<nav style="font-size:13px;color:#5c6470;margin-top:20px"><a href="{esc(SITE_URL)}/">홈</a> › 공휴일·영업일 API</nav>
<h1>대한민국 공휴일·영업일 계산 API</h1>
<p class="lede">한국 법정공휴일·대체공휴일·임시공휴일·선거일을 JSON으로. 영업일 덧셈/카운트/판별까지 한 API로.
현재 {yspan} 데이터 제공.</p>
<div class="stats">
<div class="stat"><div class="k">제공 연도</div><div class="v">{esc(yspan)}</div></div>
<div class="stat"><div class="k">대체공휴일</div><div class="v">포함 ✓</div></div>
<div class="stat"><div class="k">임시공휴일</div><div class="v">포함 ✓</div></div>
<div class="stat"><div class="k">영업일 계산</div><div class="v">지원 ✓</div></div>
</div>

<h2>2026년 대한민국 공휴일</h2>
<div class="wrap"><table>
<thead><tr><th class="num">날짜</th><th>공휴일</th></tr></thead>
<tbody>{table}</tbody></table></div>

<h2>API로 받는 법</h2>
<pre><code>{esc(curl)}</code></pre>
<p><a class="cta" href="{esc(CTA_URL)}" rel="nofollow">무료로 API 키 받기 →</a></p>

<h2 class="faq">자주 묻는 질문</h2>
<div class="faq">{''.join(f'<h3>{esc(q)}</h3><p>{esc(a)}</p>' for q, a in qas)}</div>
"""
    desc = ("대한민국 공휴일·영업일 계산 API. 대체공휴일·임시공휴일·선거일 포함, "
            "영업일 덧셈/카운트/판별 지원. 깔끔한 JSON REST.")
    return page("대한민국 공휴일·영업일 API — Korea Data Suite", desc, url, body,
                [_jsonld_faq(qas)])


def render_home(aggs: list[dict]) -> str:
    cards = "".join(
        f'<a class="card" href="{esc(SITE_URL)}/realestate/{a["code"]}-{a["slug"]}/">'
        f'<div>{esc(a["name_ko"])}</div><div class="c">매매 {a["sale_count"]:,}건 · 중위 {won_short(a["median_price"])}원</div></a>'
        for a in sorted(aggs, key=lambda x: x["sale_count"], reverse=True)
    )
    body = f"""
<h1>Korea Data Suite</h1>
<p class="lede">한국 공공데이터를 개발자 친화적인 JSON REST API로. 한국어 문서·XML·레거시 인증 없이, 깔끔한 JSON 한 번의 호출로.</p>
<p><a class="cta" href="{esc(CTA_URL)}" rel="nofollow">API 시작하기 →</a></p>

<h2 id="holidays">공휴일 · 영업일 API</h2>
<p>법정·대체·임시공휴일과 영업일 계산. → <a href="{esc(SITE_URL)}/holidays/">공휴일·영업일 API 보기</a></p>

<h2 id="realestate">실거래가 API — 지역별</h2>
<p>국토교통부 아파트 매매·전세 실거래를 정규화한 JSON. 전국 시군구 지원, 아래는 데이터가 준비된 지역입니다.</p>
<div class="grid">{cards}</div>
"""
    desc = "한국 공공데이터(공휴일·부동산 실거래가)를 개발자 친화적 JSON REST API로 제공하는 Korea Data Suite."
    import json
    website_ld = json.dumps({
        "@context": "https://schema.org", "@type": "WebSite",
        "name": "Korea Data Suite", "url": SITE_URL + "/",
    }, ensure_ascii=False)
    return page("Korea Data Suite — 한국 공공데이터 JSON API", desc, SITE_URL + "/", body, [website_ld])


def sitemap(urls: list[str]) -> str:
    today = date.today().isoformat()
    items = "".join(
        f"<url><loc>{esc(u)}</loc><lastmod>{today}</lastmod></url>" for u in urls
    )
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"{items}</urlset>\n")


# ─────────────────────────── orchestration ───────────────────────────
def build(db_path: str, out_dir: str) -> dict:
    out = Path(out_dir)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        aggs = [a for code in REGIONS if (a := aggregate_region(conn, code))]
        urls = [SITE_URL + "/", SITE_URL + "/holidays/"]

        _write(out / "index.html", render_home(aggs))
        _write(out / "holidays" / "index.html", render_holidays(conn))
        for a in aggs:
            rel = f"realestate/{a['code']}-{a['slug']}/index.html"
            _write(out / rel, render_region(a))
            urls.append(f"{SITE_URL}/realestate/{a['code']}-{a['slug']}/")

        _write(out / "sitemap.xml", sitemap(urls))
        _write(out / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
    finally:
        conn.close()
    return {"regions": len(aggs), "pages": len(urls), "urls": urls}


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Generate the SEO static site from the DB.")
    p.add_argument("--db", default=os.environ.get("KDS_DB_PATH", "data/kds.db"))
    p.add_argument("--out", default="site/dist")
    args = p.parse_args(argv)
    if not Path(args.db).exists():
        print(f"error: db not found: {args.db}", file=sys.stderr)
        return 2
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = build(args.db, args.out)
    print(f"[{stamp}] generated {result['pages']} pages "
          f"({result['regions']} region pages ≥{MIN_SALE_ROWS} rows) → {args.out}")
    print(f"  SITE_URL={SITE_URL}  CTA_URL={CTA_URL}")
    if SITE_URL.endswith(".example"):
        print("  NOTE: set KDS_SITE_URL / KDS_API_ORIGIN / KDS_CTA_URL before deploying.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
