from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def generate(rows: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    asset_types = np.array(["government_bond", "corporate_bond", "equity", "cash", "covered_bond"])
    ratings = np.array(["AAA", "AA", "A", "BBB", "BBB-", "BB", "B"])
    currencies = np.array(["USD", "EUR", "GBP", "JPY", "CHF"])
    countries = np.array(["US", "GB", "DE", "FR", "JP", "CH", "RU"])
    counterparties = np.array(["CP_A", "CP_B", "CP_C", "CP_D", "CP_E", "CP_F"])
    return pd.DataFrame(
        {
            "asset_id": [f"ASSET_{i:04d}" for i in range(rows)],
            "asset_type": rng.choice(asset_types, rows, p=[0.28, 0.30, 0.12, 0.15, 0.15]),
            "currency": rng.choice(currencies, rows, p=[0.35, 0.25, 0.20, 0.10, 0.10]),
            "credit_rating": rng.choice(ratings, rows, p=[0.10, 0.16, 0.24, 0.20, 0.12, 0.12, 0.06]),
            "market_value": rng.lognormal(mean=12.0, sigma=0.65, size=rows).round(2),
            "counterparty": rng.choice(counterparties, rows),
            "country": rng.choice(countries, rows, p=[0.30, 0.18, 0.14, 0.12, 0.10, 0.10, 0.06]),
            "maturity_days": rng.integers(0, 6000, rows),
        }
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=250)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("data/sample_portfolio.csv"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    generate(args.rows, args.seed).to_csv(args.output, index=False)
    print(f"Wrote {args.output}")
