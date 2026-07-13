"""The FastAPI app also serves the generated SEO static site at non-API paths.

The security-critical property is that folding a public HTML site into the same
app must NOT relax the locked-down headers on the /v1 JSON API. These are
regression tests for that boundary (they need no generated files — the header
branching is applied by middleware even on a 404), plus a serving smoke test that
skips when the site has not been generated.
"""
from pathlib import Path

import pytest

API_CSP = "default-src 'none'; frame-ancestors 'none'"


def test_api_path_keeps_locked_down_headers(client):
    # regression: the API must stay maximally hardened after the site was added.
    r = client.get("/v1/health")
    assert r.status_code == 200
    assert r.headers["content-security-policy"] == API_CSP
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-frame-options"] == "DENY"


def test_non_api_path_gets_relaxed_site_headers(client):
    # a non-/v1 path is the marketing site: HTML-renderable CSP + cacheable.
    # True even for a missing path (middleware applies headers before the 404),
    # so this asserts the branching itself, independent of generated files.
    r = client.get("/definitely-not-an-api-route-xyz")
    csp = r.headers["content-security-policy"]
    assert csp != API_CSP                       # not the locked-down API policy
    assert "style-src 'self' 'unsafe-inline'" in csp   # inline <style> can render
    assert "script-src 'none'" in csp           # scripts still fully blocked
    assert r.headers["cache-control"].startswith("public")
    assert r.headers["x-frame-options"] == "SAMEORIGIN"


def test_api_auth_still_enforced_after_site_mount(client):
    # boundary: mounting a public site at "/" must not open a hole in API auth.
    assert client.get("/v1/holidays?year=2026").status_code == 401


def test_serves_generated_index_when_present(client):
    # serving smoke test — skips cleanly when the site hasn't been generated
    # (site/dist is gitignored / built on demand).
    if not Path("site/dist/index.html").exists():
        pytest.skip("site not generated (run scripts/gen_site.py)")
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Korea Data Suite" in r.text
