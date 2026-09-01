# CollateralLens

CollateralLens is a synthetic collateral eligibility and portfolio risk platform. It is deliberately scoped for a strong portfolio project: deterministic eligibility, explainable rejection reasons, configurable haircuts, concentration analytics, correlated Monte Carlo simulation, VaR, Expected Shortfall, convergence output, and a downloadable HTML report.

This project uses synthetic data and synthetic rules only. It does not include confidential institutional information, production eligibility rules, live market data, authentication, or regulatory capital calculations.

## Screenshots

### Streamlit Dashboard

![CollateralLens dashboard](docs/screenshots/dashboard.png)

### Downloadable HTML Risk Report

![CollateralLens HTML risk report](docs/screenshots/report.png)

## Demo architecture vs production architecture

CollateralLens is intentionally built as a portfolio/demo system, not production risk infrastructure. SQLite stores uploaded assets, evaluated portfolios, the rule set used for evaluation, simulations, and stress results as JSON payloads so the project is easy to run and inspect locally. That is useful for a demo, but a production platform would normalize those entities into relational tables, add migrations, audit history, access control, model governance, lineage, observability, and concurrency controls.

The API enforces a simple lifecycle: upload a portfolio, evaluate it with default or custom rules, then run simulation or stress analytics. Simulation and stress endpoints return `409 Conflict` if evaluation has not happened yet, so risk analytics never silently fall back to default rules after a custom-rule workflow.

## Why this project is credible

CollateralLens combines domain understanding, backend engineering, data-product design, and quantitative methods in a small runnable system. The important design choice is restraint: the project focuses on collateral eligibility and portfolio risk rather than adding unrelated machine learning or enterprise infrastructure.

The mathematical core is intentionally explainable:

- deterministic rules produce auditable rejection reason codes;
- native market values are normalized to a USD base currency using disclosed synthetic FX assumptions;
- synthetic haircuts convert eligible market value into available collateral;
- concentration tables identify counterparty, country, and asset-type exposure;
- correlated Monte Carlo simulation uses a covariance matrix built from volatility and correlation assumptions;
- VaR and Expected Shortfall summarize loss tails;
- convergence checkpoints and confidence intervals show simulation stability;
- eigenvalue concentration describes the dominant covariance risk mode.

## Business context

Collateral is used to reduce counterparty credit exposure. Not every asset is acceptable as collateral: eligibility depends on characteristics such as asset type, currency, maturity, country, and credit quality. Even when an asset is eligible, a haircut is applied so the recognized collateral value is lower than market value.

For a trading desk, risk team, or collateral operations team, the important questions are practical:

- Which assets are usable?
- Why did rejected assets fail?
- How much usable collateral remains after haircuts?
- Is the portfolio concentrated in one counterparty, country, or asset type?
- What could the collateral pool lose under correlated market moves?
- How stable are the simulated risk estimates?

CollateralLens answers those questions with synthetic data and synthetic assumptions, making it safe to show publicly while still reflecting the structure of a real risk analytics workflow.

## Stress testing

CollateralLens includes synthetic stress scenarios for risk-analysis workflows:

- `rates_up_100bps`
- `credit_spread_up_100bps`
- `equity_down_10pct`
- `risk_off`

Each scenario applies deterministic asset-type shocks, recalculates stressed market value and available collateral, then reruns the Monte Carlo engine on the stressed portfolio. The dashboard separates the immediate deterministic scenario loss from residual post-stress VaR and Expected Shortfall, so an adverse shock is not misread as an improvement simply because the remaining stressed portfolio is smaller.

## Run locally

```bash
cd collateral-lens
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python data/generate_synthetic_portfolio.py --rows 250 --output data/sample_portfolio.csv
uvicorn app.main:app --reload
```

In a second terminal:

```bash
cd collateral-lens
source .venv/bin/activate
streamlit run dashboard/streamlit_app.py
```

Open:

- FastAPI docs: http://localhost:8000/docs
- Streamlit dashboard: http://localhost:8501

You can also use the Makefile:

```bash
make install
make sample
make test
make api
make dashboard
```

## Docker

```bash
docker compose up --build
```

## Demo flow

1. Open the Streamlit dashboard.
2. Keep the bundled sample portfolio selected, or upload your own synthetic CSV.
3. Review the rule JSON in the sidebar.
4. Click "Evaluate and simulate".
5. Walk through the executive metrics, rejection reason table, loss distribution, convergence chart, stress tab, and concentration view.
6. Download the HTML risk report from the Report tab.

## API

- `POST /portfolios`
- `POST /portfolios/{id}/evaluate`
- `POST /portfolios/{id}/simulate`
- `POST /portfolios/{id}/stress`
- `GET /portfolios/{id}/summary`
- `GET /portfolios/{id}/assets`
- `GET /portfolios/{id}/report`

## CSV schema

```text
asset_id,asset_type,currency,credit_rating,market_value,counterparty,country,maturity_days
```

Supported synthetic asset types are `government_bond`, `corporate_bond`, `equity`, `cash`, and `covered_bond`.

## Mathematical approach

Eligibility is deterministic. Each asset is checked against allowed asset types, currencies, rating floor, maturity limits, and excluded countries. Every failed rule emits a reason code, for example:

```json
{
  "asset_id": "BOND_204",
  "eligible": false,
  "reason_codes": ["RATING_BELOW_MINIMUM", "MATURITY_TOO_SHORT"]
}
```

Haircuts are additive synthetic assumptions by asset type and rating bucket. Available collateral value is:

```text
market_value_base * (1 - haircut)
```

`market_value_base` is the native market value converted into the project base currency, USD, using fixed synthetic FX rates. These rates are demonstrator assumptions, not live market data.

The risk engine simulates eligible collateral returns from a multivariate normal distribution. Synthetic annual volatilities are converted to horizon volatilities, then combined with a correlation matrix to create a covariance matrix. The portfolio loss is the negative simulated P&L, floored at zero.

VaR is the empirical loss quantile at the chosen confidence level. Expected Shortfall is the mean of losses beyond VaR. Confidence intervals use the simulated standard error, and the convergence table reports estimates after increasing simulation counts.

## Tests

```bash
make test
```
