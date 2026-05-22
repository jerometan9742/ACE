"""Order Block identification — finds institutional OB zones as entry and TP targets from intraday candle data."""

from typing import List, Dict

_IMPULSE_THRESHOLD = 0.03  # 3% move to qualify as an impulse


def detect_order_blocks(candles: List[Dict]) -> List[Dict]:
    """
    Detect Order Blocks from the candle series.

    Bullish OB: last bearish candle immediately before a 3%+ bullish impulse.
    Bearish OB: last bullish candle immediately before a 3%+ bearish impulse.

    Mitigation: bullish OB is mitigated when price later closes below its low;
                bearish OB is mitigated when price later closes above its high.

    All data must be passed in — no fetching inside this function.

    Returns list of dicts: type, high, low, open, close, candle_index, mitigated, strength.
    """
    obs: List[Dict] = []

    for i in range(len(candles) - 1):
        c = candles[i]
        is_bearish = c["close"] < c["open"]
        is_bullish = c["close"] > c["open"]

        for j in range(i + 1, min(i + 6, len(candles))):
            if c["close"] == 0:
                continue
            move = (candles[j]["close"] - c["close"]) / c["close"]

            if move >= _IMPULSE_THRESHOLD and is_bearish:
                mitigated = any(candles[k]["close"] <= c["low"] for k in range(j + 1, len(candles)))
                obs.append(
                    {
                        "type": "bullish",
                        "high": c["high"],
                        "low": c["low"],
                        "open": c["open"],
                        "close": c["close"],
                        "candle_index": i,
                        "mitigated": mitigated,
                        "strength": round(abs(move), 4),
                    }
                )
                break

            if move <= -_IMPULSE_THRESHOLD and is_bullish:
                mitigated = any(candles[k]["close"] >= c["high"] for k in range(j + 1, len(candles)))
                obs.append(
                    {
                        "type": "bearish",
                        "high": c["high"],
                        "low": c["low"],
                        "open": c["open"],
                        "close": c["close"],
                        "candle_index": i,
                        "mitigated": mitigated,
                        "strength": round(abs(move), 4),
                    }
                )
                break

    return obs


def get_nearest_ob(price: float, obs: List[Dict], direction: str) -> Dict:
    """
    Return the nearest unmitigated OB of the given direction to price.
    direction: 'bullish' or 'bearish'.
    Returns empty dict {} if none found.
    """
    candidates = [ob for ob in obs if ob["type"] == direction and not ob["mitigated"]]
    if not candidates:
        return {}

    def _dist(ob: Dict) -> float:
        return abs(price - (ob["high"] + ob["low"]) / 2)

    return min(candidates, key=_dist)
