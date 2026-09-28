# claude-heartbeat

Keep your Claude session **always alive**.

Claude's usage runs in a rolling 5-hour session. When it ends, you see
*"resets at X — send a message to start a new session."* `claude-heartbeat`
sends that message **for you, automatically, the moment the session resets** — so
you're always in a live, freshly-started session and never sit there blocked
waiting to start a new one. It chains session → session → session, around the
clock.

> This doesn't raise, bypass, or defeat any limit. It only sends a single normal
> message you could send yourself — just at the right moment, every time.

## How it works

- **Reads your usage for free.** It reads the OAuth token Claude Code stores in
  your macOS keychain and calls Anthropic's usage endpoint
  (`GET /api/oauth/usage`) to learn exactly when the current session resets. This
  is a pure read — it never spends quota. Your token is only ever sent to
  `api.anthropic.com`.
- **Restarts the session at each reset.** Just after `resets_at`, it runs
  `claude -p "ok"` on the cheapest model, which starts a fresh 5-hour session.
  Claude Code and claude.ai share the same subscription session, so this is the
  same one your normal usage uses.
- **Self-scheduling, no polling.** After each ping it reads the *new* reset time
  and re-arms a `launchd` job for the next one. That's ~2 free reads per 5-hour
  cycle — no constant polling of the endpoint.
- **Self-healing.** If the Mac was asleep through a reset, launchd runs the job
  on wake: it starts a session and re-schedules. You're never left stopped.

## Requirements

- macOS
- [Claude Code](https://claude.com/claude-code) installed and signed in with a
  Pro/Max **subscription** (not an API key)
- Python 3.9+ (ships with macOS)

## Usage

```bash
# See where you stand (read-only, no quota spent)
./bin/claude-heartbeat status

# Start a session right now
./bin/claude-heartbeat ping

# Turn the keep-alive ON — chains sessions across resets, 24/7
./bin/claude-heartbeat start

# Turn it OFF
./bin/claude-heartbeat stop
```

Once started, it just runs. Check on it anytime with `status`, or read
`~/Library/Logs/claude-heartbeat.log`.

## Notes & caveats

- **Sleep timing:** the keep-alive fires when the Mac is awake. If it's asleep
  through a reset, the next session starts when the Mac wakes (launchd catches
  up) rather than to-the-second at reset. Firing at exact reset while asleep
  needs a root LaunchDaemon + `pmset` wake — planned for a later version.
- If **you** are actively using Claude, your own messages keep the session
  alive; `run` notices an active session and skips its ping, so it never
  double-starts.
- Logs: `~/Library/Logs/claude-heartbeat.log`.

## License

MIT
