"""Read Claude subscription usage (5-hour + weekly windows) — read-only.

This never sends a message and never consumes quota. It reads the OAuth token
that Claude Code stores in the macOS keychain (the same login claude.ai and
Claude Code share) and asks Anthropic's usage endpoint for the current window
state. The token is only ever sent to api.anthropic.com.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime
from typing import Optional

KEYCHAIN_SERVICE = "Claude Code-credentials"
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
OAUTH_BETA = "oauth-2025-04-20"


class UsageError(Exception):
    """Raised when credentials or the usage endpoint are unavailable."""


def get_access_token() -> str:
    """Return the Claude Code OAuth access token from the macOS keychain."""
    result = subprocess.run(
        ["security", "find-generic-password", "-w", "-s", KEYCHAIN_SERVICE],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise UsageError(
            "Couldn't read Claude credentials from the keychain. "
            "Are you logged in? Run `claude` and sign in first."
        )
    try:
        creds = json.loads(result.stdout)
        return creds["claudeAiOauth"]["accessToken"]
    except (json.JSONDecodeError, KeyError) as exc:
        raise UsageError(f"Unexpected credential format in keychain: {exc}")


def fetch_usage(token: Optional[str] = None) -> dict:
    """GET the usage endpoint. Read-only — does not anchor a window or spend quota.

    Uses curl so we get the system certificate store (macOS Python's urllib does
    not, and fails cert verification against api.anthropic.com).
    """
    token = token or get_access_token()
    result = subprocess.run(
        [
            "curl", "-sS", "--fail-with-body",
            USAGE_URL,
            "-H", f"Authorization: Bearer {token}",
            "-H", f"anthropic-beta: {OAUTH_BETA}",
            "-H", "User-Agent: claude-anchor",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stdout.strip() or result.stderr.strip()
        raise UsageError(f"Usage request failed: {detail}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise UsageError(f"Could not parse usage response: {exc}")


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
