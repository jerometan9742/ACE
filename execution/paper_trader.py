"""Paper trading simulation — mirrors live order logic against real-time prices without placing real orders."""

import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_TRADING_MODE = os.getenv("TRADING_MODE", "paper")

# In-memory order book — keyed by order_id
_open_orders: Dict[str, dict] = {}

_monitor_thread: Optional[threading.Thread] = None
_monitor_stop = threading.Event()


# ---------------------------------------------------------------------------
# Order placement
# ---------------------------------------------------------------------------

def place_order(
    pair: str,
    side: str,
    quantity: float,
    price: float,
    sl_price: float,
    tp_price: float,
    decision: dict,
    agent_outputs: Optional[dict] = None,
) -> dict:
    """
    Simulate a market order against the real testnet price.

    Steps:
    1. Verify TRADING_MODE=paper — raise immediately if not
    2. Log intended order BEFORE placing
    3. Get real current price from exchange (simulated fill)
    4. Store in portfolio state
    5. Send Telegram trade alert
    6. Log confirmed order AFTER placing
    7. Return order dict
    """
    if _TRADING_MODE != "paper":
        raise RuntimeError(
            "place_order called with TRADING_MODE != paper. "
            "Live trading requires explicit confirmation. Aborting to protect real funds."
        )

    order_id = str(uuid.uuid4())[:8]
    from monitoring.logger import log_trade

    intended = {
        "order_id": order_id, "pair": pair, "side": side,
        "quantity": quantity, "requested_price": price,
        "sl_price": sl_price, "tp_price": tp_price,
        "status": "pending", "paper": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    log_trade({**intended, "event": "order_intended"})

    try:
        from execution.ccxt_client import get_current_price
        fill_price = get_current_price(pair)
        if fill_price <= 0:
            fill_price = price

        # Validate TP is on the correct side of the actual fill price
        side_upper = side.upper()
        if side_upper in ("BUY", "LONG") and tp_price <= fill_price:
            raise ValueError(
                f"BUY rejected: TP {tp_price:.2f} <= entry {fill_price:.2f}"
            )
        if side_upper in ("SELL", "SHORT") and tp_price >= fill_price:
            raise ValueError(
                f"SELL rejected: TP {tp_price:.2f} >= entry {fill_price:.2f}"
            )

        order = {
            "order_id": order_id,
            "pair": pair,
            "side": side,
            "action": side.upper(),
            "quantity": quantity,
            "entry_price": fill_price,
            "requested_price": price,
            "sl_price": sl_price,
            "tp_price": tp_price,
            "status": "filled",
            "paper": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_outputs": agent_outputs or {},
            "confidence": decision.get("confidence", 0.0),
            "confluence_score": decision.get("confluence_score", 0),
        }

        from risk.portfolio import update_position
        update_position(order)
        _open_orders[order_id] = order

        from monitoring.telegram_alerts import send_trade_alert
        send_trade_alert(
            pair=pair, action=side.upper(),
            quantity=quantity, price=fill_price,
            confidence=decision.get("confidence", 0.0),
            sl=sl_price, tp=tp_price,
            confluence_score=decision.get("confluence_score", 0),
        )

        log_trade({**order, "event": "order_filled"})
        logger.info("Paper order filled: %s %s %s @ %.4f", order_id, side.upper(), pair, fill_price)
        return order

    except Exception as exc:
        logger.error("place_order failed for %s: %s", pair, exc)
        from monitoring.telegram_alerts import send_error_alert
        send_error_alert("Order Error", f"{pair} {side}: {exc}")
        log_trade({**intended, "event": "order_failed", "error": str(exc)})
        return {**intended, "status": "failed", "error": str(exc)}


def cancel_order(order_id: str, pair: str) -> dict:
    """Cancel a paper order. Safe to call if order no longer exists."""
    order = _open_orders.pop(order_id, None)
    if order is None:
        logger.warning("cancel_order: %s not found", order_id)
        return {"cancelled": False, "order_id": order_id}
    order["status"] = "cancelled"
    from monitoring.logger import log_trade
    log_trade({**order, "event": "order_cancelled"})
    return {"cancelled": True, "order_id": order_id}


def get_open_orders() -> List[dict]:
    """Return all currently tracked open paper orders."""
    return list(_open_orders.values())


# ---------------------------------------------------------------------------
# Position monitor (runs every 30 s in background thread)
# ---------------------------------------------------------------------------

def monitor_positions() -> None:
    """
    Check every open position against current market price.
    Closes position immediately on SL or TP hit, fires Telegram alert,
    and triggers the reflection engine for post-trade analysis.
    """
    try:
        from execution.ccxt_client import get_current_price
        from risk.portfolio import close_position
        from monitoring.telegram_alerts import send_trade_closed
        from agents.memory.reflection import reflect, write_lesson

        to_close = []
        for order_id, order in list(_open_orders.items()):
            pair   = order.get("pair", "")
            action = order.get("action", "BUY")
            sl     = float(order.get("sl_price", 0.0))
            tp     = float(order.get("tp_price", 0.0))

            current = get_current_price(pair)
            if current <= 0:
                continue

            if action == "BUY":
                close_reason = "SL_HIT" if current <= sl else ("TP_HIT" if current >= tp else None)
            else:  # SELL / short
                close_reason = "SL_HIT" if current >= sl else ("TP_HIT" if current <= tp else None)

            if close_reason:
                to_close.append((order_id, order, current, close_reason))

        for order_id, order, current_price, close_reason in to_close:
            _open_orders.pop(order_id, None)
            closed = close_position(order["pair"], current_price, close_reason)

            if closed:
                send_trade_closed(
                    pair=order["pair"],
                    action=order["action"],
                    entry=float(order.get("entry_price", 0.0)),
                    exit_price=current_price,
                    pnl=closed.get("pnl", 0.0),
                    pnl_pct=closed.get("pnl_pct", 0.0),
                    reason=close_reason,
                )
                try:
                    trade_result = {
                        **order,
                        "exit_price": current_price,
                        "close_reason": close_reason,
                        "pnl": closed.get("pnl", 0.0),
                        "pnl_pct": closed.get("pnl_pct", 0.0),
                        "win": closed.get("win", False),
                    }
                    lesson = reflect(trade_result, order.get("agent_outputs", {}))
                    write_lesson(lesson)
                except Exception as exc:
                    logger.error("Reflection failed for %s: %s", order["pair"], exc)

                from monitoring.logger import log_trade
                log_trade({
                    **order,
                    "exit_price": current_price,
                    "close_reason": close_reason,
                    "pnl": closed.get("pnl", 0.0),
                    "event": "position_closed",
                })

    except Exception as exc:
        logger.error("monitor_positions failed: %s", exc)


def _monitor_loop() -> None:
    while not _monitor_stop.is_set():
        monitor_positions()
        _monitor_stop.wait(timeout=30)


def start_monitor() -> None:
    """Start the paper-trader position monitor as a background daemon thread."""
    global _monitor_thread
    _monitor_stop.clear()
    _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True, name="paper-monitor")
    _monitor_thread.start()
    logger.info("Paper trader position monitor started")


def stop_monitor() -> None:
    """Stop the position monitor thread cleanly."""
    _monitor_stop.set()
    if _monitor_thread and _monitor_thread.is_alive():
        _monitor_thread.join(timeout=5)
