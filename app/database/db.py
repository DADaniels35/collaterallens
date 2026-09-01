from __future__ import annotations

import json
import os
import sqlite3
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.getenv("COLLATERAL_LENS_DB_PATH", PROJECT_ROOT / "data" / "collateral_lens.db"))


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS portfolios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                assets_json TEXT NOT NULL,
                evaluated_json TEXT,
                evaluation_rules_json TEXT,
                simulation_json TEXT,
                stress_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(portfolios)").fetchall()}
        if "evaluation_rules_json" not in columns:
            conn.execute("ALTER TABLE portfolios ADD COLUMN evaluation_rules_json TEXT")
        if "stress_json" not in columns:
            conn.execute("ALTER TABLE portfolios ADD COLUMN stress_json TEXT")


def create_portfolio(name: str, assets: pd.DataFrame) -> int:
    init_db()
    with connect() as conn:
        cursor = conn.execute(
            "INSERT INTO portfolios (name, assets_json) VALUES (?, ?)",
            (name, assets.to_json(orient="records")),
        )
        return int(cursor.lastrowid)


def get_portfolio(portfolio_id: int) -> sqlite3.Row:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT * FROM portfolios WHERE id = ?", (portfolio_id,)).fetchone()
    if row is None:
        raise KeyError(f"Portfolio {portfolio_id} not found")
    return row


def assets_frame(portfolio_id: int) -> pd.DataFrame:
    return pd.read_json(StringIO(get_portfolio(portfolio_id)["assets_json"]))


def evaluated_frame(portfolio_id: int) -> pd.DataFrame:
    row = get_portfolio(portfolio_id)
    payload = row["evaluated_json"] or row["assets_json"]
    return pd.read_json(StringIO(payload))


def has_evaluation(portfolio_id: int) -> bool:
    return get_portfolio(portfolio_id)["evaluated_json"] is not None


def save_evaluation(portfolio_id: int, evaluated: pd.DataFrame, rules: dict[str, Any] | None = None) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE portfolios SET evaluated_json = ?, evaluation_rules_json = ? WHERE id = ?",
            (evaluated.to_json(orient="records"), json.dumps(rules) if rules is not None else None, portfolio_id),
        )


def save_simulation(portfolio_id: int, simulation: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE portfolios SET simulation_json = ? WHERE id = ?",
            (json.dumps(simulation), portfolio_id),
        )


def save_stress(portfolio_id: int, stress: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE portfolios SET stress_json = ? WHERE id = ?",
            (json.dumps(stress), portfolio_id),
        )


def simulation_payload(portfolio_id: int) -> dict[str, Any] | None:
    raw = get_portfolio(portfolio_id)["simulation_json"]
    return json.loads(raw) if raw else None


def stress_payload(portfolio_id: int) -> dict[str, Any] | None:
    raw = get_portfolio(portfolio_id)["stress_json"]
    return json.loads(raw) if raw else None
