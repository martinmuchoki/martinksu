from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from services.database import DB_PATH


DEFAULT_SETTINGS = {
    "broker": "Ziidi",
    "charge_rate": 1.50,
    "auto_calculate": 1,
    "manual_override": 0,
    "currency": "KES",
    "settlement": "T+3",
}


def _connect() -> sqlite3.Connection:
    db = Path(DB_PATH).expanduser().resolve()
    db.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        db,
        timeout=30,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_settings() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS investment_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                broker TEXT NOT NULL DEFAULT 'Ziidi',
                charge_rate REAL NOT NULL DEFAULT 1.50
                    CHECK (charge_rate >= 0),
                auto_calculate INTEGER NOT NULL DEFAULT 1
                    CHECK (auto_calculate IN (0, 1)),
                manual_override INTEGER NOT NULL DEFAULT 0
                    CHECK (manual_override IN (0, 1)),
                currency TEXT NOT NULL DEFAULT 'KES',
                settlement TEXT NOT NULL DEFAULT 'T+3',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            INSERT OR IGNORE INTO investment_settings (
                id,
                broker,
                charge_rate,
                auto_calculate,
                manual_override,
                currency,
                settlement
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                DEFAULT_SETTINGS["broker"],
                DEFAULT_SETTINGS["charge_rate"],
                DEFAULT_SETTINGS["auto_calculate"],
                DEFAULT_SETTINGS["manual_override"],
                DEFAULT_SETTINGS["currency"],
                DEFAULT_SETTINGS["settlement"],
            ),
        )

        conn.commit()


def get_settings() -> dict[str, Any]:
    init_settings()

    with _connect() as conn:
        row = conn.execute(
            """
            SELECT
                id,
                broker,
                charge_rate,
                auto_calculate,
                manual_override,
                currency,
                settlement,
                created_at,
                updated_at
            FROM investment_settings
            WHERE id = 1
            """
        ).fetchone()

    if row is None:
        raise RuntimeError("Investment settings could not be loaded.")

    return dict(row)

def update_settings(
    broker: str,
    charge_rate: float,
    auto_calculate: bool,
    manual_override: bool,
    currency: str,
    settlement: str,
) -> None:
    """
    Update the singleton investment settings record.
    """
    init_settings()

    if charge_rate < 0:
        raise ValueError("Charge rate cannot be negative.")

    with _connect() as conn:
        conn.execute(
            """
            UPDATE investment_settings
            SET
                broker = ?,
                charge_rate = ?,
                auto_calculate = ?,
                manual_override = ?,
                currency = ?,
                settlement = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            (
                broker.strip(),
                float(charge_rate),
                int(bool(auto_calculate)),
                int(bool(manual_override)),
                currency.strip().upper(),
                settlement.strip().upper(),
            ),
        )
        conn.commit()
