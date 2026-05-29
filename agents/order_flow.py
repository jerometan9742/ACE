"""Order book depth agent (Haiku) — assesses buy/sell pressure and volume confirmation."""

from agents._client import MODEL_FAST, get_client, parse_json

_AGENT = "order_flow"

_SYSTEM = (
    "You are the Order Flow Analyst for ACE, an intraday crypto trading bot. "
    "Analyse the provided order book snapshot, recent trades, and volume profile "
    "to assess buy/sell pressure and institutional activity. "
    "Use ONLY the data explicitly provided. Never invent values. "
    "Respond with valid JSON only."
)


def analyse(
    order_book: dict,
    recent_trades: list,
    volume_profile: dict,
    pair: str,
    timestamp: str,
) -> dict:
    """
    Assess order book depth, buy/sell pressure, and volume confirmation.

    order_book: {bids: [[price, size], ...], asks: [[price, size], ...]}
    recent_trades: [{price, size, side, timestamp}, ...]
    volume_profile: {poc: float, value_area_high: float, value_area_low: float}

    All values passed in — nothing fetched here.

    Returns: pressure, flow_confidence, large_walls_detected, volume_confirms, reasoning, agent.
    """
    _err = {
        "agent": _AGENT, "pressure": "neutral", "flow_confidence": 0,
        "large_walls_detected": False, "volume_confirms": False,
        "reasoning": "", "error": True, "error_message": "",
    }
    try:
        bids = order_book.get("bids", [])[:10]
        asks = order_book.get("asks", [])[:10]

        bid_vol = sum(float(b[1]) for b in bids if len(b) >= 2)
        ask_vol = sum(float(a[1]) for a in asks if len(a) >= 2)
        bid_ask_ratio = round(bid_vol / ask_vol, 3) if ask_vol > 0 else 0.0

        buy_trades = [t for t in recent_trades if t.get("side", "").lower() in ("buy", "b")]
        sell_trades = [t for t in recent_trades if t.get("side", "").lower() in ("sell", "s")]
        buy_vol = sum(float(t.get("size", 0)) for t in buy_trades)
        sell_vol = sum(float(t.get("size", 0)) for t in sell_trades)

        poc = volume_profile.get("poc", 0.0)
        vah = volume_profile.get("value_area_high", 0.0)
        val = volume_profile.get("value_area_low", 0.0)

        # Detect large walls (top bid or ask > 3× average)
        avg_bid = bid_vol / len(bids) if bids else 0
        avg_ask = ask_vol / len(asks) if asks else 0
        large_bid_wall = any(float(b[1]) > avg_bid * 3 for b in bids if len(b) >= 2)
        large_ask_wall = any(float(a[1]) > avg_ask * 3 for a in asks if len(a) >= 2)

        prompt = f"""Pair: {pair}  |  Timestamp: {timestamp}

Order Book (top 10 levels):
  Bid volume: {bid_vol:.2f}
  Ask volume: {ask_vol:.2f}
  Bid/Ask ratio: {bid_ask_ratio:.3f}  (>1.2 = buy pressure, <0.8 = sell pressure)
  Large bid wall detected: {large_bid_wall}
  Large ask wall detected: {large_ask_wall}

Recent trades summary:
  Buy volume:  {buy_vol:.2f}
  Sell volume: {sell_vol:.2f}
  Trade count: {len(recent_trades)}

Volume Profile:
  POC (Point of Control): {poc:.4f}
  Value Area High: {vah:.4f}
  Value Area Low:  {val:.4f}

Determine:
1. Overall pressure: "buy_pressure", "sell_pressure", or "neutral"
2. Do large walls indicate institutional activity? (large_walls_detected true/false)
3. Does volume confirm a directional move? (volume_confirms true/false)
4. Flow confidence 1–10

Respond ONLY with:
{{
  "pressure": "buy_pressure|sell_pressure|neutral",
  "flow_confidence": 0,
  "large_walls_detected": false,
  "volume_confirms": false,
  "reasoning": "one or two sentences"
}}"""

        resp = get_client().messages.create(
            model=MODEL_FAST,
            max_tokens=300,
            system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral", "ttl": 3600}}],
            messages=[{"role": "user", "content": prompt}],
        )
        p = parse_json(resp.content[0].text)
        return {
            "agent": _AGENT,
            "pressure": p.get("pressure", "neutral"),
            "flow_confidence": int(p.get("flow_confidence", 0)),
            "large_walls_detected": bool(p.get("large_walls_detected", False)),
            "volume_confirms": bool(p.get("volume_confirms", False)),
            "reasoning": p.get("reasoning", ""),
            "error": False,
            "error_message": "",
        }
    except Exception as exc:
        _err["error_message"] = str(exc)
        return _err
