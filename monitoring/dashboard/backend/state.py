"""Shared in-memory state for the ACE Mission Control dashboard."""

import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_lock = threading.Lock()

def _load_risk_params() -> Dict[str, Any]:
    return {
        "confluence_min_score":  int(os.getenv("CONFLUENCE_MIN_SCORE", "7")),
        "min_confidence_score":  float(os.getenv("MIN_CONFIDENCE_SCORE", "7.0")),
        "max_position_size_pct": float(os.getenv("MAX_POSITION_SIZE_PCT", "0.05")),
        "risk_per_trade_pct":    float(os.getenv("RISK_PER_TRADE_PCT", "0.01")),
        "max_daily_loss_pct":    float(os.getenv("MAX_DAILY_LOSS_PCT", "0.03")),
        "atr_sl_multiplier":     float(os.getenv("ATR_SL_MULTIPLIER", "1.5")),
        "atr_tp_multiplier":     float(os.getenv("ATR_TP_MULTIPLIER", "3.0")),
        "max_trades_per_session":int(os.getenv("MAX_TRADES_PER_SESSION", "10")),
        "correlation_limit":     float(os.getenv("CORRELATION_LIMIT", "0.85")),
    }

def _load_settings() -> Dict[str, Any]:
    return {
        "trading_mode": os.getenv("TRADING_MODE", "paper"),
        "exchange":     os.getenv("EXCHANGE", "binance"),
        "watchlist":    [p.strip() for p in os.getenv("WATCHLIST", "BTC/USDT,ETH/USDT,SOL/USDT").split(",")],
        "paper_balance":float(os.getenv("PAPER_BALANCE", "10000")),
        "model_fast":   os.getenv("ANTHROPIC_MODEL_FAST", "claude-haiku-4-5-20251001"),
        "model_smart":  os.getenv("ANTHROPIC_MODEL_SMART", "claude-sonnet-4-6"),
        "atr_sl_multiplier": float(os.getenv("ATR_SL_MULTIPLIER", "1.5")),
        "atr_tp_multiplier": float(os.getenv("ATR_TP_MULTIPLIER", "3.0")),
    }

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

    # Per-pair AMD phases (AMD Radar tab)
    "pair_phases": {
        "BTC/USDT": {"phase": "UNKNOWN", "confluence_score": 0},
        "ETH/USDT": {"phase": "UNKNOWN", "confluence_score": 0},
        "SOL/USDT": {"phase": "UNKNOWN", "confluence_score": 0},
    },

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

    # AMD phase (primary pair)
    "amd_phase": "UNKNOWN",        # ACCUMULATION | MANIPULATION | DISTRIBUTION | UNKNOWN
    "confluence_score": 0,

    # Open positions
    "open_positions": [],

    # Mission log (last 50 entries)
    "mission_log": [],

    # Swarm memory lessons (last 20)
    "swarm_lessons": [],

    # Session win-rate stats
    "session_stats": {
        "asia":   {"trades": 0, "wins": 0},
        "london": {"trades": 0, "wins": 0},
        "ny":     {"trades": 0, "wins": 0},
    },

    # Risk parameters (from env)
    "risk_params": _load_risk_params(),

    # Read-only settings (from env)
    "settings": _load_settings(),

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


_last_price_fetch: float = 0.0


def sync_from_portfolio() -> None:
    """
    Pull live data from the JSONL trade log and services.
    Reading from disk (not from risk.portfolio in-memory) so this works correctly
    even though the dashboard runs in a separate process from the bot.
    """
    import json as _json
    import time as _time
    from pathlib import Path

    # --- Reconstruct open positions and daily P&L from trade log ---
    try:
        log_path = Path(__file__).resolve().parents[3] / "logs" / "trades.jsonl"
        open_pos: dict = {}
        daily_pnl = 0.0
        trades_today = 0
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if log_path.exists():
            with open(log_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = _json.loads(line)
                    except _json.JSONDecodeError:
                        continue
                    event = row.get("event", "")
                    oid   = row.get("order_id", "")
                    ts    = str(row.get("ts", ""))[:10]

                    if event == "order_filled" and oid:
                        open_pos[oid] = row
                        if ts == today:
                            trades_today += 1
                    elif event == "position_closed" and oid:
                        open_pos.pop(oid, None)
                        if ts == today:
                            daily_pnl += float(row.get("pnl", 0.0))

        initial = float(os.getenv("PAPER_BALANCE", "10000"))
        with _lock:
            _state["open_positions"] = list(open_pos.values())
            _state["daily_pnl"] = round(daily_pnl, 2)
            _state["daily_pnl_pct"] = round(daily_pnl / initial * 100, 4) if initial > 0 else 0.0
            _state["trades_today"] = trades_today
    except Exception:
        pass

    # --- Current prices via REST (cached — max one fetch per 10s) ---
    global _last_price_fetch
    try:
        now = _time.time()
        if now - _last_price_fetch >= 10:
            from execution.ccxt_client import get_current_price
            watchlist = [p.strip() for p in os.getenv("WATCHLIST", "BTC/USDT,ETH/USDT,SOL/USDT").split(",")]
            prices = {}
            for pair in watchlist:
                p = get_current_price(pair)
                if p > 0:
                    prices[pair] = p
            if prices:
                with _lock:
                    _state["prices"].update(prices)
            _last_price_fetch = now
    except Exception:
        pass

    # --- Session ---
    try:
        from signal_engine.session import get_current_session
        sess = get_current_session()
        with _lock:
            _state["current_session"] = sess.get("name", "outside")
            _state["session_is_active"] = sess.get("is_active", False)
    except Exception:
        pass

    # Mirror primary pair's AMD phase into pair_phases for AMD Radar tab
    with _lock:
        _state["pair_phases"]["BTC/USDT"]["phase"] = _state["amd_phase"]
        _state["pair_phases"]["BTC/USDT"]["confluence_score"] = _state["confluence_score"]
