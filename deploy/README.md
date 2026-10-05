# 24/7 operation (macOS)

`deploy/install.sh` registers two `launchd` services that survive terminal
closes, crashes, and reboots:

| Service | What it does |
|---|---|
| `com.juggernaut.bridge` | Watches Base for x402 USDC payments, posts sats to the agent |
| `com.juggernaut.agent` | The Juggernaut itself (Laya brain, 24h epochs, `--auto-approve`) |

Both start at login and are restarted automatically if they exit. For the
agent this closes the death loop by design: exit 42 (starved epoch) is
followed by automatic resurrection — on restart it archives the death
report, absorbs the lesson, and begins a fresh epoch.

## Install

```bash
cd ~/juggernaut
git pull
bash deploy/install.sh
```

## Sleep

`launchd` cannot keep a sleeping Mac awake. For true 24/7:

```bash
sudo pmset -c sleep 0   # never idle-sleep while on the power adapter
```

Notes:
- Closing the lid still sleeps the Mac, unless it is in clamshell mode
  (lid closed, external display + power connected).
- Manual sleep (menu / power button) still works; `pmset` only disables
  *idle* sleep.

## Watching it

```bash
tail -f state/logs/agent.log    # the agent's ticks
tail -f state/logs/bridge.log   # earnings sightings
launchctl print gui/$UID/com.juggernaut.agent | grep -E "state|pid"
```

## Stop / remove

```bash
bash deploy/uninstall.sh
```

## Downtime behavior

- The bridge backfills every missed block on restart; if the agent was
  down when a payment landed, the block is re-scanned until the earning
  is recorded (no silent drops, no double counts).
- The agent's epoch clock only runs while the process is alive: downtime
  pauses the mission, it never kills it. Missed payments ledgered after
  a restart count toward the new epoch.
