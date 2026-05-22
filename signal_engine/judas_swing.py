"""Judas Swing detector — identifies manipulation candles that sweep liquidity outside the Asia range on low volume."""

from typing import List, Dict

_LOW_VOLUME_RATIO = 0.8  # sweep candle volume must be < 80% of avg_volume


def detect_judas_swing(
    candles: List[Dict],
    asia_high: float,
    asia_low: float,
    avg_volume: float,
) -> Dict:
    """
    Detect a Judas Swing (stop-hunt / manipulation candle).

    Triggered when price breaks above asia_high or below asia_low with volume below
    avg_volume * 0.8, then closes back inside the range within 1–3 candles.

    All data must be passed in — no fetching inside this function.
    asia_high, asia_low, avg_volume are caller-provided from the session layer.

    Returns dict: detected, direction, sweep_price, return_candle_index, confidence.
    """
    result: Dict = {
        "detected": False,
        "direction": "",
        "sweep_price": 0.0,
        "return_candle_index": -1,
        "confidence": 0.0,
    }

    if not candles or asia_high <= 0 or asia_low <= 0 or avg_volume <= 0:
        return result

    for i in range(len(candles)):
        c = candles[i]
        low_volume = c["volume"] < avg_volume * _LOW_VOLUME_RATIO

        # Bearish Judas: spike above Asia high on low volume → expects reversal downward
        if c["high"] > asia_high and low_volume:
            for j in range(i + 1, min(i + 4, len(candles))):
                if candles[j]["close"] < asia_high:
                    bars_to_return = j - i
                    conf = {1: 1.0, 2: 0.75, 3: 0.5}.get(bars_to_return, 0.3)
                    result.update(
                        {
                            "detected": True,
                            "direction": "bearish",
                            "sweep_price": c["high"],
                            "return_candle_index": j,
                            "confidence": min(conf * 1.1, 1.0),
                        }
                    )
                    return result

        # Bullish Judas: spike below Asia low on low volume → expects reversal upward
        elif c["low"] < asia_low and low_volume:
            for j in range(i + 1, min(i + 4, len(candles))):
                if candles[j]["close"] > asia_low:
                    bars_to_return = j - i
                    conf = {1: 1.0, 2: 0.75, 3: 0.5}.get(bars_to_return, 0.3)
                    result.update(
                        {
                            "detected": True,
                            "direction": "bullish",
                            "sweep_price": c["low"],
                            "return_candle_index": j,
                            "confidence": min(conf * 1.1, 1.0),
                        }
                    )
                    return result

    return result
