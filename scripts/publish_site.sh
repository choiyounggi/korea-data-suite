#!/usr/bin/env bash
# Regenerate the SEO static site from the current DB. The running API app serves
# site/dist at all non-API paths and reads files from disk per request, so a
# regenerate goes live immediately — no app restart, no external deploy step.
# Idempotent and safe to run on a schedule (see deploy/com.choiyounggi.kds-site.plist).
#
# Config via deploy/site.env (gitignored; copy site.env.example), sourced below:
#   KDS_SITE_URL     e.g. https://korea-data.cloud   (canonical/sitemap base)
#   KDS_API_ORIGIN   e.g. https://api.korea-data.cloud (shown in curl examples)
#   KDS_CTA_URL      your API marketplace listing URL  (signup CTA)
#   KDS_SITE_DIR     output dir (default site/dist; must match the app's KDS_SITE_DIR)
set -euo pipefail

# uv (and other user-installed CLIs) live in ~/.local/bin, which launchd and
# non-interactive SSH do NOT put on PATH — add it so `uv` resolves in both.
export PATH="$HOME/.local/bin:$PATH"

cd "$(dirname "$0")/.."

if [ -f deploy/site.env ]; then
  set -a; . deploy/site.env; set +a
fi

: "${KDS_SITE_URL:?set KDS_SITE_URL (e.g. https://korea-data.cloud) in deploy/site.env}"
: "${KDS_CTA_URL:?set KDS_CTA_URL (your API marketplace listing URL) in deploy/site.env}"
OUT="${KDS_SITE_DIR:-site/dist}"

echo "[publish] regenerating site → $OUT"
uv run python scripts/gen_site.py --out "$OUT"
echo "[publish] done — live immediately via the running app at $KDS_SITE_URL"
echo "[publish] first time only: submit $KDS_SITE_URL/sitemap.xml in Google Search Console."
