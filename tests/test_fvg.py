"""Unit tests for Fair Value Gap detection — validates bullish and bearish FVG identification and mitigation tracking."""

import pytest

from signal_engine.fvg import detect_fvgs, get_active_fvgs, is_price_in_fvg


def _c(open_, high, low, close, volume=1000):
    return {"open": open_, "high": high, "low": low, "close": close, "volume": volume}


# ---------------------------------------------------------------------------
# detect_fvgs
# ---------------------------------------------------------------------------

def test_bullish_fvg_detected():
    """candle[0].high=102 < candle[2].low=103 → bullish FVG."""
    candles = [
        _c(100, 102, 99, 101),   # high=102
        _c(101, 105, 100, 104),  # impulse
        _c(103, 108, 103, 107),  # low=103 > 102
    ]
    fvgs = detect_fvgs(candles)
    assert len(fvgs) == 1
    assert fvgs[0]["type"] == "bullish"
    assert fvgs[0]["bottom"] == 102
    assert fvgs[0]["top"] == 103


def test_bearish_fvg_detected():
    """candle[0].low=98 > candle[2].high=96 → bearish FVG."""
    candles = [
        _c(100, 101, 98, 99),   # low=98
        _c(99,  100, 94, 95),   # impulse
        _c(95,  96,  90, 91),   # high=96 < 98
    ]
    fvgs = detect_fvgs(candles)
    assert len(fvgs) == 1
    assert fvgs[0]["type"] == "bearish"
    assert fvgs[0]["top"] == 98
    assert fvgs[0]["bottom"] == 96


def test_no_fvg_when_no_gap():
    candles = [
        _c(100, 102, 99, 101),
        _c(101, 103, 100, 102),
        _c(102, 104, 101, 103),  # low=101 < high=102 — overlaps, no FVG
    ]
    assert detect_fvgs(candles) == []


def test_fvg_strength_positive():
    candles = [
        _c(100, 102, 99, 101),
        _c(101, 105, 100, 104),
        _c(103, 108, 103, 107),
    ]
    fvgs = detect_fvgs(candles)
    assert fvgs[0]["strength"] > 0


def test_returns_empty_list_for_short_series():
    assert detect_fvgs([]) == []
    assert detect_fvgs([_c(100, 102, 99, 101)]) == []
    assert detect_fvgs([_c(100, 102, 99, 101), _c(101, 103, 100, 102)]) == []


# ---------------------------------------------------------------------------
# Mitigation
# ---------------------------------------------------------------------------

def test_bullish_fvg_mitigated_when_price_fills_gap():
    candles = [
        _c(100, 102, 99, 101),   # FVG bottom = 102
        _c(101, 105, 100, 104),
        _c(103, 108, 103, 107),  # FVG at 102–103
        _c(105, 106, 100, 101),  # close=101 <= 102 → mitigated
    ]
    fvgs = detect_fvgs(candles)
    assert len(fvgs) == 1
    assert fvgs[0]["mitigated"] is True


def test_bullish_fvg_not_mitigated():
    candles = [
        _c(100, 102, 99, 101),
        _c(101, 105, 100, 104),
        _c(103, 108, 103, 107),  # FVG at 102–103 — no subsequent candle
    ]
    fvgs = detect_fvgs(candles)
    assert fvgs[0]["mitigated"] is False


# ---------------------------------------------------------------------------
# get_active_fvgs
# ---------------------------------------------------------------------------

def test_active_fvgs_excludes_mitigated():
    candles = [
        _c(100, 102, 99, 101),
        _c(101, 105, 100, 104),
        _c(103, 108, 103, 107),  # FVG 102–103
        _c(105, 106, 100, 101),  # mitigates it
    ]
    active = get_active_fvgs(candles)
    assert active == []


def test_active_fvgs_includes_unmitigated():
    candles = [
        _c(100, 102, 99, 101),
        _c(101, 105, 100, 104),
        _c(103, 108, 103, 107),  # FVG 102–103 — unmitigated
    ]
    active = get_active_fvgs(candles)
    assert len(active) == 1
    assert active[0]["mitigated"] is False


# ---------------------------------------------------------------------------
# is_price_in_fvg
# ---------------------------------------------------------------------------

def test_price_inside_fvg_returns_fvg():
    candles = [
        _c(100, 102, 99, 101),
        _c(101, 105, 100, 104),
        _c(103, 108, 103, 107),  # FVG 102–103
    ]
    fvgs = get_active_fvgs(candles)
    result = is_price_in_fvg(102.5, fvgs)
    assert result != {}
    assert result["type"] == "bullish"


def test_price_outside_fvg_returns_empty_dict():
    candles = [
        _c(100, 102, 99, 101),
        _c(101, 105, 100, 104),
        _c(103, 108, 103, 107),
    ]
    fvgs = get_active_fvgs(candles)
    result = is_price_in_fvg(200.0, fvgs)
    assert result == {}


def test_price_in_proximity_returns_fvg():
    """Price within 0.1% of FVG edge should still match."""
    candles = [
        _c(100, 102, 99, 101),
        _c(101, 105, 100, 104),
        _c(103, 108, 103, 107),  # FVG bottom = 102
    ]
    fvgs = get_active_fvgs(candles)
    # 102 * 0.001 = 0.102 below bottom
    result = is_price_in_fvg(101.95, fvgs)
    assert result != {}


def test_is_price_in_fvg_empty_list():
    assert is_price_in_fvg(100.0, []) == {}
