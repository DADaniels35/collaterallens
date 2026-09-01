from fastapi.testclient import TestClient

from app.database import db
from app.main import app


def use_temp_db(tmp_path, monkeypatch):
    test_db = tmp_path / "collateral_lens.db"
    monkeypatch.setattr(db, "DB_PATH", test_db)
    return test_db


def test_health():
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}


def test_upload_evaluate_simulate_report(tmp_path, monkeypatch):
    test_db = use_temp_db(tmp_path, monkeypatch)
    client = TestClient(app)
    csv = (
        "asset_id,asset_type,currency,credit_rating,market_value,counterparty,country,maturity_days\n"
        "A1,government_bond,USD,AAA,1000,CP_A,US,365\n"
    )
    created = client.post("/portfolios", files={"file": ("p.csv", csv, "text/csv")})
    assert created.status_code == 200
    portfolio_id = created.json()["portfolio_id"]
    assert client.post(f"/portfolios/{portfolio_id}/evaluate").status_code == 200
    sim = client.post(f"/portfolios/{portfolio_id}/simulate", json={"simulations": 500, "seed": 1})
    assert sim.status_code == 200
    report = client.get(f"/portfolios/{portfolio_id}/report")
    assert report.status_code == 200
    assert "CollateralLens Risk Report" in report.text
    assert test_db.exists()


def test_upload_persists_normalized_pydantic_values(tmp_path, monkeypatch):
    use_temp_db(tmp_path, monkeypatch)
    client = TestClient(app)
    csv = (
        "asset_id,asset_type,currency,credit_rating,market_value,counterparty,country,maturity_days\n"
        "A1,cash,gbp,aaa,1000,CP_A,gb,60\n"
    )
    created = client.post("/portfolios", files={"file": ("p.csv", csv, "text/csv")})
    portfolio_id = created.json()["portfolio_id"]
    assets = client.get(f"/portfolios/{portfolio_id}/assets").json()
    assert assets[0]["currency"] == "GBP"
    assert assets[0]["credit_rating"] == "AAA"
    assert assets[0]["country"] == "GB"
    assert assets[0]["base_currency"] == "USD"
    assert assets[0]["fx_rate_to_base"] == 1.27
    assert assets[0]["market_value_base"] == 1270.0


def test_summary_uses_base_currency_values(tmp_path, monkeypatch):
    use_temp_db(tmp_path, monkeypatch)
    client = TestClient(app)
    csv = (
        "asset_id,asset_type,currency,credit_rating,market_value,counterparty,country,maturity_days\n"
        "USD1,cash,USD,AAA,100,CP_A,US,60\n"
        "GBP1,cash,GBP,AAA,100,CP_A,GB,60\n"
    )
    created = client.post("/portfolios", files={"file": ("p.csv", csv, "text/csv")})
    portfolio_id = created.json()["portfolio_id"]
    client.post(f"/portfolios/{portfolio_id}/evaluate")
    summary = client.get(f"/portfolios/{portfolio_id}/summary").json()
    assert summary["total_market_value"] == 227.0
    assert summary["available_collateral_value"] == 227.0
    assert summary["available_value_ratio"] == 1.0
    assert "collateralization_after_haircuts" not in summary


def test_upload_rejects_missing_required_columns(tmp_path, monkeypatch):
    use_temp_db(tmp_path, monkeypatch)
    client = TestClient(app)
    csv = "asset_id,asset_type,currency\nA1,cash,USD\n"
    response = client.post("/portfolios", files={"file": ("bad.csv", csv, "text/csv")})
    assert response.status_code == 400
    assert "missing required columns" in response.json()["detail"]


def test_upload_rejects_duplicate_asset_ids(tmp_path, monkeypatch):
    use_temp_db(tmp_path, monkeypatch)
    client = TestClient(app)
    csv = (
        "asset_id,asset_type,currency,credit_rating,market_value,counterparty,country,maturity_days\n"
        "A1,cash,USD,AAA,1000,CP_A,US,60\n"
        "A1,cash,USD,AAA,1200,CP_A,US,60\n"
    )
    response = client.post("/portfolios", files={"file": ("dupes.csv", csv, "text/csv")})
    assert response.status_code == 400
    assert "duplicate asset_id" in response.json()["detail"]


def test_upload_rejects_unknown_rating(tmp_path, monkeypatch):
    use_temp_db(tmp_path, monkeypatch)
    client = TestClient(app)
    csv = (
        "asset_id,asset_type,currency,credit_rating,market_value,counterparty,country,maturity_days\n"
        "A1,cash,USD,NOTCHED,1000,CP_A,US,60\n"
    )
    response = client.post("/portfolios", files={"file": ("bad_rating.csv", csv, "text/csv")})
    assert response.status_code == 400
    assert "Unknown credit rating" in response.json()["detail"]


def test_upload_rejects_unknown_fx_currency(tmp_path, monkeypatch):
    use_temp_db(tmp_path, monkeypatch)
    client = TestClient(app)
    csv = (
        "asset_id,asset_type,currency,credit_rating,market_value,counterparty,country,maturity_days\n"
        "A1,cash,AUD,AAA,1000,CP_A,AU,60\n"
    )
    response = client.post("/portfolios", files={"file": ("bad_fx.csv", csv, "text/csv")})
    assert response.status_code == 400
    assert "No synthetic FX rate configured for currency: AUD" in response.json()["detail"]


def test_upload_rejects_malformed_asset_type(tmp_path, monkeypatch):
    use_temp_db(tmp_path, monkeypatch)
    client = TestClient(app)
    csv = (
        "asset_id,asset_type,currency,credit_rating,market_value,counterparty,country,maturity_days\n"
        "A1,crypto,USD,AAA,1000,CP_A,US,60\n"
    )
    response = client.post("/portfolios", files={"file": ("bad_type.csv", csv, "text/csv")})
    assert response.status_code == 400
    assert "asset_type" in response.json()["detail"]


def test_simulate_requires_prior_evaluation(tmp_path, monkeypatch):
    use_temp_db(tmp_path, monkeypatch)
    client = TestClient(app)
    csv = (
        "asset_id,asset_type,currency,credit_rating,market_value,counterparty,country,maturity_days\n"
        "A1,cash,USD,AAA,1000,CP_A,US,60\n"
    )
    created = client.post("/portfolios", files={"file": ("p.csv", csv, "text/csv")})
    portfolio_id = created.json()["portfolio_id"]
    response = client.post(f"/portfolios/{portfolio_id}/simulate", json={"simulations": 500})
    assert response.status_code == 409
    assert "Evaluate the portfolio" in response.json()["detail"]


def test_stress_requires_prior_evaluation(tmp_path, monkeypatch):
    use_temp_db(tmp_path, monkeypatch)
    client = TestClient(app)
    csv = (
        "asset_id,asset_type,currency,credit_rating,market_value,counterparty,country,maturity_days\n"
        "A1,cash,USD,AAA,1000,CP_A,US,60\n"
    )
    created = client.post("/portfolios", files={"file": ("p.csv", csv, "text/csv")})
    portfolio_id = created.json()["portfolio_id"]
    response = client.post(f"/portfolios/{portfolio_id}/stress", json={"simulations": 500})
    assert response.status_code == 409
    assert "Evaluate the portfolio" in response.json()["detail"]


def test_evaluation_persists_rule_metadata(tmp_path, monkeypatch):
    use_temp_db(tmp_path, monkeypatch)
    client = TestClient(app)
    csv = (
        "asset_id,asset_type,currency,credit_rating,market_value,counterparty,country,maturity_days\n"
        "A1,cash,USD,AAA,100,CP_A,US,60\n"
    )
    created = client.post("/portfolios", files={"file": ("p.csv", csv, "text/csv")})
    portfolio_id = created.json()["portfolio_id"]
    client.post(f"/portfolios/{portfolio_id}/evaluate", data={"rules_json": '{"min_rating":"AA"}'})
    row = db.get_portfolio(portfolio_id)
    assert '"min_rating": "AA"' in row["evaluation_rules_json"]


def test_simulation_rejects_invalid_confidence_level(tmp_path, monkeypatch):
    use_temp_db(tmp_path, monkeypatch)
    client = TestClient(app)
    csv = (
        "asset_id,asset_type,currency,credit_rating,market_value,counterparty,country,maturity_days\n"
        "A1,cash,USD,AAA,1000,CP_A,US,60\n"
    )
    created = client.post("/portfolios", files={"file": ("p.csv", csv, "text/csv")})
    portfolio_id = created.json()["portfolio_id"]
    response = client.post(
        f"/portfolios/{portfolio_id}/simulate",
        json={"simulations": 500, "confidence_levels": [0.95, 1.2]},
    )
    assert response.status_code == 422


def test_stress_endpoint_returns_scenario_payload(tmp_path, monkeypatch):
    use_temp_db(tmp_path, monkeypatch)
    client = TestClient(app)
    csv = (
        "asset_id,asset_type,currency,credit_rating,market_value,counterparty,country,maturity_days\n"
        "A1,corporate_bond,USD,A,1000,CP_A,US,365\n"
    )
    created = client.post("/portfolios", files={"file": ("p.csv", csv, "text/csv")})
    portfolio_id = created.json()["portfolio_id"]
    client.post(f"/portfolios/{portfolio_id}/evaluate")
    response = client.post(
        f"/portfolios/{portfolio_id}/stress",
        json={"scenario": "credit_spread_up_100bps", "simulations": 500, "seed": 1},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["scenario"] == "credit_spread_up_100bps"
    assert payload["available_collateral_change"] < 0
    assert payload["immediate_scenario_loss"] > 0
    assert "0.99" in payload["simulation"]["var"]


def test_simulation_handles_empty_eligible_portfolio(tmp_path, monkeypatch):
    use_temp_db(tmp_path, monkeypatch)
    client = TestClient(app)
    csv = (
        "asset_id,asset_type,currency,credit_rating,market_value,counterparty,country,maturity_days\n"
        "A1,equity,USD,AAA,1000,CP_A,US,60\n"
    )
    created = client.post("/portfolios", files={"file": ("p.csv", csv, "text/csv")})
    portfolio_id = created.json()["portfolio_id"]
    evaluated = client.post(f"/portfolios/{portfolio_id}/evaluate")
    assert evaluated.json()["eligible_count"] == 0
    response = client.post(f"/portfolios/{portfolio_id}/simulate", json={"simulations": 500, "seed": 1})
    payload = response.json()
    assert response.status_code == 200
    assert payload["mean_loss"] == 0.0
    assert payload["var"]["0.99"] == 0.0
    assert payload["expected_shortfall"]["0.99"] == 0.0


def test_custom_stress_scenario_uses_request_shocks(tmp_path, monkeypatch):
    use_temp_db(tmp_path, monkeypatch)
    client = TestClient(app)
    csv = (
        "asset_id,asset_type,currency,credit_rating,market_value,counterparty,country,maturity_days\n"
        "A1,corporate_bond,USD,A,1000,CP_A,US,365\n"
    )
    created = client.post("/portfolios", files={"file": ("p.csv", csv, "text/csv")})
    portfolio_id = created.json()["portfolio_id"]
    client.post(f"/portfolios/{portfolio_id}/evaluate")
    response = client.post(
        f"/portfolios/{portfolio_id}/stress",
        json={"scenario": "custom", "custom_shocks": {"corporate_bond": -0.10}, "simulations": 500, "seed": 1},
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["shocks"] == {"corporate_bond": -0.10}
    assert payload["market_value_change"] == -100.0
    assert payload["available_collateral_change"] == -90.0


def test_evaluate_rejects_invalid_haircut_rules(tmp_path, monkeypatch):
    use_temp_db(tmp_path, monkeypatch)
    client = TestClient(app)
    csv = (
        "asset_id,asset_type,currency,credit_rating,market_value,counterparty,country,maturity_days\n"
        "A1,cash,USD,AAA,100,CP_A,US,60\n"
    )
    created = client.post("/portfolios", files={"file": ("p.csv", csv, "text/csv")})
    portfolio_id = created.json()["portfolio_id"]
    response = client.post(
        f"/portfolios/{portfolio_id}/evaluate",
        data={"rules_json": '{"haircut_by_asset_type":{"cash":-0.5}}'},
    )
    assert response.status_code == 400
    assert "Haircuts must be between 0 and 1" in response.json()["detail"]


def test_evaluate_rejects_impossible_maturity_range(tmp_path, monkeypatch):
    use_temp_db(tmp_path, monkeypatch)
    client = TestClient(app)
    csv = (
        "asset_id,asset_type,currency,credit_rating,market_value,counterparty,country,maturity_days\n"
        "A1,cash,USD,AAA,100,CP_A,US,60\n"
    )
    created = client.post("/portfolios", files={"file": ("p.csv", csv, "text/csv")})
    portfolio_id = created.json()["portfolio_id"]
    response = client.post(
        f"/portfolios/{portfolio_id}/evaluate",
        data={"rules_json": '{"min_maturity_days":365,"max_maturity_days":30}'},
    )
    assert response.status_code == 400
    assert "min_maturity_days cannot exceed max_maturity_days" in response.json()["detail"]


def test_evaluate_rejects_unknown_min_rating(tmp_path, monkeypatch):
    use_temp_db(tmp_path, monkeypatch)
    client = TestClient(app)
    csv = (
        "asset_id,asset_type,currency,credit_rating,market_value,counterparty,country,maturity_days\n"
        "A1,cash,USD,AAA,100,CP_A,US,60\n"
    )
    created = client.post("/portfolios", files={"file": ("p.csv", csv, "text/csv")})
    portfolio_id = created.json()["portfolio_id"]
    response = client.post(
        f"/portfolios/{portfolio_id}/evaluate",
        data={"rules_json": '{"min_rating":"INVESTMENT_GRADE"}'},
    )
    assert response.status_code == 400
    assert "Unknown minimum credit rating" in response.json()["detail"]


def test_stress_rejects_invalid_custom_shocks(tmp_path, monkeypatch):
    use_temp_db(tmp_path, monkeypatch)
    client = TestClient(app)
    csv = (
        "asset_id,asset_type,currency,credit_rating,market_value,counterparty,country,maturity_days\n"
        "A1,cash,USD,AAA,100,CP_A,US,60\n"
    )
    created = client.post("/portfolios", files={"file": ("p.csv", csv, "text/csv")})
    portfolio_id = created.json()["portfolio_id"]
    client.post(f"/portfolios/{portfolio_id}/evaluate")
    response = client.post(
        f"/portfolios/{portfolio_id}/stress",
        json={"scenario": "custom", "custom_shocks": {"cash": -1.5}},
    )
    assert response.status_code == 422
