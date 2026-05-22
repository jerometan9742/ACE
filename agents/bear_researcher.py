"""Bear case agent (Sonnet) — challenges the bull thesis and identifies what could invalidate the setup."""

from agents._client import MODEL_SMART, get_client, parse_json

_AGENT = "bear_researcher"

_SYSTEM = (
    "You are the Bear Researcher for ACE, an intraday crypto trading bot. "
    "Your job: argue the strongest possible BEARISH counter-thesis. "
    "Challenge the bull case specifically. Identify CHoCH signals, weak FVGs, low volume, "
    "or correlation risks that could invalidate the setup. "
    "If the bear case is genuinely weak, say so honestly. "
    "Use ONLY the values provided. Respond with valid JSON only."
)


def analyse(
    regime_out: dict,
    technical_out: dict,
    flow_out: dict,
    sentiment_out: dict,
    bull_out: dict,
    confluence_score: int,
    amd_data: dict,
    pair: str,
    current_price: float,
    atr: float,
) -> dict:
    """
    Build the bear counter-case against the bull_out thesis.

    All values passed in — nothing fetched here.

    Returns: bear_case, bear_conviction, key_risks, invalidation_level, agent.
    """
    _err = {
        "agent": _AGENT, "bear_case": "", "bear_conviction": 0,
        "key_risks": [], "invalidation_level": 0.0,
        "error": True, "error_message": "",
    }
    try:
        prompt = f"""Pair: {pair}
Current price: {current_price:.4f}
ATR(14): {atr:.4f}
Confluence score: {confluence_score}/10

Bull Researcher's case to challenge:
  Conviction: {bull_out.get('bull_conviction',0)}/10
  Entry: {bull_out.get('entry_price',0):.4f}
  SL: {bull_out.get('sl_price',0):.4f}
  TP: {bull_out.get('tp_price',0):.4f}
  Case: {bull_out.get('bull_case','')}

AMD Phase Context:
  Phase: {amd_data.get('phase','unknown')}
  Manipulation detected: {amd_data.get('manipulation_detected',False)}
  Distribution direction: {amd_data.get('distribution_direction','none')}

Regime Agent:
  Phase confidence: {regime_out.get('phase_confidence',0)}/10
  Valid setup: {regime_out.get('valid_setup',False)}

Technical Agent:
  Signal: {technical_out.get('signal','HOLD')}
  BOS direction: {technical_out.get('bos_direction','none')}
  RSI divergence: {technical_out.get('rsi_divergence',False)}
  VWAP bias: {technical_out.get('vwap_bias','neutral')}

Order Flow Agent:
  Pressure: {flow_out.get('pressure','neutral')}
  Volume confirms: {flow_out.get('volume_confirms',False)}

Sentiment: {sentiment_out.get('sentiment_score',50)}/100 ({sentiment_out.get('sentiment_label','Unknown')})

Argue the BEARISH counter-thesis. Be specific. Identify:
- What could cause this setup to fail?
- Is the manipulation direction ambiguous or contradicted?
- Are there CHoCH signals or weak volume?
- What is the price level that invalidates the bull case?

bear_conviction 1–10 (10 = overwhelming bear evidence, 1 = very weak).

Respond ONLY with:
{{
  "bear_case": "2–3 sentence bear thesis",
  "bear_conviction": 0,
  "key_risks": ["risk 1", "risk 2"],
  "invalidation_level": 0.0
}}"""

        resp = get_client().messages.create(
            model=MODEL_SMART,
            max_tokens=500,
            system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
        )
        p = parse_json(resp.content[0].text)
        return {
            "agent": _AGENT,
            "bear_case": p.get("bear_case", ""),
            "bear_conviction": int(p.get("bear_conviction", 0)),
            "key_risks": list(p.get("key_risks", [])),
            "invalidation_level": float(p.get("invalidation_level", 0.0)),
            "error": False,
            "error_message": "",
        }
    except Exception as exc:
        _err["error_message"] = str(exc)
        return _err
