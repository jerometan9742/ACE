"""Real-time SL/TP watcher — monitors open positions and closes on SL/TP hit."""

import logging
import threading
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 15             # seconds between checks
_MAX_POSITION_AGE_S = 4 * 3600  # 4 hours → stale warning

_monitor_thread: Optional[threading.Thread] = None
_monitor_stop = threading.Event()


def cleanup_invalid_positions() -> None:
    """
    Close positions where TP is on the wrong side of entry — called once on startup.
    Catches the case where a bad order slipped through before TP validation was added.
    """
    try:
        from execution.paper_trader import _open_orders
        from risk.portfolio import close_position
        from monitoring.telegram_alerts import _send
        from monitoring.logger import log_trade

        for oid, pos in list(_open_orders.items()):
            action = pos.get("action", "BUY").upper()
            entry  = float(pos.get("entry_price", 0.0))
            tp     = float(pos.get("tp_price", 0.0))
            pair   = pos.get("pair", "")

            bad = (
                (action in ("BUY", "LONG")  and tp <= entry) or
                (action in ("SELL", "SHORT") and tp >= entry)
            )
            if not bad:
                continue

            logger.warning(
                "Invalid position on startup: %s %s entry=%.2f TP=%.2f — closing",
                action, pair, entry, tp,
            )
            _open_orders.pop(oid, None)
            close_position(pair, entry, "INVALID_TP")
            _send(
                f"⚠️ {pair} — invalid position closed on startup (bad TP)\n"
                f"Action {action}  Entry ${entry:,.2f}  TP ${tp:,.2f}"
            )
            log_trade({**pos, "event": "position_closed", "close_reason": "INVALID_TP", "pnl": 0.0})

    except Exception as exc:
        logger.error("cleanup_invalid_positions failed: %s", exc)


def check_positions() -> None:
    """
    Fetch current prices for all open positions and close on SL/TP hit.
    Logs every check at INFO level and fires rich Telegram alerts on close.
    """
    try:
        from execution.paper_trader import _open_orders
        from execution.ccxt_client import get_current_price
        from risk.portfolio import close_position
        from monitoring.telegram_alerts import _send
        from monitoring.logger import log_trade
        from agents.memory.reflection import reflect, write_lesson

        to_close = []
        for oid, pos in list(_open_orders.items()):
            pair       = pos.get("pair", "")
            action     = pos.get("action", "BUY").upper()
            entry      = float(pos.get("entry_price", 0.0))
            sl         = float(pos.get("sl_price", 0.0))
            tp         = float(pos.get("tp_price", 0.0))
            opened_at  = pos.get("timestamp", "")

            current = get_current_price(pair)
            if current <= 0:
                continue

            logger.info(
                "Monitoring %s: entry=%.2f current=%.2f SL=%.2f TP=%.2f",
                pair, entry, current, sl, tp,
            )

            if action in ("BUY", "LONG"):
                close_reason = "SL_HIT" if current <= sl else ("TP_HIT" if current >= tp else None)
            else:
                close_reason = "SL_HIT" if current >= sl else ("TP_HIT" if current <= tp else None)

            if not close_reason and opened_at:
                try:
                    opened_dt = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
                    age = (datetime.now(timezone.utc) - opened_dt).total_seconds()
                    if age > _MAX_POSITION_AGE_S:
                        _send(
                            f"<b>Stale Position</b>\n"
                            f"{pair} open for {age / 3600:.1f}h\n"
                            f"Entry ${entry:,.2f}  Current ${current:,.2f}"
                        )
                except Exception:
                    pass

            if close_reason:
                to_close.append((oid, pos, current, close_reason))

        for oid, pos, current_price, close_reason in to_close:
            pair      = pos.get("pair", "")
            action    = pos.get("action", "BUY")
            entry     = float(pos.get("entry_price", 0.0))
            conf      = pos.get("confidence", 0.0)
            opened_at = pos.get("timestamp", "")

            _open_orders.pop(oid, None)
            closed = close_position(pair, current_price, close_reason)
            if not closed:
                continue

            pnl     = closed.get("pnl", 0.0)
            pnl_pct = closed.get("pnl_pct", 0.0)
            win     = closed.get("win", False)
            sign    = "+" if pnl >= 0 else ""

            duration_str = "—"
            if opened_at:
                try:
                    opened_dt = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
                    mins = int((datetime.now(timezone.utc) - opened_dt).total_seconds() / 60)
                    duration_str = f"{mins}min"
                except Exception:
                    pass

            if win:
                msg = (
                    f"✅ {pair} CLOSED — TP hit\n"
                    f"Entry ${entry:,.2f} → Exit ${current_price:,.2f}\n"
                    f"P&L: {sign}${pnl:.2f} ({sign}{pnl_pct:.2f}%)\n"
                    f"Conf: {conf} | Duration: {duration_str}"
                )
            else:
                msg = (
                    f"❌ {pair} CLOSED — SL hit\n"
                    f"Entry ${entry:,.2f} → Exit ${current_price:,.2f}\n"
                    f"P&L: {sign}${pnl:.2f} ({sign}{pnl_pct:.2f}%)\n"
                    f"Conf: {conf} | Duration: {duration_str}"
                )
            _send(msg)

            try:
                trade_result = {
                    **pos,
                    "exit_price": current_price,
                    "close_reason": close_reason,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "win": win,
                }
                lesson = reflect(trade_result, pos.get("agent_outputs", {}))
                write_lesson(lesson)
            except Exception as exc:
                logger.error("Reflection failed for %s: %s", pair, exc)

            log_trade({
                **pos,
                "exit_price": current_price,
                "close_reason": close_reason,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "event": "position_closed",
            })

    except Exception as exc:
        logger.error("check_positions failed: %s", exc)


def _monitor_loop() -> None:
    cleanup_invalid_positions()
    while not _monitor_stop.is_set():
        check_positions()
        _monitor_stop.wait(timeout=_POLL_INTERVAL)


def start_price_monitor() -> None:
    """Start the SL/TP watcher as a background daemon thread."""
    global _monitor_thread
    _monitor_stop.clear()
    _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True, name="price-monitor")
    _monitor_thread.start()
    logger.info("Price monitor started (interval=%ds)", _POLL_INTERVAL)


def stop_price_monitor() -> None:
    """Stop the price monitor thread."""
    _monitor_stop.set()
    if _monitor_thread and _monitor_thread.is_alive():
        _monitor_thread.join(timeout=10)
    logger.info("Price monitor stopped")
