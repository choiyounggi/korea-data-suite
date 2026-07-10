#!/bin/zsh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
AGENTS_DIR="$HOME/Library/LaunchAgents"
UID_NUM="$(id -u)"

mkdir -p "$AGENTS_DIR" "$HOME/Library/Logs/kds"

install_agent() {
    local name="$1"
    local src="$REPO_DIR/deploy/$name.plist"
    local dst="$AGENTS_DIR/$name.plist"
    cp "$src" "$dst"
    launchctl bootout "gui/$UID_NUM" "$dst" 2>/dev/null || true
    launchctl bootstrap "gui/$UID_NUM" "$dst"
    echo "installed: $name"
}

install_agent "com.choiyounggi.kds-api"

if [[ "${1:-}" == "--with-tunnel" ]]; then
    if [[ ! -x /opt/homebrew/bin/cloudflared ]]; then
        echo "cloudflared not found — brew install cloudflared 후 재실행" >&2
        exit 1
    fi
    install_agent "com.choiyounggi.kds-tunnel"
fi

sleep 3
launchctl list | grep com.choiyounggi.kds || true
curl -s --max-time 5 http://127.0.0.1:8642/v1/health && echo
