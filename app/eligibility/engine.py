from __future__ import annotations

import pandas as pd

from app.eligibility.reason_codes import (
    ASSET_TYPE_NOT_ALLOWED,
    COUNTRY_EXCLUDED,
    CURRENCY_NOT_ALLOWED,
    MATURITY_TOO_LONG,
    MATURITY_TOO_SHORT,
    RATING_BELOW_MINIMUM,
)
from app.eligibility.rules import rating_bucket, rating_notch
from app.schemas.models import Asset, AssetEvaluation, EligibilityRules


def evaluate_asset(asset: Asset, rules: EligibilityRules) -> AssetEvaluation:
    reasons: list[str] = []

    if asset.asset_type not in rules.allowed_asset_types:
        reasons.append(ASSET_TYPE_NOT_ALLOWED)
    if asset.currency not in rules.allowed_currencies:
        reasons.append(CURRENCY_NOT_ALLOWED)
    if rating_notch(asset.credit_rating) < rating_notch(rules.min_rating):
        reasons.append(RATING_BELOW_MINIMUM)
    if asset.maturity_days < rules.min_maturity_days:
        reasons.append(MATURITY_TOO_SHORT)
    if asset.maturity_days > rules.max_maturity_days:
        reasons.append(MATURITY_TOO_LONG)
    if asset.country in {country.upper() for country in rules.excluded_countries}:
        reasons.append(COUNTRY_EXCLUDED)

    eligible = not reasons
    asset_haircut = rules.haircut_by_asset_type.get(asset.asset_type, 0.25)
    rating_haircut = rules.haircut_by_rating.get(rating_bucket(asset.credit_rating), 0.35)
    haircut = min(asset_haircut + rating_haircut, 1.0)
    market_value_base = asset.market_value_base if asset.market_value_base is not None else asset.market_value
    available_value = market_value_base * (1.0 - haircut) if eligible else 0.0

    return AssetEvaluation(
        asset_id=asset.asset_id,
        eligible=eligible,
        reason_codes=reasons,
        haircut=round(haircut, 6),
        available_value=round(available_value, 2),
    )


def evaluate_portfolio(frame: pd.DataFrame, rules: EligibilityRules) -> pd.DataFrame:
    evaluations = [
        evaluate_asset(Asset.model_validate(row), rules).model_dump()
        for row in frame.to_dict(orient="records")
    ]
    return frame.merge(pd.DataFrame(evaluations), on="asset_id", how="left")
