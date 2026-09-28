"""Schedule the daily anchor ping with launchd, and wake the Mac with pmset.

launchd fires the ping at a fixed clock time; pmset wakes the machine ~1 minute
before so it fires even while the Mac is asleep — the thing a browser extension
fundamentally cannot do.
"""
from __future__ import annotations

import plistlib
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

LABEL = "com.claudeanchor.daily"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LOG_PATH = Path.home() / "Library" / "Logs" / "claude-anchor.log"

# launchd runs with a minimal PATH; make sure claude/security/curl are findable.
LAUNCHD_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def compute_ping_time(hour: int, minute: int, policy: str) -> Tuple[int, int]:
    """Map the target time to the time we must actually ping.

    policy 'start': the window should START at the target -> ping then.
    policy 'reset': the window should RESET at the target -> ping 5h earlier,
                    because reset time = ping time + 5 hours.
    """
    if policy == "reset":
        total = (hour * 60 + minute - 5 * 60) % (24 * 60)
        return total // 60, total % 60
    return hour, minute


def write_plist(ping_hour: int, ping_minute: int, at_str: str, policy: str) -> Path:
    plist = {
        "Label": LABEL,
        "ProgramArguments": [
            sys.executable, "-m", "claude_anchor", "run",
            "--at", at_str, "--policy", policy,
        ],
        "StartCalendarInterval": {"Hour": ping_hour, "Minute": ping_minute},
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


def load_agent() -> None:
    subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
    subprocess.run(["launchctl", "load", str(PLIST_PATH)], check=True, capture_output=True)


def unload_agent() -> None:
    subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
    if PLIST_PATH.exists():
        PLIST_PATH.unlink()


def wake_command(ping_hour: int, ping_minute: int) -> List[str]:
    """pmset command to wake ~1 min before the ping, every day.

    Note: pmset supports only ONE repeating schedule system-wide, so this will
    replace any existing `pmset repeat` you have set.
    """
    total = (ping_hour * 60 + ping_minute - 1) % (24 * 60)
    when = f"{total // 60:02d}:{total % 60:02d}:00"
    return ["sudo", "pmset", "repeat", "wakeorpoweron", "MTWRFSU", when]
