from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.eligibility.rules import RATING_ORDER


AssetType = Literal["government_bond", "corporate_bond", "equity", "cash", "covered_bond"]


class Asset(BaseModel):
    asset_id: str = Field(min_length=1)
    asset_type: AssetType
    currency: str = Field(min_length=3, max_length=3)
    credit_rating: str = Field(min_length=1)
    market_value: float = Field(gt=0)
    base_currency: str | None = Field(default=None, min_length=3, max_length=3)
    fx_rate_to_base: float | None = Field(default=None, gt=0)
    market_value_base: float | None = Field(default=None, gt=0)
    counterparty: str = Field(min_length=1)
    country: str = Field(min_length=2)
    maturity_days: int = Field(ge=0)

    @field_validator("currency", "credit_rating", "country", "base_currency")
    @classmethod
    def uppercase(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return value.strip().upper()

    @field_validator("credit_rating")
    @classmethod
    def rating_is_known(cls, value: str) -> str:
        if value not in RATING_ORDER:
            raise ValueError(f"Unknown credit rating: {value}")
        return value


class EligibilityRules(BaseModel):
    allowed_asset_types: list[str] = Field(
        default_factory=lambda: ["government_bond", "corporate_bond", "cash", "covered_bond"]
    )
    allowed_currencies: list[str] = Field(default_factory=lambda: ["USD", "EUR", "GBP"])
    min_rating: str = "BBB-"
    min_maturity_days: int = 30
    max_maturity_days: int = 3650
    excluded_countries: list[str] = Field(default_factory=list)
    haircut_by_asset_type: dict[str, float] = Field(
        default_factory=lambda: {
            "cash": 0.0,
            "government_bond": 0.02,
            "covered_bond": 0.05,
            "corporate_bond": 0.08,
            "equity": 0.20,
        }
    )
    haircut_by_rating: dict[str, float] = Field(
        default_factory=lambda: {
            "AAA": 0.00,
            "AA": 0.01,
            "A": 0.02,
            "BBB": 0.05,
            "BB": 0.12,
            "B": 0.20,
            "CCC": 0.35,
        }
    )

    @field_validator("min_rating")
    @classmethod
    def min_rating_is_known(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in RATING_ORDER:
            raise ValueError(f"Unknown minimum credit rating: {value}")
        return normalized

    @field_validator("haircut_by_asset_type", "haircut_by_rating")
    @classmethod
    def haircuts_are_valid_percentages(cls, values: dict[str, float]) -> dict[str, float]:
        invalid = {key: value for key, value in values.items() if value < 0 or value > 1}
        if invalid:
            raise ValueError("Haircuts must be between 0 and 1")
        return values

    @model_validator(mode="after")
    def maturity_range_is_valid(self) -> "EligibilityRules":
        if self.min_maturity_days > self.max_maturity_days:
            raise ValueError("min_maturity_days cannot exceed max_maturity_days")
        return self


class AssetEvaluation(BaseModel):
    asset_id: str
    eligible: bool
    reason_codes: list[str]
    haircut: float
    available_value: float


class PortfolioSummary(BaseModel):
    portfolio_id: int
    asset_count: int
    eligible_count: int
    eligibility_rate: float
    total_market_value: float
    available_collateral_value: float
    available_value_ratio: float
    top_counterparty_concentration: dict[str, float]
    top_country_concentration: dict[str, float]
    top_asset_type_concentration: dict[str, float]


class SimulationRequest(BaseModel):
    simulations: int = Field(default=10_000, ge=100, le=250_000)
    horizon_days: int = Field(default=10, ge=1, le=365)
    seed: int = 42
    confidence_levels: list[float] = Field(default_factory=lambda: [0.95, 0.99])

    @field_validator("confidence_levels")
    @classmethod
    def confidence_levels_are_probabilities(cls, values: list[float]) -> list[float]:
        if not values:
            raise ValueError("At least one confidence level is required")
        invalid = [value for value in values if value <= 0 or value >= 1]
        if invalid:
            raise ValueError("Confidence levels must be between 0 and 1")
        return values


class SimulationResult(BaseModel):
    portfolio_id: int
    simulations: int
    seed: int
    mean_loss: float
    var: dict[str, float]
    expected_shortfall: dict[str, float]
    convergence: list[dict[str, float]]
    ci_95: dict[str, float]
    loss_distribution: list[dict[str, float]]
    risk_concentration: dict[str, float]


class StressRequest(SimulationRequest):
    scenario: str = "rates_up_100bps"
    custom_shocks: dict[str, float] = Field(default_factory=dict)

    @field_validator("custom_shocks")
    @classmethod
    def custom_shocks_are_bounded(cls, values: dict[str, float]) -> dict[str, float]:
        invalid = {key: value for key, value in values.items() if value < -1 or value > 1}
        if invalid:
            raise ValueError("Custom stress shocks must be between -1 and 1")
        return values


class StressResult(BaseModel):
    portfolio_id: int
    scenario: str
    shocks: dict[str, float]
    market_value_change: float
    immediate_scenario_loss: float
    available_collateral_change: float
    immediate_available_collateral_loss: float
    baseline_available_collateral: float
    stressed_available_collateral: float
    simulation: SimulationResult
