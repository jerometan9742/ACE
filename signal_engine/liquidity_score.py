"""Liquidity sweep quality scorer — rates the institutional quality of a stop-hunt from 0 to 10."""

from typing import List, Dict


def score_liquidity_sweep(
    candles: List[Dict],
    sweep_candle_index: int,
    obs: List[Dict],
    fvgs: List[Dict],
    avg_volume: float,
) -> int:
    """
    Score the quality of a liquidity sweep from 0 to 10.

    Scoring breakdown:
    - Equal highs/lows swept (stop cluster size): 1 level=+1, 2=+2, 3+=+3
    - Reversal speed after sweep:                 1 candle=+3, 2=+2, 3=+1
    - Volume spike on sweep candle:               >2x avg=+2, 1.5–2x=+1
    - OB or FVG within 0.5% of sweep price:      +2

    All data must be passed in — no fetching inside this function.

    Returns integer 0–10.
    """
    if not candles or sweep_candle_index < 0 or sweep_candle_index >= len(candles):
        return 0

    sweep = candles[sweep_candle_index]
    sweep_price = sweep["close"]
    score = 0
    tolerance = sweep_price * 0.001  # 0.1% tolerance for equal levels

    # --- Equal highs/lows count ---
    lookback = candles[max(0, sweep_candle_index - 20) : sweep_candle_index]
    equal_highs = sum(1 for c in lookback if abs(c["high"] - sweep["high"]) <= tolerance)
    equal_lows = sum(1 for c in lookback if abs(c["low"] - sweep["low"]) <= tolerance)
    cluster = max(equal_highs, equal_lows)
    score += min(cluster, 3)

    # --- Reversal speed ---
    after = candles[sweep_candle_index + 1 : sweep_candle_index + 4]
    reversal_bar = 0
    sweep_was_bearish = sweep["close"] < sweep["open"]
    for k, c in enumerate(after, start=1):
        if sweep_was_bearish and c["close"] > sweep["close"]:
            reversal_bar = k
            break
        if not sweep_was_bearish and c["close"] < sweep["close"]:
            reversal_bar = k
            break
    score += {1: 3, 2: 2, 3: 1}.get(reversal_bar, 0)

    # --- Volume spike ---
    if avg_volume > 0:
        ratio = sweep["volume"] / avg_volume
        if ratio > 2.0:
            score += 2
        elif ratio >= 1.5:
            score += 1

    # --- OB or FVG proximity (within 0.5% of sweep price) ---
    prox = sweep_price * 0.005
    ob_near = any(
        abs((ob["high"] + ob["low"]) / 2 - sweep_price) <= prox
        for ob in obs
        if not ob.get("mitigated", True)
    )
    fvg_near = any(
        fvg["bottom"] - prox <= sweep_price <= fvg["top"] + prox
        for fvg in fvgs
        if not fvg.get("mitigated", True)
    )
    if ob_near or fvg_near:
        score += 2

    return min(score, 10)
