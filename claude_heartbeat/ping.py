"""Send the one tiny message that starts (or keeps alive) the 5-hour session."""
from __future__ import annotations

import os
import shutil
import subprocess

# Cheapest model keeps the footprint on your weekly limit near-zero while still
# starting the 5-hour window (any message anchors it).
PING_MODEL = "claude-haiku-4-5-20251001"
PING_PROMPT = "ok"


def _claude_bin() -> str:
    # On Windows the launcher is claude.cmd; shutil.which resolves it for us.
    return shutil.which("claude") or "claude"


def send_ping(model: str = PING_MODEL, prompt: str = PING_PROMPT) -> str:
    """Send one message via Claude Code and return its reply text.

    ANTHROPIC_API_KEY is stripped from the child environment so the ping always
    authenticates with your subscription (OAuth) — anchoring the same window your
    claude.ai and Claude Code usage counts against, not a separate API pool.
    """
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    result = subprocess.run(
        [
            _claude_bin(), "-p", prompt,
            "--model", model,
            "--tools", "",               # no tools: fast, no permission prompts
            "--no-session-persistence",  # don't clutter session history
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Anchor ping failed: {detail}")
    return result.stdout.strip()
