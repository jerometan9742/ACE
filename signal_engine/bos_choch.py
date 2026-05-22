"""Break of Structure and Change of Character detection — confirms momentum direction or flags reversals on 15m charts."""

from typing import List, Dict


def _find_swing_highs(candles: List[Dict], lookback: int = 2) -> List[int]:
    """Return indices of swing high candles (local maxima with lookback bars on each side)."""
    highs = []
    for i in range(lookback, len(candles) - lookback):
        if all(candles[i]["high"] > candles[i - j]["high"] for j in range(1, lookback + 1)) and all(
            candles[i]["high"] > candles[i + j]["high"] for j in range(1, lookback + 1)
        ):
            highs.append(i)
    return highs


def _find_swing_lows(candles: List[Dict], lookback: int = 2) -> List[int]:
    """Return indices of swing low candles (local minima with lookback bars on each side)."""
    lows = []
    for i in range(lookback, len(candles) - lookback):
        if all(candles[i]["low"] < candles[i - j]["low"] for j in range(1, lookback + 1)) and all(
            candles[i]["low"] < candles[i + j]["low"] for j in range(1, lookback + 1)
        ):
            lows.append(i)
    return lows


def detect_bos_choch(candles: List[Dict]) -> Dict:
    """
    Detect Break of Structure (BOS) and Change of Character (CHoCH).

    BOS: current close above most recent swing high (bullish) or below swing low (bearish).
    CHoCH: after series of higher highs/lows, price breaks the opposite structural level.
    Lookback window: last 20 candles, swing detection uses 2-bar lookback.

    All data must be passed in — no fetching inside this function.

    Returns dict: bos_detected, bos_direction, choch_detected, choch_direction,
                  swing_high, swing_low, last_higher_high, last_lower_low.
    """
    result = {
        "bos_detected": False,
        "bos_direction": "",
        "choch_detected": False,
        "choch_direction": "",
        "swing_high": 0.0,
        "swing_low": 0.0,
        "last_higher_high": 0.0,
        "last_lower_low": 0.0,
    }

    if len(candles) < 6:
        return result

    window = candles[-20:] if len(candles) >= 20 else candles[:]
    current = window[-1]

    sh_indices = _find_swing_highs(window, lookback=2)
    sl_indices = _find_swing_lows(window, lookback=2)

    # Exclude the last bar itself from reference structure
    valid_sh = [i for i in sh_indices if i < len(window) - 1]
    valid_sl = [i for i in sl_indices if i < len(window) - 1]

    swing_high = window[valid_sh[-1]]["high"] if valid_sh else max(c["high"] for c in window[:-1])
    swing_low = window[valid_sl[-1]]["low"] if valid_sl else min(c["low"] for c in window[:-1])

    result["swing_high"] = swing_high
    result["swing_low"] = swing_low

    # BOS
    if current["close"] > swing_high:
        result["bos_detected"] = True
        result["bos_direction"] = "bullish"
    elif current["close"] < swing_low:
        result["bos_detected"] = True
        result["bos_direction"] = "bearish"

    # CHoCH: requires at least 2 swing highs and 2 swing lows
    if len(valid_sh) >= 2 and len(valid_sl) >= 2:
        sh_prices = [window[i]["high"] for i in valid_sh]
        sl_prices = [window[i]["low"] for i in valid_sl]

        result["last_higher_high"] = sh_prices[-1]
        result["last_lower_low"] = sl_prices[-1]

        # Bullish trend (higher highs) → bearish CHoCH: close below most recent higher low
        if sh_prices[-1] > sh_prices[-2]:
            higher_lows = [
                sl_prices[i] for i in range(1, len(sl_prices)) if sl_prices[i] > sl_prices[i - 1]
            ]
            if higher_lows and current["close"] < higher_lows[-1]:
                result["choch_detected"] = True
                result["choch_direction"] = "bearish"

        # Bearish trend (lower lows) → bullish CHoCH: close above most recent lower high
        elif sl_prices[-1] < sl_prices[-2]:
            lower_highs = [
                sh_prices[i] for i in range(1, len(sh_prices)) if sh_prices[i] < sh_prices[i - 1]
            ]
            if lower_highs and current["close"] > lower_highs[-1]:
                result["choch_detected"] = True
                result["choch_direction"] = "bullish"

    return result
