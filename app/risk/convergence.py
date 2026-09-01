from __future__ import annotations

import numpy as np
from scipy import stats

from app.risk.var import value_at_risk


def mean_confidence_interval(values: np.ndarray, confidence: float = 0.95) -> dict[str, float]:
    mean = float(np.mean(values))
    if len(values) < 2:
        return {"lower": mean, "upper": mean, "width": 0.0}
    sem = stats.sem(values)
    margin = float(sem * stats.t.ppf((1 + confidence) / 2, len(values) - 1))
    return {"lower": mean - margin, "upper": mean + margin, "width": 2 * margin}


def convergence_path(losses: np.ndarray, confidence: float = 0.99) -> list[dict[str, float]]:
    checkpoints = [100, 250, 500, 1_000, 2_500, 5_000, 10_000, 25_000, 50_000]
    rows = []
    for count in checkpoints:
        if count <= len(losses):
            sample = losses[:count]
            ci = mean_confidence_interval(sample)
            rows.append(
                {
                    "simulations": float(count),
                    "mean_loss": float(sample.mean()),
                    "var": value_at_risk(sample, confidence),
                    "ci_width": ci["width"],
                }
            )
    return rows
