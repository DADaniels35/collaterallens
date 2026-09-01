import pandas as pd

from app.risk.stress import apply_stress, run_stress_test, scenario_shocks


def test_preset_scenario_shocks_are_named_and_synthetic():
    shocks = scenario_shocks("credit_spread_up_100bps")
    assert shocks["corporate_bond"] < 0
    assert shocks["cash"] == 0.0


def test_apply_stress_changes_market_and_available_value():
    frame = pd.DataFrame(
        [
            {
                "asset_id": "A1",
                "asset_type": "corporate_bond",
                "market_value": 1000.0,
                "available_value": 900.0,
                "eligible": True,
            }
        ]
    )
    stressed = apply_stress(frame, {"corporate_bond": -0.10})
    assert stressed.iloc[0]["market_value"] == 900.0
    assert stressed.iloc[0]["available_value"] == 810.0
    assert stressed.iloc[0]["stress_shock"] == -0.10


def test_run_stress_test_returns_comparison_payload():
    frame = pd.DataFrame(
        [
            {
                "asset_id": "A1",
                "asset_type": "corporate_bond",
                "market_value": 1000.0,
                "available_value": 900.0,
                "eligible": True,
            }
        ]
    )
    result = run_stress_test(1, frame, "credit_spread_up_100bps", None, 500, 10, 42, [0.95, 0.99])
    assert result["available_collateral_change"] < 0
    assert result["immediate_scenario_loss"] > 0
    assert result["immediate_available_collateral_loss"] > 0
    assert result["simulation"]["simulations"] == 500
    assert "0.99" in result["simulation"]["var"]
