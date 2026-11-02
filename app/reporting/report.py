from __future__ import annotations

import html
from typing import Any

import pandas as pd


def value_column(frame: pd.DataFrame) -> str:
    return "market_value_base" if "market_value_base" in frame else "market_value"


def concentration_table(frame: pd.DataFrame, column: str) -> dict[str, float]:
    exposure_column = value_column(frame)
    total = frame[exposure_column].sum()
    if total == 0:
        return {}
    shares = (frame.groupby(column)[exposure_column].sum() / total).sort_values(ascending=False)
    return {str(k): round(float(v), 4) for k, v in shares.head(5).items()}


def summary_payload(portfolio_id: int, frame: pd.DataFrame) -> dict[str, Any]:
    available = frame["available_value"].sum() if "available_value" in frame else 0.0
    eligible = int(frame["eligible"].sum()) if "eligible" in frame else 0
    total_market_value = float(frame[value_column(frame)].sum())
    return {
        "portfolio_id": portfolio_id,
        "asset_count": len(frame),
        "eligible_count": eligible,
        "eligibility_rate": eligible / len(frame) if len(frame) else 0.0,
        "total_market_value": total_market_value,
        "available_collateral_value": float(available),
        "available_value_ratio": float(available / total_market_value) if total_market_value else 0.0,
        "top_counterparty_concentration": concentration_table(frame, "counterparty"),
        "top_country_concentration": concentration_table(frame, "country"),
        "top_asset_type_concentration": concentration_table(frame, "asset_type"),
    }


def _dict_table(title: str, values: dict[str, float]) -> str:
    rows = "\n".join(
        f"<tr><td>{html.escape(key)}</td><td>{value:.1%}</td></tr>" for key, value in values.items()
    )
    return f"<h3>{html.escape(title)}</h3><table><tr><th>Name</th><th>Share</th></tr>{rows}</table>"


def _reason_summary(frame: pd.DataFrame) -> str:
    if "reason_codes" not in frame:
        return ""
    counts: dict[str, int] = {}
    for reasons in frame["reason_codes"]:
        for reason in reasons:
            counts[reason] = counts.get(reason, 0) + 1
    rows = "\n".join(
        f"<tr><td>{html.escape(reason)}</td><td>{count}</td></tr>"
        for reason, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
    )
    return f"<table><tr><th>Reason code</th><th>Assets rejected</th></tr>{rows}</table>" if rows else "<p>No rejected assets.</p>"


def _simulation_section(simulation: dict[str, Any] | None) -> str:
    if not simulation:
        return "<p>No simulation has been run yet.</p>"

    var_rows = "\n".join(
        f"<tr><td>{float(level):.0%}</td><td>{value:,.2f}</td><td>{simulation['expected_shortfall'][level]:,.2f}</td></tr>"
        for level, value in simulation["var"].items()
    )
    convergence_rows = "\n".join(
        f"<tr><td>{row['simulations']:,.0f}</td><td>{row['mean_loss']:,.2f}</td><td>{row['var']:,.2f}</td><td>{row['ci_width']:,.2f}</td></tr>"
        for row in simulation["convergence"]
    )
    concentration = simulation.get("risk_concentration", {})
    return f"""
    <div class="grid">
      <div class="panel">
        <h3>Tail Risk</h3>
        <table>
          <tr><th>Confidence</th><th>VaR</th><th>Expected Shortfall</th></tr>
          {var_rows}
        </table>
      </div>
      <div class="panel">
        <h3>Simulation Quality</h3>
        <table>
          <tr><th>Metric</th><th>Value</th></tr>
          <tr><td>Simulations</td><td>{simulation["simulations"]:,.0f}</td></tr>
          <tr><td>Seed</td><td>{simulation["seed"]}</td></tr>
          <tr><td>Mean loss</td><td>{simulation["mean_loss"]:,.2f}</td></tr>
          <tr><td>95% CI width</td><td>{simulation["ci_95"]["width"]:,.2f}</td></tr>
        </table>
      </div>
    </div>
    <h3>Risk Concentration</h3>
    <table>
      <tr><th>Metric</th><th>Value</th><th>Interpretation</th></tr>
      <tr><td>Largest exposure share</td><td>{concentration.get("largest_exposure_share", 0):.1%}</td><td>Share of available collateral in the largest eligible asset.</td></tr>
      <tr><td>Effective exposure count</td><td>{concentration.get("effective_exposure_count", 0):.1f}</td><td>Inverse Herfindahl measure: lower values imply higher name concentration.</td></tr>
      <tr><td>First eigenvalue share</td><td>{concentration.get("first_eigenvalue_share", 0):.1%}</td><td>Share of covariance explained by the dominant risk direction.</td></tr>
      <tr><td>Covariance condition number</td><td>{concentration.get("condition_number", 0):.1f}</td><td>Higher values imply uneven risk modes across assets.</td></tr>
    </table>
    <h3>Convergence</h3>
    <table>
      <tr><th>Simulations</th><th>Mean loss</th><th>VaR</th><th>CI width</th></tr>
      {convergence_rows}
    </table>
    """


def _stress_section(stress: dict[str, Any] | None) -> str:
    if not stress:
        return "<p>No stress scenario has been run yet.</p>"
    simulation = stress["simulation"]
    shocks = ", ".join(f"{asset_type}: {shock:.1%}" for asset_type, shock in stress["shocks"].items())
    return f"""
    <table>
      <tr><th>Scenario</th><td>{html.escape(stress["scenario"])}</td></tr>
      <tr><th>Applied shocks</th><td>{html.escape(shocks)}</td></tr>
      <tr><th>Immediate scenario loss</th><td>{stress["immediate_scenario_loss"]:,.2f}</td></tr>
      <tr><th>Market value change, USD base</th><td>{stress["market_value_change"]:,.2f}</td></tr>
      <tr><th>Available collateral change, USD base</th><td>{stress["available_collateral_change"]:,.2f}</td></tr>
      <tr><th>Baseline available collateral, USD base</th><td>{stress["baseline_available_collateral"]:,.2f}</td></tr>
      <tr><th>Stressed available collateral, USD base</th><td>{stress["stressed_available_collateral"]:,.2f}</td></tr>
      <tr><th>Residual post-stress 99% VaR</th><td>{simulation["var"].get("0.99", 0):,.2f}</td></tr>
      <tr><th>Residual post-stress 99% Expected Shortfall</th><td>{simulation["expected_shortfall"].get("0.99", 0):,.2f}</td></tr>
    </table>
    """


def render_report(
    portfolio_id: int,
    frame: pd.DataFrame,
    simulation: dict[str, Any] | None,
    stress: dict[str, Any] | None = None,
) -> str:
    summary = summary_payload(portfolio_id, frame)
    rejection_cols = ["asset_id", "eligible", "reason_codes", "haircut", "available_value"]
    rejection_table = frame[rejection_cols].to_html(index=False, escape=True) if "eligible" in frame else ""
    report_date = pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>CollateralLens Risk Report</title>
      <style>
        body {{ font-family: Inter, Arial, sans-serif; margin: 0; color: #17202a; background: #f5f7fa; }}
        header {{ background: #102a43; color: white; padding: 36px 48px; }}
        main {{ padding: 32px 48px; }}
        h1 {{ margin: 0 0 8px; font-size: 34px; }}
        h2 {{ color: #102a43; margin-top: 34px; }}
        h3 {{ color: #243b53; margin-bottom: 8px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 12px 0 20px; background: white; }}
        th, td {{ border-bottom: 1px solid #d9e2ec; padding: 10px; text-align: left; vertical-align: top; }}
        th {{ background: #e6edf3; color: #243b53; }}
        .metric-row {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-top: 24px; }}
        .metric, .panel {{ background: white; border: 1px solid #d9e2ec; border-radius: 8px; padding: 16px; }}
        .metric span {{ display: block; color: #52606d; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
        .metric strong {{ display: block; font-size: 24px; margin-top: 6px; color: #102a43; }}
        .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }}
        .note {{ color: #d9e2ec; max-width: 900px; }}
        @media print {{ body {{ background: white; }} header, main {{ padding: 24px; }} }}
      </style>
    </head>
    <body>
      <header>
        <h1>CollateralLens Risk Report</h1>
        <p class="note">Synthetic collateral eligibility and risk report generated on {report_date}. This demonstration uses no confidential, proprietary, or production rules.</p>
      </header>
      <main>
        <h2>Executive Summary</h2>
        <div class="metric-row">
          <div class="metric"><span>Assets</span><strong>{summary["asset_count"]}</strong></div>
          <div class="metric"><span>Eligible</span><strong>{summary["eligible_count"]} ({summary["eligibility_rate"]:.0%})</strong></div>
          <div class="metric"><span>Market Value, USD Base</span><strong>{summary["total_market_value"]:,.0f}</strong></div>
          <div class="metric"><span>Available Collateral, USD Base</span><strong>{summary["available_collateral_value"]:,.0f}</strong></div>
        </div>
        <h2>Concentration</h2>
        <div class="grid">
          <div>{_dict_table("Counterparty", summary["top_counterparty_concentration"])}</div>
          <div>{_dict_table("Country", summary["top_country_concentration"])}</div>
        </div>
        {_dict_table("Asset Type", summary["top_asset_type_concentration"])}
        <h2>Eligibility Diagnostics</h2>
        {_reason_summary(frame)}
        <h2>Monte Carlo Risk</h2>
        {_simulation_section(simulation)}
        <h2>Stress Scenario</h2>
        {_stress_section(stress)}
        <h2>Asset-Level Eligibility</h2>
        {rejection_table}
        <h2>Mathematical Method</h2>
        <p>Asset returns are sampled from a multivariate normal distribution with a covariance matrix built from synthetic volatilities and correlations. Portfolio losses are computed from eligible collateral values after haircuts. VaR is the empirical loss quantile and Expected Shortfall is the average loss beyond that quantile. Confidence intervals use the standard error of simulated losses; their width narrows as simulation count increases, illustrating Monte Carlo convergence. Eigenvalue concentration summarizes how much of the covariance structure is explained by the dominant risk direction.</p>
      </main>
    </body>
    </html>
    """
