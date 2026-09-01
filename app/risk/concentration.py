from __future__ import annotations

import numpy as np


def exposure_concentration(values: np.ndarray) -> dict[str, float]:
    total = float(values.sum())
    if total <= 0:
        return {"largest_exposure_share": 0.0, "effective_exposure_count": 0.0}
    weights = values / total
    herfindahl = float(np.sum(weights**2))
    return {
        "largest_exposure_share": float(weights.max()),
        "effective_exposure_count": float(1.0 / herfindahl) if herfindahl > 0 else 0.0,
    }


def covariance_eigen_summary(covariance: np.ndarray) -> dict[str, float]:
    if covariance.size == 0:
        return {"first_eigenvalue_share": 0.0, "condition_number": 0.0}
    eigenvalues = np.linalg.eigvalsh(covariance)
    eigenvalues = np.maximum(eigenvalues, 0)
    total = float(eigenvalues.sum())
    first_share = float(eigenvalues[-1] / total) if total > 0 else 0.0
    positive = eigenvalues[eigenvalues > 1e-12]
    condition = float(positive[-1] / positive[0]) if len(positive) > 1 else 1.0
    return {"first_eigenvalue_share": first_share, "condition_number": condition}
