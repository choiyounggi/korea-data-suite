#!/bin/zsh
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p "$HOME/Library/Logs/kds"
# The API process is read-only: the scheduler runs as a separate launchd job
# (com.choiyounggi.kds-sync) so the daily ingest never competes with request
# handling for the GIL, and so we can run multiple read workers safely (WAL).
export KDS_ENABLE_SCHEDULER=false
# --no-server-header: uvicorn otherwise adds its own `Server: uvicorn/<ver>` that
# the app middleware cannot remove (it only appends), leaking the tech/version.
exec "$HOME/.local/bin/uv" run uvicorn app.main:app \
    --host 127.0.0.1 --port 8642 --no-server-header --workers "${KDS_WORKERS:-2}"
