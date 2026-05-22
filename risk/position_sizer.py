"""Position sizing with confidence tiers — maps confidence score to lot size: 8.5+ = 1.5x, 7.5+ = 1.0x, 7.0+ = 0.5x."""

import math
import os
from typing import Tuple

from dotenv import load_dotenv

load_dotenv()

_RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE_PCT", "0.01"))
_ATR_SL_MULT = float(os.getenv("ATR_SL_MULTIPLIER", "1.5"))
_ATR_TP_MULT = float(os.getenv("ATR_TP_MULTIPLIER", "3.0"))
_MIN_POSITION_VALUE = 10.0  # USD — never trade below this

# (min_confidence, tier_name, multiplier, max_position_pct)
_TIERS = [
    (8.5, "HIGH",     1.5, 0.075),
    (7.5, "STANDARD", 1.0, 0.050),
    (7.0, "REDUCED",  0.5, 0.025),
]

_ZERO = {
    "quantity": 0.0, "position_value": 0.0, "position_pct": 0.0,
    "sl_price": 0.0, "tp_price": 0.0, "risk_amount": 0.0,
    "confidence_tier": "HOLD",
}


def _get_tier(confidence: float) -> Tuple[str, float, float]:
    """Returns (tier_name, multiplier, max_pct). Returns HOLD tuple if below 7.0."""
    for min_conf, name, mult, max_pct in _TIERS:
        if confidence >= min_conf:
            return name, mult, max_pct
    return "HOLD", 0.0, 0.0


def calculate_size(
    decision: dict,
    portfolio_value: float,
    entry_price: float,
    atr: float,
) -> dict:
    """
    Calculate position size using ATR-based risk and confidence tier cap.

    Formula:
      risk_amount  = portfolio_value × RISK_PER_TRADE_PCT × tier_multiplier
      sl_distance  = atr × ATR_SL_MULTIPLIER (1.5)
      tp_distance  = atr × ATR_TP_MULTIPLIER (3.0)
      raw_qty      = risk_amount / sl_distance
      max_qty      = (portfolio_value × tier_max_pct) / entry_price
      final_qty    = floor(min(raw_qty, max_qty), 8 decimals)

    Returns: {quantity, position_value, position_pct, sl_price, tp_price,
              risk_amount, confidence_tier}
    Returns zero-quantity dict if below tier minimum or position < $10.
    """
    try:
        confidence = float(decision.get("confidence", 0.0))
        action = decision.get("action", "HOLD")

        tier_name, multiplier, max_pct = _get_tier(confidence)

        if tier_name == "HOLD" or action == "HOLD":
            return dict(_ZERO)
        if portfolio_value <= 0 or entry_price <= 0 or atr <= 0:
            return dict(_ZERO)

        sl_distance = atr * _ATR_SL_MULT
        tp_distance = atr * _ATR_TP_MULT

        if action == "BUY":
            sl_price = entry_price - sl_distance
            tp_price = entry_price + tp_distance
        else:  # SELL / short
            sl_price = entry_price + sl_distance
            tp_price = entry_price - tp_distance

        risk_amount = portfolio_value * _RISK_PER_TRADE * multiplier
        raw_qty = risk_amount / sl_distance
        max_qty = (portfolio_value * max_pct) / entry_price
        capped_qty = min(raw_qty, max_qty)

        # Floor to 8 decimal places — never round up (would exceed max)
        final_qty = math.floor(capped_qty * 1e8) / 1e8

        position_value = final_qty * entry_price
        if position_value < _MIN_POSITION_VALUE:
            return dict(_ZERO)

        return {
            "quantity": final_qty,
            "position_value": round(position_value, 2),
            "position_pct": round(position_value / portfolio_value * 100, 4),
            "sl_price": round(sl_price, 8),
            "tp_price": round(tp_price, 8),
            "risk_amount": round(risk_amount, 2),
            "confidence_tier": tier_name,
        }
    except Exception:
        return dict(_ZERO)
