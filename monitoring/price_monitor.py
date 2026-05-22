"""Real-time SL/TP watcher — monitors open positions and triggers close orders when stop-loss or take-profit is hit."""

import logging
import threading
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 15             # seconds between checks
_MAX_POSITION_AGE_S = 4 * 3600  # 4 hours before stale-position warning

_monitor_thread: Optional[threading.Thread] = None
_monitor_stop = threading.Event()


def check_positions() -> None:
    """
    Fetch current prices for all open positions and close on SL/TP hit.
    Sends a Telegram warning if any position has been open for more than 4 hours.
    Triggers the reflection engine after each close.
    """
    try:
        from risk.portfolio import get_portfolio_state, close_position
        from execution.ccxt_client import get_current_price
        from monitoring.telegram_alerts import _send, send_trade_closed
        from agents.memory.reflection import reflect, write_lesson

        positions = get_portfolio_state().get("open_positions", [])

        for pos in positions:
            pair        = pos.get("pair", "")
            action      = pos.get("action", "BUY")
            sl          = float(pos.get("sl_price", 0.0))
            tp          = float(pos.get("tp_price", 0.0))
            entry       = float(pos.get("entry_price", 0.0))
            opened_at   = pos.get("timestamp", "")

            current = get_current_price(pair)
            if current <= 0:
                continue

            if action == "BUY":
                close_reason = "SL_HIT" if current <= sl else ("TP_HIT" if current >= tp else None)
            else:
                close_reason = "SL_HIT" if current >= sl else ("TP_HIT" if current <= tp else None)

            # Stale-position warning
            if not close_reason and opened_at:
                try:
                    opened_dt = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
                    age = (datetime.now(timezone.utc) - opened_dt).total_seconds()
                    if age > _MAX_POSITION_AGE_S:
                        _send(
                            f"<b>Stale Position Warning</b>\n"
                            f"{pair} open for {age / 3600:.1f}h\n"
                            f"Entry ${entry:,.2f}  Current ${current:,.2f}"
                        )
                except Exception:
                    pass

            if not close_reason:
                continue

            closed = close_position(pair, current, close_reason)
            if not closed:
                continue

            send_trade_closed(
                pair=pair, action=action,
                entry=entry, exit_price=current,
                pnl=closed.get("pnl", 0.0),
                pnl_pct=closed.get("pnl_pct", 0.0),
                reason=close_reason,
            )

            try:
                trade_result = {
                    **pos,
                    "exit_price": current,
                    "close_reason": close_reason,
                    "pnl": closed.get("pnl", 0.0),
                    "pnl_pct": closed.get("pnl_pct", 0.0),
                    "win": closed.get("win", False),
                }
                lesson = reflect(trade_result, pos.get("agent_outputs", {}))
                write_lesson(lesson)
            except Exception as exc:
                logger.error("Reflection failed for %s: %s", pair, exc)

    except Exception as exc:
        logger.error("price_monitor.check_positions failed: %s", exc)


def _monitor_loop() -> None:
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
