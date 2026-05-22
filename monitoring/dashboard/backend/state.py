"""Shared in-memory state for the ACE Mission Control dashboard."""

import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_lock = threading.Lock()

_state: Dict[str, Any] = {
    # Bot lifecycle
    "status": "offline",          # offline | starting | running | error
    "uptime_start": None,         # ISO timestamp string

    # Account
    "equity": 10000.0,
    "daily_pnl": 0.0,
    "daily_pnl_pct": 0.0,

    # Session
    "current_session": "outside",
    "session_is_active": False,
    "trades_today": 0,
    "trades_this_session": 0,
    "win_rate": 0.0,

    # Pairs
    "prices": {},   # {"BTC/USDT": 70000.0, ...}

    # Agent pipeline
    "agents": {
        "RD": {"name": "Regime Detector",   "status": "idle", "last_output": ""},
        "TA": {"name": "Technical Analyst",  "status": "idle", "last_output": ""},
        "OF": {"name": "Order Flow",         "status": "idle", "last_output": ""},
        "SP": {"name": "Sentiment",          "status": "idle", "last_output": ""},
        "BR": {"name": "Bull Researcher",    "status": "idle", "last_output": ""},
        "BE": {"name": "Bear Researcher",    "status": "idle", "last_output": ""},
        "CB": {"name": "Consensus Builder",  "status": "idle", "last_output": ""},
        "RM": {"name": "Risk Manager",       "status": "idle", "last_output": ""},
        "FM": {"name": "Fund Manager",       "status": "idle", "last_output": ""},
        "SM": {"name": "Swarm Memory",       "status": "idle", "last_output": ""},
    },

    # AMD phase
    "amd_phase": "UNKNOWN",        # ACCUMULATION | MANIPULATION | DISTRIBUTION | UNKNOWN
    "confluence_score": 0,

    # Open positions
    "open_positions": [],

    # Mission log (last 50 entries)
    "mission_log": [],

    # Kill switch
    "kill_switch_active": False,
}


def get_state() -> Dict[str, Any]:
    with _lock:
        import copy
        return copy.deepcopy(_state)


def update(patch: Dict[str, Any]) -> None:
    with _lock:
        _state.update(patch)


def set_agent_status(agent_id: str, status: str, last_output: str = "") -> None:
    with _lock:
        if agent_id in _state["agents"]:
            _state["agents"][agent_id]["status"] = status
            if last_output:
                _state["agents"][agent_id]["last_output"] = last_output


def add_log(level: str, message: str) -> None:
    with _lock:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
        }
        _state["mission_log"].append(entry)
        if len(_state["mission_log"]) > 50:
            _state["mission_log"] = _state["mission_log"][-50:]


def sync_from_portfolio() -> None:
    """Pull live data from the portfolio and price modules if the bot is running."""
    try:
        from risk.portfolio import get_portfolio_state
        portfolio = get_portfolio_state()
        equity = portfolio.get("equity", 10000.0)
        initial = float(os.getenv("PAPER_BALANCE", "10000"))
        daily_pnl = portfolio.get("daily_pnl", 0.0)
        with _lock:
            _state["equity"] = equity
            _state["daily_pnl"] = daily_pnl
            _state["daily_pnl_pct"] = (daily_pnl / initial * 100) if initial > 0 else 0.0
            _state["trades_today"] = portfolio.get("trades_today", 0)
            _state["trades_this_session"] = portfolio.get("trades_this_session", 0)
            _state["open_positions"] = portfolio.get("open_positions", [])
    except Exception:
        pass

    try:
        from risk.risk_gate import is_kill_switch_active
        with _lock:
            _state["kill_switch_active"] = is_kill_switch_active()
    except Exception:
        pass

    try:
        from signal_engine.session import get_current_session
        sess = get_current_session()
        with _lock:
            _state["current_session"] = sess.get("name", "outside")
            _state["session_is_active"] = sess.get("is_active", False)
    except Exception:
        pass
