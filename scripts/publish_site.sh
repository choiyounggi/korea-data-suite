#!/usr/bin/env bash
# Regenerate the SEO static site from the current DB and deploy it to Cloudflare
# Pages. Idempotent — safe to run on a schedule (the daily sync updates the DB,
# this rebuilds the pages and redeploys). Pages that lost their data are dropped.
#
# One-time setup (interactive, by you):
#   npm i -g wrangler            # or use `npx wrangler`
#   wrangler login               # browser auth, once
#   wrangler pages project create kds-site   # or set KDS_PAGES_PROJECT below
#
# Config via env (put these in a .env or the launchd plist, NOT committed):
#   KDS_SITE_URL     e.g. https://data.yourdomain.com   (canonical/sitemap base)
#   KDS_API_ORIGIN   e.g. https://api.yourdomain.com     (shown in curl examples)
#   KDS_CTA_URL      your RapidAPI (and later Zyla/Postman) listing URL
#   KDS_PAGES_PROJECT  Cloudflare Pages project name (default: kds-site)
set -euo pipefail

cd "$(dirname "$0")/.."

# Site/deploy config lives in deploy/site.env (gitignored) so the domain and any
# Cloudflare token never land in a committed plist or the repo. See site.env.example.
if [ -f deploy/site.env ]; then
  set -a; . deploy/site.env; set +a
fi

: "${KDS_SITE_URL:?set KDS_SITE_URL (e.g. https://data.yourdomain.com)}"
: "${KDS_CTA_URL:?set KDS_CTA_URL (your API marketplace listing URL)}"
PROJECT="${KDS_PAGES_PROJECT:-kds-site}"
OUT="site/dist"

echo "[publish] regenerating site → $OUT"
uv run python scripts/gen_site.py --out "$OUT"

echo "[publish] deploying to Cloudflare Pages project '$PROJECT'"
npx --yes wrangler pages deploy "$OUT" --project-name "$PROJECT" --commit-dirty=true

echo "[publish] done. Live at $KDS_SITE_URL"
echo "[publish] reminder: submit $KDS_SITE_URL/sitemap.xml in Google Search Console (one-time)."
