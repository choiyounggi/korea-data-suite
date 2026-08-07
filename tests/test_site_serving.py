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


def test_head_on_api_route_is_not_swallowed_by_the_mount(client):
    # regression: FastAPI does not add HEAD to GET routes, so before the fix a HEAD
    # fell through to the StaticFiles mount and came back 404 — reading to uptime
    # monitors as a dead endpoint while GET happily returned 200.
    r = client.head("/v1/health")
    assert r.status_code == 200
    assert r.headers["content-security-policy"] == API_CSP  # still the API headers
    assert r.content == b""  # HEAD carries no body


def test_head_mirrors_get_on_authed_routes(client):
    # the fix must cover every GET route, not just the health check.
    headers = {"X-API-Key": "test-key"}
    assert client.head("/v1/holidays?year=2026", headers=headers).status_code == 200
    assert client.get("/v1/holidays?year=2026", headers=headers).status_code == 200


def test_head_still_enforces_auth(client):
    # boundary: opening HEAD must not become a way to probe the API unauthenticated.
    assert client.head("/v1/holidays?year=2026").status_code == 401


def test_head_on_unknown_path_still_falls_through_to_the_site(client):
    # the mount keeps owning non-API paths — the fix is scoped to declared routes.
    # Needs the real mount to serve, so it skips like the smoke test below.
    if not Path("site/dist").is_dir():
        pytest.skip("site not generated (run scripts/gen_site.py)")
    assert client.head("/definitely-not-an-api-route-xyz").status_code == 404


def test_unsupported_method_on_api_route_is_405_not_404(client):
    # a method the route genuinely does not implement must still report 405 — the
    # mount answers it, so this guards that opening HEAD did not widen anything else.
    if not Path("site/dist").is_dir():
        pytest.skip("site not generated (run scripts/gen_site.py)")
    assert client.post("/v1/health").status_code == 405


def test_serves_generated_index_when_present(client):
    # serving smoke test — skips cleanly when the site hasn't been generated
    # (site/dist is gitignored / built on demand).
    if not Path("site/dist/index.html").exists():
        pytest.skip("site not generated (run scripts/gen_site.py)")
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Korea Data Suite" in r.text
