"""Consensus builder (Sonnet) — Ruflo-inspired 5/7 supermajority gate with LLM reasoning."""

from agents._client import MODEL_SMART, get_client, parse_json

_AGENT = "consensus"
_REQUIRED_SIGNALS = 5
_TOTAL_SIGNALS = 7


def _count_signals(
    regime_out: dict,
    technical_out: dict,
    flow_out: dict,
    sentiment_out: dict,
    bull_out: dict,
    bear_out: dict,
    confluence_score: int,
) -> tuple:
    """
    Count signals for/against using the 7-signal supermajority framework.

    Signal definitions (from CLAUDE.md):
    1. regime valid_setup = True           → +1
    2. technical signal = BUY or SELL      → +1
    3. order_flow volume_confirms = True   → +1
    4. sentiment supports_trade = True     → +1
    5. bull_conviction >= 7               → +1
    6. bear_conviction <= 4               → +1
    7. confluence_score >= 8              → +1
    """
    signals_for = []
    signals_against = []

    # 1 — Regime
    if regime_out.get("valid_setup", False):
        signals_for.append("regime: valid setup confirmed")
    else:
        signals_against.append("regime: no valid setup")

    # 2 — Technical
    if technical_out.get("signal", "HOLD").upper() in ("BUY", "SELL"):
        signals_for.append(f"technical: {technical_out['signal']} signal")
    else:
        signals_against.append("technical: HOLD — no clear signal")

    # 3 — Order flow
    if flow_out.get("volume_confirms", False):
        signals_for.append("order_flow: volume confirms direction")
    else:
        signals_against.append("order_flow: volume does not confirm")

    # 4 — Sentiment
    if sentiment_out.get("supports_trade", False):
        signals_for.append("sentiment: supports taking this trade")
    else:
        signals_against.append("sentiment: does not support trade")

    # 5 — Bull conviction
    if bull_out.get("bull_conviction", 0) >= 7:
        signals_for.append(f"bull conviction {bull_out['bull_conviction']}/10 ≥ 7")
    else:
        signals_against.append(f"bull conviction {bull_out.get('bull_conviction',0)}/10 < 7")

    # 6 — Bear conviction low
    if bear_out.get("bear_conviction", 10) <= 4:
        signals_for.append(f"bear conviction {bear_out['bear_conviction']}/10 ≤ 4 (weak bear case)")
    else:
        signals_against.append(f"bear conviction {bear_out.get('bear_conviction',10)}/10 > 4")

    # 7 — Confluence
    if confluence_score >= 8:
        signals_for.append(f"confluence score {confluence_score}/10 ≥ 8")
    else:
        signals_against.append(f"confluence score {confluence_score}/10 < 8")

    return signals_for, signals_against


def analyse(
    regime_out: dict,
    technical_out: dict,
    flow_out: dict,
    sentiment_out: dict,
    bull_out: dict,
    bear_out: dict,
    confluence_score: int,
) -> dict:
    """
    Count 7 signals and require 5/7 supermajority to pass.
    Uses LLM to provide reasoning; Python enforces the gate.

    All values passed in — nothing fetched here.

    Returns: consensus_action, signals_for, signals_against, signals_total,
             passes_threshold, consensus_confidence, reasoning, agent.
    """
    _err = {
        "agent": _AGENT, "consensus_action": "HOLD",
        "signals_for": [], "signals_against": [], "signals_total": _TOTAL_SIGNALS,
        "passes_threshold": False, "consensus_confidence": 0,
        "reasoning": "", "error": True, "error_message": "",
    }
    try:
        signals_for, signals_against = _count_signals(
            regime_out, technical_out, flow_out, sentiment_out,
            bull_out, bear_out, confluence_score,
        )
        count_for = len(signals_for)
        passes = count_for >= _REQUIRED_SIGNALS

        # Determine action from technical signal direction
        tech_signal = technical_out.get("signal", "HOLD").upper()
        regime_dir = regime_out.get("trade_direction", "neutral")
        if passes and tech_signal in ("BUY", "SELL"):
            consensus_action = tech_signal
        elif passes and regime_dir == "bullish":
            consensus_action = "BUY"
        elif passes and regime_dir == "bearish":
            consensus_action = "SELL"
        else:
            consensus_action = "HOLD"

        prompt = f"""Supermajority result: {count_for}/{_TOTAL_SIGNALS} signals in favour (need {_REQUIRED_SIGNALS})
Action: {consensus_action}
Passes: {passes}

Signals FOR ({count_for}):
{chr(10).join('  + ' + s for s in signals_for)}

Signals AGAINST ({len(signals_against)}):
{chr(10).join('  - ' + s for s in signals_against)}

Bull case summary: {bull_out.get('bull_case','')}
Bear case summary: {bear_out.get('bear_case','')}

Provide a 2-sentence reasoning for the consensus decision and a confidence score 1–10.

Respond ONLY with:
{{
  "reasoning": "two sentences",
  "consensus_confidence": 0
}}"""

        resp = get_client().messages.create(
            model=MODEL_SMART,
            max_tokens=250,
            system=[{
                "type": "text",
                "text": "You are the Consensus Builder for ACE. Provide reasoning and confidence for the supermajority decision. JSON only.",
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": prompt}],
        )
        p = parse_json(resp.content[0].text)
        return {
            "agent": _AGENT,
            "consensus_action": consensus_action,
            "signals_for": signals_for,
            "signals_against": signals_against,
            "signals_total": _TOTAL_SIGNALS,
            "passes_threshold": passes,
            "consensus_confidence": int(p.get("consensus_confidence", count_for)),
            "reasoning": p.get("reasoning", ""),
            "error": False,
            "error_message": "",
        }
    except Exception as exc:
        _err["error_message"] = str(exc)
        return _err
