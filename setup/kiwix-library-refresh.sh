#!/usr/bin/env bash
# Rebuilds content/library.xml from whatever .zim files currently exist in
# content/zim/. Run before kiwix-serve starts (see systemd/kiwix-serve.service)
# so the service never crashes on an empty or stale library, and reflects
# content dropped in since the last (re)start.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIBRARY="$APP_DIR/content/library.xml"

rm -f "$LIBRARY"

shopt -s nullglob
zims=("$APP_DIR"/content/zim/*.zim)

if [ ${#zims[@]} -eq 0 ]; then
  cat > "$LIBRARY" <<'EOF'
<?xml version="1.0" encoding="UTF-8" ?>
<library version="20110515">
</library>
EOF
else
  for f in "${zims[@]}"; do
    kiwix-manage "$LIBRARY" add "$f"
  done
fi
