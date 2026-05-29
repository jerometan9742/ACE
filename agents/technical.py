"""Multi-timeframe technical agent (Haiku) — analyses FVG, OB, BOS, VWAP, RSI, ATR across 1m/5m/15m."""

from agents._client import MODEL_FAST, fmt_candles, fmt_fvgs, fmt_obs, get_client, parse_json

_AGENT = "technical"

_SYSTEM = (
    "You are the Technical Analyst for ACE, an intraday crypto trading bot. "
    "Interpret multi-timeframe candle data, FVGs, Order Blocks, BOS/CHoCH, VWAP, RSI, and ATR "
    "to determine technical bias. Use ONLY the values explicitly provided. "
    "VWAP is a bias filter only — never use it as an entry trigger. "
    "Respond with valid JSON only."
)


def analyse(
    candles_1m: list,
    candles_5m: list,
    candles_15m: list,
    fvgs: list,
    obs: list,
    bos_data: dict,
    vwap: float,
    rsi: float,
    atr: float,
    pair: str,
) -> dict:
    """
    Multi-timeframe technical analysis.

    All indicator values (vwap, rsi, atr, fvgs, obs, bos_data) are passed in explicitly.
    No indicator is fetched inside this function.

    Returns: signal, technical_confidence, fvg_entry, ob_level, bos_direction,
             vwap_bias, rsi_divergence, reasoning, agent.
    """
    _err = {
        "agent": _AGENT, "signal": "HOLD", "technical_confidence": 0,
        "fvg_entry": False, "ob_level": 0.0, "bos_direction": "none",
        "vwap_bias": "neutral", "rsi_divergence": False,
        "reasoning": "", "error": True, "error_message": "",
    }
    try:
        price = candles_1m[-1]["close"] if candles_1m else 0.0

        prompt = f"""Pair: {pair}
Current price (1m close): {price:.4f}

Indicators (all pre-calculated, passed in):
  ATR(14): {atr:.4f}
  VWAP:    {vwap:.4f}  → price is {'ABOVE' if price > vwap else 'BELOW'} VWAP  [bias filter only, not entry trigger]
  RSI(14): {rsi:.2f}

Active FVGs (unmitigated):
{fmt_fvgs(fvgs)}

Active Order Blocks (unmitigated):
{fmt_obs(obs)}

BOS / CHoCH:
  BOS detected:  {bos_data.get('bos_detected',False)}
  BOS direction: {bos_data.get('bos_direction','none')}
  CHoCH detected:  {bos_data.get('choch_detected',False)}
  CHoCH direction: {bos_data.get('choch_direction','none')}
  Swing High: {bos_data.get('swing_high',0):.4f}
  Swing Low:  {bos_data.get('swing_low',0):.4f}

Last 3 × 1m candles:
{fmt_candles(candles_1m, 3)}
Last 3 × 5m candles:
{fmt_candles(candles_5m, 3)}
Last 3 × 15m candles:
{fmt_candles(candles_15m, 3)}

Determine:
1. Is price inside or near an active FVG? (fvg_entry)
2. Nearest active OB level (price number, 0 if none)
3. VWAP bias: bullish / bearish / neutral
4. RSI divergence visible? (true/false)
5. Overall signal: BUY, SELL, or HOLD
6. Technical confidence 1–10

Respond ONLY with:
{{
  "signal": "BUY|SELL|HOLD",
  "technical_confidence": 0,
  "fvg_entry": false,
  "ob_level": 0.0,
  "bos_direction": "bullish|bearish|none",
  "vwap_bias": "bullish|bearish|neutral",
  "rsi_divergence": false,
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
            "signal": p.get("signal", "HOLD"),
            "technical_confidence": int(p.get("technical_confidence", 0)),
            "fvg_entry": bool(p.get("fvg_entry", False)),
            "ob_level": float(p.get("ob_level", 0.0)),
            "bos_direction": p.get("bos_direction", "none"),
            "vwap_bias": p.get("vwap_bias", "neutral"),
            "rsi_divergence": bool(p.get("rsi_divergence", False)),
            "reasoning": p.get("reasoning", ""),
            "error": False,
            "error_message": "",
        }
    except Exception as exc:
        _err["error_message"] = str(exc)
        return _err
