"""Read Claude subscription usage (5-hour + weekly windows) — read-only.

Never sends a message and never consumes quota. Asks Anthropic's usage endpoint
for the current window state using the token from credentials.py.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from typing import Optional

from .credentials import CredentialsError, get_access_token

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
OAUTH_BETA = "oauth-2025-04-20"


class UsageError(Exception):
    """Raised when credentials or the usage endpoint are unavailable."""


def _http_get_json(url: str, headers: dict) -> dict:
    """GET JSON. Prefer curl (ships on macOS, Linux, and Windows 10+ and uses the
    system cert store); fall back to urllib where curl is absent."""
    if shutil.which("curl"):
        args = ["curl", "-sS", "--fail-with-body", url]
        for key, value in headers.items():
            args += ["-H", f"{key}: {value}"]
        result = subprocess.run(args, capture_output=True, text=True)
        if result.returncode != 0:
            detail = result.stdout.strip() or result.stderr.strip()
            raise UsageError(f"Usage request failed: {detail}")
        body = result.stdout
    else:
        import urllib.request

        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode()
        except Exception as exc:  # noqa: BLE001 - report any transport failure
            raise UsageError(f"Usage request failed: {exc}")
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise UsageError(f"Could not parse usage response: {exc}")


def fetch_usage(token: Optional[str] = None) -> dict:
    """GET the usage endpoint. Read-only — does not anchor a window or spend quota."""
    try:
        token = token or get_access_token()
    except CredentialsError as exc:
        raise UsageError(str(exc))
    return _http_get_json(
        USAGE_URL,
        {
            "Authorization": f"Bearer {token}",
            "anthropic-beta": OAUTH_BETA,
            "User-Agent": "claude-heartbeat",
        },
    )


def parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


class Window:
    """One usage window (five_hour or seven_day)."""

    def __init__(self, data: Optional[dict]):
        data = data or {}
        self.utilization: Optional[float] = data.get("utilization")
        self.resets_at: Optional[datetime] = parse_iso(data.get("resets_at"))


class Summary:
    def __init__(self, usage: dict):
        self.five_hour = Window(usage.get("five_hour"))
        self.seven_day = Window(usage.get("seven_day"))
        self.session_active = any(
            lim.get("kind") == "session" and lim.get("is_active")
            for lim in usage.get("limits", [])
        )


def summarize(usage: dict) -> Summary:
    return Summary(usage)
