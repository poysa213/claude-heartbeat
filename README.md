# claude-anchor

Align your Claude **5-hour usage window** to your own schedule.

Claude's usage limits run on a rolling 5-hour window that starts the moment you
send your first message — and **reset time = first-message time + 5 hours**. If
you accidentally send one message at 6 AM, your window resets at 11 AM, right in
the middle of your workday. `claude-anchor` sends one tiny message at a time you
choose, so your window always starts (and resets) exactly when you want.

It's the thing you'd do by hand every morning — just automated, and reliable
even while your Mac is asleep.

> This does not raise, bypass, or defeat any limit. It only schedules a single
> normal message you could send yourself, so your existing quota lines up with
> your day.

## How it works

- **Reads your usage for free.** It reads the OAuth token Claude Code stores in
  your macOS keychain and calls Anthropic's usage endpoint
  (`GET /api/oauth/usage`). This is a pure read — it never spends quota. Your
  token is only ever sent to `api.anthropic.com`, nowhere else.
- **Anchors the window with one message.** At the scheduled time it runs
  `claude -p "ok"` on the cheapest model, which starts a fresh 5-hour window.
  Because Claude Code and claude.ai share the same subscription limit, this is
  the same window your normal usage counts against.
- **Fires even while asleep.** It schedules a `launchd` job at your chosen time
  and uses `pmset` to wake the Mac ~1 minute before — something a browser
  extension can't do.
- **No polling.** The reset cadence is deterministic (every 5 hours from the
  anchor), so it only reads usage once per run to check a window isn't already
  active. No background loop hammering the endpoint.

## Requirements

- macOS
- [Claude Code](https://claude.com/claude-code) installed and signed in with a
  Pro/Max **subscription** (not an API key)
- Python 3.9+ (ships with macOS)

## Usage

```bash
# See where you stand right now (read-only, no quota spent)
./bin/claude-anchor status

# Anchor the window right now
./bin/claude-anchor ping

# Schedule it: start a fresh window every day at 07:20 (resets 12:20)
./bin/claude-anchor install --at 07:20

# Or: make the window RESET at 07:20 (it pings at 02:20 and wakes the Mac)
./bin/claude-anchor install --at 07:20 --policy reset

# Skip the wake-from-sleep step (no sudo)
./bin/claude-anchor install --at 07:20 --no-wake

# Remove the schedule
./bin/claude-anchor uninstall
```

### Two policies

| Policy            | You pass         | It pings at | Window then runs |
|-------------------|------------------|-------------|------------------|
| `start` (default) | `--at 07:20`     | 07:20       | 07:20 → 12:20    |
| `reset`           | `--at 07:20`     | 02:20       | 02:20 → 07:20    |

Use `start` if you want a full fresh block when you sit down. Use `reset` if you
want your quota to become free again at a specific time.

## Notes & caveats

- If **you** send a message before the scheduled ping, *you* become the anchor
  and the window shifts. `claude-anchor run` reads usage first and skips the ping
  if a window is already active, so it won't double-anchor.
- `pmset repeat` supports only **one** repeating wake schedule system-wide;
  installing will replace an existing one.
- Logs: `~/Library/Logs/claude-anchor.log`.

## License

MIT
