"""Register the keep-alive daemon with the OS so it starts on login and stays up.

The daemon itself (see cli.cmd_daemon) is fully portable — it just loops, reads
the reset time, pings when idle, and sleeps until the next reset. This module
only handles the OS-specific "keep this process running" wiring:

    macOS   -> launchd LaunchAgent (KeepAlive)
    Linux   -> systemd user service (Restart=always)
    Windows -> Task Scheduler task (onlogon)
"""
from __future__ import annotations

import platform
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

SYSTEM = platform.system()

# Fire this many seconds AFTER the reset, so the old window has truly ended and
# our message starts a fresh one instead of being absorbed by the old one.
FIRE_BUFFER_SECONDS = 90


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def next_fire_from(resets_at: Optional[datetime]) -> datetime:
    """Local datetime for the next ping: just after the given reset, or a short
    fallback if we don't have a valid future reset time."""
    now = datetime.now().astimezone()
    if resets_at is None:
        return now + timedelta(minutes=5)
    fire = (resets_at + timedelta(seconds=FIRE_BUFFER_SECONDS)).astimezone()
    if fire <= now:
        return now + timedelta(minutes=1)
    return fire


# --------------------------------------------------------------------------- #
# macOS — launchd
# --------------------------------------------------------------------------- #
LAUNCHD_LABEL = "com.claudeheartbeat.keepalive"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"
MAC_LOG = Path.home() / "Library" / "Logs" / "claude-heartbeat.log"
LAUNCHD_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"


def _mac_install() -> None:
    import plistlib

    plist = {
        "Label": LAUNCHD_LABEL,
        "ProgramArguments": [sys.executable, "-m", "claude_heartbeat", "daemon"],
        "WorkingDirectory": str(repo_root()),
        "EnvironmentVariables": {"PATH": LAUNCHD_PATH, "PYTHONPATH": str(repo_root())},
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(MAC_LOG),
        "StandardErrorPath": str(MAC_LOG),
    }
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MAC_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(PLIST_PATH, "wb") as fh:
        plistlib.dump(plist, fh)
    subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
    subprocess.run(["launchctl", "load", str(PLIST_PATH)], check=True, capture_output=True)


def _mac_uninstall() -> None:
    subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
    if PLIST_PATH.exists():
        PLIST_PATH.unlink()


def _mac_running() -> bool:
    result = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
    return LAUNCHD_LABEL in result.stdout


# --------------------------------------------------------------------------- #
# Linux — systemd user service
# --------------------------------------------------------------------------- #
SYSTEMD_UNIT = "claude-heartbeat.service"
SYSTEMD_PATH = Path.home() / ".config" / "systemd" / "user" / SYSTEMD_UNIT


def _linux_install() -> None:
    unit = f"""[Unit]
Description=claude-heartbeat — keep the Claude session alive
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={sys.executable} -m claude_heartbeat daemon
WorkingDirectory={repo_root()}
Environment=PYTHONPATH={repo_root()}
Restart=always
RestartSec=30

[Install]
WantedBy=default.target
"""
    SYSTEMD_PATH.parent.mkdir(parents=True, exist_ok=True)
    SYSTEMD_PATH.write_text(unit)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", SYSTEMD_UNIT], check=True)
    print("Tip: to keep it running when you're logged out: "
          "`sudo loginctl enable-linger $USER`")


def _linux_uninstall() -> None:
    subprocess.run(["systemctl", "--user", "disable", "--now", SYSTEMD_UNIT], capture_output=True)
    if SYSTEMD_PATH.exists():
        SYSTEMD_PATH.unlink()
    subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)


def _linux_running() -> bool:
    result = subprocess.run(
        ["systemctl", "--user", "is-active", SYSTEMD_UNIT],
        capture_output=True, text=True,
    )
    return result.stdout.strip() == "active"


# --------------------------------------------------------------------------- #
# Windows — Task Scheduler
# --------------------------------------------------------------------------- #
TASK_NAME = "claude-heartbeat"


def _win_pythonw() -> str:
    exe = sys.executable
    return exe[:-len("python.exe")] + "pythonw.exe" if exe.lower().endswith("python.exe") else exe


def _win_install() -> None:
    root = repo_root()
    # cmd wrapper sets PYTHONPATH then launches the daemon windowless.
    command = f'cmd /c set PYTHONPATH={root}&& "{_win_pythonw()}" -m claude_heartbeat daemon'
    subprocess.run(
        ["schtasks", "/create", "/tn", TASK_NAME, "/sc", "onlogon",
         "/tr", command, "/rl", "limited", "/f"],
        check=True,
    )
    subprocess.run(["schtasks", "/run", "/tn", TASK_NAME], check=True)


def _win_uninstall() -> None:
    subprocess.run(["schtasks", "/end", "/tn", TASK_NAME], capture_output=True)
    subprocess.run(["schtasks", "/delete", "/tn", TASK_NAME, "/f"], capture_output=True)


def _win_running() -> bool:
    result = subprocess.run(
        ["schtasks", "/query", "/tn", TASK_NAME], capture_output=True, text=True
    )
    return result.returncode == 0 and "Running" in result.stdout


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #
def _unsupported(*_a, **_k):
    raise RuntimeError(f"Unsupported platform: {SYSTEM}")


_TABLE = {
    "Darwin": (_mac_install, _mac_uninstall, _mac_running),
    "Linux": (_linux_install, _linux_uninstall, _linux_running),
    "Windows": (_win_install, _win_uninstall, _win_running),
}


def install() -> None:
    _TABLE.get(SYSTEM, (_unsupported,) * 3)[0]()


def uninstall() -> None:
    _TABLE.get(SYSTEM, (_unsupported,) * 3)[1]()


def is_running() -> bool:
    return _TABLE.get(SYSTEM, (_unsupported,) * 3)[2]()


def log_hint() -> str:
    if SYSTEM == "Darwin":
        return str(MAC_LOG)
    if SYSTEM == "Linux":
        return "journalctl --user -u claude-heartbeat -f"
    if SYSTEM == "Windows":
        return "Task Scheduler > claude-heartbeat (History tab)"
    return "(unknown)"
