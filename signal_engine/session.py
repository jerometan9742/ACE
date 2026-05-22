"""Kill zone detection — returns current session name and whether we are inside an active trading window."""

from datetime import datetime, timezone, time as dtime
from typing import Optional


_SESSIONS = [
    {
        "name": "asia",
        "start": (0, 0),
        "end": (4, 0),
        "is_active": False,
        "confidence_threshold": 0.0,
    },
    {
        "name": "london",
        "start": (7, 0),
        "end": (9, 0),
        "is_active": True,
        "confidence_threshold": 7.0,
    },
    {
        "name": "ny_open",
        "start": (13, 30),
        "end": (15, 0),
        "is_active": True,
        "confidence_threshold": 7.0,
    },
    {
        "name": "ny_afternoon",
        "start": (17, 0),
        "end": (19, 0),
        "is_active": True,
        "confidence_threshold": 7.5,
    },
]

_OUTSIDE = {
    "name": "outside",
    "is_active": False,
    "confidence_threshold": 0.0,
    "utc_start": None,
    "utc_end": None,
}


def get_current_session(utc_now: Optional[datetime] = None) -> dict:
    """
    Return the current trading session based on UTC time.

    Returns dict with: name, is_active, confidence_threshold, utc_start, utc_end.
    utc_start/utc_end are None when outside all defined sessions.
    """
    if utc_now is None:
        utc_now = datetime.now(timezone.utc)

    current = utc_now.time().replace(second=0, microsecond=0)

    for session in _SESSIONS:
        sh, sm = session["start"]
        eh, em = session["end"]
        start = dtime(sh, sm)
        end = dtime(eh, em)
        if start <= current < end:
            return {
                "name": session["name"],
                "is_active": session["is_active"],
                "confidence_threshold": session["confidence_threshold"],
                "utc_start": f"{sh:02d}:{sm:02d}",
                "utc_end": f"{eh:02d}:{em:02d}",
            }

    return _OUTSIDE.copy()


def is_trading_allowed(utc_now: Optional[datetime] = None) -> bool:
    """Return True only if we are currently inside an active kill zone."""
    return get_current_session(utc_now)["is_active"]


def get_session_confidence_threshold(utc_now: Optional[datetime] = None) -> float:
    """Return the minimum confluence confidence threshold for the current session (0.0 if outside)."""
    return get_current_session(utc_now)["confidence_threshold"]
