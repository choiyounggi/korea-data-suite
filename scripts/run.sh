#!/bin/zsh
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p "$HOME/Library/Logs/kds"
# --no-server-header: uvicorn otherwise adds its own `Server: uvicorn/<ver>` that
# the app middleware cannot remove (it only appends), leaking the tech/version.
exec "$HOME/.local/bin/uv" run uvicorn app.main:app --host 127.0.0.1 --port 8642 --no-server-header
