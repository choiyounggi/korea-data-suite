#!/bin/zsh
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p "$HOME/Library/Logs/kds"
exec "$HOME/.local/bin/uv" run python scripts/sync.py
