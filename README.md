# 💓 claude-heartbeat

**Stop babysitting the "resets at 7:20 AM" timer.**

Claude's session dies every 5 hours and makes you send a message to start the next one. `claude-heartbeat` sends it for you — the *second* it resets — so your session is always warm and you're never the person refreshing a countdown at 2 AM.

![macOS](https://img.shields.io/badge/macOS-000?logo=apple&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-FCC624?logo=linux&logoColor=black)
![Windows](https://img.shields.io/badge/Windows-0078D6?logo=windows&logoColor=white)
![Python](https://img.shields.io/badge/python-3.9+-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-22c55e)
![Stars](https://img.shields.io/github/stars/poysa213/claude-heartbeat?style=social)

```console
$ claude-heartbeat status
Claude usage
  5-hour   :  14.0%  resets Mon 07:19 CET  (idle)
  weekly   :  22.0%  resets Sun 02:59 CET
  heartbeat: running ✓
```

> Not a hack. It sends one normal message you could've sent yourself — just always on time.

## Get it going

```bash
git clone https://github.com/poysa213/claude-heartbeat
cd claude-heartbeat

# macOS / Linux
./bin/claude-heartbeat start

# Windows
python -m claude_heartbeat start
```

That's it. Go do literally anything else.

## Four commands, that's the whole thing

| | |
|---|---|
| `status` | where you stand — free, read-only |
| `ping` | start a session right now |
| `start` | keep it alive, forever (auto-starts on login) |
| `stop` | …or don't |

## Works everywhere Claude Code does

| OS | Token from | Keeps itself running with |
|---|---|---|
| macOS | Keychain | launchd |
| Linux | `~/.claude/.credentials.json` | systemd user service |
| Windows | `~/.claude/.credentials.json` | Task Scheduler |

Same tiny daemon on all three — only the plumbing differs.

## How it actually works

- **Reads your reset time for free** from `/api/oauth/usage` using the token Claude Code already stored (only ever sent to Anthropic, nowhere else).
- **At each reset** it fires one tiny `claude -p` and sleeps until the next one. No polling, no cron soup — ~2 reads per cycle.
- **Naps when you nap:** if the machine was asleep, it catches up the moment it wakes.

Needs [Claude Code](https://claude.com/claude-code) signed in with a Pro/Max **subscription** (not an API key).

## One honest caveat

Dead asleep through a 3 AM reset? It starts the session when the machine wakes, not to the second. Waking the machine on its own is on the roadmap.

## Roll your own scheduler

Prefer your own cron / systemd timer / Task Scheduler? `claude-heartbeat run` does exactly one cycle (start a session if none is active) and exits.

---

MIT · built because staring at a countdown is a bad use of a human.
