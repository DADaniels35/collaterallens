from __future__ import annotations

import numpy as np


def value_at_risk(losses: np.ndarray, confidence: float) -> float:
    return float(np.quantile(losses, confidence))
