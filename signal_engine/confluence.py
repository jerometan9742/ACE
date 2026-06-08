"""Confluence Engine — scores each trade setup 0–10 and gates agent pipeline entry at threshold >= 7."""

import logging
import os
from datetime import datetime, timezone
from typing import List, Dict

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

CONFLUENCE_MIN_SCORE = int(os.getenv("CONFLUENCE_MIN_SCORE", "7"))

_PROXIMITY_PCT = 0.005  # 0.5% proximity window for OB/FVG checks


def score_setup(
    pair: str,
    price: float,
    candles: List[Dict],
    session: Dict,
    fvgs: List[Dict],
    obs: List[Dict],
    bos_data: Dict,
    judas_data: Dict,
    volume_data: Dict,
) -> Dict:
    """
    Score a trade setup using the Confluence Engine (0–10).

    Scoring:
    - FVG present and price inside/near it:          +2
    - Order Block within 0.5% of price:              +2
    - Inside active kill zone:                        +2
    - BOS confirmed in trade direction:               +1
    - Judas Swing detected this session:              +2
    - Volume confirms (declining acc / expanding dist): +1

    All signal data must be passed in — no fetching inside this function.
    This is the single gate before the 10-agent pipeline fires.

    Returns dict: score, breakdown, passes_threshold, confidence_tier, reasoning.
    """
    score = 0
    breakdown: Dict[str, int] = {}
    reasoning: List[str] = []

    # --- FVG: +2 ---
    active_fvgs = [f for f in fvgs if not f.get("mitigated", True)]
    fvg_hit = any(
        f["bottom"] - price * _PROXIMITY_PCT <= price <= f["top"] + price * _PROXIMITY_PCT
        for f in active_fvgs
    )
    fvg_score = 2 if fvg_hit else 0
    breakdown["fvg"] = fvg_score
    score += fvg_score
    if fvg_hit:
        reasoning.append("Price at/near active FVG (+2)")

    # --- Order Block: +2 ---
    active_obs = [o for o in obs if not o.get("mitigated", True)]
    ob_hit = any(
        abs((o["high"] + o["low"]) / 2 - price) / price <= _PROXIMITY_PCT
        for o in active_obs
        if price > 0
    )
    ob_score = 2 if ob_hit else 0
    breakdown["order_block"] = ob_score
    score += ob_score
    if ob_hit:
        reasoning.append("Order Block within 0.5% of price (+2)")

    # --- Kill zone: +2 ---
    in_kill_zone = session.get("is_active", False)
    kz_score = 2 if in_kill_zone else 0
    breakdown["kill_zone"] = kz_score
    score += kz_score
    if in_kill_zone:
        reasoning.append(f"Inside {session.get('name', 'unknown')} kill zone (+2)")

    # --- BOS confirmed: +1 ---
    bos_score = 1 if bos_data.get("bos_detected", False) else 0
    breakdown["bos"] = bos_score
    score += bos_score
    if bos_score:
        reasoning.append(f"BOS {bos_data.get('bos_direction', '')} confirmed (+1)")

    # --- Judas Swing: +2 ---
    judas_score = 2 if judas_data.get("detected", False) else 0
    breakdown["judas"] = judas_score
    score += judas_score
    if judas_score:
        reasoning.append(f"Judas Swing {judas_data.get('direction', '')} detected (+2)")

    # --- Volume confirms: +1 ---
    vol_score = 1 if volume_data.get("confirms", False) else 0
    breakdown["volume"] = vol_score
    score += vol_score
    if vol_score:
        reasoning.append("Volume confirms setup (+1)")

    score = min(score, 10)
    passes_threshold = score >= CONFLUENCE_MIN_SCORE

    if score >= 9:
        tier = "very_high"
    elif score >= 8:
        tier = "high"
    elif score >= 7:
        tier = "medium"
    else:
        tier = "low"

    _ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _reason = "" if passes_threshold else f"score {score} < threshold {CONFLUENCE_MIN_SCORE}"
    logger.info(
        "[CONFLUENCE] %s | %s | score=%d/10 | fvg=%d ob=%d kill_zone=%d bos=%d judas=%d volume=%d"
        " | kill_zone_active=%s | fired=%s | reason=%s",
        _ts, pair, score,
        breakdown.get("fvg", 0), breakdown.get("order_block", 0), breakdown.get("kill_zone", 0),
        breakdown.get("bos", 0), breakdown.get("judas", 0), breakdown.get("volume", 0),
        in_kill_zone, passes_threshold, _reason,
    )

    return {
        "score": score,
        "breakdown": breakdown,
        "passes_threshold": passes_threshold,
        "confidence_tier": tier,
        "reasoning": reasoning,
    }
