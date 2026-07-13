"""Tests for the Korea Data Suite MCP server (mcp_server/server.py).

Covers tool→endpoint routing, and _get()'s JSON parsing, None-param stripping
(boundary), and clear error raising on HTTP failure (error case) — using an
httpx MockTransport so no network is touched.
"""
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp_server import server  # noqa: E402

_REAL_HTTPX_CLIENT = httpx.Client  # captured before any monkeypatch of httpx.Client


def _mock_client_factory(handler):
    """Return a drop-in for httpx.Client that routes through a MockTransport."""
    def factory(**kwargs):
        return _REAL_HTTPX_CLIENT(
            transport=httpx.MockTransport(handler),
            base_url=kwargs.get("base_url", ""),
            headers=kwargs.get("headers"),
            timeout=kwargs.get("timeout"),
        )
    return factory


def test_tools_route_to_expected_endpoints(monkeypatch):
    calls = []
    monkeypatch.setattr(server, "_get", lambda path, params=None: calls.append((path, params)) or {"ok": True})

    server.get_holidays(2026)
    assert calls[-1][0] == "/v1/holidays" and calls[-1][1]["year"] == 2026
    server.check_holiday("2026-03-02")
    assert calls[-1][0] == "/v1/holidays/check"
    server.add_business_days("2026-12-31", 1)
    assert calls[-1][0] == "/v1/business-days/add" and calls[-1][1]["days"] == 1
    server.get_real_estate_transactions("11680", property_type="apartment")
    assert calls[-1][0] == "/v1/realestate/transactions" and calls[-1][1]["region"] == "11680"


def test_get_parses_json_and_strips_none_params(monkeypatch):
    seen = {}

    def handler(request):
        seen["params"] = dict(request.url.params)
        seen["key"] = request.headers.get("x-api-key")
        return httpx.Response(200, json={"data": [1, 2]})

    monkeypatch.setattr(server, "API_KEY", "test-key")
    monkeypatch.setattr(httpx, "Client", _mock_client_factory(handler))

    out = server._get("/v1/holidays", {"year": 2026, "month": None})  # boundary: None dropped
    assert out == {"data": [1, 2]}
    assert "month" not in seen["params"]
    assert seen["params"]["year"] == "2026"
    assert seen["key"] == "test-key"


def test_get_raises_clear_error_on_http_failure(monkeypatch):
    def handler(request):
        return httpx.Response(401, json={"detail": "Invalid or missing API key"})

    monkeypatch.setattr(httpx, "Client", _mock_client_factory(handler))
    with pytest.raises(RuntimeError, match="401"):
        server._get("/v1/holidays", {"year": 2026})
