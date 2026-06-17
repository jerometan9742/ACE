"""Unit tests for Judas Swing manipulation candle detection."""

import pytest

from signal_engine.judas_swing import detect_judas_swing


def _c(open_, high, low, close, volume):
    return {"open": open_, "high": high, "low": low, "close": close, "volume": volume}


ASIA_HIGH = 102.0
ASIA_LOW = 98.0
AVG_VOL = 1000.0


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

def test_result_has_all_required_keys():
    result = detect_judas_swing([], ASIA_HIGH, ASIA_LOW, AVG_VOL)
    for key in ["detected", "direction", "sweep_price", "return_candle_index", "confidence"]:
        assert key in result, f"Missing key: {key}"


def test_returns_not_detected_for_empty_candles():
    result = detect_judas_swing([], ASIA_HIGH, ASIA_LOW, AVG_VOL)
    assert result["detected"] is False


def test_returns_not_detected_for_zero_avg_volume():
    candles = [_c(100, 105, 99, 101, 400)]
    result = detect_judas_swing(candles, ASIA_HIGH, ASIA_LOW, 0)
    assert result["detected"] is False


# ---------------------------------------------------------------------------
# Bearish Judas Swing
# ---------------------------------------------------------------------------

def test_bearish_judas_detected():
    """Spike above Asia high on low volume, closes back below within 1 candle."""
    candles = [
        _c(101, 102, 100, 101, 1000),   # normal
        _c(101, 105, 100, 104, 400),    # spike above 102, LOW volume (< 800)
        _c(104, 104, 100, 101, 900),    # closes back below 102
    ]
    result = detect_judas_swing(candles, ASIA_HIGH, ASIA_LOW, AVG_VOL)
    assert result["detected"] is True
    assert result["direction"] == "bearish"
    assert result["sweep_price"] == 105.0


def test_bearish_judas_returns_within_2_candles():
    """Returns inside range within 2 candles — still a Judas but lower confidence."""
    candles = [
        _c(101, 102, 100, 101, 1000),
        _c(101, 105, 100, 104, 400),    # spike
        _c(104, 105, 102, 103, 800),    # still above asia_high
        _c(103, 103, 100, 101, 700),    # closes below 102
    ]
    result = detect_judas_swing(candles, ASIA_HIGH, ASIA_LOW, AVG_VOL)
    assert result["detected"] is True
    assert result["direction"] == "bearish"
    assert result["confidence"] < 1.0  # 2-bar return → lower confidence


# ---------------------------------------------------------------------------
# Bullish Judas Swing
# ---------------------------------------------------------------------------

def test_bullish_judas_detected():
    """Spike below Asia low on low volume, closes back above within 1 candle."""
    candles = [
        _c(99, 100, 98, 99, 900),
        _c(99, 100, 95, 96, 400),    # spike below 98, LOW volume
        _c(96, 100, 96, 99, 800),    # closes above 98
    ]
    result = detect_judas_swing(candles, ASIA_HIGH, ASIA_LOW, AVG_VOL)
    assert result["detected"] is True
    assert result["direction"] == "bullish"
    assert result["sweep_price"] == 95.0


# ---------------------------------------------------------------------------
# No Judas conditions
# ---------------------------------------------------------------------------

def test_no_judas_spike_on_high_volume():
    """Spike above Asia high but volume is HIGH — not a manipulation candle."""
    candles = [
        _c(101, 102, 100, 101, 1000),
        _c(101, 105, 100, 103, 2500),  # spike but volume > avg → not Judas
        _c(103, 103, 100, 101, 900),
    ]
    result = detect_judas_swing(candles, ASIA_HIGH, ASIA_LOW, AVG_VOL)
    assert result["detected"] is False


def test_no_judas_when_price_never_returns():
    """Breaks above Asia high with low volume but never closes back inside."""
    candles = [
        _c(101, 102, 100, 101, 1000),
        _c(101, 105, 100, 104, 400),   # spike
        _c(104, 106, 103, 105, 600),   # still above 102 — no return
        _c(105, 107, 104, 106, 700),
    ]
    result = detect_judas_swing(candles, ASIA_HIGH, ASIA_LOW, AVG_VOL)
    assert result["detected"] is False


def test_confidence_is_highest_for_1_bar_return():
    candles = [
        _c(101, 102, 100, 101, 1000),
        _c(101, 105, 100, 104, 400),  # spike
        _c(104, 104, 100, 101, 900),  # returns in 1 bar
    ]
    result = detect_judas_swing(candles, ASIA_HIGH, ASIA_LOW, AVG_VOL)
    assert result["confidence"] > 0.9


def test_returns_most_recent_judas_not_oldest():
    """With two Judas swings in the series, the most recent one must be returned."""
    old_sweep  = _c(101, 105, 100, 104, 400)  # bearish: high=105 > ASIA_HIGH=102, low vol
    old_return = _c(104, 104, 100, 101, 900)  # closes < 102

    filler = [_c(100, 101, 99, 100, 900) for _ in range(10)]

    new_sweep  = _c(99, 100, 95, 96, 400)  # bullish: low=95 < ASIA_LOW=98, low vol
    new_return = _c(96, 100, 96, 99, 800)  # closes > 98

    candles = [_c(101, 102, 100, 101, 1000), old_sweep, old_return] + filler + [new_sweep, new_return]
    result = detect_judas_swing(candles, ASIA_HIGH, ASIA_LOW, AVG_VOL)

    assert result["detected"] is True
    assert result["direction"] == "bullish", "should return the most recent swing, not the old resolved one"
    assert result["sweep_price"] == 95.0
