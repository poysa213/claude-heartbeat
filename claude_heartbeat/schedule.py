"""Keep the session alive by re-scheduling the ping at each reset.

A LaunchAgent fires `claude-heartbeat run` just after the current 5-hour
window's reset time. Each run reads the *new* reset time and rewrites its own
schedule for the next one — so the session chains window -> window forever, with
only a couple of free usage reads per cycle instead of constant polling.
"""
from __future__ import annotations

import plistlib
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

LABEL = "com.claudeheartbeat.keepalive"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LOG_PATH = Path.home() / "Library" / "Logs" / "claude-heartbeat.log"

# launchd runs with a minimal PATH; make sure claude/security/curl are findable.
LAUNCHD_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# Fire this many seconds AFTER the reset, so the old window has truly ended and
# our message starts a fresh one instead of being absorbed by the old window.
FIRE_BUFFER_SECONDS = 90


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def write_plist(fire_hour: int, fire_minute: int) -> Path:
    plist = {
        "Label": LABEL,
        "ProgramArguments": [sys.executable, "-m", "claude_heartbeat", "run"],
        "StartCalendarInterval": {"Hour": fire_hour, "Minute": fire_minute},
        "WorkingDirectory": str(_repo_root()),
        "EnvironmentVariables": {
            "PATH": LAUNCHD_PATH,
            "PYTHONPATH": str(_repo_root()),
        },
        "StandardOutPath": str(LOG_PATH),
        "StandardErrorPath": str(LOG_PATH),
        "RunAtLoad": False,
    }
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PLIST_PATH, "wb") as fh:
        plistlib.dump(plist, fh)
    return PLIST_PATH


def next_fire_from(resets_at: Optional[datetime]) -> datetime:
    """Local datetime for the next ping: just after the given reset, or a short
    fallback if we don't have a valid future reset time."""
    now = datetime.now().astimezone()
    if resets_at is None:
        return now + timedelta(minutes=5)
    fire = (resets_at + timedelta(seconds=FIRE_BUFFER_SECONDS)).astimezone()
    if fire <= now:
        return now + timedelta(minutes=1)  # reset already passed; fire almost now
    return fire


def reschedule(fire: datetime) -> None:
    """Point the agent at the next fire time and reload it.

    The reload runs in a detached process so it happens *after* the current run
    exits — a launchd job can't cleanly unload itself while it's still running.
    """
    write_plist(fire.hour, fire.minute)
    script = (
        f'sleep 3; '
        f'launchctl unload "{PLIST_PATH}" 2>/dev/null; '
        f'launchctl load "{PLIST_PATH}" 2>/dev/null'
    )
    subprocess.Popen(
        ["/bin/bash", "-c", script],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def load_agent() -> None:
    subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
    subprocess.run(["launchctl", "load", str(PLIST_PATH)], check=True, capture_output=True)


def unload_agent() -> None:
    subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
    if PLIST_PATH.exists():
        PLIST_PATH.unlink()


def is_loaded() -> bool:
    result = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
    return LABEL in result.stdout
