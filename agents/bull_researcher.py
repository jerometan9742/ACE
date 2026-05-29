"""Bull case agent (Sonnet) — builds the strongest possible bullish trade thesis with ATR-calculated levels."""

from agents._client import MODEL_SMART, fmt_fvgs, fmt_obs, get_client, parse_json

_AGENT = "bull_researcher"

_SYSTEM = (
    "You are the Bull Researcher for ACE, an intraday crypto trading bot. "
    "Your job: argue the strongest possible BULLISH case for this setup. "
    "Use AMD phase, FVG zones, Order Blocks, and BOS to support your thesis. "
    "If the bull case is genuinely weak, say so honestly — do not over-inflate conviction. "
    "SL = entry - (1.5 × ATR). TP = entry + (3.0 × ATR). Use ONLY the values provided. "
    "Respond with valid JSON only."
)


def analyse(
    regime_out: dict,
    technical_out: dict,
    flow_out: dict,
    sentiment_out: dict,
    confluence_score: int,
    amd_data: dict,
    fvgs: list,
    obs: list,
    pair: str,
    current_price: float,
    atr: float,
) -> dict:
    """
    Build the bull case using Layer 1 agent outputs and signal engine data.

    SL = current_price - (1.5 × atr).  TP = current_price + (3.0 × atr).
    All values passed in — nothing fetched here.

    Returns: bull_case, bull_conviction, entry_price, sl_price, tp_price, key_levels, agent.
    """
    _err = {
        "agent": _AGENT, "bull_case": "", "bull_conviction": 0,
        "entry_price": current_price, "sl_price": 0.0, "tp_price": 0.0,
        "key_levels": [], "error": True, "error_message": "",
    }
    try:
        sl = round(current_price - 1.5 * atr, 6)
        tp = round(current_price + 3.0 * atr, 6)

        prompt = f"""Pair: {pair}
Current price: {current_price:.4f}
ATR(14): {atr:.4f}
Confluence score: {confluence_score}/10

AMD Phase Context:
  Phase: {amd_data.get('phase','unknown')}
  Manipulation direction: {amd_data.get('manipulation_direction','none')}
  Distribution direction: {amd_data.get('distribution_direction','none')}
  Range High: {amd_data.get('range_high',0):.4f}
  Range Low:  {amd_data.get('range_low',0):.4f}

Regime Agent:
  Phase: {regime_out.get('phase','unknown')}
  Trade direction: {regime_out.get('trade_direction','neutral')}
  Confidence: {regime_out.get('phase_confidence',0)}/10

Technical Agent:
  Signal: {technical_out.get('signal','HOLD')}
  FVG entry: {technical_out.get('fvg_entry',False)}
  VWAP bias: {technical_out.get('vwap_bias','neutral')}
  BOS direction: {technical_out.get('bos_direction','none')}
  Confidence: {technical_out.get('technical_confidence',0)}/10

Order Flow Agent:
  Pressure: {flow_out.get('pressure','neutral')}
  Volume confirms: {flow_out.get('volume_confirms',False)}
  Confidence: {flow_out.get('flow_confidence',0)}/10

Sentiment Agent:
  Score: {sentiment_out.get('sentiment_score',50)}/100 ({sentiment_out.get('sentiment_label','Unknown')})
  Supports trade: {sentiment_out.get('supports_trade',False)}

Active FVGs (unmitigated):
{fmt_fvgs(fvgs)}

Active Order Blocks (unmitigated):
{fmt_obs(obs)}

Pre-calculated trade levels (ATR-based, do not change):
  Entry: {current_price:.4f}
  SL:    {sl:.4f}  (entry - 1.5×ATR)
  TP:    {tp:.4f}  (entry + 3.0×ATR)

Build the strongest BULLISH case. Be honest — if the bull case is weak, say so.
bull_conviction 1–10 (10 = overwhelming bull evidence, 1 = very weak).

Respond ONLY with:
{{
  "bull_case": "2–3 sentence bull thesis",
  "bull_conviction": 0,
  "entry_price": {current_price:.4f},
  "sl_price": {sl:.4f},
  "tp_price": {tp:.4f},
  "key_levels": ["level description", ...]
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
            "bull_case": p.get("bull_case", ""),
            "bull_conviction": int(p.get("bull_conviction", 0)),
            "entry_price": float(p.get("entry_price", current_price)),
            "sl_price": float(p.get("sl_price", sl)),
            "tp_price": float(p.get("tp_price", tp)),
            "key_levels": list(p.get("key_levels", [])),
            "error": False,
            "error_message": "",
        }
    except Exception as exc:
        _err["error_message"] = str(exc)
        return _err
