import numpy as np
import pandas as pd

from app.risk.simulation import simulate_losses
from app.risk.var import value_at_risk


def test_var_is_empirical_quantile():
    losses = np.array([0, 1, 2, 3, 4])
    assert value_at_risk(losses, 0.8) == 3.2


def test_simulation_is_reproducible_with_fixed_seed():
    frame = pd.DataFrame(
        [
            {
                "asset_id": "A",
                "asset_type": "corporate_bond",
                "market_value": 1000.0,
                "eligible": True,
                "available_value": 920.0,
            },
            {
                "asset_id": "B",
                "asset_type": "government_bond",
                "market_value": 1000.0,
                "eligible": True,
                "available_value": 980.0,
            },
        ]
    )
    losses_1, meta_1 = simulate_losses(frame, 1000, 10, 7, [0.95, 0.99])
    losses_2, meta_2 = simulate_losses(frame, 1000, 10, 7, [0.95, 0.99])
    assert np.allclose(losses_1, losses_2)
    assert meta_1["var"] == meta_2["var"]


def test_simulation_returns_dashboard_and_report_fields():
    frame = pd.DataFrame(
        [
            {
                "asset_id": "A",
                "asset_type": "corporate_bond",
                "market_value": 1000.0,
                "eligible": True,
                "available_value": 920.0,
            }
        ]
    )
    _, metadata = simulate_losses(frame, 1000, 10, 11, [0.95, 0.99])
    assert len(metadata["loss_distribution"]) == 30
    assert metadata["risk_concentration"]["effective_exposure_count"] == 1.0
    assert "first_eigenvalue_share" in metadata["risk_concentration"]
