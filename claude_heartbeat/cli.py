"""Command-line interface for claude-heartbeat."""
from __future__ import annotations

import argparse
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


def _now() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def cmd_status(args) -> None:
    summary = usage_mod.summarize(usage_mod.fetch_usage())
    five, seven = summary.five_hour, summary.seven_day
    state = "active" if summary.session_active else "idle"
    print("Claude usage")
    print(f"  5-hour   : {_fmt_pct(five.utilization)}  resets {_fmt_time(five.resets_at)}  ({state})")
    print(f"  weekly   : {_fmt_pct(seven.utilization)}  resets {_fmt_time(seven.resets_at)}")
    print(f"  heartbeat: {'running' if sched.is_loaded() else 'stopped'}")


def cmd_ping(args) -> None:
    print("Sending message to start/keep the session…")
    reply = send_ping()
    print(f"  claude replied: {reply[:60]!r}")
    time.sleep(2)
    summary = usage_mod.summarize(usage_mod.fetch_usage())
    print(f"  session resets {_fmt_time(summary.five_hour.resets_at)}")


def cmd_run(args) -> None:
    """launchd entry point: start a session if none is active, then schedule the
    next heartbeat for just after this window resets."""
    try:
        summary = usage_mod.summarize(usage_mod.fetch_usage())
    except usage_mod.UsageError as exc:
        print(f"[{_now()}] usage read failed ({exc}); starting a session anyway")
        summary = None

    if summary and summary.session_active:
        resets_at = summary.five_hour.resets_at
        print(f"[{_now()}] session already active (resets {_fmt_time(resets_at)}); no ping needed")
    else:
        reply = send_ping()
        print(f"[{_now()}] session started ({reply[:40]!r})")
        try:
            summary = usage_mod.summarize(usage_mod.fetch_usage())
        except usage_mod.UsageError:
            summary = None
        resets_at = summary.five_hour.resets_at if summary else None

    fire = sched.next_fire_from(resets_at)
    sched.reschedule(fire)
    print(f"[{_now()}] next heartbeat scheduled for {_fmt_time(fire)}")


def cmd_start(args) -> None:
    fire = sched.next_fire_from(None)  # placeholder; cmd_run sets the real time
    sched.write_plist(fire.hour, fire.minute)
    sched.load_agent()
    print("Heartbeat started — keeping your Claude session alive across resets.")
    cmd_run(args)
    print(f"Logs: {sched.LOG_PATH}")


def cmd_stop(args) -> None:
    sched.unload_agent()
    print("Heartbeat stopped. Your session will now expire normally at its next reset.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="claude-heartbeat",
        description="Keep your Claude session alive across every reset.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="show usage, reset times, and heartbeat state").set_defaults(func=cmd_status)
    sub.add_parser("ping", help="start/refresh the session right now").set_defaults(func=cmd_ping)
    sub.add_parser("start", help="start the keep-alive (runs across resets, 24/7)").set_defaults(func=cmd_start)
    sub.add_parser("stop", help="stop the keep-alive").set_defaults(func=cmd_stop)
    sub.add_parser("run").set_defaults(func=cmd_run)  # internal: launchd entry point
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
