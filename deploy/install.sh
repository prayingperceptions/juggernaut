#!/bin/bash
# Install the Juggernaut as macOS launchd services (24/7 operation).
# - Starts the bridge + agent at login, restarts them if they crash.
# - An agent death (exit 42) is followed by automatic resurrection:
#   on restart it archives the death report and begins a fresh epoch.
#
# Robust against launchd flakiness: pauses after bootout so the old
# process can exit fully, retries bootstrap, and verifies each service
# actually registered before reporting success.
set -uo pipefail

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

fail=0
for svc in bridge agent; do
  label="com.juggernaut.$svc"
  plist="$AGENTS_DIR/$label.plist"
  render "$REPO/deploy/com.juggernaut.$svc.plist.tmpl" "$plist"

  launchctl bootout "gui/$UID/$label" 2>/dev/null || true
  sleep 3  # let the old process exit fully before re-registering

  ok=0
  for attempt in 1 2 3; do
    if launchctl bootstrap "gui/$UID" "$plist" 2>/dev/null; then
      ok=1
      break
    fi
    sleep 5
  done

  if [ "$ok" = 1 ] && launchctl print "gui/$UID/$label" >/dev/null 2>&1; then
    echo "installed $label"
  else
    echo "FAILED $label -- bootstrap did not take after 3 attempts."
    echo "Last error:"
    launchctl bootstrap "gui/$UID" "$plist" 2>&1 || true
    fail=1
  fi
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

[ "$fail" = 0 ] || exit 1
