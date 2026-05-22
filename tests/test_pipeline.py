"""Pipeline tests — gate logic, memory store/retrieve, and full pipeline integration with mocked APIs."""

import json
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _mock_message(payload: dict) -> MagicMock:
    msg = MagicMock()
    msg.content = [MagicMock()]
    msg.content[0].text = json.dumps(payload)
    return msg


def _mock_client(payload: dict) -> MagicMock:
    client = MagicMock()
    client.messages.create.return_value = _mock_message(payload)
    return client


# ---------------------------------------------------------------------------
# Shared state fixture
# ---------------------------------------------------------------------------

CANDLE = {"open": 100.0, "high": 102.0, "low": 98.0, "close": 100.0, "volume": 1000.0}
CANDLES = [CANDLE] * 20

BASE_STATE = {
    "pair": "BTC/USDT",
    "timestamp": "2024-01-15T08:00:00Z",
    "current_price": 100.0,
    "candles_1m": CANDLES,
    "candles_5m": CANDLES,
    "candles_15m": CANDLES,
    "amd_data": {
        "phase": "distribution", "confidence": 0.8,
        "range_high": 102.0, "range_low": 98.0,
        "manipulation_detected": True, "manipulation_direction": "bullish",
        "distribution_direction": "bullish",
    },
    "bos_data": {
        "bos_detected": True, "bos_direction": "bullish",
        "choch_detected": False, "choch_direction": "",
        "swing_high": 102.0, "swing_low": 98.0,
        "last_higher_high": 0.0, "last_lower_low": 0.0,
    },
    "fvgs": [{"type": "bullish", "top": 100.5, "bottom": 99.5, "mitigated": False, "strength": 0.005}],
    "obs": [{"type": "bullish", "high": 100.2, "low": 99.8, "mitigated": False, "strength": 0.04}],
    "session": {"name": "london", "is_active": True, "confidence_threshold": 7.0},
    "vwap": 99.5,
    "rsi": 58.0,
    "atr": 1.2,
    "order_book": {"bids": [[99.5, 10.0]], "asks": [[100.5, 9.0]]},
    "recent_trades": [{"price": 100.0, "size": 5.0, "side": "buy", "timestamp": 1000}],
    "volume_profile": {"poc": 100.0, "value_area_high": 101.0, "value_area_low": 99.0},
    "fear_greed_index": 35,
    "fear_greed_label": "Fear",
    "confluence_score": 9,
    "current_positions": {},
    "daily_pnl": 0.0,
    "account_balance": 10000.0,
    "kill_switch_active": False,
    "correlation_data": {"correlation": 0.0},
    "layer1_outputs": {},
    "layer2_outputs": {},
    "similar_trades": [],
    "final_decision": {},
}


# ---------------------------------------------------------------------------
# Test: confluence gate
# ---------------------------------------------------------------------------

class TestConfluenceGate:
    def test_gate_passes_score_7(self):
        from agents.pipeline import confluence_gate
        state = {**BASE_STATE, "confluence_score": 7}
        assert confluence_gate(state) == "run_bull_researcher"

    def test_gate_passes_score_10(self):
        from agents.pipeline import confluence_gate
        state = {**BASE_STATE, "confluence_score": 10}
        assert confluence_gate(state) == "run_bull_researcher"

    def test_gate_blocks_score_6(self):
        from agents.pipeline import confluence_gate
        from langgraph.graph import END
        state = {**BASE_STATE, "confluence_score": 6}
        assert confluence_gate(state) == END

    def test_gate_blocks_score_0(self):
        from agents.pipeline import confluence_gate
        from langgraph.graph import END
        state = {**BASE_STATE, "confluence_score": 0}
        assert confluence_gate(state) == END


# ---------------------------------------------------------------------------
# Test: consensus gate
# ---------------------------------------------------------------------------

class TestConsensusGate:
    def test_passes_when_threshold_met(self):
        from agents.pipeline import consensus_gate
        state = dict(BASE_STATE)
        state["layer2_outputs"] = {"consensus": {"passes_threshold": True, "consensus_action": "BUY"}}
        assert consensus_gate(state) == "run_risk_manager"

    def test_blocks_when_threshold_not_met(self):
        from agents.pipeline import consensus_gate
        from langgraph.graph import END
        state = dict(BASE_STATE)
        state["layer2_outputs"] = {"consensus": {"passes_threshold": False}}
        assert consensus_gate(state) == END


# ---------------------------------------------------------------------------
# Test: risk gate
# ---------------------------------------------------------------------------

class TestRiskGate:
    def test_passes_when_approved(self):
        from agents.pipeline import risk_gate
        state = dict(BASE_STATE)
        state["layer2_outputs"] = {"risk": {"approved": True, "risk_flags": [], "veto_reason": ""}}
        assert risk_gate(state) == "query_memory"

    def test_blocks_when_vetoed(self):
        from agents.pipeline import risk_gate
        from langgraph.graph import END
        state = dict(BASE_STATE)
        state["layer2_outputs"] = {"risk": {"approved": False, "risk_flags": ["kill switch"], "veto_reason": "Kill switch active"}}
        assert risk_gate(state) == END


# ---------------------------------------------------------------------------
# Test: signal counting in consensus (no LLM needed)
# ---------------------------------------------------------------------------

class TestConsensusSignalCounting:
    def test_counts_all_7_signals_for(self):
        from agents.consensus import _count_signals
        regime = {"valid_setup": True}
        technical = {"signal": "BUY"}
        flow = {"volume_confirms": True}
        sentiment = {"supports_trade": True}
        bull = {"bull_conviction": 8}
        bear = {"bear_conviction": 3}
        signals_for, signals_against = _count_signals(
            regime, technical, flow, sentiment, bull, bear, 9
        )
        assert len(signals_for) == 7
        assert len(signals_against) == 0

    def test_counts_all_7_signals_against(self):
        from agents.consensus import _count_signals
        regime = {"valid_setup": False}
        technical = {"signal": "HOLD"}
        flow = {"volume_confirms": False}
        sentiment = {"supports_trade": False}
        bull = {"bull_conviction": 3}
        bear = {"bear_conviction": 8}
        signals_for, signals_against = _count_signals(
            regime, technical, flow, sentiment, bull, bear, 5
        )
        assert len(signals_for) == 0
        assert len(signals_against) == 7

    def test_partial_count(self):
        from agents.consensus import _count_signals
        regime = {"valid_setup": True}
        technical = {"signal": "BUY"}
        flow = {"volume_confirms": False}
        sentiment = {"supports_trade": False}
        bull = {"bull_conviction": 8}
        bear = {"bear_conviction": 3}
        signals_for, signals_against = _count_signals(
            regime, technical, flow, sentiment, bull, bear, 9
        )
        assert len(signals_for) == 5
        assert len(signals_against) == 2


# ---------------------------------------------------------------------------
# Test: risk manager hard vetoes (no LLM needed)
# ---------------------------------------------------------------------------

class TestRiskHardVetoes:
    def test_veto_outside_session(self):
        from agents.risk_manager import _hard_veto
        outside = {"name": "outside", "is_active": False}
        vetos = _hard_veto(0.0, 10000.0, outside, False, 0.0, 8.0)
        assert any("kill zone" in v.lower() for v in vetos)

    def test_veto_kill_switch(self):
        from agents.risk_manager import _hard_veto
        session = {"name": "london", "is_active": True}
        vetos = _hard_veto(0.0, 10000.0, session, True, 0.0, 8.0)
        assert any("kill switch" in v.lower() for v in vetos)

    def test_veto_daily_loss(self):
        from agents.risk_manager import _hard_veto
        session = {"name": "london", "is_active": True}
        vetos = _hard_veto(-350.0, 10000.0, session, False, 0.0, 8.0)
        assert any("daily loss" in v.lower() for v in vetos)

    def test_no_veto_all_clear(self):
        from agents.risk_manager import _hard_veto
        session = {"name": "london", "is_active": True}
        vetos = _hard_veto(0.0, 10000.0, session, False, 0.4, 8.0)
        assert vetos == []


# ---------------------------------------------------------------------------
# Test: swarm memory (in-memory chromadb)
# ---------------------------------------------------------------------------

class TestSwarmMemory:
    def _make_collection(self):
        import chromadb
        client = chromadb.EphemeralClient()
        col = client.get_or_create_collection("test_trades")
        return client, col

    def test_store_and_retrieve(self):
        import chromadb
        from agents.memory import swarm_memory as sm

        client = chromadb.EphemeralClient()
        col = client.get_or_create_collection("test_trades")

        with patch.object(sm, "_get_collection", return_value=col):
            trade = {
                "trade_id": "t1",
                "pair": "BTC/USDT",
                "session": "london",
                "confluence_score": 8,
                "amd_phase": "distribution",
                "entry_price": 100.0,
                "exit_price": 103.6,
                "pnl": 36.0,
                "pnl_pct": 3.6,
                "win": True,
                "setup_description": "Strong FVG + OB confluence in london session",
                "timestamp": "2024-01-15T08:00:00Z",
            }
            sm.store_trade(trade)
            results = sm.retrieve_similar(
                {"pair": "BTC/USDT", "session": "london",
                 "confluence_score": 8, "amd_phase": "distribution",
                 "setup_description": "FVG OB london"},
                n=3,
            )
            assert len(results) >= 1

    def test_get_session_stats_empty(self):
        import chromadb
        from agents.memory import swarm_memory as sm

        client = chromadb.EphemeralClient()
        col = client.get_or_create_collection("test_trades2")

        with patch.object(sm, "_get_collection", return_value=col):
            stats = sm.get_session_stats("london")
            assert stats["trade_count"] == 0
            assert stats["win_rate"] == 0.0

    def test_retrieve_returns_empty_on_empty_collection(self):
        import chromadb
        from agents.memory import swarm_memory as sm

        client = chromadb.EphemeralClient()
        col = client.get_or_create_collection("test_trades3")

        with patch.object(sm, "_get_collection", return_value=col):
            results = sm.retrieve_similar({"pair": "ETH/USDT"}, n=5)
            assert results == []


# ---------------------------------------------------------------------------
# Test: full pipeline integration (all LLM calls mocked)
# ---------------------------------------------------------------------------

class TestPipelineIntegration:
    def _make_all_mocks(self):
        """Return a client that handles all 9 agent calls with valid JSON."""
        responses = {
            "regime": {"phase": "distribution", "phase_confidence": 8,
                       "valid_setup": True, "trade_direction": "bullish", "reasoning": "ok"},
            "technical": {"signal": "BUY", "technical_confidence": 7, "fvg_entry": True,
                          "ob_level": 99.8, "bos_direction": "bullish",
                          "vwap_bias": "bullish", "rsi_divergence": False, "reasoning": "ok"},
            "flow": {"pressure": "buy_pressure", "flow_confidence": 6,
                     "large_walls_detected": False, "volume_confirms": True, "reasoning": "ok"},
            "sentiment": {"sentiment_score": 35, "sentiment_label": "Fear",
                          "supports_trade": True, "sentiment_confidence": 5, "reasoning": "ok"},
            "bull": {"bull_case": "Strong bull", "bull_conviction": 8,
                     "entry_price": 100.0, "sl_price": 98.2, "tp_price": 103.6, "key_levels": []},
            "bear": {"bear_case": "Weak bear", "bear_conviction": 3,
                     "key_risks": [], "invalidation_level": 97.0},
            "consensus": {"reasoning": "5/7 supermajority", "consensus_confidence": 8},
            "risk": {"approved": True, "risk_flags": [], "adjusted_position_size": 1.0,
                     "reasoning": "all clear"},
            "fund": {"action": "BUY", "confidence": 8.0, "confidence_tier": "STANDARD",
                     "position_size_multiplier": 1.0, "reasoning": "Execute", "risk_flags": []},
        }
        # All agents get the same mock client; parse_json will pick the right keys
        combined = {}
        for v in responses.values():
            combined.update(v)
        return _mock_client(combined)

    def test_pipeline_returns_final_decision(self):
        import agents.sentiment as sa
        sa.clear_cache()

        import chromadb
        from agents.memory import swarm_memory as sm
        col = chromadb.EphemeralClient().get_or_create_collection("pipe_test")

        with patch("anthropic.Anthropic", return_value=self._make_all_mocks()), \
             patch.object(sm, "_get_collection", return_value=col):
            from agents.pipeline import run_pipeline
            result = run_pipeline(BASE_STATE)

        assert "final_decision" in result
        fd = result["final_decision"]
        assert "action" in fd
        assert fd["action"] in ("BUY", "SELL", "HOLD")

    def test_pipeline_ends_at_confluence_gate_score_below_7(self):
        import agents.sentiment as sa
        sa.clear_cache()

        low_state = {**BASE_STATE, "confluence_score": 5}
        with patch("anthropic.Anthropic", return_value=self._make_all_mocks()):
            from agents.pipeline import run_pipeline
            result = run_pipeline(low_state)

        # Pipeline should terminate at confluence gate — final_decision stays empty or default
        fd = result.get("final_decision", {})
        # layer2 agents should NOT have run
        assert result.get("layer2_outputs", {}) == {}
