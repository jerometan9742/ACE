"""Tests for risk_gate — all 9 ordered checks plus kill switch lifecycle."""

import time

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decision(**overrides) -> dict:
    d = {
        "action": "BUY",
        "confidence": 8.0,
        "position_size_multiplier": 1.0,
        "signal_timestamp": time.time(),
    }
    d.update(overrides)
    return d


def _portfolio(**overrides) -> dict:
    p = {
        "session": {"name": "london", "is_active": True},
        "daily_pnl": 0.0,
        "equity": 10000.0,
        "trades_this_session": 0,
        "open_positions": [],
        "correlation": 0.0,
    }
    p.update(overrides)
    return p


def _check(decision, portfolio, tmp_path, monkeypatch):
    """Run check_trade with kill switch redirected to a temp file."""
    from risk import risk_gate as rg
    monkeypatch.setattr(rg, "_KILL_SWITCH_FILE", str(tmp_path / "kill_switch.lock"))
    return rg.check_trade(decision, portfolio)


# ---------------------------------------------------------------------------
# Kill switch lifecycle
# ---------------------------------------------------------------------------

class TestKillSwitch:
    def test_activate_creates_file(self, tmp_path, monkeypatch):
        from risk import risk_gate as rg
        monkeypatch.setattr(rg, "_KILL_SWITCH_FILE", str(tmp_path / "kill_switch.lock"))
        rg.activate_kill_switch("test reason")
        assert (tmp_path / "kill_switch.lock").exists()

    def test_deactivate_removes_file(self, tmp_path, monkeypatch):
        from risk import risk_gate as rg
        lock = tmp_path / "kill_switch.lock"
        lock.write_text("{}")
        monkeypatch.setattr(rg, "_KILL_SWITCH_FILE", str(lock))
        rg.deactivate_kill_switch()
        assert not lock.exists()

    def test_deactivate_is_idempotent(self, tmp_path, monkeypatch):
        from risk import risk_gate as rg
        monkeypatch.setattr(rg, "_KILL_SWITCH_FILE", str(tmp_path / "kill_switch.lock"))
        rg.deactivate_kill_switch()  # no file — must not raise

    def test_is_active_true_when_file_exists(self, tmp_path, monkeypatch):
        from risk import risk_gate as rg
        lock = tmp_path / "kill_switch.lock"
        lock.write_text("{}")
        monkeypatch.setattr(rg, "_KILL_SWITCH_FILE", str(lock))
        assert rg.is_kill_switch_active() is True

    def test_is_active_false_when_file_absent(self, tmp_path, monkeypatch):
        from risk import risk_gate as rg
        monkeypatch.setattr(rg, "_KILL_SWITCH_FILE", str(tmp_path / "kill_switch.lock"))
        assert rg.is_kill_switch_active() is False


# ---------------------------------------------------------------------------
# check_trade — 9 checks in strict order
# ---------------------------------------------------------------------------

class TestCheckTradeOrder:

    # ── check 1: kill switch ──────────────────────────────────────────────
    def test_kill_switch_blocks(self, tmp_path, monkeypatch):
        from risk import risk_gate as rg
        lock = tmp_path / "kill_switch.lock"
        lock.write_text('{"reason": "test"}')
        monkeypatch.setattr(rg, "_KILL_SWITCH_FILE", str(lock))
        result = rg.check_trade(_decision(), _portfolio())
        assert result["approved"] is False
        assert result["blocked_by"] == "kill_switch"

    # ── check 2: HOLD passthrough ─────────────────────────────────────────
    def test_hold_passes_through(self, tmp_path, monkeypatch):
        result = _check(_decision(action="HOLD"), _portfolio(), tmp_path, monkeypatch)
        assert result["approved"] is True
        assert result["adjusted_size"] == 0.0

    # ── check 3: confidence gate ──────────────────────────────────────────
    def test_confidence_below_london_threshold_blocks(self, tmp_path, monkeypatch):
        result = _check(
            _decision(confidence=6.9),
            _portfolio(session={"name": "london", "is_active": True}),
            tmp_path, monkeypatch,
        )
        assert result["approved"] is False
        assert result["blocked_by"] == "confidence_gate"

    def test_confidence_below_ny_afternoon_threshold_blocks(self, tmp_path, monkeypatch):
        result = _check(
            _decision(confidence=7.4),
            _portfolio(session={"name": "ny_afternoon", "is_active": True}),
            tmp_path, monkeypatch,
        )
        assert result["approved"] is False
        assert result["blocked_by"] == "confidence_gate"

    def test_confidence_at_threshold_not_blocked_by_confidence_gate(self, tmp_path, monkeypatch):
        result = _check(_decision(confidence=7.0), _portfolio(), tmp_path, monkeypatch)
        assert result["blocked_by"] != "confidence_gate"

    # ── check 4: kill zone gate ───────────────────────────────────────────
    def test_outside_session_blocks(self, tmp_path, monkeypatch):
        # Use confidence=10.0 so check #3 passes (outside threshold is 10.0)
        result = _check(
            _decision(confidence=10.0),
            _portfolio(session={"name": "outside", "is_active": False}),
            tmp_path, monkeypatch,
        )
        assert result["approved"] is False
        assert result["blocked_by"] == "kill_zone_gate"

    def test_asia_session_blocks(self, tmp_path, monkeypatch):
        result = _check(
            _decision(confidence=10.0),
            _portfolio(session={"name": "asia", "is_active": False}),
            tmp_path, monkeypatch,
        )
        assert result["approved"] is False
        assert result["blocked_by"] == "kill_zone_gate"

    # ── check 5: daily loss limit ─────────────────────────────────────────
    def test_daily_loss_limit_blocks(self, tmp_path, monkeypatch):
        # 3.1% loss > 3% limit
        result = _check(
            _decision(),
            _portfolio(daily_pnl=-310.0, equity=10000.0),
            tmp_path, monkeypatch,
        )
        assert result["approved"] is False
        assert result["blocked_by"] == "daily_loss_limit"

    def test_daily_loss_limit_creates_lock_file(self, tmp_path, monkeypatch):
        _check(
            _decision(),
            _portfolio(daily_pnl=-310.0, equity=10000.0),
            tmp_path, monkeypatch,
        )
        assert (tmp_path / "kill_switch.lock").exists()

    # ── check 6: max trades per session ───────────────────────────────────
    def test_max_trades_per_session_blocks(self, tmp_path, monkeypatch):
        result = _check(
            _decision(),
            _portfolio(trades_this_session=10),
            tmp_path, monkeypatch,
        )
        assert result["approved"] is False
        assert result["blocked_by"] == "max_trades"

    # ── check 7: position limit ───────────────────────────────────────────
    def test_position_limit_blocks(self, tmp_path, monkeypatch):
        positions = [
            {"pair": "BTC/USDT"}, {"pair": "ETH/USDT"}, {"pair": "SOL/USDT"},
            {"pair": "BNB/USDT"}, {"pair": "LINK/USDT"},
        ]
        result = _check(
            _decision(),
            _portfolio(open_positions=positions),
            tmp_path, monkeypatch,
        )
        assert result["approved"] is False
        assert result["blocked_by"] == "position_limit"

    def test_four_open_positions_allowed(self, tmp_path, monkeypatch):
        positions = [{"pair": "BTC/USDT"}, {"pair": "ETH/USDT"}, {"pair": "SOL/USDT"}, {"pair": "BNB/USDT"}]
        result = _check(_decision(), _portfolio(open_positions=positions), tmp_path, monkeypatch)
        assert result["blocked_by"] != "position_limit"

    # ── check 8: correlation ──────────────────────────────────────────────
    def test_correlation_above_limit_blocks(self, tmp_path, monkeypatch):
        result = _check(_decision(), _portfolio(correlation=0.9), tmp_path, monkeypatch)
        assert result["approved"] is False
        assert result["blocked_by"] == "correlation"

    def test_correlation_at_limit_blocks(self, tmp_path, monkeypatch):
        result = _check(_decision(), _portfolio(correlation=0.86), tmp_path, monkeypatch)
        assert result["approved"] is False
        assert result["blocked_by"] == "correlation"

    def test_correlation_below_limit_passes(self, tmp_path, monkeypatch):
        result = _check(_decision(), _portfolio(correlation=0.84), tmp_path, monkeypatch)
        assert result["blocked_by"] != "correlation"

    # ── check 9: stale signal ─────────────────────────────────────────────
    def test_stale_signal_blocks(self, tmp_path, monkeypatch):
        result = _check(
            _decision(signal_timestamp=time.time() - 61),
            _portfolio(),
            tmp_path, monkeypatch,
        )
        assert result["approved"] is False
        assert result["blocked_by"] == "stale_signal"

    def test_fresh_signal_passes(self, tmp_path, monkeypatch):
        result = _check(
            _decision(signal_timestamp=time.time() - 10),
            _portfolio(),
            tmp_path, monkeypatch,
        )
        assert result["blocked_by"] != "stale_signal"

    # ── all checks pass ───────────────────────────────────────────────────
    def test_valid_trade_passes_all_checks(self, tmp_path, monkeypatch):
        result = _check(_decision(confidence=8.0), _portfolio(), tmp_path, monkeypatch)
        assert result["approved"] is True
        assert result["blocked_by"] == ""
        assert result["adjusted_size"] == 1.0
