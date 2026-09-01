from __future__ import annotations

import json
import os
from pathlib import Path

import altair as alt
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components


API_URL = os.getenv("API_URL", "http://localhost:8000")
SAMPLE_PATH = Path("data/sample_portfolio.csv")
REQUIRED_COLUMNS = {
    "asset_id",
    "asset_type",
    "currency",
    "credit_rating",
    "market_value",
    "counterparty",
    "country",
    "maturity_days",
}


def money(value: float) -> str:
    return f"${value / 1_000_000:,.2f}m" if value >= 1_000_000 else f"${value:,.0f}"


def percent(value: float) -> str:
    return f"{value:.1%}"


def load_csv_safely(source) -> pd.DataFrame | None:
    try:
        return pd.read_csv(source)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError, ValueError) as exc:
        st.error(f"Could not read portfolio CSV: {exc}")
        return None


def validate_preview_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        st.error("Portfolio CSV is empty.")
        st.stop()

    missing_columns = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing_columns:
        st.error(f"Portfolio CSV is missing required columns: {', '.join(missing_columns)}")
        st.stop()

    validated = frame.copy()
    for column in ["market_value", "maturity_days"]:
        validated[column] = pd.to_numeric(validated[column], errors="coerce")

    invalid_market_values = validated["market_value"].isna() | (validated["market_value"] <= 0)
    if invalid_market_values.any():
        st.error("Portfolio CSV contains invalid market_value entries. Values must be numeric and greater than zero.")
        st.stop()

    invalid_maturities = validated["maturity_days"].isna() | (validated["maturity_days"] < 0)
    if invalid_maturities.any():
        st.error("Portfolio CSV contains invalid maturity_days entries. Values must be numeric and non-negative.")
        st.stop()

    validated["currency"] = validated["currency"].astype(str).str.strip().str.upper()
    return validated


def api_post(path: str, **kwargs) -> requests.Response:
    response = requests.post(f"{API_URL}{path}", timeout=90, **kwargs)
    response.raise_for_status()
    return response


def api_get(path: str) -> requests.Response:
    response = requests.get(f"{API_URL}{path}", timeout=30)
    response.raise_for_status()
    return response


default_rules = {
    "allowed_asset_types": ["government_bond", "corporate_bond", "cash", "covered_bond"],
    "allowed_currencies": ["USD", "EUR", "GBP"],
    "min_rating": "BBB-",
    "min_maturity_days": 30,
    "max_maturity_days": 3650,
    "excluded_countries": ["RU"],
}

st.set_page_config(page_title="CollateralLens", layout="wide")
st.markdown(
    """
    <style>
      .stApp { background: #f7f9fc; color: #17202a; }
      .block-container { padding-top: 4.25rem; max-width: 1280px; }
      [data-testid="stMetricValue"] { font-size: 1.55rem; }
      [data-testid="stMetricLabel"] { color: #52606d; }
      div[data-testid="stDataFrame"] { border: 1px solid #d9e2ec; border-radius: 8px; }
      .lens-header {
        border-bottom: 1px solid #d9e2ec;
        background: #ffffff;
        border-radius: 8px;
        padding: 1.25rem 1.4rem 1.35rem;
        margin-bottom: 1.2rem;
        overflow: visible;
      }
      .lens-kicker {
        color: #52606d;
        font-size: 0.9rem;
        line-height: 1.35;
        text-transform: uppercase;
        letter-spacing: .08em;
      }
      .lens-title {
        color: #102a43;
        font-size: 2.4rem;
        line-height: 1.15;
        font-weight: 700;
        margin: .35rem 0 .35rem;
      }
      .lens-subtitle {
        color: #334e68;
        font-size: 1rem;
        line-height: 1.6;
        max-width: 900px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="lens-header">
      <div class="lens-kicker">Collateral eligibility and portfolio risk</div>
      <div class="lens-title">CollateralLens</div>
      <div class="lens-subtitle">
        Upload a synthetic collateral portfolio, apply explainable eligibility rules, calculate available collateral,
        and run reproducible correlated Monte Carlo tail-risk analytics.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Portfolio")
    use_sample = st.toggle("Use bundled sample portfolio", value=True)
    upload = st.file_uploader("Upload CSV", type=["csv"], disabled=use_sample)

    st.header("Eligibility Rules")
    rules_text = st.text_area("Rules JSON", json.dumps(default_rules, indent=2), height=260)

    st.header("Simulation")
    simulations = st.slider("Simulation count", 1_000, 50_000, 10_000, step=1_000)
    horizon_days = st.slider("Horizon days", 1, 60, 10)
    seed = st.number_input("Random seed", value=42, min_value=0)
    scenario = st.selectbox(
        "Stress scenario",
        ["rates_up_100bps", "credit_spread_up_100bps", "equity_down_10pct", "risk_off"],
    )

if use_sample and SAMPLE_PATH.exists():
    frame = load_csv_safely(SAMPLE_PATH)
    source_name = SAMPLE_PATH.name
elif upload:
    frame = load_csv_safely(upload)
    source_name = upload.name
else:
    frame = None
    source_name = ""

if frame is None:
    st.info("Upload a portfolio CSV or use the bundled sample portfolio.")
    st.stop()

frame = validate_preview_frame(frame)

try:
    parsed_rules = json.loads(rules_text)
except json.JSONDecodeError as exc:
    st.error(f"Invalid rules JSON: {exc}")
    st.stop()

top = st.columns([2, 1, 1, 1])
top[0].subheader(source_name)
top[1].metric("Rows", f"{len(frame):,}")
top[2].metric("Currencies", frame["currency"].nunique())
top[3].metric("Asset types", frame["asset_type"].nunique())

preview_tab, rule_tab = st.tabs(["Portfolio Preview", "Rules"])
with preview_tab:
    st.dataframe(frame.head(50), use_container_width=True, hide_index=True)
    st.markdown("#### Native market value by currency")
    currency_breakdown = (
        frame.groupby("currency", as_index=False)["market_value"]
        .sum()
        .sort_values("market_value", ascending=False)
    )
    st.dataframe(currency_breakdown, use_container_width=True, hide_index=True)
with rule_tab:
    st.json(parsed_rules)

if st.button("Evaluate and simulate", type="primary", use_container_width=True):
    try:
        with st.status("Running CollateralLens pipeline", expanded=True) as status:
            st.write("Uploading portfolio")
            files = {"file": (source_name, frame.to_csv(index=False), "text/csv")}
            created = api_post("/portfolios", files=files, data={"name": source_name}).json()
            portfolio_id = created["portfolio_id"]

            st.write("Applying eligibility rules")
            api_post(f"/portfolios/{portfolio_id}/evaluate", data={"rules_json": rules_text})

            st.write("Running correlated Monte Carlo simulation")
            simulation = api_post(
                f"/portfolios/{portfolio_id}/simulate",
                json={
                    "simulations": simulations,
                    "seed": int(seed),
                    "horizon_days": horizon_days,
                    "confidence_levels": [0.95, 0.99],
                },
            ).json()

            st.write("Running stress scenario")
            stress = api_post(
                f"/portfolios/{portfolio_id}/stress",
                json={
                    "scenario": scenario,
                    "simulations": simulations,
                    "seed": int(seed),
                    "horizon_days": horizon_days,
                    "confidence_levels": [0.95, 0.99],
                },
            ).json()

            st.write("Building report")
            summary = api_get(f"/portfolios/{portfolio_id}/summary").json()
            assets = pd.DataFrame(api_get(f"/portfolios/{portfolio_id}/assets").json())
            report = api_get(f"/portfolios/{portfolio_id}/report").text
            status.update(label="Pipeline complete", state="complete")

        st.session_state["result"] = {
            "portfolio_id": portfolio_id,
            "summary": summary,
            "assets": assets,
            "simulation": simulation,
            "stress": stress,
            "report": report,
        }
    except (requests.RequestException, json.JSONDecodeError, KeyError) as exc:
        st.error(f"Pipeline failed: {exc}")

result = st.session_state.get("result")
if not result:
    st.stop()

summary = result["summary"]
assets = result["assets"]
simulation = result["simulation"]
stress = result["stress"]

st.divider()
st.subheader("Executive Summary")
cols = st.columns(5)
cols[0].metric("Eligible assets", f'{summary["eligible_count"]:,} / {summary["asset_count"]:,}')
cols[1].metric("Eligibility rate", percent(summary["eligibility_rate"]))
cols[2].metric("Available collateral", money(summary["available_collateral_value"]))
cols[3].metric("99% VaR", money(simulation["var"]["0.99"]))
cols[4].metric("99% ES", money(simulation["expected_shortfall"]["0.99"]))

risk_tab, stress_tab, eligibility_tab, concentration_tab, report_tab = st.tabs(
    ["Risk", "Stress", "Eligibility", "Concentration", "Report"]
)

with risk_tab:
    left, right = st.columns([1, 1])
    with left:
        st.markdown("#### Loss Distribution")
        hist = pd.DataFrame(simulation["loss_distribution"])
        hist["loss_midpoint"] = (hist["bin_start"] + hist["bin_end"]) / 2
        chart = (
            alt.Chart(hist)
            .mark_bar(color="#2f80ed")
            .encode(
                x=alt.X("loss_midpoint:Q", title="Simulated loss"),
                y=alt.Y("count:Q", title="Frequency"),
                tooltip=[
                    alt.Tooltip("bin_start:Q", title="Bin start", format=",.0f"),
                    alt.Tooltip("bin_end:Q", title="Bin end", format=",.0f"),
                    alt.Tooltip("count:Q", title="Frequency", format=",.0f"),
                ],
            )
        )
        st.altair_chart(chart, use_container_width=True)
    with right:
        st.markdown("#### Convergence")
        convergence = pd.DataFrame(simulation["convergence"])
        convergence_long = convergence.melt(
            id_vars="simulations",
            value_vars=["var", "ci_width"],
            var_name="metric",
            value_name="value",
        )
        conv_chart = (
            alt.Chart(convergence_long)
            .mark_line(point=True)
            .encode(
                x=alt.X("simulations:Q", title="Simulation count"),
                y=alt.Y("value:Q", title="Estimate"),
                color=alt.Color("metric:N", title="Metric"),
                tooltip=[
                    alt.Tooltip("simulations:Q", title="Simulations", format=",.0f"),
                    alt.Tooltip("metric:N", title="Metric"),
                    alt.Tooltip("value:Q", title="Value", format=",.0f"),
                ],
            )
        )
        st.altair_chart(conv_chart, use_container_width=True)

    concentration = simulation["risk_concentration"]
    risk_cols = st.columns(4)
    risk_cols[0].metric("Mean loss", money(simulation["mean_loss"]))
    risk_cols[1].metric("95% CI width", money(simulation["ci_95"]["width"]))
    risk_cols[2].metric("Effective exposures", f'{concentration["effective_exposure_count"]:.1f}')
    risk_cols[3].metric("Dominant risk mode", percent(concentration["first_eigenvalue_share"]))

with stress_tab:
    st.markdown("#### Scenario Comparison")
    stress_sim = stress["simulation"]
    s_cols = st.columns(5)
    s_cols[0].metric("Scenario", stress["scenario"])
    s_cols[1].metric("Immediate scenario loss", money(stress["immediate_scenario_loss"]))
    s_cols[2].metric("Stressed collateral", money(stress["stressed_available_collateral"]))
    s_cols[3].metric("Residual post-stress 99% VaR", money(stress_sim["var"]["0.99"]))
    s_cols[4].metric("Residual post-stress 99% ES", money(stress_sim["expected_shortfall"]["0.99"]))

    comparison = pd.DataFrame(
        [
            {
                "metric": "Available collateral after scenario",
                "baseline": summary["available_collateral_value"],
                "stressed": stress["stressed_available_collateral"],
            },
            {
                "metric": "Residual 99% VaR",
                "baseline": simulation["var"]["0.99"],
                "stressed": stress_sim["var"]["0.99"],
            },
            {
                "metric": "Residual 99% Expected Shortfall",
                "baseline": simulation["expected_shortfall"]["0.99"],
                "stressed": stress_sim["expected_shortfall"]["0.99"],
            },
        ]
    )
    comparison_long = comparison.melt(id_vars="metric", var_name="state", value_name="value")
    stress_chart = (
        alt.Chart(comparison_long)
        .mark_bar()
        .encode(
            x=alt.X("metric:N", title=None),
            y=alt.Y("value:Q", title="Value"),
            color=alt.Color("state:N", title="State"),
            xOffset="state:N",
            tooltip=[
                alt.Tooltip("metric:N", title="Metric"),
                alt.Tooltip("state:N", title="State"),
                alt.Tooltip("value:Q", title="Value", format=",.0f"),
            ],
        )
    )
    st.altair_chart(stress_chart, use_container_width=True)
    st.markdown("#### Applied shocks")
    st.dataframe(
        pd.DataFrame(
            [{"asset_type": asset_type, "shock": shock} for asset_type, shock in stress["shocks"].items()]
        ),
        use_container_width=True,
        hide_index=True,
    )

with eligibility_tab:
    rejected = assets[assets["eligible"] == False].copy()  # noqa: E712
    reason_counts = (
        rejected.explode("reason_codes")["reason_codes"].value_counts().rename_axis("reason_code").reset_index(name="count")
        if not rejected.empty
        else pd.DataFrame(columns=["reason_code", "count"])
    )
    left, right = st.columns([1, 2])
    with left:
        st.markdown("#### Rejection Reasons")
        st.dataframe(reason_counts, use_container_width=True, hide_index=True)
    with right:
        st.markdown("#### Asset-Level Results")
        columns = [
            "asset_id",
            "asset_type",
            "currency",
            "credit_rating",
            "eligible",
            "reason_codes",
            "haircut",
            "available_value",
        ]
        st.dataframe(assets[columns], use_container_width=True, hide_index=True)

with concentration_tab:
    c1, c2, c3 = st.columns(3)
    c1.markdown("#### Counterparty")
    c1.dataframe(pd.Series(summary["top_counterparty_concentration"], name="share").reset_index(), hide_index=True)
    c2.markdown("#### Country")
    c2.dataframe(pd.Series(summary["top_country_concentration"], name="share").reset_index(), hide_index=True)
    c3.markdown("#### Asset Type")
    c3.dataframe(pd.Series(summary["top_asset_type_concentration"], name="share").reset_index(), hide_index=True)

with report_tab:
    st.download_button(
        "Download HTML risk report",
        result["report"],
        file_name=f'collateral_lens_report_{result["portfolio_id"]}.html',
        mime="text/html",
        use_container_width=True,
    )
    components.html(result["report"], height=700, scrolling=True)
