"""AMD phase detection — classifies price action into Accumulation, Manipulation, or Distribution from 15m OHLCV data."""

import statistics
from typing import List, Dict


def _calculate_atr(candles: List[Dict], period: int = 14) -> float:
    """Calculate Average True Range over the given period."""
    if len(candles) < 2:
        return 0.0
    true_ranges = []
    for i in range(1, len(candles)):
        h = candles[i]["high"]
        l = candles[i]["low"]
        pc = candles[i - 1]["close"]
        true_ranges.append(max(h - l, abs(h - pc), abs(l - pc)))
    tail = true_ranges[-period:] if len(true_ranges) >= period else true_ranges
    return statistics.mean(tail) if tail else 0.0


def detect_phase(candles: List[Dict]) -> Dict:
    """
    Detect AMD phase from the last 50 candles on 15m timeframe.

    Accumulation: tight range (<0.5% of mid-price) over last 10 candles with declining volume.
    Manipulation: single candle breaks acc range by >0.3% then closes back inside within 3 candles.
    Distribution: BOS-style directional move with expanding volume after manipulation.

    All data must be passed in — no fetching inside this function.

    Returns dict: phase, confidence, range_high, range_low,
                  manipulation_detected, manipulation_direction, distribution_direction.
    """
    empty = {
        "phase": "unknown",
        "confidence": 0.0,
        "range_high": 0.0,
        "range_low": 0.0,
        "manipulation_detected": False,
        "manipulation_direction": "",
        "distribution_direction": "",
    }

    if len(candles) < 15:
        return empty

    # Accumulation window: last 10 candles
    recent = candles[-10:]
    highs = [c["high"] for c in recent]
    lows = [c["low"] for c in recent]
    volumes = [c["volume"] for c in recent]

    range_high = max(highs)
    range_low = min(lows)
    mid_price = (range_high + range_low) / 2 if (range_high + range_low) > 0 else 1.0
    range_pct = (range_high - range_low) / mid_price

    first_half_vol = statistics.mean(volumes[:5]) if volumes[:5] else 1.0
    second_half_vol = statistics.mean(volumes[5:]) if volumes[5:] else 1.0
    volume_declining = second_half_vol < first_half_vol * 0.9

    is_accumulation = range_pct < 0.005 and volume_declining

    # Accumulation range for manipulation detection: 20 candles back
    acc_window = candles[-20:-10] if len(candles) >= 20 else candles[: max(1, len(candles) - 10)]
    acc_high = max(c["high"] for c in acc_window) if acc_window else range_high
    acc_low = min(c["low"] for c in acc_window) if acc_window else range_low

    manipulation_detected = False
    manipulation_direction = ""

    for i in range(max(0, len(candles) - 10), len(candles)):
        c = candles[i]
        # Bearish Judas: spike below acc_low then closes back above (bullish reversal)
        if c["low"] < acc_low * (1 - 0.003) and c["close"] > acc_low:
            manipulation_detected = True
            manipulation_direction = "bullish"
            break
        # Bullish Judas: spike above acc_high then closes back below (bearish reversal)
        if c["high"] > acc_high * (1 + 0.003) and c["close"] < acc_high:
            manipulation_detected = True
            manipulation_direction = "bearish"
            break

    # Distribution: directional move with expanding volume
    distribution_direction = ""
    is_distribution = False

    if len(candles) >= 5:
        last5 = candles[-5:]
        vol5 = [c["volume"] for c in last5]
        vol_expanding = statistics.mean(vol5[-3:]) > statistics.mean(vol5[:2]) * 1.1
        price_move = (
            (candles[-1]["close"] - candles[-5]["close"]) / candles[-5]["close"]
            if candles[-5]["close"] > 0
            else 0.0
        )
        if vol_expanding and abs(price_move) > 0.002:
            is_distribution = True
            distribution_direction = "bullish" if price_move > 0 else "bearish"

    if manipulation_detected and is_distribution:
        phase, confidence = "distribution", 0.85
    elif manipulation_detected:
        phase, confidence = "manipulation", 0.75
    elif is_distribution:
        phase, confidence = "distribution", 0.60
    elif is_accumulation:
        phase, confidence = "accumulation", 0.70
    else:
        phase, confidence = "accumulation", 0.40

    return {
        "phase": phase,
        "confidence": confidence,
        "range_high": range_high,
        "range_low": range_low,
        "manipulation_detected": manipulation_detected,
        "manipulation_direction": manipulation_direction,
        "distribution_direction": distribution_direction,
    }
