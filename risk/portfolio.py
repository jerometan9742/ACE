"""In-memory portfolio state — open positions, daily P&L, session counters, equity."""

import os
from datetime import datetime, timezone
from typing import Dict, List

from dotenv import load_dotenv

load_dotenv()

_state: Dict = {
    "open_positions": [],
    "daily_pnl": 0.0,
    "trades_today": 0,
    "trades_this_session": 0,
    "equity": float(os.getenv("PAPER_BALANCE", "10000")),
}


def get_portfolio_state() -> dict:
    """Return a shallow copy of the current portfolio state."""
    return {
        **_state,
        "open_positions": list(_state["open_positions"]),
    }


def update_position(trade: dict) -> None:
    """
    Add or replace an open position and increment session/daily counters.
    Replaces any existing position for the same pair.
    """
    pair = trade.get("pair", "")
    _state["open_positions"] = [
        p for p in _state["open_positions"] if p.get("pair") != pair
    ]
    _state["open_positions"].append(dict(trade))
    _state["trades_today"] += 1
    _state["trades_this_session"] += 1


def close_position(pair: str, exit_price: float, reason: str) -> dict:
    """
    Close an open position, realise P&L into daily_pnl, and return the closed
    trade dict. Returns {} if the pair has no open position.
    """
    position = next(
        (p for p in _state["open_positions"] if p.get("pair") == pair), None
    )
    if position is None:
        return {}

    _state["open_positions"] = [
        p for p in _state["open_positions"] if p.get("pair") != pair
    ]

    entry = float(position.get("entry_price", exit_price))
    qty = float(position.get("quantity", 0.0))
    action = position.get("action", "BUY")

    if action == "BUY":
        pnl = (exit_price - entry) * qty
    else:
        pnl = (entry - exit_price) * qty

    _state["daily_pnl"] += pnl

    cost_basis = entry * qty
    return {
        **position,
        "exit_price": exit_price,
        "exit_reason": reason,
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl / cost_basis * 100, 4) if cost_basis > 0 else 0.0,
        "win": pnl > 0,
        "closed_at": datetime.now(timezone.utc).isoformat(),
    }


def reset_session_counters() -> None:
    """Reset per-session trade counter. Call at the start of each kill zone."""
    _state["trades_this_session"] = 0


def get_daily_pnl() -> float:
    """Return cumulative realised P&L for today."""
    return _state["daily_pnl"]
