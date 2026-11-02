from __future__ import annotations

import pandas as pd

BASE_CURRENCY = "USD"
FX_RATES_TO_USD = {
    "USD": 1.00,
    "EUR": 1.09,
    "GBP": 1.27,
    "JPY": 0.0068,
    "CHF": 1.12,
}


def fx_rate_to_base(currency: str) -> float:
    try:
        return FX_RATES_TO_USD[currency.upper()]
    except KeyError as exc:
        raise ValueError(f"No synthetic FX rate configured for currency: {currency}") from exc


def add_base_values(frame: pd.DataFrame) -> pd.DataFrame:
    valued = frame.copy()
    valued["base_currency"] = BASE_CURRENCY
    valued["fx_rate_to_base"] = valued["currency"].map(lambda currency: fx_rate_to_base(str(currency)))
    valued["market_value_base"] = valued["market_value"].astype(float) * valued["fx_rate_to_base"]
    return valued
