from __future__ import annotations

import numpy as np


def expected_shortfall(losses: np.ndarray, confidence: float) -> float:
    threshold = np.quantile(losses, confidence)
    tail = losses[losses >= threshold]
    return float(tail.mean()) if len(tail) else float(threshold)
