"""Fair Value Gap detection — identifies unmitigated price gaps on intraday charts as precision entry zones."""

from typing import List, Dict


def detect_fvgs(candles: List[Dict]) -> List[Dict]:
    """
    Detect Fair Value Gaps in the candle series.

    Bullish FVG: candle[i-2].high < candle[i].low  (gap above)
    Bearish FVG: candle[i-2].low  > candle[i].high (gap below)

    Mitigation: an FVG is mitigated once a subsequent candle closes through the gap.

    All data must be passed in — no fetching inside this function.

    Returns list of dicts: type, top, bottom, candle_index, mitigated, strength.
    """
    fvgs: List[Dict] = []

    for i in range(2, len(candles)):
        c0 = candles[i - 2]
        c2 = candles[i]

        # Bullish FVG
        if c0["high"] < c2["low"]:
            mid = (c0["high"] + c2["low"]) / 2
            strength = (c2["low"] - c0["high"]) / mid if mid > 0 else 0.0
            mitigated = any(candles[j]["close"] <= c0["high"] for j in range(i + 1, len(candles)))
            fvgs.append(
                {
                    "type": "bullish",
                    "top": c2["low"],
                    "bottom": c0["high"],
                    "candle_index": i,
                    "mitigated": mitigated,
                    "strength": round(strength, 6),
                }
            )

        # Bearish FVG
        elif c0["low"] > c2["high"]:
            mid = (c0["low"] + c2["high"]) / 2
            strength = (c0["low"] - c2["high"]) / mid if mid > 0 else 0.0
            mitigated = any(candles[j]["close"] >= c0["low"] for j in range(i + 1, len(candles)))
            fvgs.append(
                {
                    "type": "bearish",
                    "top": c0["low"],
                    "bottom": c2["high"],
                    "candle_index": i,
                    "mitigated": mitigated,
                    "strength": round(strength, 6),
                }
            )

    return fvgs


def get_active_fvgs(candles: List[Dict]) -> List[Dict]:
    """Return only unmitigated FVGs from the candle series."""
    return [fvg for fvg in detect_fvgs(candles) if not fvg["mitigated"]]


def is_price_in_fvg(price: float, fvgs: List[Dict]) -> Dict:
    """
    Return the first FVG where price sits inside or within 0.1% proximity.
    Returns empty dict {} if no matching FVG is found.
    """
    for fvg in fvgs:
        proximity = price * 0.001
        if fvg["bottom"] - proximity <= price <= fvg["top"] + proximity:
            return fvg
    return {}
