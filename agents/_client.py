"""Shared Anthropic client, model names, JSON parser, and prompt-formatting utilities for all ACE agents."""

import json
import os
import re

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL_FAST = os.getenv("ANTHROPIC_MODEL_FAST", "claude-haiku-4-5-20251001")
MODEL_SMART = os.getenv("ANTHROPIC_MODEL_SMART", "claude-sonnet-4-6")


def get_client() -> anthropic.Anthropic:
    """Return a new Anthropic client using ANTHROPIC_API_KEY from env."""
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))


def parse_json(text: str) -> dict:
    """
    Extract the first JSON object from an LLM response.
    Handles plain JSON, markdown code blocks, and inline JSON objects.
    Returns {} on any failure — never raises.
    """
    if not text:
        return {}
    try:
        return json.loads(text.strip())
    except (json.JSONDecodeError, ValueError):
        pass
    m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if m:
        try:
            return json.loads(m.group(1))
        except (json.JSONDecodeError, ValueError):
            pass
    m = re.search(r"\{[\s\S]+\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except (json.JSONDecodeError, ValueError):
            pass
    return {}


def fmt_candles(candles: list, limit: int = 3) -> str:
    """Compact candle table for prompt injection — uses only values passed in."""
    if not candles:
        return "  (no candle data)"
    return "\n".join(
        f"  O:{c.get('open', 0):.4f}  H:{c.get('high', 0):.4f}  "
        f"L:{c.get('low', 0):.4f}  C:{c.get('close', 0):.4f}  V:{c.get('volume', 0):.0f}"
        for c in candles[-limit:]
    )


def fmt_fvgs(fvgs: list) -> str:
    """Format active (unmitigated) FVGs for prompt injection."""
    active = [f for f in fvgs if not f.get("mitigated", True)]
    if not active:
        return "  (none)"
    return "\n".join(
        f"  {f.get('type','?').upper()} FVG  "
        f"{f.get('bottom', 0):.4f} – {f.get('top', 0):.4f}  "
        f"strength={f.get('strength', 0):.5f}"
        for f in active[:5]
    )


def fmt_obs(obs: list) -> str:
    """Format active (unmitigated) Order Blocks for prompt injection."""
    active = [o for o in obs if not o.get("mitigated", True)]
    if not active:
        return "  (none)"
    return "\n".join(
        f"  {o.get('type','?').upper()} OB  "
        f"{o.get('low', 0):.4f} – {o.get('high', 0):.4f}  "
        f"strength={o.get('strength', 0):.4f}"
        for o in active[:5]
    )
