"""Trade filter and kill switch — enforces daily loss limits, confidence thresholds, and emergency stop."""

import json
import os
import time
from datetime import datetime, timezone
from typing import List

from dotenv import load_dotenv

load_dotenv()

_KILL_SWITCH_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "kill_switch.lock")
)

_MAX_DAILY_LOSS_PCT = float(os.getenv("MAX_DAILY_LOSS_PCT", "0.03"))
_MAX_TRADES_PER_SESSION = int(os.getenv("MAX_TRADES_PER_SESSION", "10"))
_CORRELATION_LIMIT = float(os.getenv("CORRELATION_LIMIT", "0.85"))
_MAX_OPEN_POSITIONS = int(os.getenv("MAX_CONCURRENT_POSITIONS", "3"))
_SIGNAL_MAX_AGE_SECONDS = 60


# ---------------------------------------------------------------------------
# Kill switch — file-based so it survives process restarts
# ---------------------------------------------------------------------------

def activate_kill_switch(reason: str) -> None:
    """Create kill_switch.lock with reason and UTC timestamp."""
    payload = {
        "reason": reason,
        "activated_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(_KILL_SWITCH_FILE, "w") as f:
        json.dump(payload, f)


def deactivate_kill_switch() -> None:
    """Remove kill_switch.lock. Safe to call when no lock exists."""
    try:
        os.remove(_KILL_SWITCH_FILE)
    except FileNotFoundError:
        pass


def is_kill_switch_active() -> bool:
    """Returns True if kill_switch.lock exists on disk."""
    return os.path.exists(_KILL_SWITCH_FILE)


# ---------------------------------------------------------------------------
# Final trade filter — 9 ordered checks
# ---------------------------------------------------------------------------

def check_trade(decision: dict, portfolio: dict) -> dict:
    """
    Run 9 checks in strict order. First failure blocks the trade immediately.

    decision : fund_manager output — must contain action, confidence, signal_timestamp
    portfolio: {session, daily_pnl, equity, trades_this_session,
                open_positions, correlation}

    Returns: {approved, blocked_by, reason, risk_flags, adjusted_size}
    """
    risk_flags: List[str] = []

    def _block(by: str, reason: str) -> dict:
        return {
            "approved": False,
            "blocked_by": by,
            "reason": reason,
            "risk_flags": risk_flags + [reason],
            "adjusted_size": 0.0,
        }

    def _approve(size: float) -> dict:
        return {
            "approved": True,
            "blocked_by": "",
            "reason": "",
            "risk_flags": risk_flags,
            "adjusted_size": size,
        }

    # 1. Kill switch — checked before anything else
    if is_kill_switch_active():
        return _block("kill_switch", "Kill switch is active")

    # 2. HOLD passthrough — no sizing needed
    if decision.get("action", "HOLD") == "HOLD":
        return _approve(0.0)

    confidence = float(decision.get("confidence", 0.0))
    signal_timestamp = float(decision.get("signal_timestamp", time.time()))
    session = portfolio.get("session", {})
    daily_pnl = float(portfolio.get("daily_pnl", 0.0))
    equity = float(portfolio.get("equity", 1.0))
    trades_this_session = int(portfolio.get("trades_this_session", 0))
    open_positions = portfolio.get("open_positions", [])
    correlation = float(portfolio.get("correlation", 0.0))

    # 3. Confidence gate — session threshold varies by kill zone
    from risk.kill_zones import get_session_threshold
    threshold = get_session_threshold(session)
    if confidence < threshold:
        return _block(
            "confidence_gate",
            f"Confidence {confidence:.1f} below session threshold {threshold:.1f}",
        )

    # 4. Kill zone gate — must be inside an active trading window
    session_name = session.get("name", "outside")
    if not session.get("is_active", False) or session_name not in ("london", "ny_open", "ny_afternoon"):
        return _block("kill_zone_gate", f"Outside active kill zone (session={session_name})")

    # 5. Daily loss limit — activates kill switch to stop further trading
    if equity > 0 and abs(daily_pnl / equity) >= _MAX_DAILY_LOSS_PCT:
        activate_kill_switch(
            f"Daily loss limit hit: pnl={daily_pnl:.2f} equity={equity:.2f}"
        )
        return _block(
            "daily_loss_limit",
            f"Daily loss limit {_MAX_DAILY_LOSS_PCT * 100:.1f}% hit — kill switch activated",
        )

    # 6. Max trades per session
    if trades_this_session >= _MAX_TRADES_PER_SESSION:
        return _block(
            "max_trades",
            f"Max trades per session ({_MAX_TRADES_PER_SESSION}) reached",
        )

    # 7. Position limit — max 3 concurrent open positions
    if len(open_positions) >= _MAX_OPEN_POSITIONS:
        return _block(
            "position_limit",
            f"Max open positions ({_MAX_OPEN_POSITIONS}) reached",
        )

    # 8. Correlation — avoid double exposure on correlated pairs
    if correlation > _CORRELATION_LIMIT:
        return _block(
            "correlation",
            f"Correlation {correlation:.2f} exceeds limit {_CORRELATION_LIMIT}",
        )

    # 9. Stale signal — intraday signals expire after 60 seconds
    age = time.time() - signal_timestamp
    if age > _SIGNAL_MAX_AGE_SECONDS:
        return _block(
            "stale_signal",
            f"Signal is {age:.0f}s old (max {_SIGNAL_MAX_AGE_SECONDS}s)",
        )

    return _approve(float(decision.get("position_size_multiplier", 1.0)))
