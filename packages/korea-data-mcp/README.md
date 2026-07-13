# Korea Data Suite — MCP server

<!-- mcp-name: io.github.choiyounggi/korea-data-mcp -->

An [MCP](https://modelcontextprotocol.io) server that exposes [Korea Data Suite](https://api.korea-data.cloud)
as tools, so AI agents (Claude Desktop/Code, Cursor, …) can query Korean public
data directly: public holidays & business-day math, and normalized MOLIT
real-estate transactions (apartment/officetel/land; sale/jeonse/monthly-rent).

## Tools

- `get_holidays(year, month?)` — Korean public holidays (incl. substitute/temporary)
- `check_holiday(date)` — is a date a holiday / business day?
- `add_business_days(date, days)` — add N business days (skips weekends & holidays)
- `count_business_days(start, end)` — business days in a range
- `list_real_estate_regions()` — LAWD region codes
- `get_real_estate_transactions(region, property_type?, trade_type?, date_from?, date_to?, limit?, cursor?)`

## Install & run

Bring your own API key (subscribe on the [RapidAPI listing](https://rapidapi.com/dch0202/api/korea-real-estate-holidays)):

```bash
KDS_API_KEY=<your key> uvx korea-data-mcp
```

Before it's on PyPI, install straight from the repo:

```bash
KDS_API_KEY=<your key> uvx --from "git+https://github.com/choiyounggi/korea-data-suite#subdirectory=packages/korea-data-mcp" korea-data-mcp
```

## MCP client config

```json
{
  "mcpServers": {
    "korea-data-suite": {
      "command": "uvx",
      "args": ["korea-data-mcp"],
      "env": {
        "KDS_API_KEY": "your-rapidapi-key",
        "KDS_API_BASE": "https://api.korea-data.cloud"
      }
    }
  }
}
```

Config env: `KDS_API_KEY` (required), `KDS_API_BASE` (default `https://api.korea-data.cloud`).

## License

MIT © choiyounggi
