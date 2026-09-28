"""Command-line interface for claude-heartbeat."""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from typing import Optional

from . import service
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
    print(f"  heartbeat: {'running' if service.is_running() else 'stopped'}")


def cmd_ping(args) -> None:
    print("Sending message to start/keep the session…")
    reply = send_ping()
    print(f"  claude replied: {reply[:60]!r}")
    time.sleep(2)
    summary = usage_mod.summarize(usage_mod.fetch_usage())
    print(f"  session resets {_fmt_time(summary.five_hour.resets_at)}")


def _one_cycle() -> datetime:
    """Start a session if none is active; return when to run the next cycle."""
    try:
        summary = usage_mod.summarize(usage_mod.fetch_usage())
    except usage_mod.UsageError as exc:
        print(f"[{_now()}] usage read failed ({exc}); starting a session anyway", flush=True)
        summary = None

    if summary and summary.session_active:
        resets_at = summary.five_hour.resets_at
        print(f"[{_now()}] session active (resets {_fmt_time(resets_at)}); no ping needed", flush=True)
    else:
        reply = send_ping()
        print(f"[{_now()}] session started ({reply[:40]!r})", flush=True)
        try:
            summary = usage_mod.summarize(usage_mod.fetch_usage())
            resets_at = summary.five_hour.resets_at
        except usage_mod.UsageError:
            resets_at = None

    fire = service.next_fire_from(resets_at)
    print(f"[{_now()}] next heartbeat at {_fmt_time(fire)}", flush=True)
    return fire


def _sleep_until(target: datetime) -> None:
    """Sleep in short chunks so we recover quickly after the machine wakes."""
    while True:
        remaining = (target - datetime.now().astimezone()).total_seconds()
        if remaining <= 0:
            return
        time.sleep(min(60, remaining))


def cmd_daemon(args) -> None:
    """Portable keep-alive loop. Run by the OS service; identical on every platform."""
    print(f"[{_now()}] heartbeat daemon started ({service.SYSTEM})", flush=True)
    while True:
        try:
            fire = _one_cycle()
        except Exception as exc:  # noqa: BLE001 - never let the loop die
            print(f"[{_now()}] cycle error: {exc}; retrying in 5 min", flush=True)
            time.sleep(300)
            continue
        _sleep_until(fire)


def cmd_run(args) -> None:
    """One cycle and exit — for wiring into your own cron / timer / Task Scheduler."""
    _one_cycle()


def cmd_start(args) -> None:
    service.install()
    print(f"Heartbeat started on {service.SYSTEM} — keeping your session alive across resets.")
    print(f"Logs: {service.log_hint()}")


def cmd_stop(args) -> None:
    service.uninstall()
    print("Heartbeat stopped. Your session will expire normally at its next reset.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="claude-heartbeat",
        description="Keep your Claude session alive across every reset.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="show usage, reset times, and heartbeat state").set_defaults(func=cmd_status)
    sub.add_parser("ping", help="start/refresh the session right now").set_defaults(func=cmd_ping)
    sub.add_parser("start", help="start the keep-alive (auto-starts on login, runs 24/7)").set_defaults(func=cmd_start)
    sub.add_parser("stop", help="stop the keep-alive").set_defaults(func=cmd_stop)
    sub.add_parser("run", help="run one cycle and exit (for your own scheduler)").set_defaults(func=cmd_run)
    sub.add_parser("daemon").set_defaults(func=cmd_daemon)  # internal: run by the OS service
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
