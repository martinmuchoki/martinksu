#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$HOME/nse_signal_bot_v10_3"
cd "$PROJECT_DIR"

PYTHON="$PROJECT_DIR/venv/bin/python"
TIMESTAMP="$(date +%Y-%m-%d_%H-%M-%S)"
BACKUP_DIR="$PROJECT_DIR/backups/ziidi_copilot_stage1/$TIMESTAMP"

mkdir -p "$BACKUP_DIR"

echo "======================================================"
echo "MIP PRO v12.0 — Ziidi Co-Pilot Stage 1"
echo "Manual Ziidi Trade Capture and Portfolio Foundation"
echo "======================================================"

echo
echo "==> Creating backups"

cp app.py "$BACKUP_DIR/app.py"
cp templates/dashboard_v115.html \
   "$BACKUP_DIR/dashboard_v115.html"

[ -f services/ziidi_copilot.py ] && \
    cp services/ziidi_copilot.py \
       "$BACKUP_DIR/ziidi_copilot.py"

[ -f templates/ziidi_copilot.html ] && \
    cp templates/ziidi_copilot.html \
       "$BACKUP_DIR/ziidi_copilot.html"

echo "Backup directory:"
echo "$BACKUP_DIR"

echo
echo "==> Creating Ziidi portfolio service"

cat > services/ziidi_copilot.py <<'PY'
from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from services.database import DB_PATH


MONEY_PLACES = Decimal("0.01")
PRICE_PLACES = Decimal("0.0001")


class ZiidiTradeError(ValueError):
    """Raised when a Ziidi trade cannot be validated or recorded."""


def _connect() -> sqlite3.Connection:
    database_path = Path(DB_PATH).expanduser().resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        database_path,
        timeout=30,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def _decimal(
    value: Any,
    field_name: str,
    *,
    allow_zero: bool = False,
) -> Decimal:
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError):
        raise ZiidiTradeError(
            f"{field_name} must be a valid number."
        )

    minimum_allowed = Decimal("0") if allow_zero else Decimal("0.0000001")

    if result < minimum_allowed:
        comparison = "zero or more" if allow_zero else "greater than zero"
        raise ZiidiTradeError(
            f"{field_name} must be {comparison}."
        )

    return result


def _money(value: Decimal) -> Decimal:
    return value.quantize(
        MONEY_PLACES,
        rounding=ROUND_HALF_UP,
    )


def _price(value: Decimal) -> Decimal:
    return value.quantize(
        PRICE_PLACES,
        rounding=ROUND_HALF_UP,
    )


def init_ziidi_schema() -> None:
    with _connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS ziidi_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                side TEXT NOT NULL
                    CHECK (side IN ('BUY', 'SELL')),
                symbol TEXT NOT NULL,
                company_name TEXT,
                trade_date TEXT NOT NULL,
                settlement_date TEXT,
                quantity INTEGER NOT NULL
                    CHECK (quantity > 0),
                executed_price REAL NOT NULL
                    CHECK (executed_price > 0),
                gross_amount REAL NOT NULL
                    CHECK (gross_amount >= 0),
                charges REAL NOT NULL DEFAULT 0
                    CHECK (charges >= 0),
                net_amount REAL NOT NULL
                    CHECK (net_amount >= 0),
                reference_number TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS
                idx_ziidi_trades_symbol
                ON ziidi_trades(symbol);

            CREATE INDEX IF NOT EXISTS
                idx_ziidi_trades_date
                ON ziidi_trades(trade_date);

            CREATE UNIQUE INDEX IF NOT EXISTS
                idx_ziidi_reference_unique
                ON ziidi_trades(reference_number)
                WHERE reference_number IS NOT NULL
                  AND TRIM(reference_number) <> '';
            """
        )


def _normalise_symbol(value: Any) -> str:
    symbol = str(value or "").strip().upper()

    if not symbol:
        raise ZiidiTradeError("Stock symbol is required.")

    if len(symbol) > 20:
        raise ZiidiTradeError("Stock symbol is too long.")

    allowed = set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-"
    )

    if any(character not in allowed for character in symbol):
        raise ZiidiTradeError(
            "Stock symbol contains unsupported characters."
        )

    return symbol


def _normalise_date(
    value: Any,
    field_name: str,
    *,
    required: bool,
) -> str | None:
    raw_value = str(value or "").strip()

    if not raw_value:
        if required:
            raise ZiidiTradeError(
                f"{field_name} is required."
            )
        return None

    try:
        parsed = date.fromisoformat(raw_value)
    except ValueError:
        raise ZiidiTradeError(
            f"{field_name} must use YYYY-MM-DD format."
        )

    return parsed.isoformat()


def _build_positions_from_rows(
    rows: list[sqlite3.Row],
) -> dict[str, dict[str, Any]]:
    positions: dict[str, dict[str, Any]] = {}

    for row in rows:
        symbol = row["symbol"]
        side = row["side"]
        quantity = int(row["quantity"])

        price = Decimal(str(row["executed_price"]))
        charges = Decimal(str(row["charges"]))
        net_amount = Decimal(str(row["net_amount"]))

        position = positions.setdefault(
            symbol,
            {
                "symbol": symbol,
                "company_name": row["company_name"] or "",
                "quantity": 0,
                "cost_basis": Decimal("0"),
                "average_cost": Decimal("0"),
                "realized_profit_loss": Decimal("0"),
                "buy_count": 0,
                "sell_count": 0,
            },
        )

        if side == "BUY":
            total_buy_cost = net_amount

            if total_buy_cost <= 0:
                total_buy_cost = (
                    price * Decimal(quantity)
                ) + charges

            position["cost_basis"] += total_buy_cost
            position["quantity"] += quantity
            position["buy_count"] += 1

            if position["quantity"] > 0:
                position["average_cost"] = (
                    position["cost_basis"]
                    / Decimal(position["quantity"])
                )

        else:
            available_quantity = int(position["quantity"])

            if quantity > available_quantity:
                raise ZiidiTradeError(
                    f"{symbol} sell quantity exceeds "
                    f"available shares."
                )

            average_cost = Decimal(
                str(position["average_cost"])
            )
            sold_cost_basis = (
                average_cost * Decimal(quantity)
            )

            net_proceeds = net_amount

            if net_proceeds <= 0:
                net_proceeds = (
                    price * Decimal(quantity)
                ) - charges

            position["realized_profit_loss"] += (
                net_proceeds - sold_cost_basis
            )
            position["cost_basis"] -= sold_cost_basis
            position["quantity"] -= quantity
            position["sell_count"] += 1

            if position["quantity"] > 0:
                position["average_cost"] = (
                    position["cost_basis"]
                    / Decimal(position["quantity"])
                )
            else:
                position["quantity"] = 0
                position["cost_basis"] = Decimal("0")
                position["average_cost"] = Decimal("0")

    return positions


def get_positions(
    *,
    include_closed: bool = False,
) -> list[dict[str, Any]]:
    init_ziidi_schema()

    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                side,
                symbol,
                company_name,
                trade_date,
                settlement_date,
                quantity,
                executed_price,
                gross_amount,
                charges,
                net_amount,
                reference_number,
                notes,
                created_at
            FROM ziidi_trades
            ORDER BY
                trade_date ASC,
                id ASC
            """
        ).fetchall()

    positions = _build_positions_from_rows(list(rows))
    output: list[dict[str, Any]] = []

    for position in positions.values():
        if (
            not include_closed
            and int(position["quantity"]) <= 0
        ):
            continue

        output.append(
            {
                "symbol": position["symbol"],
                "company_name": position["company_name"],
                "quantity": int(position["quantity"]),
                "average_cost": float(
                    _money(position["average_cost"])
                ),
                "cost_basis": float(
                    _money(position["cost_basis"])
                ),
                "realized_profit_loss": float(
                    _money(
                        position["realized_profit_loss"]
                    )
                ),
                "buy_count": int(position["buy_count"]),
                "sell_count": int(position["sell_count"]),
            }
        )

    return sorted(
        output,
        key=lambda item: item["symbol"],
    )


def get_available_quantity(symbol: str) -> int:
    normalised_symbol = _normalise_symbol(symbol)

    for position in get_positions(
        include_closed=True
    ):
        if position["symbol"] == normalised_symbol:
            return int(position["quantity"])

    return 0


def record_trade(payload: dict[str, Any]) -> dict[str, Any]:
    init_ziidi_schema()

    side = str(payload.get("side", "")).strip().upper()

    if side not in {"BUY", "SELL"}:
        raise ZiidiTradeError(
            "Trade side must be BUY or SELL."
        )

    symbol = _normalise_symbol(payload.get("symbol"))

    company_name = str(
        payload.get("company_name", "")
    ).strip()[:150]

    try:
        quantity = int(
            str(payload.get("quantity", "")).strip()
        )
    except (TypeError, ValueError):
        raise ZiidiTradeError(
            "Number of shares must be a whole number."
        )

    if quantity <= 0:
        raise ZiidiTradeError(
            "Number of shares must be greater than zero."
        )

    executed_price = _price(
        _decimal(
            payload.get("executed_price"),
            "Executed price",
        )
    )

    calculated_gross = _money(
        executed_price * Decimal(quantity)
    )

    gross_raw = payload.get("gross_amount")

    if str(gross_raw or "").strip():
        gross_amount = _money(
            _decimal(
                gross_raw,
                "Gross amount",
                allow_zero=True,
            )
        )
    else:
        gross_amount = calculated_gross

    charges = _money(
        _decimal(
            payload.get("charges", 0),
            "Charges",
            allow_zero=True,
        )
    )

    calculated_net = (
        gross_amount + charges
        if side == "BUY"
        else gross_amount - charges
    )

    if calculated_net < 0:
        raise ZiidiTradeError(
            "Charges cannot exceed gross sale proceeds."
        )

    net_raw = payload.get("net_amount")

    if str(net_raw or "").strip():
        net_amount = _money(
            _decimal(
                net_raw,
                "Total or net amount",
                allow_zero=True,
            )
        )
    else:
        net_amount = _money(calculated_net)

    trade_date = _normalise_date(
        payload.get("trade_date"),
        "Trade date",
        required=True,
    )

    settlement_date = _normalise_date(
        payload.get("settlement_date"),
        "Settlement date",
        required=False,
    )

    reference_number = str(
        payload.get("reference_number", "")
    ).strip()[:100]

    notes = str(
        payload.get("notes", "")
    ).strip()[:2000]

    if side == "SELL":
        available_quantity = get_available_quantity(
            symbol
        )

        if quantity > available_quantity:
            raise ZiidiTradeError(
                f"Cannot sell {quantity} {symbol} shares. "
                f"Only {available_quantity} are recorded."
            )

    with _connect() as connection:
        try:
            cursor = connection.execute(
                """
                INSERT INTO ziidi_trades (
                    side,
                    symbol,
                    company_name,
                    trade_date,
                    settlement_date,
                    quantity,
                    executed_price,
                    gross_amount,
                    charges,
                    net_amount,
                    reference_number,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    side,
                    symbol,
                    company_name or None,
                    trade_date,
                    settlement_date,
                    quantity,
                    float(executed_price),
                    float(gross_amount),
                    float(charges),
                    float(net_amount),
                    reference_number or None,
                    notes or None,
                ),
            )
        except sqlite3.IntegrityError as exc:
            if "reference" in str(exc).lower():
                raise ZiidiTradeError(
                    "This Ziidi reference number is "
                    "already recorded."
                )
            raise ZiidiTradeError(
                f"Trade could not be saved: {exc}"
            )

        trade_id = int(cursor.lastrowid)

    return get_trade(trade_id)


def get_trade(trade_id: int) -> dict[str, Any]:
    init_ziidi_schema()

    with _connect() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                side,
                symbol,
                company_name,
                trade_date,
                settlement_date,
                quantity,
                executed_price,
                gross_amount,
                charges,
                net_amount,
                reference_number,
                notes,
                created_at
            FROM ziidi_trades
            WHERE id = ?
            """,
            (trade_id,),
        ).fetchone()

    if row is None:
        raise ZiidiTradeError("Trade was not found.")

    return dict(row)


def get_trade_history(
    limit: int = 100,
) -> list[dict[str, Any]]:
    init_ziidi_schema()

    safe_limit = max(1, min(int(limit), 500))

    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                side,
                symbol,
                company_name,
                trade_date,
                settlement_date,
                quantity,
                executed_price,
                gross_amount,
                charges,
                net_amount,
                reference_number,
                notes,
                created_at
            FROM ziidi_trades
            ORDER BY
                trade_date DESC,
                id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    return [dict(row) for row in rows]


def get_portfolio_summary() -> dict[str, Any]:
    positions = get_positions()
    trades = get_trade_history(limit=500)

    invested_capital = sum(
        (
            Decimal(str(position["cost_basis"]))
            for position in positions
        ),
        Decimal("0"),
    )

    realized_profit_loss = sum(
        (
            Decimal(
                str(position["realized_profit_loss"])
            )
            for position in get_positions(
                include_closed=True
            )
        ),
        Decimal("0"),
    )

    total_charges = sum(
        (
            Decimal(str(trade["charges"]))
            for trade in trades
        ),
        Decimal("0"),
    )

    return {
        "open_positions": len(positions),
        "total_trades": len(trades),
        "invested_capital": float(
            _money(invested_capital)
        ),
        "realized_profit_loss": float(
            _money(realized_profit_loss)
        ),
        "total_charges": float(
            _money(total_charges)
        ),
    }
PY

echo
echo "==> Creating Ziidi Co-Pilot template"

cat > templates/ziidi_copilot.html <<'HTML'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >
    <title>MIP PRO — Ziidi Co-Pilot</title>

    <link
        rel="stylesheet"
        href="{{ url_for('static', filename='css/v115.css') }}"
    >

    <style>
        .ziidi-page {
            max-width: 1450px;
            margin: 0 auto;
            padding: 24px;
        }

        .ziidi-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 18px;
            margin-bottom: 24px;
            flex-wrap: wrap;
        }

        .ziidi-header h1 {
            margin: 0 0 8px;
        }

        .ziidi-header p {
            margin: 0;
            opacity: 0.75;
        }

        .ziidi-nav {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }

        .ziidi-nav a {
            text-decoration: none;
            padding: 10px 16px;
            border-radius: 10px;
            background: rgba(148, 163, 184, 0.14);
            color: inherit;
        }

        .ziidi-grid {
            display: grid;
            grid-template-columns:
                minmax(0, 1.1fr)
                minmax(320px, 0.9fr);
            gap: 22px;
            align-items: start;
        }

        .ziidi-card {
            background: var(--panel-bg, rgba(15, 23, 42, 0.76));
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 18px;
            padding: 22px;
            box-shadow: 0 18px 45px rgba(0, 0, 0, 0.14);
        }

        .ziidi-card h2 {
            margin-top: 0;
        }

        .trade-tabs {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-bottom: 20px;
        }

        .trade-tab {
            border: 0;
            border-radius: 12px;
            padding: 13px;
            cursor: pointer;
            font-weight: 800;
            background: rgba(148, 163, 184, 0.14);
            color: inherit;
        }

        .trade-tab.active[data-side="BUY"] {
            background: rgba(34, 197, 94, 0.22);
            color: #22c55e;
        }

        .trade-tab.active[data-side="SELL"] {
            background: rgba(239, 68, 68, 0.20);
            color: #ef4444;
        }

        .trade-form {
            display: none;
        }

        .trade-form.active {
            display: block;
        }

        .form-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 15px;
        }

        .form-field {
            display: flex;
            flex-direction: column;
            gap: 7px;
        }

        .form-field.full {
            grid-column: 1 / -1;
        }

        .form-field label {
            font-size: 0.86rem;
            font-weight: 750;
            opacity: 0.82;
        }

        .form-field input,
        .form-field textarea {
            width: 100%;
            box-sizing: border-box;
            border: 1px solid rgba(148, 163, 184, 0.28);
            border-radius: 10px;
            padding: 12px;
            background: rgba(15, 23, 42, 0.42);
            color: inherit;
        }

        .form-field textarea {
            min-height: 90px;
            resize: vertical;
        }

        .calculation-box {
            margin: 18px 0;
            padding: 16px;
            border-radius: 13px;
            background: rgba(59, 130, 246, 0.10);
            border: 1px solid rgba(59, 130, 246, 0.20);
        }

        .calculation-row {
            display: flex;
            justify-content: space-between;
            gap: 18px;
            padding: 6px 0;
        }

        .save-trade {
            width: 100%;
            border: 0;
            border-radius: 12px;
            padding: 14px;
            font-weight: 850;
            cursor: pointer;
            color: white;
        }

        .save-trade.buy {
            background: #16a34a;
        }

        .save-trade.sell {
            background: #dc2626;
        }

        .message {
            margin-bottom: 18px;
            padding: 13px 15px;
            border-radius: 12px;
        }

        .message.success {
            background: rgba(34, 197, 94, 0.14);
            border: 1px solid rgba(34, 197, 94, 0.3);
        }

        .message.error {
            background: rgba(239, 68, 68, 0.14);
            border: 1px solid rgba(239, 68, 68, 0.3);
        }

        .summary-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 12px;
            margin-bottom: 20px;
        }

        .summary-item {
            padding: 15px;
            border-radius: 13px;
            background: rgba(148, 163, 184, 0.10);
        }

        .summary-item span {
            display: block;
            font-size: 0.78rem;
            opacity: 0.7;
            margin-bottom: 6px;
        }

        .summary-item strong {
            font-size: 1.2rem;
        }

        .table-wrapper {
            overflow-x: auto;
        }

        .ziidi-table {
            width: 100%;
            border-collapse: collapse;
            min-width: 680px;
        }

        .ziidi-table th,
        .ziidi-table td {
            text-align: left;
            padding: 11px 9px;
            border-bottom: 1px solid rgba(148, 163, 184, 0.15);
            white-space: nowrap;
        }

        .trade-side {
            display: inline-flex;
            padding: 5px 9px;
            border-radius: 999px;
            font-weight: 800;
            font-size: 0.74rem;
        }

        .trade-side.buy {
            color: #22c55e;
            background: rgba(34, 197, 94, 0.14);
        }

        .trade-side.sell {
            color: #ef4444;
            background: rgba(239, 68, 68, 0.14);
        }

        .section-spacing {
            margin-top: 22px;
        }

        .empty-state {
            padding: 24px;
            text-align: center;
            opacity: 0.65;
        }

        @media (max-width: 950px) {
            .ziidi-grid {
                grid-template-columns: 1fr;
            }
        }

        @media (max-width: 640px) {
            .ziidi-page {
                padding: 14px;
            }

            .form-grid,
            .summary-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>

<body>
<main class="ziidi-page">
    <header class="ziidi-header">
        <div>
            <h1>Ziidi Investment Co-Pilot</h1>
            <p>
                Enter completed Ziidi trades exactly as executed.
                MIP PRO records and analyses them.
            </p>
        </div>

        <nav class="ziidi-nav">
            <a href="{{ url_for('dashboard') }}">Dashboard</a>
            <a href="/control-center">Control Center</a>
            <a href="{{ url_for('about') }}">About Us</a>
            <a href="{{ url_for('logout') }}">Logout</a>
        </nav>
    </header>

    {% if message %}
        <div class="message success">
            {{ message }}
        </div>
    {% endif %}

    {% if error %}
        <div class="message error">
            {{ error }}
        </div>
    {% endif %}

    <section class="ziidi-grid">
        <article class="ziidi-card">
            <h2>Record Ziidi Trade</h2>

            <div class="trade-tabs">
                <button
                    type="button"
                    class="trade-tab active"
                    data-side="BUY"
                >
                    BUY
                </button>

                <button
                    type="button"
                    class="trade-tab"
                    data-side="SELL"
                >
                    SELL
                </button>
            </div>

            {% for side in ["BUY", "SELL"] %}
            <form
                method="post"
                class="trade-form {% if side == 'BUY' %}active{% endif %}"
                data-form-side="{{ side }}"
                autocomplete="off"
            >
                <input
                    type="hidden"
                    name="side"
                    value="{{ side }}"
                >

                <div class="form-grid">
                    <div class="form-field">
                        <label>Stock symbol</label>
                        <input
                            name="symbol"
                            required
                            maxlength="20"
                            placeholder="KCB"
                        >
                    </div>

                    <div class="form-field">
                        <label>Company name</label>
                        <input
                            name="company_name"
                            maxlength="150"
                            placeholder="KCB Group"
                        >
                    </div>

                    <div class="form-field">
                        <label>
                            Executed {{ side|lower }} price
                        </label>
                        <input
                            name="executed_price"
                            class="js-price"
                            type="number"
                            min="0.0001"
                            step="0.0001"
                            required
                            placeholder="81.50"
                        >
                    </div>

                    <div class="form-field">
                        <label>Number of shares</label>
                        <input
                            name="quantity"
                            class="js-quantity"
                            type="number"
                            min="1"
                            step="1"
                            required
                            placeholder="100"
                        >
                    </div>

                    <div class="form-field">
                        <label>
                            {% if side == "BUY" %}
                                Cost of shares
                            {% else %}
                                Gross proceeds
                            {% endif %}
                        </label>
                        <input
                            name="gross_amount"
                            class="js-gross"
                            type="number"
                            min="0"
                            step="0.01"
                            placeholder="Calculated automatically"
                        >
                    </div>

                    <div class="form-field">
                        <label>Charges shown by Ziidi</label>
                        <input
                            name="charges"
                            class="js-charges"
                            type="number"
                            min="0"
                            step="0.01"
                            value="0.00"
                            required
                        >
                    </div>

                    <div class="form-field">
                        <label>
                            {% if side == "BUY" %}
                                Exact total paid
                            {% else %}
                                Exact net proceeds
                            {% endif %}
                        </label>
                        <input
                            name="net_amount"
                            class="js-net"
                            type="number"
                            min="0"
                            step="0.01"
                            placeholder="Enter exact Ziidi total"
                        >
                    </div>

                    <div class="form-field">
                        <label>Trade date</label>
                        <input
                            name="trade_date"
                            type="date"
                            required
                            value="{{ today }}"
                        >
                    </div>

                    <div class="form-field">
                        <label>Settlement date</label>
                        <input
                            name="settlement_date"
                            type="date"
                        >
                    </div>

                    <div class="form-field">
                        <label>Ziidi reference number</label>
                        <input
                            name="reference_number"
                            maxlength="100"
                            placeholder="Optional"
                        >
                    </div>

                    <div class="form-field full">
                        <label>Trade notes</label>
                        <textarea
                            name="notes"
                            maxlength="2000"
                            placeholder="Reason for trade or Ziidi confirmation notes"
                        ></textarea>
                    </div>
                </div>

                <div class="calculation-box">
                    <div class="calculation-row">
                        <span>
                            {% if side == "BUY" %}
                                Calculated share cost
                            {% else %}
                                Calculated gross proceeds
                            {% endif %}
                        </span>
                        <strong class="js-preview-gross">
                            KSh 0.00
                        </strong>
                    </div>

                    <div class="calculation-row">
                        <span>Charges</span>
                        <strong class="js-preview-charges">
                            KSh 0.00
                        </strong>
                    </div>

                    <div class="calculation-row">
                        <span>
                            {% if side == "BUY" %}
                                Estimated total
                            {% else %}
                                Estimated net proceeds
                            {% endif %}
                        </span>
                        <strong class="js-preview-net">
                            KSh 0.00
                        </strong>
                    </div>
                </div>

                <button
                    type="submit"
                    class="save-trade {{ side|lower }}"
                >
                    Save {{ side }} Trade
                </button>
            </form>
            {% endfor %}
        </article>

        <aside class="ziidi-card">
            <h2>Ziidi Portfolio Summary</h2>

            <div class="summary-grid">
                <div class="summary-item">
                    <span>Open Positions</span>
                    <strong>
                        {{ summary.open_positions }}
                    </strong>
                </div>

                <div class="summary-item">
                    <span>Total Trades</span>
                    <strong>
                        {{ summary.total_trades }}
                    </strong>
                </div>

                <div class="summary-item">
                    <span>Invested Capital</span>
                    <strong>
                        KSh {{ "%.2f"|format(summary.invested_capital) }}
                    </strong>
                </div>

                <div class="summary-item">
                    <span>Realized P/L</span>
                    <strong>
                        KSh {{ "%.2f"|format(summary.realized_profit_loss) }}
                    </strong>
                </div>

                <div class="summary-item">
                    <span>Total Charges</span>
                    <strong>
                        KSh {{ "%.2f"|format(summary.total_charges) }}
                    </strong>
                </div>
            </div>

            <h2>Current Positions</h2>

            {% if positions %}
            <div class="table-wrapper">
                <table class="ziidi-table">
                    <thead>
                        <tr>
                            <th>Symbol</th>
                            <th>Shares</th>
                            <th>Average Cost</th>
                            <th>Cost Basis</th>
                            <th>Realized P/L</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for position in positions %}
                        <tr>
                            <td>
                                <strong>{{ position.symbol }}</strong>
                            </td>
                            <td>{{ position.quantity }}</td>
                            <td>
                                KSh {{ "%.2f"|format(position.average_cost) }}
                            </td>
                            <td>
                                KSh {{ "%.2f"|format(position.cost_basis) }}
                            </td>
                            <td>
                                KSh {{ "%.2f"|format(position.realized_profit_loss) }}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% else %}
                <div class="empty-state">
                    No Ziidi positions recorded yet.
                </div>
            {% endif %}
        </aside>
    </section>

    <section class="ziidi-card section-spacing">
        <h2>Ziidi Trade History</h2>

        {% if trades %}
        <div class="table-wrapper">
            <table class="ziidi-table">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Side</th>
                        <th>Symbol</th>
                        <th>Shares</th>
                        <th>Price</th>
                        <th>Gross</th>
                        <th>Charges</th>
                        <th>Total / Net</th>
                        <th>Reference</th>
                    </tr>
                </thead>

                <tbody>
                    {% for trade in trades %}
                    <tr>
                        <td>{{ trade.trade_date }}</td>
                        <td>
                            <span class="trade-side {{ trade.side|lower }}">
                                {{ trade.side }}
                            </span>
                        </td>
                        <td><strong>{{ trade.symbol }}</strong></td>
                        <td>{{ trade.quantity }}</td>
                        <td>
                            KSh {{ "%.2f"|format(trade.executed_price) }}
                        </td>
                        <td>
                            KSh {{ "%.2f"|format(trade.gross_amount) }}
                        </td>
                        <td>
                            KSh {{ "%.2f"|format(trade.charges) }}
                        </td>
                        <td>
                            KSh {{ "%.2f"|format(trade.net_amount) }}
                        </td>
                        <td>
                            {{ trade.reference_number or "—" }}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% else %}
            <div class="empty-state">
                Your exact Ziidi transactions will appear here.
            </div>
        {% endif %}
    </section>
</main>

<script>
(function () {
    "use strict";

    const tabs = document.querySelectorAll(".trade-tab");
    const forms = document.querySelectorAll(".trade-form");

    function activateSide(side) {
        tabs.forEach((tab) => {
            tab.classList.toggle(
                "active",
                tab.dataset.side === side
            );
        });

        forms.forEach((form) => {
            form.classList.toggle(
                "active",
                form.dataset.formSide === side
            );
        });
    }

    tabs.forEach((tab) => {
        tab.addEventListener("click", () => {
            activateSide(tab.dataset.side);
        });
    });

    function numberValue(input) {
        const value = Number.parseFloat(input.value);
        return Number.isFinite(value) ? value : 0;
    }

    function money(value) {
        return new Intl.NumberFormat(
            "en-KE",
            {
                style: "currency",
                currency: "KES",
                minimumFractionDigits: 2
            }
        ).format(value);
    }

    forms.forEach((form) => {
        const side = form.dataset.formSide;
        const price = form.querySelector(".js-price");
        const quantity = form.querySelector(".js-quantity");
        const gross = form.querySelector(".js-gross");
        const charges = form.querySelector(".js-charges");
        const net = form.querySelector(".js-net");

        const previewGross =
            form.querySelector(".js-preview-gross");
        const previewCharges =
            form.querySelector(".js-preview-charges");
        const previewNet =
            form.querySelector(".js-preview-net");

        function calculate() {
            const calculatedGross =
                numberValue(price) * numberValue(quantity);

            const enteredGross = numberValue(gross);
            const effectiveGross =
                enteredGross > 0
                    ? enteredGross
                    : calculatedGross;

            const chargeValue = numberValue(charges);

            const calculatedNet =
                side === "BUY"
                    ? effectiveGross + chargeValue
                    : Math.max(
                        effectiveGross - chargeValue,
                        0
                    );

            previewGross.textContent =
                money(calculatedGross);

            previewCharges.textContent =
                money(chargeValue);

            previewNet.textContent =
                money(calculatedNet);

            if (!gross.dataset.manuallyEdited) {
                gross.placeholder =
                    calculatedGross.toFixed(2);
            }

            if (!net.dataset.manuallyEdited) {
                net.placeholder =
                    calculatedNet.toFixed(2);
            }
        }

        [price, quantity, charges].forEach((input) => {
            input.addEventListener("input", calculate);
        });

        gross.addEventListener("input", () => {
            gross.dataset.manuallyEdited =
                gross.value ? "true" : "";
            calculate();
        });

        net.addEventListener("input", () => {
            net.dataset.manuallyEdited =
                net.value ? "true" : "";
        });

        calculate();
    });
})();
</script>
</body>
</html>
HTML

echo
echo "==> Patching Flask application and dashboard"

"$PYTHON" - <<'PY'
from pathlib import Path
import re


app_path = Path("app.py")
dashboard_path = Path("templates/dashboard_v115.html")

app_text = app_path.read_text(encoding="utf-8")
dashboard_text = dashboard_path.read_text(encoding="utf-8")


IMPORT_MARKER = "# BEGIN MIP PRO ZIIDI COPILOT IMPORTS"
ROUTE_MARKER = "# BEGIN MIP PRO ZIIDI COPILOT ROUTES"


if IMPORT_MARKER not in app_text:
    import_block = """
# BEGIN MIP PRO ZIIDI COPILOT IMPORTS
from services.ziidi_copilot import (
    ZiidiTradeError,
    get_portfolio_summary as get_ziidi_portfolio_summary,
    get_positions as get_ziidi_positions,
    get_trade_history as get_ziidi_trade_history,
    init_ziidi_schema,
    record_trade as record_ziidi_trade,
)
# END MIP PRO ZIIDI COPILOT IMPORTS
"""

    insertion_patterns = [
        r"(?m)^(from flask import .+)$",
        r"(?m)^(import flask.*)$",
    ]

    inserted = False

    for pattern in insertion_patterns:
        match = re.search(pattern, app_text)

        if match:
            position = match.end()
            app_text = (
                app_text[:position]
                + "\n"
                + import_block
                + app_text[position:]
            )
            inserted = True
            break

    if not inserted:
        app_text = import_block + "\n" + app_text


if ROUTE_MARKER not in app_text:
    route_block = '''
# BEGIN MIP PRO ZIIDI COPILOT ROUTES
@app.route("/ziidi-copilot", methods=["GET", "POST"])
def ziidi_copilot():
    from datetime import date

    init_ziidi_schema()

    message = request.args.get("message", "").strip()
    error = ""

    if request.method == "POST":
        try:
            trade = record_ziidi_trade(
                request.form.to_dict()
            )

            return redirect(
                url_for(
                    "ziidi_copilot",
                    message=(
                        f'{trade["side"]} trade for '
                        f'{trade["quantity"]} '
                        f'{trade["symbol"]} shares saved.'
                    ),
                )
            )
        except ZiidiTradeError as exc:
            error = str(exc)
        except Exception as exc:
            app.logger.exception(
                "Ziidi trade recording failed"
            )
            error = (
                "The trade could not be saved. "
                f"Technical detail: {exc}"
            )

    return render_template(
        "ziidi_copilot.html",
        today=date.today().isoformat(),
        message=message,
        error=error,
        positions=get_ziidi_positions(),
        trades=get_ziidi_trade_history(limit=100),
        summary=get_ziidi_portfolio_summary(),
        version=VERSION,
    )


@app.route("/api/v12/ziidi/portfolio")
def api_v12_ziidi_portfolio():
    return jsonify(
        {
            "summary": get_ziidi_portfolio_summary(),
            "positions": get_ziidi_positions(),
        }
    )


@app.route("/api/v12/ziidi/trades")
def api_v12_ziidi_trades():
    return jsonify(
        {
            "trades": get_ziidi_trade_history(
                limit=200
            )
        }
    )
# END MIP PRO ZIIDI COPILOT ROUTES

'''

    route_anchor = re.search(
        r'(?m)^@app\.route\("/download_report"\)',
        app_text,
    )

    if not route_anchor:
        route_anchor = re.search(
            r'(?m)^if __name__\s*==\s*["\']__main__["\']',
            app_text,
        )

    if not route_anchor:
        raise SystemExit(
            "Could not locate a safe Flask route insertion point."
        )

    app_text = (
        app_text[:route_anchor.start()]
        + route_block
        + app_text[route_anchor.start():]
    )


# Add Ziidi menu link before Control Center where possible.
if 'href="/ziidi-copilot"' not in dashboard_text:
    control_pattern = re.compile(
        r'(?P<indent>[ \t]*)'
        r'<a(?P<attrs>[^>]*href=["\']/control-center["\'][^>]*)>'
        r'(?P<label>.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    control_match = control_pattern.search(dashboard_text)

    if not control_match:
        raise SystemExit(
            "Control Center menu link was not found."
        )

    indent = control_match.group("indent")
    ziidi_link = (
        f'{indent}<a href="/ziidi-copilot">'
        "Ziidi Co-Pilot</a>\n"
    )

    dashboard_text = (
        dashboard_text[:control_match.start()]
        + ziidi_link
        + dashboard_text[control_match.start():]
    )


# Place Control Center before About Us when both links exist.
control_match = re.search(
    r'(?P<control>[ \t]*<a[^>]*href=["\']/control-center["\'][^>]*>'
    r'.*?</a>)',
    dashboard_text,
    re.IGNORECASE | re.DOTALL,
)

about_match = re.search(
    r'(?P<about>[ \t]*<a[^>]*href=["\']/about["\'][^>]*>'
    r'.*?</a>)',
    dashboard_text,
    re.IGNORECASE | re.DOTALL,
)

if (
    control_match
    and about_match
    and control_match.start() > about_match.start()
):
    control_html = control_match.group("control")
    about_html = about_match.group("about")

    first_start = about_match.start()
    first_end = about_match.end()
    second_start = control_match.start()
    second_end = control_match.end()

    between = dashboard_text[first_end:second_start]

    dashboard_text = (
        dashboard_text[:first_start]
        + control_html
        + between
        + about_html
        + dashboard_text[second_end:]
    )


# Remove the dashboard report card but preserve menu Reports link.
report_card_pattern = re.compile(
    r'\s*<article\s+class=["\'][^"\']*\breport-card\b[^"\']*["\']\s*>'
    r'.*?Daily Intelligence Report.*?</article>\s*',
    re.IGNORECASE | re.DOTALL,
)

dashboard_text, report_count = report_card_pattern.subn(
    "\n",
    dashboard_text,
    count=1,
)

if report_count == 0:
    print(
        "NOTICE: Report card was not found or was already removed."
    )
else:
    print("Dashboard report card removed.")


app_path.write_text(app_text, encoding="utf-8")
dashboard_path.write_text(
    dashboard_text,
    encoding="utf-8",
)

print("Flask and dashboard patches completed.")
PY

echo
echo "==> Initialising Ziidi database"

"$PYTHON" - <<'PY'
from services.ziidi_copilot import (
    get_portfolio_summary,
    init_ziidi_schema,
)

init_ziidi_schema()
print("Ziidi schema created.")
print("Summary:", get_portfolio_summary())
PY

echo
echo "==> Compiling Python modules"

"$PYTHON" -m py_compile \
    app.py \
    services/ziidi_copilot.py

echo "PYTHON COMPILATION: PASS"

echo
echo "==> Validating Flask routes"

"$PYTHON" - <<'PY'
from app import app

required_routes = {
    "/ziidi-copilot",
    "/api/v12/ziidi/portfolio",
    "/api/v12/ziidi/trades",
}

registered_routes = {
    rule.rule
    for rule in app.url_map.iter_rules()
}

missing = required_routes - registered_routes

if missing:
    raise SystemExit(
        f"Missing routes: {sorted(missing)}"
    )

print("FLASK ROUTE TEST: PASS")

with app.test_request_context("/ziidi-copilot"):
    template = app.jinja_env.get_template(
        "ziidi_copilot.html"
    )

    rendered = template.render(
        today="2026-07-17",
        message="",
        error="",
        positions=[],
        trades=[],
        summary={
            "open_positions": 0,
            "total_trades": 0,
            "invested_capital": 0,
            "realized_profit_loss": 0,
            "total_charges": 0,
        },
        version="12.0",
    )

    if "Ziidi Investment Co-Pilot" not in rendered:
        raise SystemExit(
            "Ziidi template validation failed."
        )

print("ZIIDI TEMPLATE TEST: PASS")
PY

echo
echo "==> Verifying dashboard changes"

grep -n 'href="/ziidi-copilot"' \
    templates/dashboard_v115.html

if grep -q "Daily Intelligence Report" \
    templates/dashboard_v115.html
then
    echo "WARNING: Daily report text still exists somewhere."
else
    echo "DASHBOARD REPORT CARD REMOVAL: PASS"
fi

echo
echo "==> Checking SQLite integrity"

"$PYTHON" - <<'PY'
import sqlite3
from services.database import DB_PATH

with sqlite3.connect(DB_PATH) as connection:
    result = connection.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]

print("SQLITE INTEGRITY:", result)

if result != "ok":
    raise SystemExit(
        "SQLite integrity check failed."
    )
PY

echo
echo "==> Restarting application service"

sudo systemctl restart nse-v10-3.service
sleep 5

sudo systemctl is-active --quiet \
    nse-v10-3.service

echo "SERVICE STATUS: active"

echo
echo "==> Checking listening port"

sudo ss -lntp | grep ':5000'

echo
echo "==> Testing protected Ziidi page"

ZIIDI_STATUS="$(
    curl -sS \
        -o /dev/null \
        -w '%{http_code}' \
        --max-time 10 \
        http://127.0.0.1:5000/ziidi-copilot
)"

echo "/ziidi-copilot -> HTTP $ZIIDI_STATUS"

case "$ZIIDI_STATUS" in
    200|302)
        echo "ZIIDI HTTP TEST: PASS"
        ;;
    *)
        echo "ZIIDI HTTP TEST: FAIL"
        sudo journalctl \
            -u nse-v10-3.service \
            --since "3 minutes ago" \
            --no-pager \
            -l
        exit 1
        ;;
esac

echo
echo "==> Recent service errors"

if sudo journalctl \
    -u nse-v10-3.service \
    --since "3 minutes ago" \
    --no-pager \
    -l \
    | grep -Ei \
        'traceback|worker failed|exception|syntaxerror'
then
    echo "SERVICE LOG CHECK: FAIL"
    exit 1
else
    echo "SERVICE LOG CHECK: PASS"
fi

echo
echo "======================================================"
echo "Ziidi Co-Pilot Stage 1: COMPLETE"
echo "======================================================"
echo
echo "Open:"
echo "http://164.92.133.0/ziidi-copilot"
echo
echo "Backup:"
echo "$BACKUP_DIR"
