#!/bin/bash
# Install the Juggernaut as macOS launchd services (24/7 operation).
# - Starts the bridge + agent at login, restarts them if they crash.
# - An agent death (exit 42) is followed by automatic resurrection:
#   on restart it archives the death report and begins a fresh epoch.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
AGENTS_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$AGENTS_DIR" "$REPO/state/logs"

render() {  # render <template> <dest>
  REPO="$REPO" python3 - "$1" "$2" << 'EOF'
import os, sys
tmpl, dest = sys.argv[1], sys.argv[2]
s = open(tmpl).read().replace("{{REPO}}", os.environ["REPO"])
open(dest, "w").write(s)
EOF
}

for svc in bridge agent; do
  render "$REPO/deploy/com.juggernaut.$svc.plist.tmpl" \
         "$AGENTS_DIR/com.juggernaut.$svc.plist"
  launchctl bootout "gui/$UID/com.juggernaut.$svc" 2>/dev/null || true
  launchctl bootstrap "gui/$UID" "$AGENTS_DIR/com.juggernaut.$svc.plist"
  echo "installed com.juggernaut.$svc"
done

echo
echo "Status:  launchctl print gui/$UID/com.juggernaut.agent | head -20"
echo "Logs:    tail -f $REPO/state/logs/agent.log"
echo "Bridge:  tail -f $REPO/state/logs/bridge.log"
echo
echo "For true 24/7 also prevent idle sleep while on power:"
echo "  sudo pmset -c sleep 0"
echo "(Closing the lid still sleeps the Mac unless it is in clamshell mode"
echo "with an external display.)"
