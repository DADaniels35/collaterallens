from __future__ import annotations

import pandas as pd

from app.risk.simulation import simulate_losses

PRESET_SCENARIOS: dict[str, dict[str, float]] = {
    "rates_up_100bps": {
        "government_bond": -0.06,
        "covered_bond": -0.05,
        "corporate_bond": -0.04,
        "cash": 0.0,
        "equity": 0.0,
    },
    "equity_down_10pct": {
        "government_bond": 0.0,
        "covered_bond": 0.0,
        "corporate_bond": 0.0,
        "cash": 0.0,
        "equity": -0.10,
    },
    "credit_spread_up_100bps": {
        "government_bond": 0.0,
        "covered_bond": -0.03,
        "corporate_bond": -0.06,
        "cash": 0.0,
        "equity": -0.03,
    },
    "risk_off": {
        "government_bond": 0.02,
        "covered_bond": -0.03,
        "corporate_bond": -0.07,
        "cash": 0.0,
        "equity": -0.12,
    },
}


def scenario_shocks(scenario: str, custom_shocks: dict[str, float] | None = None) -> dict[str, float]:
    if scenario == "custom":
        return custom_shocks or {}
    if scenario not in PRESET_SCENARIOS:
        raise ValueError(f"Unknown stress scenario: {scenario}")
    return PRESET_SCENARIOS[scenario]


def apply_stress(evaluated_assets: pd.DataFrame, shocks: dict[str, float]) -> pd.DataFrame:
    stressed = evaluated_assets.copy()
    asset_shocks = stressed["asset_type"].map(shocks).fillna(0.0).astype(float)
    stress_factor = 1.0 + asset_shocks
    stressed["stress_shock"] = asset_shocks
    stressed["baseline_market_value"] = stressed["market_value"]
    stressed["baseline_available_value"] = stressed.get("available_value", 0.0)
    stressed["market_value"] = (stressed["market_value"].astype(float) * stress_factor).clip(lower=0.0)
    if "market_value_base" in stressed:
        stressed["baseline_market_value_base"] = stressed["market_value_base"]
        stressed["market_value_base"] = (stressed["market_value_base"].astype(float) * stress_factor).clip(lower=0.0)
    if "available_value" in stressed:
        stressed["available_value"] = (stressed["available_value"].astype(float) * stress_factor).clip(lower=0.0)
    return stressed


def run_stress_test(
    portfolio_id: int,
    evaluated_assets: pd.DataFrame,
    scenario: str,
    custom_shocks: dict[str, float] | None,
    simulations: int,
    horizon_days: int,
    seed: int,
    confidence_levels: list[float],
) -> dict[str, object]:
    shocks = scenario_shocks(scenario, custom_shocks)
    stressed = apply_stress(evaluated_assets, shocks)
    _, simulation = simulate_losses(stressed, simulations, horizon_days, seed, confidence_levels)

    baseline_available = float(evaluated_assets["available_value"].sum()) if "available_value" in evaluated_assets else 0.0
    stressed_available = float(stressed["available_value"].sum()) if "available_value" in stressed else 0.0
    market_column = "market_value_base" if "market_value_base" in stressed else "market_value"
    market_value_change = float(stressed[market_column].sum() - evaluated_assets[market_column].sum())
    available_change = float(stressed_available - baseline_available)
    immediate_scenario_loss = max(-market_value_change, 0.0)
    immediate_available_loss = max(-available_change, 0.0)

    return {
        "portfolio_id": portfolio_id,
        "scenario": scenario,
        "shocks": shocks,
        "market_value_change": market_value_change,
        "immediate_scenario_loss": immediate_scenario_loss,
        "available_collateral_change": available_change,
        "immediate_available_collateral_loss": immediate_available_loss,
        "baseline_available_collateral": baseline_available,
        "stressed_available_collateral": stressed_available,
        "simulation": {
            "portfolio_id": portfolio_id,
            "simulations": simulations,
            "seed": seed,
            **simulation,
        },
    }
