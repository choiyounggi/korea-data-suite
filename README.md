# Korea Data Suite

<!-- mcp-name: io.github.choiyounggi/korea-data-suite -->

Clean, developer-friendly REST APIs for Korean public data.
Korean government open data is powerful but hard to consume — Korean-only docs,
XML responses, legacy auth. This suite normalizes it into simple JSON APIs.

## APIs

| API | Status | Description |
|-----|--------|-------------|
| Holidays & Business Days | ✅ v1 | Korean public holidays (incl. substitute & temporary holidays) and business-day calculations |
| Real Estate Transactions | ✅ v1 | Normalized MOLIT real transaction prices (apartment/officetel/land, sale & rent) — nationwide (261 sigungu) |
| Address Toolkit | 🚧 planned | Road/lot address conversion, romanization |
| Business Registration | 🚧 planned | BRN validation & enrichment |

## Quick start (self-host)

```bash
uv sync
uv run uvicorn app.main:app --port 8642
curl "http://127.0.0.1:8642/v1/health"
```

## Holidays & Business Days API

```bash
# All holidays in a year (or a month)
curl "http://127.0.0.1:8642/v1/holidays?year=2026" -H "X-API-Key: <key>"

# Is a given date a holiday / business day?
curl "http://127.0.0.1:8642/v1/holidays/check?date=2026-03-02" -H "X-API-Key: <key>"

# Add N business days (skips weekends & holidays)
curl "http://127.0.0.1:8642/v1/business-days/add?date=2026-12-31&days=1" -H "X-API-Key: <key>"

# Count business days in a range (inclusive)
curl "http://127.0.0.1:8642/v1/business-days/count?start=2026-09-21&end=2026-09-27" -H "X-API-Key: <key>"
```

Covers official public holidays, **substitute holidays** (대체공휴일),
**temporary holidays** (임시공휴일), and election days — the cases most
global holiday APIs get wrong for Korea.

## Real Estate Transactions API

Normalized MOLIT (Ministry of Land) real transaction prices — apartment,
officetel, and land; sale, jeonse, and monthly-rent — as clean English JSON
with cursor pagination.

```bash
# Real transaction prices (apartment sales in Gangnam-gu)
curl "http://127.0.0.1:8642/v1/realestate/transactions?region=11680&property_type=apartment&trade_type=sale" -H "X-API-Key: <key>"

# Filter by date range + paginate with the returned cursor
curl "http://127.0.0.1:8642/v1/realestate/transactions?region=11680&date_from=2026-01-01&limit=50&cursor=<next_cursor>" -H "X-API-Key: <key>"

# Region codes (LAWD 5-digit)
curl "http://127.0.0.1:8642/v1/realestate/regions" -H "X-API-Key: <key>"
```

Daily sync ingests the current + previous month; use the backfill CLI for history:

```bash
uv run python scripts/backfill.py --from 2025-01 --to 2025-12 --regions 11680,11650
```

## Configuration

Environment variables (prefix `KDS_`, `.env` supported):

| Variable | Default | Description |
|----------|---------|-------------|
| `KDS_DEV_MODE` | `false` | Skip API-key auth (local dev) |
| `KDS_API_KEYS` | — | Comma-separated accepted API keys |
| `KDS_PROXY_SECRETS` | — | Comma-separated marketplace proxy secrets |
| `KDS_DB_PATH` | `data/kds.db` | SQLite path |
| `KDS_DATA_GO_KR_KEY` | — | data.go.kr service key (optional; enables holiday + real-estate sync) |
| `KDS_ENABLE_SCHEDULER` | `true` | Holiday (weekly) + real-estate (daily) sync scheduler |
| `KDS_RE_REGIONS` | all 261 nationwide sigungu | Comma LAWD codes to sync (subset override) |
| `KDS_RE_DATASETS` | all | Comma dataset keys (apt_trade, apt_rent, offi_trade, offi_rent, land_trade) |

## Data sources & attribution

- Holiday data: KASI Special Day Information (한국천문연구원 특일정보),
  via [Korea Public Data Portal (data.go.kr)](https://www.data.go.kr/) — KOGL Type 1.
  Ships with bundled seed data (2025–2027); refreshed weekly when a service key is configured.
- Real transaction data: MOLIT 실거래가 공개시스템 (국토교통부),
  via [Korea Public Data Portal (data.go.kr)](https://www.data.go.kr/) — KOGL Type 1.

## Run as a daemon (macOS)

```bash
# Install & start (auto-restart on crash, start at login)
./scripts/install-daemon.sh

# With Cloudflare Tunnel (after one-time `cloudflared tunnel login/create`)
./scripts/install-daemon.sh --with-tunnel

# Logs
tail -f ~/Library/Logs/kds/api.out.log

# Uninstall
launchctl bootout "gui/$(id -u)" ~/Library/LaunchAgents/com.choiyounggi.kds-api.plist
rm ~/Library/LaunchAgents/com.choiyounggi.kds-api.plist
```

To keep the machine awake for serving, disable system sleep
(`sudo pmset -a sleep 0`) or use a dedicated always-on machine.
See `deploy/cloudflared.example.yml` for exposing the API via Cloudflare Tunnel
without opening ports.

### Handling concurrent traffic

The read path and the write path are separated so traffic scales independently:

- **SQLite in WAL mode** (set once at init) + `busy_timeout` — readers never block
  the daily writer and vice-versa, and multiple read workers can run concurrently.
- **API process is read-only, multi-worker.** `scripts/run.sh` runs uvicorn with
  `--workers ${KDS_WORKERS:-2}` and `KDS_ENABLE_SCHEDULER=false`. Each worker is a
  separate process (separate GIL); WAL lets them all read at once. Raise
  `KDS_WORKERS` to scale reads with cores.
- **The daily ingest runs as its own process** (`com.choiyounggi.kds-sync`,
  04:00) via `scripts/sync.py` — never inside the API server, so a multi-thousand-row
  batch never competes with request handling for the GIL.
- **Edge caching** (optional): responses carry `Cache-Control: no-store` for
  security. The real-estate data is public and changes at most daily — if origin
  load grows, serve it with a short `Cache-Control: public, max-age=...` and let
  the CDN absorb reads.

### Security checklist before exposing externally

The app is hardened at the code layer (API-key auth fail-closed, parameterized
SQL, strict input validation, security headers on every response including 5xx,
docs/schema off by default, sanitized errors). The following are **edge/deploy
responsibilities** that must be in place before opening the tunnel:

- **Never set `KDS_DEV_MODE=true` in production** — it disables all auth. The
  app logs a warning at startup if it is on.
- **Cloudflare rate limiting + WAF** on the tunnel hostname — the app has no
  app-layer rate limit by design (edge responsibility).
- **HSTS + TLS** are terminated at the Cloudflare edge; confirm HSTS is enabled
  there (the origin serves plain HTTP on `127.0.0.1` only).
- Keep `KDS_ENABLE_DOCS` unset (or `false`) in production; set `true` only to
  serve `/docs` `/openapi.json` at the origin.

## SEO marketing site (programmatic)

A static, SEO-optimized marketing site is generated **from the live DB** by
`scripts/gen_site.py`. For every region that has real transaction data it emits a
Korean landing page (the query users actually type — "강남구 아파트 실거래가 API" — backed
by real MOLIT stats, a working `curl` example, and a signup CTA), plus a holidays
pillar page, a home page, `sitemap.xml`, and `robots.txt`.

**Quality gate (important):** a region is only published if it has at least
`MIN_SALE_ROWS` (30) apartment-sale rows. Regions without enough data are skipped —
this deliberately avoids thin/doorway pages, which search engines penalize.

```bash
# generate into site/dist (reads data/kds.db)
uv run python scripts/gen_site.py --out site/dist
```

Config is env-driven so the same generator works for any domain (put these in
`deploy/site.env`, gitignored — copy `deploy/site.env.example`):

| Env | Meaning |
|-----|---------|
| `KDS_SITE_URL` | canonical/sitemap base, e.g. `https://korea-data.cloud` |
| `KDS_API_ORIGIN` | origin shown in the on-page `curl` examples, e.g. `https://api.korea-data.cloud` |
| `KDS_CTA_URL` | signup call-to-action (RapidAPI / Zyla / Postman listing) |
| `KDS_SITE_DIR` | output dir the app serves (default `site/dist`) |

### Serving — the API app serves it

The FastAPI app serves `site/dist` at **all non-API paths** (`app.mount("/")`),
while `/v1/*` stays the JSON API. The two get different response headers: the API
keeps its locked-down `default-src 'none'` CSP + `no-store`; the site gets an
HTML-renderable CSP (`script-src 'none'`, inline styles allowed) + `public` cache.
Files are read from disk per request, so **regenerating the site goes live with no
app restart** — only a code change needs a restart.

The site is served on the **same host as the API** (`api.korea-data.cloud`) — the
API lives under `/v1`, the site everywhere else — so no new tunnel hostname or DNS
is needed. One-time on the serving host:

```bash
cp deploy/site.env.example deploy/site.env    # KDS_SITE_URL == KDS_API_ORIGIN == https://api.korea-data.cloud
uv run python scripts/gen_site.py --out site/dist   # generate once
# restart the API app so this integration (new code) takes effect — the site is
# then live at https://api.korea-data.cloud/ , /holidays/ , /realestate/... .
```

Submit `https://api.korea-data.cloud/sitemap.xml` once in Google Search Console.

> Want the site on a bare `korea-data.cloud` / `www` later? Add an ingress rule
> pointing that hostname at the same `http://127.0.0.1:8642`, route its DNS, and
> switch `KDS_SITE_URL` to it. Not required — the api host works for SEO today.

> First run needs history: the daily sync only ingests the current month. To give
> pages real depth, backfill once —
> `uv run python scripts/backfill.py --from 2025-07 --to 2026-06 --regions <codes> --datasets apt_trade,apt_rent`.

### Automate (macOS daemon)

`deploy/com.choiyounggi.kds-site.plist` regenerates the site daily at 04:30 (right
after the 04:00 sync) via `scripts/publish_site.sh`. Because the app serves from
disk, the refreshed pages are live immediately — no restart, no external deploy:

```bash
cp deploy/com.choiyounggi.kds-site.plist ~/Library/LaunchAgents/
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.choiyounggi.kds-site.plist
tail -f ~/Library/Logs/kds/site.out.log
```

> Uptime note: since the site is served by the local app (not a CDN), its SEO
> availability tracks the machine — keep it awake for serving (`pmset`, as the API
> already requires). If always-on hosting is wanted later, the same `site/dist` can
> be pushed to Cloudflare Pages instead.

## MCP server (AI-agent access)

`mcp_server/` exposes the API as a [Model Context Protocol](https://modelcontextprotocol.io)
server so AI agents (Claude Desktop/Code, Cursor, …) can discover and call the
endpoints directly — the agent-era discovery channel alongside the REST API.

**Tools:** `get_holidays`, `check_holiday`, `add_business_days`,
`count_business_days`, `list_real_estate_regions`, `get_real_estate_transactions`.

Each user supplies **their own** API key (from the RapidAPI listing) via
`KDS_API_KEY`. Install + run straight from this public repo with `uvx` — no clone:

```bash
KDS_API_KEY=<your key> uvx --from git+https://github.com/choiyounggi/korea-data-suite korea-data-mcp
```

Add to an MCP client (e.g. Claude Desktop `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "korea-data-suite": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/choiyounggi/korea-data-suite", "korea-data-mcp"],
      "env": {
        "KDS_API_KEY": "your-rapidapi-key",
        "KDS_API_BASE": "https://api.korea-data.cloud"
      }
    }
  }
}
```

Or with Claude Code:

```bash
claude mcp add korea-data-suite --env KDS_API_KEY=<key> \
  -- uvx --from git+https://github.com/choiyounggi/korea-data-suite korea-data-mcp
```

Once published to PyPI, this shortens to `uvx korea-data-suite`. Config env:
`KDS_API_KEY` (required), `KDS_API_BASE` (default `https://api.korea-data.cloud`).
This server is described by [`server.json`](./server.json) for the
[MCP Registry](https://registry.modelcontextprotocol.io/).

## License

MIT © choiyounggi
