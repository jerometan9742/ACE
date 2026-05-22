"""Unit tests for the Confluence Engine — validates all 6 scoring factors independently and combined."""

import pytest

from signal_engine.confluence import score_setup

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _c(open_=100, high=102, low=98, close=100, volume=1000):
    return {"open": open_, "high": high, "low": low, "close": close, "volume": volume}


BASE_CANDLES = [_c() for _ in range(20)]
PRICE = 100.0


def _session(active: bool = True, name: str = "london") -> dict:
    return {
        "name": name,
        "is_active": active,
        "confidence_threshold": 7.0 if active else 0.0,
        "utc_start": "07:00" if active else None,
        "utc_end": "09:00" if active else None,
    }


def _fvg(price: float = PRICE) -> list:
    return [{"type": "bullish", "top": price + 0.3, "bottom": price - 0.3, "mitigated": False}]


def _ob(price: float = PRICE) -> list:
    return [{"type": "bullish", "high": price + 0.1, "low": price - 0.1, "mitigated": False}]


def _bos(detected: bool = True) -> dict:
    return {"bos_detected": detected, "bos_direction": "bullish" if detected else ""}


def _judas(detected: bool = True) -> dict:
    return {"detected": detected, "direction": "bullish" if detected else ""}


def _vol(confirms: bool = True) -> dict:
    return {"confirms": confirms}


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

def test_result_has_all_required_keys():
    result = score_setup(
        "BTC/USDT", PRICE, BASE_CANDLES,
        _session(False), [], [], _bos(False), _judas(False), _vol(False),
    )
    for key in ["score", "breakdown", "passes_threshold", "confidence_tier", "reasoning"]:
        assert key in result, f"Missing key: {key}"


def test_breakdown_has_all_factor_keys():
    result = score_setup(
        "BTC/USDT", PRICE, BASE_CANDLES,
        _session(False), [], [], _bos(False), _judas(False), _vol(False),
    )
    for key in ["fvg", "order_block", "kill_zone", "bos", "judas", "volume"]:
        assert key in result["breakdown"], f"Missing breakdown key: {key}"


# ---------------------------------------------------------------------------
# Individual factor scoring
# ---------------------------------------------------------------------------

def test_kill_zone_adds_2():
    r_in = score_setup("BTC/USDT", PRICE, BASE_CANDLES, _session(True), [], [], _bos(False), _judas(False), _vol(False))
    r_out = score_setup("BTC/USDT", PRICE, BASE_CANDLES, _session(False), [], [], _bos(False), _judas(False), _vol(False))
    assert r_in["breakdown"]["kill_zone"] == 2
    assert r_out["breakdown"]["kill_zone"] == 0
    assert r_in["score"] - r_out["score"] == 2


def test_fvg_adds_2():
    r = score_setup("BTC/USDT", PRICE, BASE_CANDLES, _session(False), _fvg(), [], _bos(False), _judas(False), _vol(False))
    assert r["breakdown"]["fvg"] == 2


def test_fvg_zero_when_no_fvg():
    r = score_setup("BTC/USDT", PRICE, BASE_CANDLES, _session(False), [], [], _bos(False), _judas(False), _vol(False))
    assert r["breakdown"]["fvg"] == 0


def test_ob_adds_2():
    r = score_setup("BTC/USDT", PRICE, BASE_CANDLES, _session(False), [], _ob(), _bos(False), _judas(False), _vol(False))
    assert r["breakdown"]["order_block"] == 2


def test_ob_zero_when_no_ob():
    r = score_setup("BTC/USDT", PRICE, BASE_CANDLES, _session(False), [], [], _bos(False), _judas(False), _vol(False))
    assert r["breakdown"]["order_block"] == 0


def test_bos_adds_1():
    r = score_setup("BTC/USDT", PRICE, BASE_CANDLES, _session(False), [], [], _bos(True), _judas(False), _vol(False))
    assert r["breakdown"]["bos"] == 1


def test_bos_zero_when_not_detected():
    r = score_setup("BTC/USDT", PRICE, BASE_CANDLES, _session(False), [], [], _bos(False), _judas(False), _vol(False))
    assert r["breakdown"]["bos"] == 0


def test_judas_adds_2():
    r = score_setup("BTC/USDT", PRICE, BASE_CANDLES, _session(False), [], [], _bos(False), _judas(True), _vol(False))
    assert r["breakdown"]["judas"] == 2


def test_judas_zero_when_not_detected():
    r = score_setup("BTC/USDT", PRICE, BASE_CANDLES, _session(False), [], [], _bos(False), _judas(False), _vol(False))
    assert r["breakdown"]["judas"] == 0


def test_volume_adds_1():
    r = score_setup("BTC/USDT", PRICE, BASE_CANDLES, _session(False), [], [], _bos(False), _judas(False), _vol(True))
    assert r["breakdown"]["volume"] == 1


def test_volume_zero_when_not_confirming():
    r = score_setup("BTC/USDT", PRICE, BASE_CANDLES, _session(False), [], [], _bos(False), _judas(False), _vol(False))
    assert r["breakdown"]["volume"] == 0


# ---------------------------------------------------------------------------
# Combined scoring
# ---------------------------------------------------------------------------

def test_zero_score_when_no_factors():
    r = score_setup("BTC/USDT", PRICE, BASE_CANDLES, _session(False), [], [], _bos(False), _judas(False), _vol(False))
    assert r["score"] == 0
    assert r["passes_threshold"] is False


def test_full_score_all_factors_passes_threshold():
    r = score_setup(
        "BTC/USDT", PRICE, BASE_CANDLES,
        _session(True), _fvg(), _ob(), _bos(True), _judas(True), _vol(True),
    )
    assert r["score"] == 10  # 2+2+2+1+2+1 = 10
    assert r["passes_threshold"] is True


def test_score_capped_at_10():
    r = score_setup(
        "BTC/USDT", PRICE, BASE_CANDLES,
        _session(True), _fvg(), _ob(), _bos(True), _judas(True), _vol(True),
    )
    assert r["score"] <= 10


def test_passes_threshold_false_below_7():
    r = score_setup(
        "BTC/USDT", PRICE, BASE_CANDLES,
        _session(False), [], [], _bos(True), _judas(False), _vol(True),
    )
    assert r["score"] == 2  # bos=1 + vol=1
    assert r["passes_threshold"] is False


def test_mitigated_fvg_does_not_score():
    fvgs = [{"type": "bullish", "top": PRICE + 0.3, "bottom": PRICE - 0.3, "mitigated": True}]
    r = score_setup("BTC/USDT", PRICE, BASE_CANDLES, _session(False), fvgs, [], _bos(False), _judas(False), _vol(False))
    assert r["breakdown"]["fvg"] == 0


def test_mitigated_ob_does_not_score():
    obs = [{"type": "bullish", "high": PRICE + 0.1, "low": PRICE - 0.1, "mitigated": True}]
    r = score_setup("BTC/USDT", PRICE, BASE_CANDLES, _session(False), [], obs, _bos(False), _judas(False), _vol(False))
    assert r["breakdown"]["order_block"] == 0


def test_reasoning_list_populated_for_active_factors():
    r = score_setup(
        "BTC/USDT", PRICE, BASE_CANDLES,
        _session(True), _fvg(), _ob(), _bos(True), _judas(True), _vol(True),
    )
    assert len(r["reasoning"]) == 6  # one entry per active factor


def test_confidence_tier_low_for_score_under_7():
    r = score_setup("BTC/USDT", PRICE, BASE_CANDLES, _session(False), [], [], _bos(False), _judas(False), _vol(False))
    assert r["confidence_tier"] == "low"


def test_confidence_tier_medium_for_score_7():
    # kill_zone(2) + fvg(2) + judas(2) + bos(1) = 7
    r = score_setup("BTC/USDT", PRICE, BASE_CANDLES, _session(True), _fvg(), [], _bos(True), _judas(True), _vol(False))
    assert r["score"] == 7
    assert r["confidence_tier"] == "medium"
