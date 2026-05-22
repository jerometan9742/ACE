"""Multi-pair correlation filter — prevents double exposure when BTC/ETH/SOL move in lockstep."""

import os
import statistics
from typing import List, Dict

from dotenv import load_dotenv

load_dotenv()

CORRELATION_LIMIT = float(os.getenv("CORRELATION_LIMIT", "0.85"))


def calculate_correlation(prices_a: List[float], prices_b: List[float]) -> float:
    """
    Calculate Pearson correlation coefficient between two equal-length price series.
    Returns float in [-1.0, 1.0]. Returns 0.0 on insufficient or identical data.
    """
    n = len(prices_a)
    if n != len(prices_b) or n < 2:
        return 0.0

    mean_a = statistics.mean(prices_a)
    mean_b = statistics.mean(prices_b)

    try:
        std_a = statistics.stdev(prices_a)
        std_b = statistics.stdev(prices_b)
    except statistics.StatisticsError:
        return 0.0

    if std_a == 0 or std_b == 0:
        return 0.0

    numerator = sum((prices_a[i] - mean_a) * (prices_b[i] - mean_b) for i in range(n))
    denominator = (n - 1) * std_a * std_b

    return round(numerator / denominator, 4) if denominator != 0 else 0.0


def check_correlation_risk(
    open_positions: Dict[str, Dict],
    new_signal_pair: str,
) -> Dict:
    """
    Check whether opening a new position would create unsafe correlation with existing ones.

    open_positions: mapping of pair → {prices: List[float], new_prices: List[float], ...}
    new_signal_pair: the pair we want to enter.

    All data must be passed in — no fetching inside this function.

    Returns dict: allowed, correlation, position_size_multiplier, reason.
    """
    result = {
        "allowed": True,
        "correlation": 0.0,
        "position_size_multiplier": 1.0,
        "reason": "No open correlated positions",
    }

    if not open_positions:
        return result

    max_corr = 0.0

    for pair, pos in open_positions.items():
        if pair == new_signal_pair:
            continue
        prices_existing = pos.get("prices", [])
        prices_new = pos.get("new_prices", [])
        if not prices_existing or not prices_new:
            continue
        corr = abs(calculate_correlation(prices_existing, prices_new))
        max_corr = max(max_corr, corr)

    result["correlation"] = round(max_corr, 4)

    if max_corr > CORRELATION_LIMIT:
        result["allowed"] = False
        result["position_size_multiplier"] = 0.0
        result["reason"] = f"Correlation {max_corr:.2f} exceeds limit {CORRELATION_LIMIT}"
    elif max_corr > CORRELATION_LIMIT * 0.8:
        result["position_size_multiplier"] = 0.5
        result["reason"] = f"Elevated correlation {max_corr:.2f} — reduced size"

    return result


def get_pair_agreement(signals: Dict[str, Dict]) -> Dict:
    """
    Check whether BTC and ETH agree on direction before firing on any pair.

    signals: mapping of pair → {direction: 'bullish'|'bearish'|'neutral', ...}

    All data must be passed in — no fetching inside this function.

    Returns dict: agrees, direction, agreement_count, pairs.
    """
    result: Dict = {
        "agrees": False,
        "direction": "",
        "agreement_count": 0,
        "pairs": [],
    }

    if not signals:
        return result

    directions = {pair: data.get("direction", "neutral") for pair, data in signals.items()}

    btc_dir = next((v for k, v in directions.items() if "BTC" in k.upper()), "neutral")
    eth_dir = next((v for k, v in directions.items() if "ETH" in k.upper()), "neutral")

    if btc_dir == "neutral" or eth_dir == "neutral":
        result["reason"] = "BTC or ETH signal is neutral"
        return result

    if btc_dir == eth_dir:
        agreeing = [p for p, d in directions.items() if d == btc_dir]
        result.update(
            {
                "agrees": True,
                "direction": btc_dir,
                "agreement_count": len(agreeing),
                "pairs": agreeing,
            }
        )
    else:
        result["reason"] = f"BTC ({btc_dir}) and ETH ({eth_dir}) disagree"

    return result
