from __future__ import annotations

import numpy as np
import pandas as pd

from app.risk.concentration import covariance_eigen_summary, exposure_concentration
from app.risk.convergence import convergence_path, mean_confidence_interval
from app.risk.expected_shortfall import expected_shortfall
from app.risk.var import value_at_risk

ASSET_VOL = {
    "cash": 0.002,
    "government_bond": 0.045,
    "covered_bond": 0.055,
    "corporate_bond": 0.085,
    "equity": 0.18,
}


def loss_distribution(losses: np.ndarray, bins: int = 30) -> list[dict[str, float]]:
    counts, edges = np.histogram(losses, bins=bins)
    return [
        {
            "bin_start": float(edges[index]),
            "bin_end": float(edges[index + 1]),
            "count": float(count),
        }
        for index, count in enumerate(counts)
    ]


def _correlation_matrix(asset_types: list[str]) -> np.ndarray:
    n = len(asset_types)
    corr = np.full((n, n), 0.25)
    np.fill_diagonal(corr, 1.0)
    for i, left in enumerate(asset_types):
        for j, right in enumerate(asset_types):
            if left == right and i != j:
                corr[i, j] = 0.65
            elif "cash" in (left, right) and left != right:
                corr[i, j] = 0.05
            elif {left, right} == {"government_bond", "corporate_bond"}:
                corr[i, j] = 0.45
    return corr


def simulate_losses(
    evaluated_assets: pd.DataFrame,
    simulations: int,
    horizon_days: int,
    seed: int,
    confidence_levels: list[float],
) -> tuple[np.ndarray, dict[str, object]]:
    eligible = evaluated_assets[evaluated_assets["eligible"].eq(True)].copy()
    risk_concentration = {"largest_exposure_share": 0.0, "effective_exposure_count": 0.0}
    if eligible.empty:
        losses = np.zeros(simulations)
    else:
        rng = np.random.default_rng(seed)
        values = eligible["available_value"].to_numpy(dtype=float)
        asset_types = eligible["asset_type"].astype(str).tolist()
        annual_vol = np.array([ASSET_VOL.get(asset_type, 0.10) for asset_type in asset_types])
        horizon_vol = annual_vol * np.sqrt(horizon_days / 252)
        cov = np.outer(horizon_vol, horizon_vol) * _correlation_matrix(asset_types)
        returns = rng.multivariate_normal(mean=np.zeros(len(values)), cov=cov, size=simulations)
        pnl = returns @ values
        losses = np.maximum(-pnl, 0.0)
        risk_concentration = {**exposure_concentration(values), **covariance_eigen_summary(cov)}

    var = {str(level): value_at_risk(losses, level) for level in confidence_levels}
    es = {str(level): expected_shortfall(losses, level) for level in confidence_levels}
    metadata: dict[str, object] = {
        "mean_loss": float(losses.mean()),
        "var": var,
        "expected_shortfall": es,
        "convergence": convergence_path(losses, max(confidence_levels)),
        "ci_95": mean_confidence_interval(losses),
        "loss_distribution": loss_distribution(losses),
        "risk_concentration": risk_concentration,
    }
    return losses, metadata
