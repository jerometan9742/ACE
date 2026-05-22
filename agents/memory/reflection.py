"""Post-trade reflection engine — uses Sonnet to analyse each closed trade and write structured lessons."""

import json
import os
from datetime import datetime, timezone

from agents._client import MODEL_SMART, get_client, parse_json

_LESSONS_DIR = os.path.join(os.path.dirname(__file__), "lessons")

_SYSTEM = (
    "You are the ACE Reflection Engine. After each closed trade, you analyse why it won or lost, "
    "which agents were right or wrong, and what the Confluence Engine should watch next time. "
    "Be specific and honest. Use ONLY the data provided. Respond with valid JSON only."
)


def reflect(trade_result: dict, agent_outputs: dict) -> dict:
    """
    Analyse a closed trade and produce a structured lesson.

    trade_result: {pair, session, confluence_score, amd_phase, entry_price, exit_price,
                   pnl, pnl_pct, win, setup_description, close_reason, timestamp}
    agent_outputs: {regime, technical, flow, sentiment, bull, bear, consensus, risk, fund}

    All values passed in — nothing fetched here.

    Returns structured lesson dict.
    """
    _err = {
        "trade_id": trade_result.get("trade_id", ""),
        "pair": trade_result.get("pair", ""),
        "error": True, "error_message": "",
    }
    try:
        outcome = "WIN" if trade_result.get("win", False) else "LOSS"
        pnl_pct = trade_result.get("pnl_pct", 0)

        prompt = f"""Trade outcome: {outcome}
Pair: {trade_result.get('pair','?')}
Session: {trade_result.get('session','?')}
Confluence score: {trade_result.get('confluence_score','?')}/10
AMD phase: {trade_result.get('amd_phase','?')}
Entry: {trade_result.get('entry_price','?')}
Exit: {trade_result.get('exit_price','?')}
P&L: {pnl_pct}%
Close reason: {trade_result.get('close_reason','?')}

Agent signals at time of entry:
  Regime: phase={agent_outputs.get('regime',{}).get('phase','?')} \
direction={agent_outputs.get('regime',{}).get('trade_direction','?')} \
confidence={agent_outputs.get('regime',{}).get('phase_confidence','?')}/10
  Technical: signal={agent_outputs.get('technical',{}).get('signal','?')} \
vwap={agent_outputs.get('technical',{}).get('vwap_bias','?')} \
confidence={agent_outputs.get('technical',{}).get('technical_confidence','?')}/10
  Flow: pressure={agent_outputs.get('flow',{}).get('pressure','?')} \
vol_confirms={agent_outputs.get('flow',{}).get('volume_confirms','?')}
  Bull conviction: {agent_outputs.get('bull',{}).get('bull_conviction','?')}/10
  Bear conviction: {agent_outputs.get('bear',{}).get('bear_conviction','?')}/10
  Consensus: {agent_outputs.get('consensus',{}).get('signals_for',[])} \
signals for / {agent_outputs.get('consensus',{}).get('signals_total',7)} total
  Fund Manager confidence: {agent_outputs.get('fund',{}).get('confidence','?')}/10

Analyse:
1. Primary reason this trade won / lost
2. Which agents gave correct signals? Which were wrong?
3. What did the Confluence Engine miss or get right?
4. One specific thing to look for next time in similar setups

Respond ONLY with:
{{
  "outcome": "{outcome}",
  "primary_reason": "one sentence",
  "agents_correct": ["agent names"],
  "agents_wrong": ["agent names"],
  "confluence_assessment": "one sentence",
  "lesson": "one specific actionable lesson",
  "tags": ["session_name", "amd_phase", "other_tags"]
}}"""

        resp = get_client().messages.create(
            model=MODEL_SMART,
            max_tokens=500,
            system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
        )
        p = parse_json(resp.content[0].text)

        lesson = {
            "trade_id": trade_result.get("trade_id", ""),
            "pair": trade_result.get("pair", ""),
            "session": trade_result.get("session", ""),
            "confluence_score": trade_result.get("confluence_score", 0),
            "amd_phase": trade_result.get("amd_phase", ""),
            "pnl_pct": pnl_pct,
            "win": trade_result.get("win", False),
            "outcome": p.get("outcome", outcome),
            "primary_reason": p.get("primary_reason", ""),
            "agents_correct": p.get("agents_correct", []),
            "agents_wrong": p.get("agents_wrong", []),
            "confluence_assessment": p.get("confluence_assessment", ""),
            "lesson": p.get("lesson", ""),
            "tags": p.get("tags", []),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": False,
            "error_message": "",
        }
        return lesson

    except Exception as exc:
        _err["error_message"] = str(exc)
        return _err


def write_lesson(lesson: dict) -> None:
    """
    Persist a lesson to agents/memory/lessons/ as a JSON file,
    then store in ChromaDB via swarm_memory.
    """
    try:
        os.makedirs(_LESSONS_DIR, exist_ok=True)
        trade_id = lesson.get("trade_id") or f"{lesson.get('pair','?')}_{lesson.get('timestamp','')}"
        filename = f"lesson_{trade_id}.json".replace("/", "-").replace(":", "-")
        filepath = os.path.join(_LESSONS_DIR, filename)
        with open(filepath, "w") as f:
            json.dump(lesson, f, indent=2)

        # Also store in swarm_memory for future RAG queries
        from agents.memory.swarm_memory import store_trade
        store_trade({
            **lesson,
            "setup_description": lesson.get("lesson", ""),
        })
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("write_lesson failed: %s", exc)
