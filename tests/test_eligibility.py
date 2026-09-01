import pandas as pd

from app.eligibility.engine import evaluate_portfolio
from app.schemas.models import EligibilityRules


def test_rejection_reasons_are_precise():
    frame = pd.DataFrame(
        [
            {
                "asset_id": "BOND_204",
                "asset_type": "corporate_bond",
                "currency": "USD",
                "credit_rating": "BB",
                "market_value": 1000.0,
                "counterparty": "CP_A",
                "country": "US",
                "maturity_days": 10,
            }
        ]
    )
    result = evaluate_portfolio(frame, EligibilityRules(min_rating="BBB-", min_maturity_days=30))
    row = result.iloc[0]
    assert bool(row["eligible"]) is False
    assert row["available_value"] == 0
    assert row["reason_codes"] == ["RATING_BELOW_MINIMUM", "MATURITY_TOO_SHORT"]


def test_eligible_asset_gets_haircut_and_available_value():
    frame = pd.DataFrame(
        [
            {
                "asset_id": "CASH_1",
                "asset_type": "cash",
                "currency": "GBP",
                "credit_rating": "AAA",
                "market_value": 500.0,
                "counterparty": "CP_A",
                "country": "GB",
                "maturity_days": 60,
            }
        ]
    )
    result = evaluate_portfolio(frame, EligibilityRules())
    assert bool(result.iloc[0]["eligible"]) is True
    assert result.iloc[0]["available_value"] == 500.0
