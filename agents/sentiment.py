"""Crypto sentiment agent (Haiku) — interprets Fear & Greed index; runs every 30 min with in-memory cache."""

import time
from typing import Optional

from agents._client import MODEL_FAST, get_client, parse_json

_AGENT = "sentiment"

_SYSTEM = (
    "You are the Sentiment Analyst for ACE, an intraday crypto trading bot. "
    "Interpret the provided Fear & Greed index in the context of intraday AMD trading. "
    "Use ONLY the data explicitly provided. "
    "Respond with valid JSON only."
)

# In-memory cache: stores last result + expiry timestamp
_cache: dict = {"result": None, "expires_at": 0.0}
_CACHE_TTL = 30 * 60  # 30 minutes


def analyse(
    fear_greed_index: int,
    fear_greed_label: str,
    pair: str,
    timestamp: str,
) -> dict:
    """
    Interpret Fear & Greed index and assess whether sentiment supports the current setup.

    Results are cached for 30 minutes — the agent fires only when the cache expires.
    fear_greed_index: 0–100 (0 = extreme fear, 100 = extreme greed)
    fear_greed_label: human-readable label ("Extreme Fear", "Greed", etc.)

    All values passed in — nothing fetched here.

    Returns: sentiment_score, sentiment_label, supports_trade, sentiment_confidence,
             reasoning, agent, cached_until.
    """
    _err = {
        "agent": _AGENT, "sentiment_score": fear_greed_index,
        "sentiment_label": fear_greed_label, "supports_trade": False,
        "sentiment_confidence": 0, "reasoning": "", "cached_until": 0.0,
        "error": True, "error_message": "",
    }

    now = time.time()

    # Return cached result if still valid
    if _cache["result"] and now < _cache["expires_at"]:
        cached = dict(_cache["result"])
        cached["cached_until"] = _cache["expires_at"]
        return cached

    try:
        # Classify index for the prompt
        if fear_greed_index <= 25:
            context = "EXTREME FEAR — capitulation possible, contrarian long opportunity in accumulation"
        elif fear_greed_index <= 45:
            context = "FEAR — weak hands shaken out, distribution phase likely"
        elif fear_greed_index <= 55:
            context = "NEUTRAL — no clear sentiment edge"
        elif fear_greed_index <= 75:
            context = "GREED — bulls in control, momentum may extend"
        else:
            context = "EXTREME GREED — euphoria zone, Judas swing / reversal risk elevated"

        prompt = f"""Pair: {pair}  |  Timestamp: {timestamp}

Crypto Fear & Greed Index:
  Score: {fear_greed_index}/100
  Label: {fear_greed_label}
  Context: {context}

Determine:
1. Does this sentiment level support taking a new intraday trade now?
   (Consider: extreme fear = contrarian long, extreme greed = caution / fade)
2. Sentiment confidence 1–10 (how strongly does sentiment give an edge?)

Respond ONLY with:
{{
  "sentiment_score": {fear_greed_index},
  "sentiment_label": "{fear_greed_label}",
  "supports_trade": false,
  "sentiment_confidence": 0,
  "reasoning": "one or two sentences"
}}"""

        resp = get_client().messages.create(
            model=MODEL_FAST,
            max_tokens=250,
            system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral", "ttl": 3600}}],
            messages=[{"role": "user", "content": prompt}],
        )
        p = parse_json(resp.content[0].text)
        result = {
            "agent": _AGENT,
            "sentiment_score": int(p.get("sentiment_score", fear_greed_index)),
            "sentiment_label": p.get("sentiment_label", fear_greed_label),
            "supports_trade": bool(p.get("supports_trade", False)),
            "sentiment_confidence": int(p.get("sentiment_confidence", 0)),
            "reasoning": p.get("reasoning", ""),
            "cached_until": now + _CACHE_TTL,
            "error": False,
            "error_message": "",
        }
        _cache["result"] = result
        _cache["expires_at"] = now + _CACHE_TTL
        return result

    except Exception as exc:
        _err["error_message"] = str(exc)
        return _err


def clear_cache() -> None:
    """Clear the sentiment cache — used in tests and on service restart."""
    _cache["result"] = None
    _cache["expires_at"] = 0.0
