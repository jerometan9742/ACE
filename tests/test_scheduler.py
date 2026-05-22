"""Tests for scheduler — session transitions, daily counter resets, graceful shutdown state save."""

import json
import os
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Session transition handling
# ---------------------------------------------------------------------------

class TestSessionManagement:
    def test_entering_kill_zone_resets_session_counters(self, monkeypatch):
        import scheduler
        monkeypatch.setitem(scheduler._session_state, "BTC/USDT", "outside")
        reset_called = []
        with patch("risk.portfolio.reset_session_counters", side_effect=lambda: reset_called.append(1)):
            with patch("monitoring.telegram_alerts._send", return_value=True):
                with patch("risk.portfolio.get_daily_pnl", return_value=0.0):
                    scheduler._check_session_transition(
                        "BTC/USDT", {"name": "london", "is_active": True}
                    )
        assert len(reset_called) == 1

    def test_entering_kill_zone_sends_telegram_alert(self, monkeypatch):
        import scheduler
        monkeypatch.setitem(scheduler._session_state, "BTC/USDT", "outside")
        sent = []
        with patch("monitoring.telegram_alerts._send", side_effect=lambda t: sent.append(t) or True):
            with patch("risk.portfolio.reset_session_counters"):
                with patch("risk.portfolio.get_daily_pnl", return_value=0.0):
                    scheduler._check_session_transition(
                        "BTC/USDT", {"name": "london", "is_active": True}
                    )
        assert any("london" in s.lower() or "session start" in s.lower() for s in sent)

    def test_leaving_kill_zone_sends_session_end_summary(self, monkeypatch):
        import scheduler
        monkeypatch.setitem(scheduler._session_state, "BTC/USDT", "london")
        sent = []
        with patch("monitoring.telegram_alerts._send", side_effect=lambda t: sent.append(t) or True):
            with patch("risk.portfolio.get_daily_pnl", return_value=150.0):
                with patch("risk.portfolio.reset_session_counters"):
                    scheduler._check_session_transition(
                        "BTC/USDT", {"name": "outside", "is_active": False}
                    )
        assert any("session end" in s.lower() or "london" in s.lower() for s in sent)

    def test_no_duplicate_alerts_for_same_session(self, monkeypatch):
        import scheduler
        monkeypatch.setitem(scheduler._session_state, "BTC/USDT", "london")
        sent = []
        with patch("monitoring.telegram_alerts._send", side_effect=lambda t: sent.append(t) or True):
            with patch("risk.portfolio.reset_session_counters"):
                # Same session — should not fire
                scheduler._check_session_transition(
                    "BTC/USDT", {"name": "london", "is_active": True}
                )
        assert len(sent) == 0

    def test_no_alerts_for_non_primary_pair(self, monkeypatch):
        import scheduler
        # ETH/USDT is not WATCHLIST[0] → no alerts
        monkeypatch.setitem(scheduler._session_state, "ETH/USDT", "outside")
        sent = []
        with patch("monitoring.telegram_alerts._send", side_effect=lambda t: sent.append(t) or True):
            with patch("risk.portfolio.reset_session_counters"):
                scheduler._check_session_transition(
                    "ETH/USDT", {"name": "london", "is_active": True}
                )
        assert len(sent) == 0

    def test_ny_open_transition_fires_alert(self, monkeypatch):
        import scheduler
        monkeypatch.setitem(scheduler._session_state, "BTC/USDT", "outside")
        sent = []
        with patch("monitoring.telegram_alerts._send", side_effect=lambda t: sent.append(t) or True):
            with patch("risk.portfolio.reset_session_counters"):
                with patch("risk.portfolio.get_daily_pnl", return_value=0.0):
                    scheduler._check_session_transition(
                        "BTC/USDT", {"name": "ny_open", "is_active": True}
                    )
        assert len(sent) >= 1


# ---------------------------------------------------------------------------
# Daily counter reset
# ---------------------------------------------------------------------------

class TestDailyCounters:
    def test_reset_clears_trade_count(self):
        import scheduler
        scheduler._daily_stats["trades"] = 7
        scheduler._reset_daily_counters()
        assert scheduler._daily_stats["trades"] == 0

    def test_reset_clears_pnl(self):
        import scheduler
        scheduler._daily_stats["pnl"] = 450.0
        scheduler._reset_daily_counters()
        assert scheduler._daily_stats["pnl"] == 0.0

    def test_reset_clears_wins(self):
        import scheduler
        scheduler._daily_stats["wins"] = 5
        scheduler._reset_daily_counters()
        assert scheduler._daily_stats["wins"] == 0

    def test_reset_sets_today_date(self):
        import scheduler
        from datetime import datetime, timezone
        scheduler._reset_daily_counters()
        expected = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert scheduler._daily_stats["date"] == expected


# ---------------------------------------------------------------------------
# Graceful shutdown — portfolio state save
# ---------------------------------------------------------------------------

class TestGracefulShutdown:
    def test_save_portfolio_state_writes_json_file(self, tmp_path, monkeypatch):
        import scheduler
        state = {
            "open_positions": [],
            "daily_pnl": 0.0,
            "equity": 10000.0,
            "trades_today": 0,
            "trades_this_session": 0,
        }
        save_path = str(tmp_path / "logs" / "portfolio_state.json")
        monkeypatch.setattr(scheduler, "_STATE_FILE", save_path)
        with patch("risk.portfolio.get_portfolio_state", return_value=state):
            scheduler._save_portfolio_state()
        assert os.path.exists(save_path)

    def test_save_portfolio_state_content_is_valid_json(self, tmp_path, monkeypatch):
        import scheduler
        state = {"open_positions": [], "daily_pnl": 42.0, "equity": 10500.0}
        save_path = str(tmp_path / "logs" / "portfolio_state.json")
        monkeypatch.setattr(scheduler, "_STATE_FILE", save_path)
        with patch("risk.portfolio.get_portfolio_state", return_value=state):
            scheduler._save_portfolio_state()
        with open(save_path) as f:
            data = json.load(f)
        assert data["daily_pnl"] == 42.0
        assert "open_positions" in data

    def test_save_portfolio_state_handles_error_without_raising(self, monkeypatch):
        import scheduler
        with patch("risk.portfolio.get_portfolio_state", side_effect=RuntimeError("db down")):
            scheduler._save_portfolio_state()  # must not propagate the exception

    def test_run_raises_if_not_paper_mode(self, monkeypatch):
        import scheduler
        monkeypatch.setattr(scheduler, "TRADING_MODE", "live")
        with pytest.raises(RuntimeError, match="paper"):
            scheduler.run()
