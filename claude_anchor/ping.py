"""Send the one tiny message that anchors the 5-hour window."""
from __future__ import annotations

import os
import subprocess

# Cheapest model keeps the footprint on your weekly limit near-zero while still
# starting the 5-hour window (any message anchors it).
PING_MODEL = "claude-haiku-4-5-20251001"
PING_PROMPT = "ok"


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
            "claude", "-p", prompt,
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
