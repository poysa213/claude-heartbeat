"""Command-line interface for claude-anchor."""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from typing import Optional

from . import schedule as sched
from . import usage as usage_mod
from .ping import send_ping


def _fmt_time(dt: Optional[datetime]) -> str:
    if dt is None:
        return "—"
    return dt.astimezone().strftime("%a %H:%M %Z")


def _fmt_pct(value: Optional[float]) -> str:
    return f"{value:5.1f}%" if value is not None else "   —  "


def _parse_at(at: str) -> tuple[int, int]:
    try:
        hour, minute = (int(part) for part in at.split(":"))
    except ValueError:
        raise SystemExit(f"error: --at must be HH:MM (got {at!r})")
    if not (0 <= hour < 24 and 0 <= minute < 60):
        raise SystemExit(f"error: --at out of range: {at!r}")
    return hour, minute


def _now() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def cmd_status(args) -> None:
    summary = usage_mod.summarize(usage_mod.fetch_usage())
    five, seven = summary.five_hour, summary.seven_day
    state = "active" if summary.session_active else "idle"
    print("Claude usage")
    print(f"  5-hour : {_fmt_pct(five.utilization)}  resets {_fmt_time(five.resets_at)}  ({state})")
    print(f"  weekly : {_fmt_pct(seven.utilization)}  resets {_fmt_time(seven.resets_at)}")


def cmd_ping(args) -> None:
    print("Sending anchor ping…")
    reply = send_ping()
    print(f"  claude replied: {reply[:60]!r}")
    time.sleep(2)
    summary = usage_mod.summarize(usage_mod.fetch_usage())
    print(f"  window now resets {_fmt_time(summary.five_hour.resets_at)}")


def cmd_run(args) -> None:
    """launchd entry point: read usage once, ping only if no window is active."""
    try:
        summary = usage_mod.summarize(usage_mod.fetch_usage())
    except usage_mod.UsageError as exc:
        print(f"[{_now()}] usage read failed ({exc}); pinging anyway")
        summary = None

    if summary and summary.session_active:
        print(f"[{_now()}] window already active (resets "
              f"{_fmt_time(summary.five_hour.resets_at)}); skipping ping")
        return

    reply = send_ping()
    print(f"[{_now()}] anchored ({reply[:40]!r})")


def cmd_install(args) -> None:
    hour, minute = _parse_at(args.at)
    ping_hour, ping_minute = sched.compute_ping_time(hour, minute, args.policy)
    sched.write_plist(ping_hour, ping_minute, args.at, args.policy)
    sched.load_agent()
    print(f"Installed. Anchor ping fires daily at {ping_hour:02d}:{ping_minute:02d} "
          f"(policy: {args.policy}, target {args.at}).")

    if args.no_wake:
        return
    cmd = sched.wake_command(ping_hour, ping_minute)
    print(f"Scheduling wake-from-sleep (needs sudo): {' '.join(cmd)}")
    if subprocess.run(cmd).returncode != 0:
        print("  wake scheduling failed — run that command yourself, or re-run with --no-wake")


def cmd_uninstall(args) -> None:
    sched.unload_agent()
    print("Removed the launchd agent.")
    print("To clear the wake schedule too: sudo pmset repeat cancel")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="claude-anchor",
        description="Align your Claude 5-hour usage window to your schedule.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="show current usage and reset times").set_defaults(func=cmd_status)
    sub.add_parser("ping", help="anchor the window right now").set_defaults(func=cmd_ping)

    install = sub.add_parser("install", help="schedule the daily anchor ping")
    install.add_argument("--at", required=True, metavar="HH:MM", help="target time, 24h local")
    install.add_argument(
        "--policy", choices=["start", "reset"], default="start",
        help="'start' (default): window starts at --at. 'reset': window resets at --at (pings 5h earlier)",
    )
    install.add_argument("--no-wake", action="store_true", help="don't schedule wake-from-sleep")
    install.set_defaults(func=cmd_install)

    run = sub.add_parser("run")  # internal entry point invoked by launchd
    run.add_argument("--at", required=True)
    run.add_argument("--policy", choices=["start", "reset"], default="start")
    run.set_defaults(func=cmd_run)

    sub.add_parser("uninstall", help="remove the schedule").set_defaults(func=cmd_uninstall)
    return parser


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (usage_mod.UsageError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
