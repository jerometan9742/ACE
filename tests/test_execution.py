"""Tests for execution layer — paper order placement, SL/TP monitoring, mode guard, Telegram alerts."""

import time
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE_DECISION = {
    "action": "BUY",
    "confidence": 8.0,
    "confidence_tier": "STANDARD",
    "position_size_multiplier": 1.0,
    "reasoning": "test",
    "risk_flags": [],
    "entry_price": 100.0,
    "sl_price": 97.0,
    "tp_price": 106.0,
    "confluence_score": 8,
    "agent": "fund_manager",
    "error": False,
    "error_message": "",
}


def _mock_exchange(price: float = 100.0) -> MagicMock:
    exc = MagicMock()
    exc.fetch_ticker.return_value = {"last": price}
    exc.fetch_balance.return_value = {
        "USDT": {"total": 10000.0, "free": 10000.0, "used": 0.0}
    }
    return exc


def _open_position(action="BUY", entry=100.0, sl=97.0, tp=106.0) -> dict:
    return {
        "order_id": "test-order-1",
        "pair": "BTC/USDT",
        "action": action,
        "side": action.lower(),
        "quantity": 0.1,
        "entry_price": entry,
        "sl_price": sl,
        "tp_price": tp,
        "status": "filled",
        "paper": True,
        "timestamp": "2024-01-15T08:00:00Z",
        "agent_outputs": {},
        "confidence": 8.0,
        "confluence_score": 8,
    }


# ---------------------------------------------------------------------------
# TRADING_MODE guard
# ---------------------------------------------------------------------------

class TestTradingModeGuard:
    def test_live_mode_raises_immediately(self, monkeypatch):
        import execution.paper_trader as pt
        monkeypatch.setattr(pt, "_TRADING_MODE", "live")
        with pytest.raises(RuntimeError, match="paper"):
            pt.place_order("BTC/USDT", "buy", 0.01, 100.0, 97.0, 106.0, BASE_DECISION)

    def test_paper_mode_does_not_raise(self, monkeypatch):
        import execution.paper_trader as pt
        import execution.ccxt_client as cc
        monkeypatch.setattr(pt, "_TRADING_MODE", "paper")
        monkeypatch.setattr(cc, "get_exchange", lambda: _mock_exchange())
        with patch("risk.portfolio.update_position"):
            with patch("monitoring.telegram_alerts._send", return_value=True):
                with patch("monitoring.logger.log_trade"):
                    result = pt.place_order("BTC/USDT", "buy", 0.01, 100.0, 97.0, 106.0, BASE_DECISION)
        assert result["status"] == "filled"


# ---------------------------------------------------------------------------
# Paper order placement
# ---------------------------------------------------------------------------

class TestPaperOrderPlacement:
    def _place(self, monkeypatch, price=100.0, **decision_overrides):
        import execution.paper_trader as pt
        import execution.ccxt_client as cc
        monkeypatch.setattr(pt, "_TRADING_MODE", "paper")
        monkeypatch.setattr(cc, "get_exchange", lambda: _mock_exchange(price))
        decision = {**BASE_DECISION, **decision_overrides}
        with patch("risk.portfolio.update_position"):
            with patch("monitoring.telegram_alerts._send", return_value=True):
                with patch("monitoring.logger.log_trade"):
                    return pt.place_order("BTC/USDT", "buy", 0.01, price, 97.0, 106.0, decision)

    def test_returns_correct_structure(self, monkeypatch):
        result = self._place(monkeypatch)
        for key in ("order_id", "pair", "side", "quantity", "entry_price",
                    "sl_price", "tp_price", "status", "timestamp", "paper"):
            assert key in result, f"Missing key: {key}"

    def test_paper_flag_is_true(self, monkeypatch):
        assert self._place(monkeypatch)["paper"] is True

    def test_status_is_filled(self, monkeypatch):
        assert self._place(monkeypatch)["status"] == "filled"

    def test_fill_price_comes_from_exchange(self, monkeypatch):
        result = self._place(monkeypatch, price=99.5)
        assert result["entry_price"] == 99.5

    def test_order_id_is_generated(self, monkeypatch):
        result = self._place(monkeypatch)
        assert isinstance(result["order_id"], str)
        assert len(result["order_id"]) > 0

    def test_telegram_alert_sent_on_order_placed(self, monkeypatch):
        import execution.paper_trader as pt
        import execution.ccxt_client as cc
        monkeypatch.setattr(pt, "_TRADING_MODE", "paper")
        monkeypatch.setattr(cc, "get_exchange", lambda: _mock_exchange())
        sent = []
        with patch("risk.portfolio.update_position"):
            with patch("monitoring.telegram_alerts._send", side_effect=lambda t: sent.append(t) or True):
                with patch("monitoring.logger.log_trade"):
                    pt.place_order("BTC/USDT", "buy", 0.01, 100.0, 97.0, 106.0, BASE_DECISION)
        assert len(sent) >= 1

    def test_order_stored_in_open_orders(self, monkeypatch):
        import execution.paper_trader as pt
        import execution.ccxt_client as cc
        monkeypatch.setattr(pt, "_TRADING_MODE", "paper")
        monkeypatch.setattr(cc, "get_exchange", lambda: _mock_exchange())
        monkeypatch.setattr(pt, "_open_orders", {})
        with patch("risk.portfolio.update_position"):
            with patch("monitoring.telegram_alerts._send", return_value=True):
                with patch("monitoring.logger.log_trade"):
                    result = pt.place_order("BTC/USDT", "buy", 0.01, 100.0, 97.0, 106.0, BASE_DECISION)
        assert result["order_id"] in pt._open_orders


# ---------------------------------------------------------------------------
# Position monitor — SL / TP / price-in-range
# ---------------------------------------------------------------------------

class TestPositionMonitor:
    def _run_monitor(self, monkeypatch, current_price: float, position=None):
        """Run monitor_positions with a single open position at given price."""
        import execution.paper_trader as pt
        pos = position or _open_position()
        monkeypatch.setattr(pt, "_open_orders", {"test-order-1": dict(pos)})

        closed_calls = []
        with patch("execution.ccxt_client.get_current_price", return_value=current_price):
            with patch("risk.portfolio.close_position",
                       side_effect=lambda pair, price, reason: closed_calls.append((pair, price, reason)) or {
                           "pnl": (price - pos["entry_price"]) * pos["quantity"],
                           "pnl_pct": 0.0,
                           "win": price > pos["entry_price"],
                           "entry_price": pos["entry_price"],
                           "action": pos["action"],
                       }):
                with patch("monitoring.telegram_alerts._send", return_value=True):
                    with patch("agents.memory.reflection.reflect", return_value={}):
                        with patch("agents.memory.reflection.write_lesson"):
                            with patch("monitoring.logger.log_trade"):
                                pt.monitor_positions()
        return closed_calls

    def test_sl_hit_closes_position(self, monkeypatch):
        closed = self._run_monitor(monkeypatch, current_price=96.0)  # below SL=97
        assert len(closed) == 1
        assert closed[0][0] == "BTC/USDT"
        assert closed[0][2] == "SL_HIT"

    def test_tp_hit_closes_position(self, monkeypatch):
        closed = self._run_monitor(monkeypatch, current_price=107.0)  # above TP=106
        assert len(closed) == 1
        assert closed[0][2] == "TP_HIT"

    def test_price_between_sl_tp_does_not_close(self, monkeypatch):
        closed = self._run_monitor(monkeypatch, current_price=102.0)  # between SL=97 and TP=106
        assert len(closed) == 0

    def test_sl_hit_for_sell_position(self, monkeypatch):
        # SELL: SL is ABOVE entry, TP is below entry
        pos = _open_position(action="SELL", entry=100.0, sl=103.0, tp=94.0)
        closed = self._run_monitor(monkeypatch, current_price=104.0, position=pos)
        assert len(closed) == 1
        assert closed[0][2] == "SL_HIT"

    def test_tp_hit_for_sell_position(self, monkeypatch):
        pos = _open_position(action="SELL", entry=100.0, sl=103.0, tp=94.0)
        closed = self._run_monitor(monkeypatch, current_price=93.0, position=pos)
        assert len(closed) == 1
        assert closed[0][2] == "TP_HIT"

    def test_telegram_alert_sent_on_close(self, monkeypatch):
        import execution.paper_trader as pt
        pos = _open_position()
        monkeypatch.setattr(pt, "_open_orders", {"test-order-1": dict(pos)})
        sent = []
        with patch("execution.ccxt_client.get_current_price", return_value=96.0):
            with patch("risk.portfolio.close_position", return_value={
                "pnl": -40.0, "pnl_pct": -4.0, "win": False,
                "entry_price": 100.0, "action": "BUY",
            }):
                with patch("monitoring.telegram_alerts._send",
                           side_effect=lambda t: sent.append(t) or True):
                    with patch("agents.memory.reflection.reflect", return_value={}):
                        with patch("agents.memory.reflection.write_lesson"):
                            with patch("monitoring.logger.log_trade"):
                                pt.monitor_positions()
        assert len(sent) >= 1

    def test_order_removed_from_open_orders_after_close(self, monkeypatch):
        import execution.paper_trader as pt
        pos = _open_position()
        orders = {"test-order-1": dict(pos)}
        monkeypatch.setattr(pt, "_open_orders", orders)
        with patch("execution.ccxt_client.get_current_price", return_value=96.0):
            with patch("risk.portfolio.close_position", return_value={
                "pnl": -40.0, "pnl_pct": -4.0, "win": False
            }):
                with patch("monitoring.telegram_alerts._send", return_value=True):
                    with patch("agents.memory.reflection.reflect", return_value={}):
                        with patch("agents.memory.reflection.write_lesson"):
                            with patch("monitoring.logger.log_trade"):
                                pt.monitor_positions()
        assert "test-order-1" not in orders


# ---------------------------------------------------------------------------
# TP/SL validation in place_order
# ---------------------------------------------------------------------------

class TestTPValidation:
    def test_buy_with_tp_below_entry_is_rejected(self, monkeypatch):
        import execution.paper_trader as pt
        import execution.ccxt_client as cc
        monkeypatch.setattr(pt, "_TRADING_MODE", "paper")
        monkeypatch.setattr(cc, "get_exchange", lambda: _mock_exchange(100.0))
        # fill price = 100, tp = 95 — TP below entry for BUY → reject
        with patch("monitoring.telegram_alerts._send", return_value=True):
            with patch("monitoring.logger.log_trade"):
                result = pt.place_order("BTC/USDT", "BUY", 0.01, 100.0, 97.0, 95.0, BASE_DECISION)
        assert result["status"] == "failed"
        assert "BUY rejected" in result.get("error", "")

    def test_buy_with_tp_equal_to_entry_is_rejected(self, monkeypatch):
        import execution.paper_trader as pt
        import execution.ccxt_client as cc
        monkeypatch.setattr(pt, "_TRADING_MODE", "paper")
        monkeypatch.setattr(cc, "get_exchange", lambda: _mock_exchange(100.0))
        # tp == fill_price — also invalid
        with patch("monitoring.telegram_alerts._send", return_value=True):
            with patch("monitoring.logger.log_trade"):
                result = pt.place_order("BTC/USDT", "BUY", 0.01, 100.0, 97.0, 100.0, BASE_DECISION)
        assert result["status"] == "failed"
        assert "BUY rejected" in result.get("error", "")

    def test_sell_with_tp_above_entry_is_rejected(self, monkeypatch):
        import execution.paper_trader as pt
        import execution.ccxt_client as cc
        monkeypatch.setattr(pt, "_TRADING_MODE", "paper")
        monkeypatch.setattr(cc, "get_exchange", lambda: _mock_exchange(100.0))
        # fill price = 100, tp = 105 — TP above entry for SELL → reject
        sell_decision = {**BASE_DECISION, "action": "SELL"}
        with patch("monitoring.telegram_alerts._send", return_value=True):
            with patch("monitoring.logger.log_trade"):
                result = pt.place_order("BTC/USDT", "SELL", 0.01, 100.0, 103.0, 105.0, sell_decision)
        assert result["status"] == "failed"
        assert "SELL rejected" in result.get("error", "")

    def test_valid_buy_is_accepted(self, monkeypatch):
        import execution.paper_trader as pt
        import execution.ccxt_client as cc
        monkeypatch.setattr(pt, "_TRADING_MODE", "paper")
        monkeypatch.setattr(cc, "get_exchange", lambda: _mock_exchange(100.0))
        # tp=106 > entry=100 — valid
        with patch("risk.portfolio.update_position"):
            with patch("monitoring.telegram_alerts._send", return_value=True):
                with patch("monitoring.logger.log_trade"):
                    result = pt.place_order("BTC/USDT", "BUY", 0.01, 100.0, 97.0, 106.0, BASE_DECISION)
        assert result["status"] == "filled"

    def test_valid_sell_is_accepted(self, monkeypatch):
        import execution.paper_trader as pt
        import execution.ccxt_client as cc
        monkeypatch.setattr(pt, "_TRADING_MODE", "paper")
        monkeypatch.setattr(cc, "get_exchange", lambda: _mock_exchange(100.0))
        # tp=94 < entry=100 — valid for SELL
        sell_decision = {**BASE_DECISION, "action": "SELL"}
        with patch("risk.portfolio.update_position"):
            with patch("monitoring.telegram_alerts._send", return_value=True):
                with patch("monitoring.logger.log_trade"):
                    result = pt.place_order("BTC/USDT", "SELL", 0.01, 100.0, 103.0, 94.0, sell_decision)
        assert result["status"] == "filled"


# ---------------------------------------------------------------------------
# price_monitor — SL/TP/price-in-range
# ---------------------------------------------------------------------------

class TestPriceMonitor:
    def _run(self, monkeypatch, current_price: float, position=None):
        import execution.paper_trader as pt
        import monitoring.price_monitor as pm
        pos = position or _open_position()
        monkeypatch.setattr(pt, "_open_orders", {"test-order-1": dict(pos)})

        closed_calls = []
        with patch("execution.ccxt_client.get_current_price", return_value=current_price):
            with patch("risk.portfolio.close_position",
                       side_effect=lambda pair, price, reason:
                           closed_calls.append((pair, price, reason)) or {
                               "pnl": (price - pos["entry_price"]) * pos["quantity"],
                               "pnl_pct": 0.0,
                               "win": price > pos["entry_price"],
                           }):
                with patch("monitoring.telegram_alerts._send", return_value=True):
                    with patch("agents.memory.reflection.reflect", return_value={}):
                        with patch("agents.memory.reflection.write_lesson"):
                            with patch("monitoring.logger.log_trade"):
                                pm.check_positions()
        return closed_calls

    def test_closes_buy_on_tp_hit(self, monkeypatch):
        closed = self._run(monkeypatch, current_price=107.0)  # above TP=106
        assert len(closed) == 1
        assert closed[0][2] == "TP_HIT"

    def test_closes_buy_on_sl_hit(self, monkeypatch):
        closed = self._run(monkeypatch, current_price=96.0)   # below SL=97
        assert len(closed) == 1
        assert closed[0][2] == "SL_HIT"

    def test_no_close_when_price_between_sl_and_tp(self, monkeypatch):
        closed = self._run(monkeypatch, current_price=102.0)
        assert len(closed) == 0

    def test_closes_sell_on_sl_hit(self, monkeypatch):
        pos = _open_position(action="SELL", entry=100.0, sl=103.0, tp=94.0)
        closed = self._run(monkeypatch, current_price=104.0, position=pos)
        assert len(closed) == 1
        assert closed[0][2] == "SL_HIT"

    def test_closes_sell_on_tp_hit(self, monkeypatch):
        pos = _open_position(action="SELL", entry=100.0, sl=103.0, tp=94.0)
        closed = self._run(monkeypatch, current_price=93.0, position=pos)
        assert len(closed) == 1
        assert closed[0][2] == "TP_HIT"

    def test_order_removed_from_open_orders_after_close(self, monkeypatch):
        import execution.paper_trader as pt
        pos = _open_position()
        orders = {"test-order-1": dict(pos)}
        monkeypatch.setattr(pt, "_open_orders", orders)
        with patch("execution.ccxt_client.get_current_price", return_value=107.0):
            with patch("risk.portfolio.close_position", return_value={
                "pnl": 0.7, "pnl_pct": 0.7, "win": True
            }):
                with patch("monitoring.telegram_alerts._send", return_value=True):
                    with patch("agents.memory.reflection.reflect", return_value={}):
                        with patch("agents.memory.reflection.write_lesson"):
                            with patch("monitoring.logger.log_trade"):
                                import monitoring.price_monitor as pm
                                pm.check_positions()
        assert "test-order-1" not in orders


# ---------------------------------------------------------------------------
# ccxt_client live-mode guard
# ---------------------------------------------------------------------------

class TestCcxtClientLiveGuard:
    def test_live_mode_without_confirmed_raises(self, monkeypatch):
        import execution.ccxt_client as cc
        cc._reset_exchange_for_testing()
        monkeypatch.setattr(cc, "_TRADING_MODE", "live")
        monkeypatch.setattr(cc, "_LIVE_CONFIRMED", False)
        with pytest.raises(RuntimeError, match="LIVE_CONFIRMED"):
            cc.get_exchange()
        cc._reset_exchange_for_testing()

    def test_testnet_url_used_in_paper_mode(self, monkeypatch):
        import execution.ccxt_client as cc
        cc._reset_exchange_for_testing()
        monkeypatch.setattr(cc, "_TRADING_MODE", "paper")

        created_kwargs = {}

        class FakeExchange:
            def __init__(self, kwargs):
                created_kwargs.update(kwargs)
            def set_sandbox_mode(self, val):
                created_kwargs["sandbox"] = val

        import ccxt
        monkeypatch.setattr(ccxt, "binance", FakeExchange)
        cc.get_exchange()

        urls = created_kwargs.get("urls", {}).get("api", {})
        assert "testnet.binance.vision" in urls.get("public", "")
        cc._reset_exchange_for_testing()
