"""Risk veto agent (Sonnet) — hard Python veto checks first, then LLM nuanced risk analysis."""

import os

from dotenv import load_dotenv

from agents._client import MODEL_SMART, get_client, parse_json

load_dotenv()

_AGENT = "risk_manager"

_MAX_DAILY_LOSS_PCT = float(os.getenv("MAX_DAILY_LOSS_PCT", "0.03"))
_CORRELATION_LIMIT = float(os.getenv("CORRELATION_LIMIT", "0.85"))
_MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE_SCORE", "7.0"))

_SYSTEM = (
    "You are the Risk Manager for ACE, an intraday crypto trading bot. "
    "Hard veto conditions are already enforced by Python. "
    "Your job: assess nuanced risk factors and recommend a final position size multiplier. "
    "Use ONLY the data provided. Respond with valid JSON only."
)


def _hard_veto(
    daily_pnl: float,
    account_balance: float,
    session: dict,
    kill_switch_active: bool,
    correlation: float,
    consensus_confidence: float,
) -> list:
    """Return list of hard veto reasons (Python-enforced, no LLM needed)."""
    vetos = []
    daily_loss_limit = account_balance * _MAX_DAILY_LOSS_PCT
    if daily_pnl <= -daily_loss_limit:
        vetos.append(f"Daily loss limit reached: P&L {daily_pnl:.2f} ≤ -{daily_loss_limit:.2f}")
    if not session.get("is_active", False):
        vetos.append(f"Outside kill zone: session={session.get('name','unknown')}")
    if kill_switch_active:
        vetos.append("Kill switch is active")
    if correlation > _CORRELATION_LIMIT:
        vetos.append(f"Correlation {correlation:.2f} > limit {_CORRELATION_LIMIT}")
    if consensus_confidence < _MIN_CONFIDENCE:
        vetos.append(f"Consensus confidence {consensus_confidence} < threshold {_MIN_CONFIDENCE}")
    return vetos


def analyse(
    consensus_out: dict,
    current_positions: dict,
    daily_pnl: float,
    account_balance: float,
    session: dict,
    correlation_data: dict,
    atr: float,
    pair: str,
    entry_price: float,
    kill_switch_active: bool,
) -> dict:
    """
    Apply hard veto conditions then LLM nuanced risk analysis.

    Hard vetoes (Python):
    1. Daily loss limit reached
    2. Correlation > 0.85 with existing position
    3. Outside kill zone
    4. Kill switch active
    5. Confidence below session threshold

    All values passed in — nothing fetched here.

    Returns: approved, veto_reason, risk_flags, adjusted_position_size, agent.
    """
    _err = {
        "agent": _AGENT, "approved": False,
        "veto_reason": "", "risk_flags": [],
        "adjusted_position_size": 0.0,
        "error": True, "error_message": "",
    }
    try:
        correlation = float(correlation_data.get("correlation", 0.0))
        consensus_confidence = float(consensus_out.get("consensus_confidence", 0))

        # Python hard veto — no LLM needed if any veto fires
        vetos = _hard_veto(
            daily_pnl, account_balance, session,
            kill_switch_active, correlation, consensus_confidence,
        )
        if vetos:
            return {
                "agent": _AGENT,
                "approved": False,
                "veto_reason": "; ".join(vetos),
                "risk_flags": vetos,
                "adjusted_position_size": 0.0,
                "error": False,
                "error_message": "",
            }

        open_count = len(current_positions)
        max_pos = float(os.getenv("MAX_POSITION_SIZE_PCT", "0.05"))

        prompt = f"""Pair: {pair}
Entry price: {entry_price:.4f}
ATR(14): {atr:.4f}
SL distance: {1.5 * atr:.4f}  (1.5×ATR)

Account status:
  Daily P&L: {daily_pnl:.2f}
  Account balance: {account_balance:.2f}
  Max daily loss limit: {account_balance * _MAX_DAILY_LOSS_PCT:.2f} ({_MAX_DAILY_LOSS_PCT*100:.1f}%)
  Open positions: {open_count}
  Correlation with existing: {correlation:.2f} (limit {_CORRELATION_LIMIT})

Session: {session.get('name','unknown')} (threshold {session.get('confidence_threshold',7.0)})
Consensus confidence: {consensus_confidence}/10
Consensus action: {consensus_out.get('consensus_action','HOLD')}
Signals for: {consensus_out.get('signals_for',[])}

Hard veto checks: ALL PASSED (no hard veto triggered)

Assess nuanced risk and recommend position size multiplier:
  1.0 = standard (up to {max_pos*100:.1f}% of balance)
  0.5 = reduced  (up to {max_pos*50:.1f}% of balance)
  0.0 = block    (do not trade)

Respond ONLY with:
{{
  "approved": true,
  "risk_flags": ["flag if any"],
  "adjusted_position_size": 1.0,
  "reasoning": "one sentence"
}}"""

        resp = get_client().messages.create(
            model=MODEL_SMART,
            max_tokens=300,
            system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral", "ttl": 3600}}],
            messages=[{"role": "user", "content": prompt}],
        )
        p = parse_json(resp.content[0].text)
        approved = bool(p.get("approved", True))
        adj_size = float(p.get("adjusted_position_size", 1.0))
        if adj_size <= 0:
            approved = False

        return {
            "agent": _AGENT,
            "approved": approved,
            "veto_reason": "" if approved else p.get("reasoning", "Risk manager blocked"),
            "risk_flags": list(p.get("risk_flags", [])),
            "adjusted_position_size": adj_size,
            "error": False,
            "error_message": "",
        }
    except Exception as exc:
        _err["error_message"] = str(exc)
        return _err
