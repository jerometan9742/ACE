"""Final decision agent (Sonnet) — synthesises all agent reports into BUY/SELL/HOLD with confidence tier."""

import os

from agents._client import MODEL_SMART, get_client, parse_json

_AGENT = "fund_manager"

_SYSTEM = (
    "You are the Fund Manager for ACE, an intraday crypto trading bot and the final decision maker. "
    "Synthesise all agent reports into a single actionable decision. "
    "Only output BUY or SELL if confidence ≥ 7.0. Otherwise output HOLD. "
    "Apply confidence tiers exactly as specified. Use ONLY the data provided. "
    "Respond with valid JSON only."
)

# Confidence tiers from CLAUDE.md — do not change without backtesting
_TIERS = [
    (8.5, "HIGH", 1.5, 0.075),
    (7.5, "STANDARD", 1.0, 0.05),
    (7.0, "REDUCED", 0.5, 0.025),
]


def _get_tier(confidence: float) -> tuple:
    """Return (tier_name, size_multiplier, max_position_pct) for a given confidence."""
    for threshold, name, multiplier, max_pct in _TIERS:
        if confidence >= threshold:
            return name, multiplier, max_pct
    return "HOLD", 0.0, 0.0


def analyse(
    regime_out: dict,
    technical_out: dict,
    flow_out: dict,
    sentiment_out: dict,
    bull_out: dict,
    bear_out: dict,
    consensus_out: dict,
    risk_out: dict,
    similar_trades: list,
    pair: str,
    current_price: float,
    atr: float,
    confluence_score: int,
) -> dict:
    """
    Final BUY/SELL/HOLD decision with confidence tier and position size.

    Confidence tiers (from CLAUDE.md — do not change):
      8.5–10.0 → HIGH (1.5×, max 7.5%)
      7.5–8.4  → STANDARD (1.0×, max 5.0%)
      7.0–7.4  → REDUCED (0.5×, max 2.5%)
      < 7.0    → HOLD

    All values passed in — nothing fetched here.
    similar_trades come from swarm_memory.retrieve_similar() called before this agent.

    Returns: action, confidence, confidence_tier, position_size_multiplier,
             reasoning, risk_flags, entry_price, sl_price, tp_price, agent.
    """
    sl = round(current_price - 1.5 * atr, 6)
    tp = round(current_price + 3.0 * atr, 6)

    _err = {
        "agent": _AGENT, "action": "HOLD", "confidence": 0.0,
        "confidence_tier": "HOLD", "position_size_multiplier": 0.0,
        "reasoning": "", "risk_flags": [],
        "entry_price": current_price, "sl_price": sl, "tp_price": tp,
        "error": True, "error_message": "",
    }
    try:
        similar_summary = "\n".join(
            f"  {t.get('pair','?')} {t.get('session','?')} conf={t.get('confluence_score','?')} "
            f"pnl={t.get('pnl_pct','?')}% {'WIN' if t.get('win') else 'LOSS'}"
            for t in (similar_trades or [])[:5]
        ) or "  (no similar past trades)"

        prompt = f"""Pair: {pair}
Current price: {current_price:.4f}
Confluence score: {confluence_score}/10

=== LAYER 1 SUMMARY ===
Regime:    phase={regime_out.get('phase','?')} direction={regime_out.get('trade_direction','?')} \
conf={regime_out.get('phase_confidence',0)}/10
Technical: signal={technical_out.get('signal','?')} vwap={technical_out.get('vwap_bias','?')} \
conf={technical_out.get('technical_confidence',0)}/10
Flow:      pressure={flow_out.get('pressure','?')} vol_confirms={flow_out.get('volume_confirms',False)} \
conf={flow_out.get('flow_confidence',0)}/10
Sentiment: {sentiment_out.get('sentiment_score',50)}/100 supports={sentiment_out.get('supports_trade',False)} \
conf={sentiment_out.get('sentiment_confidence',0)}/10

=== LAYER 2 SUMMARY ===
Bull conviction: {bull_out.get('bull_conviction',0)}/10
  {bull_out.get('bull_case','')}

Bear conviction: {bear_out.get('bear_conviction',0)}/10
  {bear_out.get('bear_case','')}

Consensus: {consensus_out.get('consensus_action','HOLD')} \
({consensus_out.get('signals_for',[]) and len(consensus_out.get('signals_for',[]))}/{consensus_out.get('signals_total',7)} signals) \
conf={consensus_out.get('consensus_confidence',0)}/10

Risk Manager: approved={risk_out.get('approved',False)} \
size_multiplier={risk_out.get('adjusted_position_size',0.0)}
  Flags: {risk_out.get('risk_flags',[])}

=== SIMILAR PAST TRADES (from memory) ===
{similar_summary}

=== PRE-CALCULATED TRADE LEVELS ===
  Entry: {current_price:.4f}
  SL:    {sl:.4f}  (1.5×ATR)
  TP:    {tp:.4f}  (3.0×ATR)

Make the final decision. Only BUY or SELL if confidence ≥ 7.0.
Apply confidence tiers:
  8.5–10.0 → HIGH (multiplier 1.5)
  7.5–8.4  → STANDARD (multiplier 1.0)
  7.0–7.4  → REDUCED (multiplier 0.5)
  < 7.0    → HOLD (multiplier 0.0)

Respond ONLY with:
{{
  "action": "BUY|SELL|HOLD",
  "confidence": 0.0,
  "confidence_tier": "HIGH|STANDARD|REDUCED|HOLD",
  "position_size_multiplier": 0.0,
  "reasoning": "2–3 sentences synthesising the key reasons",
  "risk_flags": []
}}"""

        resp = get_client().messages.create(
            model=MODEL_SMART,
            max_tokens=500,
            system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
        )
        p = parse_json(resp.content[0].text)
        raw_confidence = float(p.get("confidence", 0.0))

        # Python enforces confidence tier — LLM can't override
        tier_name, multiplier, _ = _get_tier(raw_confidence)
        action = p.get("action", "HOLD").upper()

        # Enforce: HOLD if confidence < 7.0 regardless of LLM output
        if raw_confidence < 7.0:
            action = "HOLD"
            tier_name = "HOLD"
            multiplier = 0.0

        return {
            "agent": _AGENT,
            "action": action,
            "confidence": raw_confidence,
            "confidence_tier": tier_name,
            "position_size_multiplier": multiplier,
            "reasoning": p.get("reasoning", ""),
            "risk_flags": list(p.get("risk_flags", [])),
            "entry_price": current_price,
            "sl_price": sl,
            "tp_price": tp,
            "error": False,
            "error_message": "",
        }
    except Exception as exc:
        _err["error_message"] = str(exc)
        return _err
