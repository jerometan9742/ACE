"""Main bot runner — orchestrates WebSocket streams, signal engine, agent pipeline, and execution loop."""

import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Optional

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

TRADING_MODE = os.getenv("TRADING_MODE", "paper")
WATCHLIST = [p.strip() for p in os.getenv("WATCHLIST", "BTC/USDT,ETH/USDT,SOL/USDT").split(",")]
_CONFLUENCE_MIN = int(os.getenv("CONFLUENCE_MIN_SCORE", "7"))
_PAPER_BALANCE = float(os.getenv("PAPER_BALANCE", "10000"))

# File written on shutdown — monkeypatch this in tests
_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "portfolio_state.json")

# Per-pair last-known session name — used to detect transitions
_session_state: Dict[str, Optional[str]] = {pair: None for pair in WATCHLIST}

# Mutable daily stats (reset at 00:00 UTC)
_daily_stats: Dict = {"trades": 0, "pnl": 0.0, "wins": 0, "date": ""}

_shutdown_requested = False


# ---------------------------------------------------------------------------
# Candle callback — fires on every WebSocket candle close
# ---------------------------------------------------------------------------

def _process_candle(signal_data: dict) -> None:
    """
    Entry point for every WebSocket candle. Only acts on 5m timeframe to
    balance signal frequency with pipeline latency.
    """
    if signal_data.get("timeframe") != "5m":
        return

    pair = signal_data.get("pair", "")
    candles = signal_data.get("candles", [])
    if len(candles) < 20:
        return

    try:
        _run_analysis(pair, candles)
    except Exception as exc:
        logger.error("Analysis error for %s: %s", pair, exc)
        from monitoring.telegram_alerts import send_error_alert
        send_error_alert("Analysis Error", f"{pair}: {exc}")


# ---------------------------------------------------------------------------
# Full signal → pipeline → risk → execution chain
# ---------------------------------------------------------------------------

def _run_analysis(pair: str, candles: list) -> None:
    """Process one pair's candle set through the full ACE stack."""
    from signal_engine import session as sess
    from signal_engine import amd_detector, bos_choch, fvg, order_blocks, judas_swing, confluence
    from execution import ccxt_client as cc

    current_session = sess.get_current_session()
    _check_session_transition(pair, current_session)

    if not sess.is_trading_allowed():
        return

    price = cc.get_current_price(pair)
    if price <= 0:
        return
    atr = cc.get_atr(pair)

    # Signal engine (pure Python — no LLM)
    amd_data  = amd_detector.detect_phase(candles)
    bos_data  = bos_choch.detect_bos_choch(candles)
    fvgs      = fvg.get_active_fvgs(candles)
    obs       = order_blocks.detect_order_blocks(candles)

    recent    = candles[-20:]
    asia_high = max(c["high"] for c in recent)
    asia_low  = min(c["low"]  for c in recent)
    avg_vol   = sum(c["volume"] for c in recent) / len(recent)
    judas_data = judas_swing.detect_judas_swing(candles, asia_high, asia_low, avg_vol)
    volume_data = {"confirms": avg_vol > 0}

    conf_result = confluence.score_setup(
        pair=pair, price=price, candles=candles,
        session=current_session, fvgs=fvgs, obs=obs,
        bos_data=bos_data, judas_data=judas_data, volume_data=volume_data,
    )
    score = conf_result.get("score", 0)

    from monitoring.logger import log_signal
    log_signal(pair, score, score >= _CONFLUENCE_MIN, conf_result.get("breakdown", {}))

    if score < _CONFLUENCE_MIN:
        return  # below threshold — discard silently

    logger.info("Confluence %d/10 for %s — firing agent pipeline", score, pair)

    # Agent pipeline
    from agents.pipeline import run_pipeline
    from risk.portfolio import get_portfolio_state

    portfolio = get_portfolio_state()
    ob = cc.get_order_book(pair)

    pipeline_state = {
        "pair": pair,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "current_price": price,
        "candles_1m": candles,
        "candles_5m": candles,
        "candles_15m": candles,
        "amd_data": amd_data,
        "bos_data": bos_data,
        "fvgs": fvgs,
        "obs": obs,
        "session": current_session,
        "vwap": price,
        "rsi": 50.0,
        "atr": atr,
        "order_book": ob,
        "recent_trades": [],
        "volume_profile": {
            "poc": price,
            "value_area_high": price * 1.005,
            "value_area_low":  price * 0.995,
        },
        "fear_greed_index": 50,
        "fear_greed_label": "Neutral",
        "confluence_score": score,
        "current_positions": {p.get("pair", ""): p for p in portfolio.get("open_positions", [])},
        "daily_pnl": portfolio.get("daily_pnl", 0.0),
        "account_balance": portfolio.get("equity", _PAPER_BALANCE),
        "kill_switch_active": False,
        "correlation_data": {"correlation": 0.0},
    }

    result   = run_pipeline(pipeline_state)
    decision = result.get("final_decision", {})

    if not decision or decision.get("action") == "HOLD":
        return

    from monitoring.logger import log_decision
    log_decision(pair, decision.get("action", ""), decision.get("confidence", 0.0),
                 decision.get("reasoning", ""))

    # Risk gate final check
    from risk.risk_gate import check_trade
    decision["signal_timestamp"] = time.time()
    gate_result = check_trade(decision, {
        "session": current_session,
        "daily_pnl": portfolio.get("daily_pnl", 0.0),
        "equity": portfolio.get("equity", _PAPER_BALANCE),
        "trades_this_session": portfolio.get("trades_this_session", 0),
        "open_positions": portfolio.get("open_positions", []),
        "correlation": 0.0,
    })

    if not gate_result.get("approved", False):
        logger.info("Risk gate blocked %s: %s", pair, gate_result.get("reason", ""))
        return

    # Position sizing + order placement
    from risk.position_sizer import calculate_size
    from execution.paper_trader import place_order

    balance    = cc.get_balance()
    equity     = balance.get("total", _PAPER_BALANCE) or _PAPER_BALANCE
    size_result = calculate_size(decision, equity, price, atr)

    if size_result.get("quantity", 0) <= 0:
        return

    place_order(
        pair=pair,
        side=decision["action"].lower(),
        quantity=size_result["quantity"],
        price=price,
        sl_price=size_result["sl_price"],
        tp_price=size_result["tp_price"],
        decision=decision,
        agent_outputs=result,
    )

    _daily_stats["trades"] += 1


# ---------------------------------------------------------------------------
# Session transition handler
# ---------------------------------------------------------------------------

def _check_session_transition(pair: str, current_session: dict) -> None:
    """
    Detect kill-zone start/end for a pair and:
    - On start: reset session counters, send Telegram alert
    - On end: send session P&L summary
    Alerts only fire for the primary pair to avoid duplicate messages.
    """
    from monitoring.telegram_alerts import _send
    from risk.portfolio import reset_session_counters, get_daily_pnl

    prev      = _session_state.get(pair)
    curr_name = current_session.get("name", "outside")

    if prev == curr_name:
        return
    _session_state[pair] = curr_name

    # Only the first pair fires session alerts to avoid N×3 duplicate messages
    if pair != WATCHLIST[0]:
        return

    active = {"london", "ny_open", "ny_afternoon"}
    entering = curr_name in active and prev not in active
    leaving  = curr_name not in active and prev in active

    if entering:
        reset_session_counters()
        _send(f"<b>Session Start: {curr_name.upper()}</b>\nACE entering kill zone")
    elif leaving:
        pnl  = get_daily_pnl()
        sign = "+" if pnl >= 0 else ""
        _send(f"<b>Session End: {(prev or '').upper()}</b>\nSession P&L: {sign}${pnl:,.2f}")


# ---------------------------------------------------------------------------
# Daily tasks
# ---------------------------------------------------------------------------

def _reset_daily_counters() -> None:
    """Reset P&L and trade stats at 00:00 UTC."""
    global _daily_stats
    _daily_stats = {
        "trades": 0, "pnl": 0.0, "wins": 0,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    logger.info("Daily counters reset")


def _send_daily_summary() -> None:
    """Send end-of-day summary at 23:59 UTC."""
    from risk.portfolio import get_daily_pnl
    from monitoring.telegram_alerts import send_daily_summary

    pnl    = get_daily_pnl()
    trades = _daily_stats.get("trades", 0)
    wins   = _daily_stats.get("wins", 0)
    send_daily_summary(
        date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        total_pnl=pnl,
        win_rate=(wins / trades * 100) if trades > 0 else 0.0,
        trades=trades,
        best_trade="—",
        worst_trade="—",
    )


# ---------------------------------------------------------------------------
# Shutdown helpers
# ---------------------------------------------------------------------------

def _save_portfolio_state() -> None:
    """Persist portfolio snapshot to disk on shutdown."""
    try:
        from risk.portfolio import get_portfolio_state
        state = get_portfolio_state()
        os.makedirs(os.path.dirname(_STATE_FILE), exist_ok=True)
        with open(_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2, default=str)
        logger.info("Portfolio state saved to %s", _STATE_FILE)
    except Exception as exc:
        logger.error("Failed to save portfolio state: %s", exc)


def _handle_shutdown(signum, frame) -> None:
    """SIGTERM / SIGINT handler — signal streams to stop and return control to run()."""
    global _shutdown_requested
    logger.info("Shutdown signal received (%s)", signum)
    _shutdown_requested = True

    from signal_engine.websocket import stop_streams
    stop_streams()
    # Do NOT call sys.exit() here — asyncio.run() is still on the call stack.
    # Calling sys.exit() while the event loop is running cancels all tasks abruptly
    # and propagates CancelledError, crashing the process. Instead, stop_streams()
    # sets _running=False; streams exit their while loops, asyncio.run() returns
    # cleanly, and run() performs the final cleanup.


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run() -> None:
    """Start ACE. Blocks until SIGTERM/SIGINT."""
    if TRADING_MODE != "paper":
        raise RuntimeError(
            "TRADING_MODE must be 'paper'. Live trading is not enabled."
        )

    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT,  _handle_shutdown)

    from monitoring.telegram_alerts import send_startup_alert, send_message
    from execution.paper_trader import start_monitor, stop_monitor
    from signal_engine.websocket import start_streams
    import asyncio as _asyncio

    send_startup_alert()
    start_monitor()

    logger.info("ACE starting — pairs: %s  mode: %s", WATCHLIST, TRADING_MODE)

    try:
        start_streams(_process_candle)  # blocks until _running is False
    except Exception as exc:
        logger.error("WebSocket fatal error: %s", exc)

    # Reached after SIGTERM/SIGINT sets _running=False and streams exit cleanly.
    # asyncio.run() is now closed — use a fresh run() for the final Telegram send.
    stop_monitor()
    _save_portfolio_state()
    try:
        _asyncio.run(send_message("<b>ACE Offline</b> — graceful shutdown complete"))
    except Exception:
        pass
    logger.info("ACE shutdown complete")


if __name__ == "__main__":
    run()
