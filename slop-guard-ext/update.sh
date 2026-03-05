#!/usr/bin/env bash
# Pull latest slop-guard and regenerate the bundle.
# Usage: ./update.sh [path-to-slop-guard-repo]

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

REPO="${1:-}"
if [ -z "$REPO" ]; then
    REPO="/tmp/slop-guard-latest"
    echo "Cloning latest slop-guard into $REPO …"
    rm -rf "$REPO"
    git clone --depth 1 https://github.com/eric-tramel/slop-guard.git "$REPO"
fi

cd "$SCRIPT_DIR"
python3 bundle.py "$REPO"

if [ ! -f "manifest.json" ]; then
    echo ""
    echo "⚠  No manifest.json found. First-time setup:"
    echo "   Chrome:  cp manifest.chrome.json manifest.json"
    echo "   Firefox: cp manifest.firefox.json manifest.json"
fi

echo ""
echo "Reload the extension in your browser:"
echo "  Chrome:  chrome://extensions → reload Slop Guard"
echo "  Firefox: about:debugging → This Firefox → Reload"
