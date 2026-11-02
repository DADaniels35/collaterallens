from __future__ import annotations

import json
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import ValidationError

from app.database import db
from app.eligibility.engine import evaluate_portfolio
from app.reporting.report import render_report, summary_payload
from app.risk.simulation import simulate_losses
from app.risk.stress import run_stress_test
from app.schemas.models import (
    Asset,
    EligibilityRules,
    SimulationRequest,
    SimulationResult,
    StressRequest,
    StressResult,
)
from app.valuation.fx import add_base_values

router = APIRouter()
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


def _read_csv(upload: UploadFile) -> pd.DataFrame:
    try:
        frame = pd.read_csv(upload.file)
        if frame.empty:
            raise ValueError("Portfolio CSV is empty")
        missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
        if missing:
            raise ValueError(f"Portfolio CSV is missing required columns: {', '.join(missing)}")
        duplicates = frame["asset_id"][frame["asset_id"].duplicated()].astype(str).unique().tolist()
        if duplicates:
            raise ValueError(f"Portfolio CSV contains duplicate asset_id values: {', '.join(duplicates[:5])}")
        validated_rows = [Asset.model_validate(row).model_dump() for row in frame.to_dict(orient="records")]
        return add_base_values(pd.DataFrame(validated_rows))
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError, ValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _rules_from_json(rules_json: str | None) -> EligibilityRules:
    if not rules_json:
        return EligibilityRules()
    try:
        return EligibilityRules.model_validate(json.loads(rules_json))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid rules JSON: {exc}") from exc


def _require_evaluation(portfolio_id: int) -> pd.DataFrame:
    try:
        if not db.has_evaluation(portfolio_id):
            raise HTTPException(status_code=409, detail="Evaluate the portfolio before running risk analytics")
        return db.evaluated_frame(portfolio_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/portfolios")
async def create_portfolio(
    file: Annotated[UploadFile, File()],
    name: Annotated[str, Form()] = "uploaded_portfolio",
):
    frame = _read_csv(file)
    portfolio_id = db.create_portfolio(name=name, assets=frame)
    return {"portfolio_id": portfolio_id, "asset_count": len(frame)}


@router.post("/portfolios/{portfolio_id}/evaluate")
async def evaluate(portfolio_id: int, rules_json: str | None = Form(None)):
    try:
        frame = db.assets_frame(portfolio_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    rules = _rules_from_json(rules_json)
    evaluated = evaluate_portfolio(frame, rules)
    db.save_evaluation(portfolio_id, evaluated, rules.model_dump())
    return {
        "portfolio_id": portfolio_id,
        "eligible_count": int(evaluated["eligible"].sum()),
        "results": evaluated[["asset_id", "eligible", "reason_codes", "haircut", "available_value"]].to_dict(
            orient="records"
        ),
    }


@router.post("/portfolios/{portfolio_id}/simulate", response_model=SimulationResult)
async def simulate(portfolio_id: int, request: SimulationRequest | None = None):
    request = request or SimulationRequest()
    frame = _require_evaluation(portfolio_id)
    _, metadata = simulate_losses(
        frame,
        simulations=request.simulations,
        horizon_days=request.horizon_days,
        seed=request.seed,
        confidence_levels=request.confidence_levels,
    )
    payload = {"portfolio_id": portfolio_id, "simulations": request.simulations, "seed": request.seed, **metadata}
    db.save_simulation(portfolio_id, payload)
    return payload


@router.post("/portfolios/{portfolio_id}/stress", response_model=StressResult)
async def stress(portfolio_id: int, request: StressRequest | None = None):
    request = request or StressRequest()
    frame = _require_evaluation(portfolio_id)
    try:
        payload = run_stress_test(
            portfolio_id=portfolio_id,
            evaluated_assets=frame,
            scenario=request.scenario,
            custom_shocks=request.custom_shocks,
            simulations=request.simulations,
            horizon_days=request.horizon_days,
            seed=request.seed,
            confidence_levels=request.confidence_levels,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.save_stress(portfolio_id, payload)
    return payload


@router.get("/portfolios/{portfolio_id}/summary")
async def summary(portfolio_id: int):
    try:
        return summary_payload(portfolio_id, db.evaluated_frame(portfolio_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/portfolios/{portfolio_id}/assets")
async def assets(portfolio_id: int):
    try:
        return db.evaluated_frame(portfolio_id).to_dict(orient="records")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/portfolios/{portfolio_id}/report", response_class=HTMLResponse)
async def report(portfolio_id: int):
    try:
        frame = db.evaluated_frame(portfolio_id)
        return render_report(portfolio_id, frame, db.simulation_payload(portfolio_id), db.stress_payload(portfolio_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
