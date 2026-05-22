"""Unit tests for kill zone detection — validates all 4 sessions and the outside window."""

from datetime import datetime, timezone

import pytest

from signal_engine.session import (
    get_current_session,
    get_session_confidence_threshold,
    is_trading_allowed,
)


def _utc(hour: int, minute: int = 0) -> datetime:
    return datetime(2024, 1, 15, hour, minute, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# get_current_session
# ---------------------------------------------------------------------------

def test_london_session_detected():
    s = get_current_session(_utc(8, 0))
    assert s["name"] == "london"
    assert s["is_active"] is True
    assert s["confidence_threshold"] == 7.0
    assert s["utc_start"] == "07:00"
    assert s["utc_end"] == "09:00"


def test_london_session_boundary_start():
    s = get_current_session(_utc(7, 0))
    assert s["name"] == "london"


def test_london_session_boundary_end():
    # 09:00 is the exclusive end — should be outside
    s = get_current_session(_utc(9, 0))
    assert s["name"] != "london"


def test_ny_open_session_detected():
    s = get_current_session(_utc(14, 0))
    assert s["name"] == "ny_open"
    assert s["is_active"] is True
    assert s["confidence_threshold"] == 7.0


def test_ny_open_boundary_start():
    s = get_current_session(_utc(13, 30))
    assert s["name"] == "ny_open"


def test_ny_afternoon_session_detected():
    s = get_current_session(_utc(18, 0))
    assert s["name"] == "ny_afternoon"
    assert s["is_active"] is True
    assert s["confidence_threshold"] == 7.5


def test_ny_afternoon_boundary_start():
    s = get_current_session(_utc(17, 0))
    assert s["name"] == "ny_afternoon"


def test_asia_session_detected():
    s = get_current_session(_utc(2, 0))
    assert s["name"] == "asia"
    assert s["is_active"] is False
    assert s["confidence_threshold"] == 0.0


def test_outside_session_detected():
    s = get_current_session(_utc(20, 0))
    assert s["name"] == "outside"
    assert s["is_active"] is False
    assert s["utc_start"] is None
    assert s["utc_end"] is None


def test_outside_session_early_morning():
    s = get_current_session(_utc(5, 0))
    assert s["name"] == "outside"


# ---------------------------------------------------------------------------
# is_trading_allowed
# ---------------------------------------------------------------------------

def test_trading_allowed_inside_london():
    assert is_trading_allowed(_utc(8, 0)) is True


def test_trading_allowed_inside_ny_open():
    assert is_trading_allowed(_utc(14, 0)) is True


def test_trading_not_allowed_asia():
    assert is_trading_allowed(_utc(2, 0)) is False


def test_trading_not_allowed_outside():
    assert is_trading_allowed(_utc(21, 0)) is False


# ---------------------------------------------------------------------------
# get_session_confidence_threshold
# ---------------------------------------------------------------------------

def test_threshold_london():
    assert get_session_confidence_threshold(_utc(8, 0)) == 7.0


def test_threshold_ny_afternoon():
    assert get_session_confidence_threshold(_utc(17, 30)) == 7.5


def test_threshold_outside_is_zero():
    assert get_session_confidence_threshold(_utc(20, 0)) == 0.0


def test_all_sessions_return_required_keys():
    required = {"name", "is_active", "confidence_threshold", "utc_start", "utc_end"}
    for hour in [2, 8, 14, 18, 20]:
        s = get_current_session(_utc(hour))
        assert required.issubset(s.keys()), f"Missing keys at hour {hour}: {required - s.keys()}"
