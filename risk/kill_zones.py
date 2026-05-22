"""Session-based trading windows — gates entries to London open, NY open, NY afternoon kill zones only."""

import os

from dotenv import load_dotenv

load_dotenv()

# Shared path — kill_zones checks the file; risk_gate owns activate/deactivate
_KILL_SWITCH_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "kill_switch.lock")
)

_ACTIVE_SESSIONS = {"london", "ny_open", "ny_afternoon"}


def is_entry_allowed(session: dict) -> bool:
    """
    Returns True only if session is an active kill zone and kill switch is off.

    Returns False if:
    - Outside all kill zones (asia / outside / unknown)
    - Kill switch lock file exists
    (Daily loss limit is enforced in risk_gate.check_trade — requires portfolio data.)
    """
    if os.path.exists(_KILL_SWITCH_FILE):
        return False
    name = session.get("name", "outside")
    return session.get("is_active", False) and name in _ACTIVE_SESSIONS


def get_session_threshold(session: dict) -> float:
    """
    Minimum confidence score required to enter a trade in the current session.

    london / ny_open  → 7.0
    ny_afternoon      → 7.5
    outside / asia    → 10.0  (effectively blocks all entries)
    """
    name = session.get("name", "outside")
    if name in ("london", "ny_open"):
        return 7.0
    if name == "ny_afternoon":
        return 7.5
    return 10.0
