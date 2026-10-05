#!/bin/bash
# Stop and remove the Juggernaut launchd services.
set -euo pipefail
AGENTS_DIR="$HOME/Library/LaunchAgents"
for svc in bridge agent; do
  launchctl bootout "gui/$UID/com.juggernaut.$svc" 2>/dev/null || true
  rm -f "$AGENTS_DIR/com.juggernaut.$svc.plist"
  echo "removed com.juggernaut.$svc"
done
