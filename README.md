# Korea Data Suite

Clean, developer-friendly REST APIs for Korean public data.
Korean government open data is powerful but hard to consume — Korean-only docs,
XML responses, legacy auth. This suite normalizes it into simple JSON APIs.

## APIs

| API | Status | Description |
|-----|--------|-------------|
| Holidays & Business Days | ✅ v1 | Korean public holidays (incl. substitute & temporary holidays) and business-day calculations |
| Real Estate Transactions | 🚧 planned | Normalized MOLIT real transaction prices |
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

## Configuration

Environment variables (prefix `KDS_`, `.env` supported):

| Variable | Default | Description |
|----------|---------|-------------|
| `KDS_DEV_MODE` | `false` | Skip API-key auth (local dev) |
| `KDS_API_KEYS` | — | Comma-separated accepted API keys |
| `KDS_PROXY_SECRETS` | — | Comma-separated marketplace proxy secrets |
| `KDS_DB_PATH` | `data/kds.db` | SQLite path |
| `KDS_DATA_GO_KR_KEY` | — | data.go.kr service key (optional; enables weekly sync) |
| `KDS_ENABLE_SCHEDULER` | `true` | Weekly holiday sync scheduler |

## Data sources & attribution

- Holiday data: KASI Special Day Information (한국천문연구원 특일정보),
  via [Korea Public Data Portal (data.go.kr)](https://www.data.go.kr/) — KOGL Type 1.
  Ships with bundled seed data (2025–2027); refreshed weekly when a service key is configured.

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

## License

MIT © choiyounggi
