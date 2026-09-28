"""Find the Claude subscription OAuth token, cross-platform.

Order:
  1. ~/.claude/.credentials.json  (Linux, Windows, and some macOS setups)
  2. macOS Keychain               (default on macOS)

The token is only ever handed to usage.py, which sends it to api.anthropic.com
and nowhere else.
"""
from __future__ import annotations

import json
import platform
import subprocess
from pathlib import Path
from typing import Optional

KEYCHAIN_SERVICE = "Claude Code-credentials"
CREDENTIALS_FILE = Path.home() / ".claude" / ".credentials.json"


class CredentialsError(Exception):
    """Raised when Claude credentials can't be found or read."""


def _extract(data: dict) -> str:
    oauth = data.get("claudeAiOauth", data)
    token = oauth.get("accessToken") or oauth.get("access_token")
    if not token:
        raise CredentialsError("No access token found in Claude credentials.")
    return token


def _from_file() -> Optional[str]:
    if not CREDENTIALS_FILE.exists():
        return None
    try:
        data = json.loads(CREDENTIALS_FILE.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise CredentialsError(f"Couldn't read {CREDENTIALS_FILE}: {exc}")
    return _extract(data)


def _from_macos_keychain() -> Optional[str]:
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-w", "-s", KEYCHAIN_SERVICE],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    try:
        return _extract(json.loads(result.stdout))
    except json.JSONDecodeError as exc:
        raise CredentialsError(f"Unexpected keychain credential format: {exc}")


def get_access_token() -> str:
    token = _from_file()
    if token:
        return token
    if platform.system() == "Darwin":
        token = _from_macos_keychain()
        if token:
            return token
    raise CredentialsError(
        "Couldn't find Claude credentials. Sign in with Claude Code first: "
        "run `claude` and log in with your subscription."
    )
