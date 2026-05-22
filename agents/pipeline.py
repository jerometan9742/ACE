"""LangGraph pipeline — wires all 10 ACE agents into a stateful decision graph."""

import concurrent.futures
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

load_dotenv()

_CONFLUENCE_MIN = int(os.getenv("CONFLUENCE_MIN_SCORE", "7"))
_CONSENSUS_REQUIRED = 5


# ---------------------------------------------------------------------------
# Pipeline state — passed between every node
# ---------------------------------------------------------------------------

class ACEState(TypedDict):
    # Signal engine inputs
    pair: str
    timestamp: str
    current_price: float
    candles_1m: list
    candles_5m: list
    candles_15m: list
    amd_data: dict
    bos_data: dict
    fvgs: list
    obs: list
    session: dict
    vwap: float
    rsi: float
    atr: float
    order_book: dict
    recent_trades: list
    volume_profile: dict
    fear_greed_index: int
    fear_greed_label: str
    confluence_score: int
    # Position / risk state
    current_positions: dict
    daily_pnl: float
    account_balance: float
    kill_switch_active: bool
    correlation_data: dict
    # Agent outputs
    layer1_outputs: dict
    layer2_outputs: dict
    similar_trades: list
    final_decision: dict


# ---------------------------------------------------------------------------
# Node: run Layer 1 agents in parallel (Haiku)
# ---------------------------------------------------------------------------

def run_layer1(state: ACEState) -> dict:
    """Run regime_detector, technical, order_flow, and sentiment in parallel threads."""
    import agents.regime_detector as rd
    import agents.technical as ta
    import agents.order_flow as of_
    import agents.sentiment as sa

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        f_regime = pool.submit(
            rd.analyse,
            state["amd_data"], state["bos_data"], state["session"],
            state["candles_15m"], state["pair"], state["timestamp"],
        )
        f_technical = pool.submit(
            ta.analyse,
            state["candles_1m"], state["candles_5m"], state["candles_15m"],
            state["fvgs"], state["obs"], state["bos_data"],
            state["vwap"], state["rsi"], state["atr"], state["pair"],
        )
        f_flow = pool.submit(
            of_.analyse,
            state["order_book"], state["recent_trades"],
            state["volume_profile"], state["pair"], state["timestamp"],
        )
        f_sentiment = pool.submit(
            sa.analyse,
            state["fear_greed_index"], state["fear_greed_label"],
            state["pair"], state["timestamp"],
        )
        regime_out = f_regime.result()
        technical_out = f_technical.result()
        flow_out = f_flow.result()
        sentiment_out = f_sentiment.result()

    return {
        "layer1_outputs": {
            "regime": regime_out,
            "technical": technical_out,
            "flow": flow_out,
            "sentiment": sentiment_out,
        }
    }


# ---------------------------------------------------------------------------
# Confluence gate — Python, no LLM
# ---------------------------------------------------------------------------

def confluence_gate(state: ACEState) -> str:
    """Return next node name or END based on confluence score."""
    if state.get("confluence_score", 0) >= _CONFLUENCE_MIN:
        return "run_bull_researcher"
    return END


# ---------------------------------------------------------------------------
# Layer 2 nodes (Sonnet, sequential)
# ---------------------------------------------------------------------------

def run_bull_researcher(state: ACEState) -> dict:
    """Bull case node."""
    import agents.bull_researcher as br
    l1 = state.get("layer1_outputs", {})
    out = br.analyse(
        l1.get("regime", {}), l1.get("technical", {}),
        l1.get("flow", {}), l1.get("sentiment", {}),
        state["confluence_score"], state["amd_data"],
        state["fvgs"], state["obs"],
        state["pair"], state["current_price"], state["atr"],
    )
    l2 = dict(state.get("layer2_outputs", {}))
    l2["bull"] = out
    return {"layer2_outputs": l2}


def run_bear_researcher(state: ACEState) -> dict:
    """Bear case node."""
    import agents.bear_researcher as br
    l1 = state.get("layer1_outputs", {})
    l2 = state.get("layer2_outputs", {})
    out = br.analyse(
        l1.get("regime", {}), l1.get("technical", {}),
        l1.get("flow", {}), l1.get("sentiment", {}),
        l2.get("bull", {}),
        state["confluence_score"], state["amd_data"],
        state["pair"], state["current_price"], state["atr"],
    )
    l2 = dict(l2)
    l2["bear"] = out
    return {"layer2_outputs": l2}


def run_consensus(state: ACEState) -> dict:
    """Consensus node."""
    import agents.consensus as ca
    l1 = state.get("layer1_outputs", {})
    l2 = state.get("layer2_outputs", {})
    out = ca.analyse(
        l1.get("regime", {}), l1.get("technical", {}),
        l1.get("flow", {}), l1.get("sentiment", {}),
        l2.get("bull", {}), l2.get("bear", {}),
        state["confluence_score"],
    )
    l2 = dict(l2)
    l2["consensus"] = out
    return {"layer2_outputs": l2}


def consensus_gate(state: ACEState) -> str:
    """Return next node or END if consensus fails."""
    consensus = state.get("layer2_outputs", {}).get("consensus", {})
    if consensus.get("passes_threshold", False):
        return "run_risk_manager"
    hold = {"action": "HOLD", "confidence": 0.0, "confidence_tier": "HOLD",
            "position_size_multiplier": 0.0, "reasoning": "Consensus gate: insufficient signals",
            "risk_flags": [], "entry_price": state["current_price"],
            "sl_price": 0.0, "tp_price": 0.0, "agent": "pipeline", "error": False, "error_message": ""}
    state["final_decision"] = hold  # type: ignore[index]
    return END


def run_risk_manager(state: ACEState) -> dict:
    """Risk veto node."""
    import agents.risk_manager as rm
    l2 = state.get("layer2_outputs", {})
    out = rm.analyse(
        l2.get("consensus", {}),
        state["current_positions"], state["daily_pnl"],
        state["account_balance"], state["session"],
        state["correlation_data"], state["atr"],
        state["pair"], state["current_price"], state["kill_switch_active"],
    )
    l2 = dict(l2)
    l2["risk"] = out
    return {"layer2_outputs": l2}


def risk_gate(state: ACEState) -> str:
    """Return next node or END if risk manager vetoes."""
    risk = state.get("layer2_outputs", {}).get("risk", {})
    if risk.get("approved", False):
        return "query_memory"
    hold = {"action": "HOLD", "confidence": 0.0, "confidence_tier": "HOLD",
            "position_size_multiplier": 0.0,
            "reasoning": f"Risk veto: {risk.get('veto_reason','')}",
            "risk_flags": risk.get("risk_flags", []), "entry_price": state["current_price"],
            "sl_price": 0.0, "tp_price": 0.0, "agent": "pipeline", "error": False, "error_message": ""}
    state["final_decision"] = hold  # type: ignore[index]
    return END


def query_memory(state: ACEState) -> dict:
    """Retrieve similar past trades from swarm_memory before fund manager fires."""
    try:
        from agents.memory.swarm_memory import retrieve_similar
        setup = {
            "pair": state["pair"],
            "session": state["session"].get("name", ""),
            "confluence_score": state["confluence_score"],
            "amd_phase": state["amd_data"].get("phase", ""),
            "setup_description": (
                f"{state['pair']} {state['session'].get('name','')} "
                f"confluence={state['confluence_score']}"
            ),
        }
        similar = retrieve_similar(setup, n=5)
    except Exception:
        similar = []
    return {"similar_trades": similar}


def run_fund_manager(state: ACEState) -> dict:
    """Final decision node."""
    import agents.fund_manager as fm
    l1 = state.get("layer1_outputs", {})
    l2 = state.get("layer2_outputs", {})
    out = fm.analyse(
        l1.get("regime", {}), l1.get("technical", {}),
        l1.get("flow", {}), l1.get("sentiment", {}),
        l2.get("bull", {}), l2.get("bear", {}),
        l2.get("consensus", {}), l2.get("risk", {}),
        state.get("similar_trades", []),
        state["pair"], state["current_price"], state["atr"],
        state["confluence_score"],
    )
    return {"final_decision": out}


# ---------------------------------------------------------------------------
# Build and compile the graph
# ---------------------------------------------------------------------------

def build_pipeline():
    """Compile and return the ACE LangGraph pipeline."""
    g = StateGraph(ACEState)

    g.add_node("run_layer1", run_layer1)
    g.add_node("run_bull_researcher", run_bull_researcher)
    g.add_node("run_bear_researcher", run_bear_researcher)
    g.add_node("run_consensus", run_consensus)
    g.add_node("run_risk_manager", run_risk_manager)
    g.add_node("query_memory", query_memory)
    g.add_node("run_fund_manager", run_fund_manager)

    g.set_entry_point("run_layer1")
    g.add_conditional_edges("run_layer1", confluence_gate)
    g.add_edge("run_bull_researcher", "run_bear_researcher")
    g.add_edge("run_bear_researcher", "run_consensus")
    g.add_conditional_edges("run_consensus", consensus_gate)
    g.add_conditional_edges("run_risk_manager", risk_gate)
    g.add_edge("query_memory", "run_fund_manager")
    g.add_edge("run_fund_manager", END)

    return g.compile()


def run_pipeline(initial_state: dict) -> dict:
    """
    Execute the full ACE decision pipeline with the given initial state.
    Returns the final state dict including final_decision.
    """
    app = build_pipeline()
    # Provide safe defaults for optional fields
    defaults: Dict[str, Any] = {
        "layer1_outputs": {},
        "layer2_outputs": {},
        "similar_trades": [],
        "final_decision": {},
        "current_positions": {},
        "daily_pnl": 0.0,
        "account_balance": float(os.getenv("PAPER_BALANCE", "10000")),
        "kill_switch_active": False,
        "correlation_data": {"correlation": 0.0},
        "order_book": {"bids": [], "asks": []},
        "recent_trades": [],
        "volume_profile": {"poc": 0.0, "value_area_high": 0.0, "value_area_low": 0.0},
        "fear_greed_index": 50,
        "fear_greed_label": "Neutral",
    }
    state = {**defaults, **initial_state}
    result = app.invoke(state)
    return result
