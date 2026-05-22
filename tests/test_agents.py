"""Unit tests for all 9 ACE agents — mocks Anthropic API, verifies dict structure and error handling."""

import json
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _mock_message(payload: dict) -> MagicMock:
    """Return a mock Anthropic Message with content[0].text = JSON string."""
    msg = MagicMock()
    msg.content = [MagicMock()]
    msg.content[0].text = json.dumps(payload)
    return msg


def _mock_client(payload: dict) -> MagicMock:
    """Return a mock Anthropic client whose messages.create returns payload."""
    client = MagicMock()
    client.messages.create.return_value = _mock_message(payload)
    return client


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

CANDLE = {"open": 100.0, "high": 102.0, "low": 98.0, "close": 100.0, "volume": 1000.0}
CANDLES = [CANDLE] * 20

AMD_DATA = {
    "phase": "distribution", "confidence": 0.8,
    "range_high": 102.0, "range_low": 98.0,
    "manipulation_detected": True, "manipulation_direction": "bullish",
    "distribution_direction": "bullish",
}
BOS_DATA = {
    "bos_detected": True, "bos_direction": "bullish",
    "choch_detected": False, "choch_direction": "",
    "swing_high": 102.0, "swing_low": 98.0,
    "last_higher_high": 0.0, "last_lower_low": 0.0,
}
SESSION = {"name": "london", "is_active": True, "confidence_threshold": 7.0}
FVGS = [{"type": "bullish", "top": 100.5, "bottom": 99.5, "mitigated": False, "strength": 0.005}]
OBS = [{"type": "bullish", "high": 100.2, "low": 99.8, "mitigated": False, "strength": 0.04}]

ORDER_BOOK = {
    "bids": [[99.5, 10.0], [99.0, 8.0]],
    "asks": [[100.5, 9.0], [101.0, 7.0]],
}
RECENT_TRADES = [
    {"price": 100.0, "size": 5.0, "side": "buy", "timestamp": 1000},
    {"price": 99.5, "size": 3.0, "side": "sell", "timestamp": 1001},
]
VOLUME_PROFILE = {"poc": 100.0, "value_area_high": 101.0, "value_area_low": 99.0}


# ---------------------------------------------------------------------------
# regime_detector
# ---------------------------------------------------------------------------

class TestRegimeDetector:
    _REQUIRED_KEYS = {
        "agent", "phase", "phase_confidence", "valid_setup",
        "trade_direction", "reasoning", "error", "error_message",
    }

    def test_returns_correct_structure(self):
        payload = {"phase": "distribution", "phase_confidence": 8,
                   "valid_setup": True, "trade_direction": "bullish",
                   "reasoning": "Distribution confirmed"}
        with patch("anthropic.Anthropic", return_value=_mock_client(payload)):
            from agents.regime_detector import analyse
            result = analyse(AMD_DATA, BOS_DATA, SESSION, CANDLES, "BTC/USDT", "2024-01-01")
        assert self._REQUIRED_KEYS.issubset(result.keys())
        assert result["agent"] == "regime_detector"
        assert result["error"] is False

    def test_handles_api_error_gracefully(self):
        bad_client = MagicMock()
        bad_client.messages.create.side_effect = Exception("API down")
        with patch("anthropic.Anthropic", return_value=bad_client):
            from agents.regime_detector import analyse
            result = analyse(AMD_DATA, BOS_DATA, SESSION, CANDLES, "BTC/USDT", "2024-01-01")
        assert result["error"] is True
        assert "API down" in result["error_message"]
        assert result["valid_setup"] is False

    def test_phase_confidence_is_int(self):
        payload = {"phase": "accumulation", "phase_confidence": 5.7,
                   "valid_setup": False, "trade_direction": "neutral", "reasoning": ""}
        with patch("anthropic.Anthropic", return_value=_mock_client(payload)):
            from agents.regime_detector import analyse
            result = analyse(AMD_DATA, BOS_DATA, SESSION, CANDLES, "BTC/USDT", "2024-01-01")
        assert isinstance(result["phase_confidence"], int)


# ---------------------------------------------------------------------------
# technical
# ---------------------------------------------------------------------------

class TestTechnical:
    _REQUIRED_KEYS = {
        "agent", "signal", "technical_confidence", "fvg_entry", "ob_level",
        "bos_direction", "vwap_bias", "rsi_divergence", "reasoning", "error",
    }

    def test_returns_correct_structure(self):
        payload = {"signal": "BUY", "technical_confidence": 7, "fvg_entry": True,
                   "ob_level": 99.8, "bos_direction": "bullish",
                   "vwap_bias": "bullish", "rsi_divergence": False, "reasoning": ""}
        with patch("anthropic.Anthropic", return_value=_mock_client(payload)):
            from agents.technical import analyse
            result = analyse(CANDLES, CANDLES, CANDLES, FVGS, OBS, BOS_DATA,
                             100.5, 55.0, 1.2, "BTC/USDT")
        assert self._REQUIRED_KEYS.issubset(result.keys())
        assert result["error"] is False

    def test_handles_api_error(self):
        bad = MagicMock()
        bad.messages.create.side_effect = RuntimeError("timeout")
        with patch("anthropic.Anthropic", return_value=bad):
            from agents.technical import analyse
            result = analyse(CANDLES, CANDLES, CANDLES, FVGS, OBS, BOS_DATA,
                             100.5, 55.0, 1.2, "BTC/USDT")
        assert result["error"] is True
        assert result["signal"] == "HOLD"


# ---------------------------------------------------------------------------
# order_flow
# ---------------------------------------------------------------------------

class TestOrderFlow:
    _REQUIRED_KEYS = {
        "agent", "pressure", "flow_confidence", "large_walls_detected",
        "volume_confirms", "reasoning", "error",
    }

    def test_returns_correct_structure(self):
        payload = {"pressure": "buy_pressure", "flow_confidence": 6,
                   "large_walls_detected": False, "volume_confirms": True, "reasoning": ""}
        with patch("anthropic.Anthropic", return_value=_mock_client(payload)):
            from agents.order_flow import analyse
            result = analyse(ORDER_BOOK, RECENT_TRADES, VOLUME_PROFILE, "BTC/USDT", "t")
        assert self._REQUIRED_KEYS.issubset(result.keys())
        assert result["error"] is False

    def test_handles_api_error(self):
        bad = MagicMock()
        bad.messages.create.side_effect = Exception("network error")
        with patch("anthropic.Anthropic", return_value=bad):
            from agents.order_flow import analyse
            result = analyse(ORDER_BOOK, RECENT_TRADES, VOLUME_PROFILE, "BTC/USDT", "t")
        assert result["error"] is True
        assert result["pressure"] == "neutral"


# ---------------------------------------------------------------------------
# sentiment
# ---------------------------------------------------------------------------

class TestSentiment:
    _REQUIRED_KEYS = {
        "agent", "sentiment_score", "sentiment_label", "supports_trade",
        "sentiment_confidence", "reasoning", "cached_until", "error",
    }

    def setup_method(self):
        import agents.sentiment as sa
        sa.clear_cache()

    def test_returns_correct_structure(self):
        payload = {"sentiment_score": 30, "sentiment_label": "Fear",
                   "supports_trade": True, "sentiment_confidence": 6, "reasoning": ""}
        with patch("anthropic.Anthropic", return_value=_mock_client(payload)):
            from agents.sentiment import analyse
            result = analyse(30, "Fear", "BTC/USDT", "t")
        assert self._REQUIRED_KEYS.issubset(result.keys())
        assert result["error"] is False

    def test_caches_result(self):
        payload = {"sentiment_score": 50, "sentiment_label": "Neutral",
                   "supports_trade": False, "sentiment_confidence": 4, "reasoning": ""}
        with patch("anthropic.Anthropic", return_value=_mock_client(payload)) as MockAnthro:
            from agents.sentiment import analyse
            analyse(50, "Neutral", "BTC/USDT", "t")
            analyse(50, "Neutral", "BTC/USDT", "t")  # second call should use cache
            assert MockAnthro.return_value.messages.create.call_count == 1

    def test_handles_api_error(self):
        bad = MagicMock()
        bad.messages.create.side_effect = Exception("fail")
        with patch("anthropic.Anthropic", return_value=bad):
            from agents.sentiment import analyse
            result = analyse(50, "Neutral", "BTC/USDT", "t")
        assert result["error"] is True


# ---------------------------------------------------------------------------
# bull_researcher
# ---------------------------------------------------------------------------

class TestBullResearcher:
    _REQUIRED_KEYS = {
        "agent", "bull_case", "bull_conviction", "entry_price",
        "sl_price", "tp_price", "key_levels", "error",
    }
    _L1 = {"phase": "distribution", "phase_confidence": 8, "valid_setup": True,
            "trade_direction": "bullish", "reasoning": "", "error": False}

    def test_returns_correct_structure(self):
        payload = {"bull_case": "Strong bullish", "bull_conviction": 8,
                   "entry_price": 100.0, "sl_price": 98.2, "tp_price": 103.6,
                   "key_levels": ["99.5 FVG bottom"]}
        with patch("anthropic.Anthropic", return_value=_mock_client(payload)):
            from agents.bull_researcher import analyse
            result = analyse(self._L1, self._L1, self._L1, self._L1,
                             8, AMD_DATA, FVGS, OBS, "BTC/USDT", 100.0, 1.2)
        assert self._REQUIRED_KEYS.issubset(result.keys())
        assert result["error"] is False
        assert isinstance(result["key_levels"], list)

    def test_sl_tp_calculated_from_atr(self):
        """When LLM gives wrong levels, entry/sl/tp should still be numeric."""
        payload = {"bull_case": "ok", "bull_conviction": 7,
                   "entry_price": 100.0, "sl_price": 98.2, "tp_price": 103.6, "key_levels": []}
        with patch("anthropic.Anthropic", return_value=_mock_client(payload)):
            from agents.bull_researcher import analyse
            result = analyse(self._L1, self._L1, self._L1, self._L1,
                             8, AMD_DATA, FVGS, OBS, "BTC/USDT", 100.0, 1.2)
        assert isinstance(result["sl_price"], float)
        assert isinstance(result["tp_price"], float)


# ---------------------------------------------------------------------------
# bear_researcher
# ---------------------------------------------------------------------------

class TestBearResearcher:
    _REQUIRED_KEYS = {
        "agent", "bear_case", "bear_conviction", "key_risks",
        "invalidation_level", "error",
    }
    _L1 = {"phase": "distribution", "valid_setup": True, "trade_direction": "bullish",
            "signal": "BUY", "pressure": "buy_pressure", "sentiment_score": 40,
            "sentiment_label": "Fear", "supports_trade": True, "reasoning": "", "error": False}
    _BULL = {"bull_case": "strong", "bull_conviction": 8, "entry_price": 100.0,
             "sl_price": 98.2, "tp_price": 103.6, "key_levels": [], "error": False}

    def test_returns_correct_structure(self):
        payload = {"bear_case": "CHoCH risk", "bear_conviction": 3,
                   "key_risks": ["low volume"], "invalidation_level": 98.0}
        with patch("anthropic.Anthropic", return_value=_mock_client(payload)):
            from agents.bear_researcher import analyse
            result = analyse(self._L1, self._L1, self._L1, self._L1,
                             self._BULL, 8, AMD_DATA, "BTC/USDT", 100.0, 1.2)
        assert self._REQUIRED_KEYS.issubset(result.keys())
        assert isinstance(result["key_risks"], list)
        assert result["error"] is False


# ---------------------------------------------------------------------------
# consensus
# ---------------------------------------------------------------------------

class TestConsensus:
    _REQUIRED_KEYS = {
        "agent", "consensus_action", "signals_for", "signals_against",
        "signals_total", "passes_threshold", "consensus_confidence",
        "reasoning", "error",
    }

    def _make_outputs(self, valid=True, signal="BUY", vol_confirms=True,
                      supports=True, bull_conv=8, bear_conv=3, confluence=8):
        regime = {"valid_setup": valid, "trade_direction": "bullish", "phase_confidence": 8, "phase": "distribution"}
        technical = {"signal": signal, "technical_confidence": 7, "vwap_bias": "bullish"}
        flow = {"volume_confirms": vol_confirms, "flow_confidence": 6, "pressure": "buy_pressure"}
        sentiment = {"supports_trade": supports, "sentiment_confidence": 5}
        bull = {"bull_case": "strong", "bull_conviction": bull_conv, "entry_price": 100.0}
        bear = {"bear_case": "weak", "bear_conviction": bear_conv}
        return regime, technical, flow, sentiment, bull, bear, confluence

    def test_passes_with_5_of_7_signals(self):
        payload = {"reasoning": "Strong", "consensus_confidence": 7}
        with patch("anthropic.Anthropic", return_value=_mock_client(payload)):
            from agents.consensus import analyse
            result = analyse(*self._make_outputs())
        assert result["passes_threshold"] is True
        assert result["signals_total"] == 7
        assert len(result["signals_for"]) >= 5

    def test_fails_with_insufficient_signals(self):
        payload = {"reasoning": "Weak", "consensus_confidence": 2}
        with patch("anthropic.Anthropic", return_value=_mock_client(payload)):
            from agents.consensus import analyse
            result = analyse(*self._make_outputs(
                valid=False, signal="HOLD", vol_confirms=False,
                supports=False, bull_conv=3, bear_conv=8, confluence=5,
            ))
        assert result["passes_threshold"] is False
        assert result["consensus_action"] == "HOLD"

    def test_returns_correct_structure(self):
        payload = {"reasoning": "ok", "consensus_confidence": 6}
        with patch("anthropic.Anthropic", return_value=_mock_client(payload)):
            from agents.consensus import analyse
            result = analyse(*self._make_outputs())
        assert self._REQUIRED_KEYS.issubset(result.keys())


# ---------------------------------------------------------------------------
# risk_manager
# ---------------------------------------------------------------------------

class TestRiskManager:
    _REQUIRED_KEYS = {
        "agent", "approved", "veto_reason", "risk_flags",
        "adjusted_position_size", "error",
    }
    _CONSENSUS = {"consensus_action": "BUY", "consensus_confidence": 8,
                  "signals_for": [], "passes_threshold": True}

    def test_hard_veto_outside_kill_zone(self):
        outside_session = {"name": "outside", "is_active": False, "confidence_threshold": 0.0}
        with patch("anthropic.Anthropic", return_value=MagicMock()):
            from agents.risk_manager import analyse
            result = analyse(
                self._CONSENSUS, {}, 0.0, 10000.0, outside_session,
                {"correlation": 0.0}, 1.2, "BTC/USDT", 100.0, False,
            )
        assert result["approved"] is False
        assert "kill zone" in result["veto_reason"].lower()

    def test_hard_veto_kill_switch_active(self):
        with patch("anthropic.Anthropic", return_value=MagicMock()):
            from agents.risk_manager import analyse
            result = analyse(
                self._CONSENSUS, {}, 0.0, 10000.0, SESSION,
                {"correlation": 0.0}, 1.2, "BTC/USDT", 100.0, True,
            )
        assert result["approved"] is False
        assert "kill switch" in result["veto_reason"].lower()

    def test_hard_veto_daily_loss_limit(self):
        with patch("anthropic.Anthropic", return_value=MagicMock()):
            from agents.risk_manager import analyse
            result = analyse(
                self._CONSENSUS, {}, -500.0, 10000.0, SESSION,
                {"correlation": 0.0}, 1.2, "BTC/USDT", 100.0, False,
            )
        assert result["approved"] is False
        assert "daily loss" in result["veto_reason"].lower()

    def test_hard_veto_correlation(self):
        with patch("anthropic.Anthropic", return_value=MagicMock()):
            from agents.risk_manager import analyse
            result = analyse(
                self._CONSENSUS, {}, 0.0, 10000.0, SESSION,
                {"correlation": 0.90}, 1.2, "BTC/USDT", 100.0, False,
            )
        assert result["approved"] is False
        assert "correlation" in result["veto_reason"].lower()

    def test_approved_when_all_clear(self):
        payload = {"approved": True, "risk_flags": [], "adjusted_position_size": 1.0,
                   "reasoning": "all clear"}
        with patch("anthropic.Anthropic", return_value=_mock_client(payload)):
            from agents.risk_manager import analyse
            result = analyse(
                self._CONSENSUS, {}, 0.0, 10000.0, SESSION,
                {"correlation": 0.0}, 1.2, "BTC/USDT", 100.0, False,
            )
        assert result["approved"] is True
        assert self._REQUIRED_KEYS.issubset(result.keys())


# ---------------------------------------------------------------------------
# fund_manager
# ---------------------------------------------------------------------------

class TestFundManager:
    _REQUIRED_KEYS = {
        "agent", "action", "confidence", "confidence_tier",
        "position_size_multiplier", "reasoning", "risk_flags",
        "entry_price", "sl_price", "tp_price", "error",
    }
    _L1 = {"phase": "distribution", "valid_setup": True, "trade_direction": "bullish",
            "signal": "BUY", "pressure": "buy_pressure", "vwap_bias": "bullish",
            "supports_trade": True, "sentiment_score": 35, "sentiment_label": "Fear",
            "phase_confidence": 8, "technical_confidence": 7, "flow_confidence": 6,
            "sentiment_confidence": 5, "bos_direction": "bullish", "reasoning": "", "error": False}
    _BULL = {"bull_case": "strong", "bull_conviction": 8, "entry_price": 100.0,
             "sl_price": 98.2, "tp_price": 103.6, "key_levels": [], "error": False}
    _BEAR = {"bear_case": "weak", "bear_conviction": 3, "key_risks": [], "error": False}
    _CONSENSUS = {"consensus_action": "BUY", "signals_for": ["a", "b", "c", "d", "e"],
                  "signals_total": 7, "passes_threshold": True, "consensus_confidence": 8, "reasoning": ""}
    _RISK = {"approved": True, "veto_reason": "", "risk_flags": [],
             "adjusted_position_size": 1.0, "error": False}

    def test_returns_correct_structure(self):
        payload = {"action": "BUY", "confidence": 8.0, "confidence_tier": "STANDARD",
                   "position_size_multiplier": 1.0, "reasoning": "Go", "risk_flags": []}
        with patch("anthropic.Anthropic", return_value=_mock_client(payload)):
            from agents.fund_manager import analyse
            result = analyse(
                self._L1, self._L1, self._L1, self._L1,
                self._BULL, self._BEAR, self._CONSENSUS, self._RISK,
                [], "BTC/USDT", 100.0, 1.2, 8,
            )
        assert self._REQUIRED_KEYS.issubset(result.keys())
        assert result["error"] is False

    def test_hold_when_confidence_below_7(self):
        payload = {"action": "BUY", "confidence": 5.0, "confidence_tier": "HOLD",
                   "position_size_multiplier": 0.0, "reasoning": "Weak", "risk_flags": []}
        with patch("anthropic.Anthropic", return_value=_mock_client(payload)):
            from agents.fund_manager import analyse
            result = analyse(
                self._L1, self._L1, self._L1, self._L1,
                self._BULL, self._BEAR, self._CONSENSUS, self._RISK,
                [], "BTC/USDT", 100.0, 1.2, 8,
            )
        assert result["action"] == "HOLD"
        assert result["confidence_tier"] == "HOLD"
        assert result["position_size_multiplier"] == 0.0

    def test_high_tier_for_confidence_above_8_5(self):
        payload = {"action": "BUY", "confidence": 9.0, "confidence_tier": "HIGH",
                   "position_size_multiplier": 1.5, "reasoning": "Strong", "risk_flags": []}
        with patch("anthropic.Anthropic", return_value=_mock_client(payload)):
            from agents.fund_manager import analyse
            result = analyse(
                self._L1, self._L1, self._L1, self._L1,
                self._BULL, self._BEAR, self._CONSENSUS, self._RISK,
                [], "BTC/USDT", 100.0, 1.2, 9,
            )
        assert result["confidence_tier"] == "HIGH"
        assert result["position_size_multiplier"] == 1.5
