"""Tests for position_sizer — confidence tiers, caps, minimums, and ATR-based SL/TP."""

import pytest


def _decision(**overrides) -> dict:
    d = {"action": "BUY", "confidence": 8.0}
    d.update(overrides)
    return d


class TestConfidenceTiers:
    def test_high_tier_for_confidence_8_5(self):
        from risk.position_sizer import calculate_size
        result = calculate_size(_decision(confidence=8.5), 10000.0, 100.0, 1.0)
        assert result["confidence_tier"] == "HIGH"
        assert result["quantity"] > 0

    def test_high_tier_for_confidence_9_0(self):
        from risk.position_sizer import calculate_size
        result = calculate_size(_decision(confidence=9.0), 10000.0, 100.0, 1.0)
        assert result["confidence_tier"] == "HIGH"

    def test_standard_tier_for_confidence_7_5(self):
        from risk.position_sizer import calculate_size
        result = calculate_size(_decision(confidence=7.5), 10000.0, 100.0, 1.0)
        assert result["confidence_tier"] == "STANDARD"
        assert result["quantity"] > 0

    def test_standard_tier_for_confidence_8_0(self):
        from risk.position_sizer import calculate_size
        result = calculate_size(_decision(confidence=8.0), 10000.0, 100.0, 1.0)
        assert result["confidence_tier"] == "STANDARD"

    def test_reduced_tier_for_confidence_7_0(self):
        from risk.position_sizer import calculate_size
        result = calculate_size(_decision(confidence=7.0), 10000.0, 100.0, 1.0)
        assert result["confidence_tier"] == "REDUCED"
        assert result["quantity"] > 0

    def test_hold_for_confidence_below_7(self):
        from risk.position_sizer import calculate_size
        result = calculate_size(_decision(confidence=6.9), 10000.0, 100.0, 1.0)
        assert result["quantity"] == 0.0
        assert result["confidence_tier"] == "HOLD"

    def test_hold_for_confidence_zero(self):
        from risk.position_sizer import calculate_size
        result = calculate_size(_decision(confidence=0.0), 10000.0, 100.0, 1.0)
        assert result["quantity"] == 0.0
        assert result["confidence_tier"] == "HOLD"


class TestATRCalculation:
    def test_sl_tp_buy_direction(self):
        from risk.position_sizer import calculate_size
        # SL = 100 - 1.5×2 = 97.0, TP = 100 + 3.0×2 = 106.0
        result = calculate_size(_decision(action="BUY"), 10000.0, 100.0, 2.0)
        assert abs(result["sl_price"] - 97.0) < 0.01
        assert abs(result["tp_price"] - 106.0) < 0.01

    def test_sl_tp_sell_direction(self):
        from risk.position_sizer import calculate_size
        # SL = 100 + 1.5×2 = 103.0, TP = 100 - 3.0×2 = 94.0
        result = calculate_size(_decision(action="SELL"), 10000.0, 100.0, 2.0)
        assert abs(result["sl_price"] - 103.0) < 0.01
        assert abs(result["tp_price"] - 94.0) < 0.01

    def test_risk_reward_ratio_is_2_to_1(self):
        from risk.position_sizer import calculate_size
        result = calculate_size(_decision(action="BUY"), 10000.0, 100.0, 3.0)
        tp_dist = abs(result["tp_price"] - 100.0)
        sl_dist = abs(result["sl_price"] - 100.0)
        assert abs(tp_dist / sl_dist - 2.0) < 0.001


class TestPositionCaps:
    def test_high_tier_max_position_is_7_5_pct(self):
        from risk.position_sizer import calculate_size
        # Tiny ATR → raw_qty would be enormous without the cap
        result = calculate_size(_decision(confidence=9.0), 10000.0, 1.0, 0.001)
        # HIGH max = 7.5% of 10000 = $750
        assert result["position_value"] <= 750.01

    def test_standard_tier_max_position_is_5_pct(self):
        from risk.position_sizer import calculate_size
        result = calculate_size(_decision(confidence=8.0), 10000.0, 1.0, 0.001)
        assert result["position_value"] <= 500.01

    def test_reduced_tier_max_position_is_2_5_pct(self):
        from risk.position_sizer import calculate_size
        result = calculate_size(_decision(confidence=7.0), 10000.0, 1.0, 0.001)
        assert result["position_value"] <= 250.01


class TestMinimumPosition:
    def test_sub_minimum_returns_zero_quantity(self):
        from risk.position_sizer import calculate_size
        # REDUCED tier: max_value = 100 × 0.025 = $2.50 < $10 minimum
        result = calculate_size(_decision(confidence=7.0), 100.0, 100.0, 1.0)
        assert result["quantity"] == 0.0
        assert result["confidence_tier"] == "HOLD"

    def test_position_above_minimum_is_accepted(self):
        from risk.position_sizer import calculate_size
        result = calculate_size(_decision(confidence=8.0), 10000.0, 100.0, 1.0)
        assert result["quantity"] > 0
        assert result["position_value"] >= 10.0


class TestRiskAmount:
    def test_standard_tier_risk_amount(self):
        from risk.position_sizer import calculate_size
        # STANDARD: risk = 10000 × 0.01 × 1.0 = $100
        result = calculate_size(_decision(confidence=8.0), 10000.0, 100.0, 1.0)
        assert abs(result["risk_amount"] - 100.0) < 0.01

    def test_high_tier_risk_amount_uses_multiplier(self):
        from risk.position_sizer import calculate_size
        # HIGH: risk = 10000 × 0.01 × 1.5 = $150
        result = calculate_size(_decision(confidence=9.0), 10000.0, 100.0, 1.0)
        assert abs(result["risk_amount"] - 150.0) < 0.01

    def test_reduced_tier_risk_amount_uses_multiplier(self):
        from risk.position_sizer import calculate_size
        # REDUCED: risk = 10000 × 0.01 × 0.5 = $50
        result = calculate_size(_decision(confidence=7.0), 10000.0, 100.0, 1.0)
        assert abs(result["risk_amount"] - 50.0) < 0.01


class TestQuantityPrecision:
    def test_quantity_floored_to_8_decimals(self):
        from risk.position_sizer import calculate_size
        result = calculate_size(_decision(confidence=8.0), 10000.0, 47123.45, 500.0)
        qty = result["quantity"]
        # Verify floor (not round): recomputing floor should equal the result
        import math
        assert abs(qty - math.floor(qty * 1e8) / 1e8) < 1e-12

    def test_hold_action_returns_zero_qty(self):
        from risk.position_sizer import calculate_size
        result = calculate_size(_decision(action="HOLD"), 10000.0, 100.0, 1.0)
        assert result["quantity"] == 0.0

    def test_zero_portfolio_returns_zero_qty(self):
        from risk.position_sizer import calculate_size
        result = calculate_size(_decision(), 0.0, 100.0, 1.0)
        assert result["quantity"] == 0.0

    def test_zero_atr_returns_zero_qty(self):
        from risk.position_sizer import calculate_size
        result = calculate_size(_decision(), 10000.0, 100.0, 0.0)
        assert result["quantity"] == 0.0
