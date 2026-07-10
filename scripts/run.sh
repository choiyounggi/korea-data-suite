#!/bin/zsh
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p "$HOME/Library/Logs/kds"
exec "$HOME/.local/bin/uv" run uvicorn app.main:app --host 127.0.0.1 --port 8642
