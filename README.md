# 💓 claude-heartbeat

**Stop babysitting the "resets at 7:20 AM" timer.**

Claude's session dies every 5 hours and makes you send a message to start the next one. `claude-heartbeat` sends it for you — the *second* it resets — so your session is always warm and you're never the person refreshing a countdown at 2 AM.

![macOS](https://img.shields.io/badge/macOS-000?logo=apple&logoColor=white)
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
./bin/claude-heartbeat start
```

That's it. Go do literally anything else.

## Four commands, that's the whole thing

| | |
|---|---|
| `status` | where you stand — free, read-only |
| `ping` | start a session right now |
| `start` | keep it alive, forever |
| `stop` | …or don't |

## How it actually works

- **Reads your reset time for free** from `/api/oauth/usage` using the token already in your macOS keychain (only ever sent to Anthropic, nowhere else).
- **At each reset** it fires one tiny `claude -p` and re-arms itself for the next one. No polling, no cron soup — ~2 reads per cycle.
- **Naps when you nap:** if your Mac was asleep, it catches up the moment it wakes.

Needs macOS + [Claude Code](https://claude.com/claude-code) signed in with a Pro/Max **subscription** (not an API key).

## One honest caveat

Dead asleep through a 3 AM reset? It starts the session when your Mac wakes, not to the second. True lid-closed, round-the-clock keep-alive is on the roadmap.

---

MIT · built because staring at a countdown is a bad use of a human.
