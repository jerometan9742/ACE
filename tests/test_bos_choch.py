"""Unit tests for Break of Structure and Change of Character detection."""

import pytest

from signal_engine.bos_choch import detect_bos_choch


def _c(open_, high, low, close, volume=1000):
    return {"open": open_, "high": high, "low": low, "close": close, "volume": volume}


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

def test_result_has_all_required_keys():
    candles = [_c(100, 102, 98, 100) for _ in range(10)]
    result = detect_bos_choch(candles)
    for key in [
        "bos_detected",
        "bos_direction",
        "choch_detected",
        "choch_direction",
        "swing_high",
        "swing_low",
        "last_higher_high",
        "last_lower_low",
    ]:
        assert key in result, f"Missing key: {key}"


def test_returns_empty_result_for_short_series():
    result = detect_bos_choch([_c(100, 102, 98, 100)] * 3)
    assert result["bos_detected"] is False
    assert result["choch_detected"] is False


# ---------------------------------------------------------------------------
# BOS
# ---------------------------------------------------------------------------

def test_bullish_bos_detected():
    """
    Monotonically rising series → swing_high = max high before last candle.
    Final candle closes well above that → bullish BOS.
    """
    candles = []
    for i in range(15):
        p = 100 + i
        candles.append(_c(p, p + 2, p - 1, p + 1))
    # Big close above the prior swing high (max high ≈ 116)
    candles.append(_c(115, 130, 114, 128))

    result = detect_bos_choch(candles)
    assert result["bos_detected"] is True
    assert result["bos_direction"] == "bullish"


def test_bearish_bos_detected():
    """
    Monotonically falling series → swing_low = min low before last candle.
    Final candle closes well below that → bearish BOS.
    """
    candles = []
    for i in range(15):
        p = 100 - i
        candles.append(_c(p, p + 1, p - 2, p - 1))
    # Big close below the prior swing low (min low ≈ 84)
    candles.append(_c(86, 87, 70, 72))

    result = detect_bos_choch(candles)
    assert result["bos_detected"] is True
    assert result["bos_direction"] == "bearish"


def test_no_bos_when_price_stays_inside_range():
    """Flat, ranging candles — current close stays within range → no BOS."""
    candles = [_c(100, 102, 98, 100) for _ in range(10)]
    # Final candle still inside range
    candles.append(_c(100, 101, 99, 100))
    result = detect_bos_choch(candles)
    assert result["bos_detected"] is False


def test_swing_high_and_low_are_positive():
    candles = [_c(100 + i % 3, 102 + i % 3, 98 + i % 2, 100 + i % 3) for i in range(12)]
    result = detect_bos_choch(candles)
    assert result["swing_high"] > 0
    assert result["swing_low"] > 0


def test_bos_direction_empty_when_no_bos():
    candles = [_c(100, 102, 98, 100) for _ in range(10)]
    candles.append(_c(100, 101, 99, 100))
    result = detect_bos_choch(candles)
    assert result["bos_direction"] == ""
