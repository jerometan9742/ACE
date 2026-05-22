"""AMD phase agent (Haiku) — classifies current market regime using signal_engine output."""

from agents._client import MODEL_FAST, fmt_candles, get_client, parse_json

_AGENT = "regime_detector"

_SYSTEM = (
    "You are the AMD Regime Detector for ACE, an intraday crypto trading bot. "
    "Classify the current market phase and assess trade validity using ONLY the data provided. "
    "Never assume or invent indicator values not present in the input. "
    "Respond with valid JSON only — no prose before or after."
)


def analyse(
    amd_data: dict,
    bos_data: dict,
    session: dict,
    candles_15m: list,
    pair: str,
    timestamp: str,
) -> dict:
    """
    Classify AMD phase and determine if a Distribution setup is valid for trading.

    All inputs come from signal_engine — nothing is fetched here.
    Every value referenced in the prompt is an explicit parameter.

    Returns: phase, phase_confidence, valid_setup, trade_direction, reasoning, agent.
    """
    _err = {
        "agent": _AGENT, "phase": "unknown", "phase_confidence": 0,
        "valid_setup": False, "trade_direction": "neutral",
        "reasoning": "", "error": True, "error_message": "",
    }
    try:
        prompt = f"""Pair: {pair}  |  Timestamp: {timestamp}
Session: {session.get('name','unknown')} \
(active={session.get('is_active',False)}, threshold={session.get('confidence_threshold',0)})

AMD Detection:
  Phase: {amd_data.get('phase','unknown')}
  Confidence: {amd_data.get('confidence',0):.2f}
  Range High: {amd_data.get('range_high',0):.4f}
  Range Low:  {amd_data.get('range_low',0):.4f}
  Manipulation detected: {amd_data.get('manipulation_detected',False)}
  Manipulation direction: {amd_data.get('manipulation_direction','none')}
  Distribution direction: {amd_data.get('distribution_direction','none')}

BOS / CHoCH:
  BOS detected:  {bos_data.get('bos_detected',False)}
  BOS direction: {bos_data.get('bos_direction','none')}
  CHoCH detected:  {bos_data.get('choch_detected',False)}
  CHoCH direction: {bos_data.get('choch_direction','none')}
  Swing High: {bos_data.get('swing_high',0):.4f}
  Swing Low:  {bos_data.get('swing_low',0):.4f}

Last 3 × 15m candles:
{fmt_candles(candles_15m, 3)}

Determine:
1. Which AMD phase is price currently in?
2. Is this a valid Distribution (tradeable) setup?
3. Expected trade direction (use manipulation_direction + BOS as primary guide)?
4. Phase confidence 1–10 (10 = crystal clear, 1 = ambiguous)

Respond ONLY with this JSON:
{{
  "phase": "accumulation|manipulation|distribution|unknown",
  "phase_confidence": 0,
  "valid_setup": false,
  "trade_direction": "bullish|bearish|neutral",
  "reasoning": "one or two sentences"
}}"""

        resp = get_client().messages.create(
            model=MODEL_FAST,
            max_tokens=300,
            system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
        )
        p = parse_json(resp.content[0].text)
        return {
            "agent": _AGENT,
            "phase": p.get("phase", "unknown"),
            "phase_confidence": int(p.get("phase_confidence", 0)),
            "valid_setup": bool(p.get("valid_setup", False)),
            "trade_direction": p.get("trade_direction", "neutral"),
            "reasoning": p.get("reasoning", ""),
            "error": False,
            "error_message": "",
        }
    except Exception as exc:
        _err["error_message"] = str(exc)
        return _err
