from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from services.database import DB_PATH
from services.investment_settings import get_settings


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



def _calculate_settlement_date(
    trade_date_value: str,
    settlement_rule: str,
) -> str:
    """
    Calculate settlement using business days.

    T+0 settles on the trade date.
    T+1, T+2 and T+3 skip Saturdays and Sundays.

    NSE public holidays are not yet excluded.
    """
    trade_day = date.fromisoformat(trade_date_value)

    rule = str(settlement_rule or "T+3").strip().upper()

    settlement_days = {
        "T+0": 0,
        "T+1": 1,
        "T+2": 2,
        "T+3": 3,
    }.get(rule)

    if settlement_days is None:
        raise ZiidiTradeError(
            "Settlement rule must be T+0, T+1, T+2, or T+3."
        )

    settlement_day = trade_day
    completed_days = 0

    while completed_days < settlement_days:
        settlement_day += timedelta(days=1)

        if settlement_day.weekday() < 5:
            completed_days += 1

    return settlement_day.isoformat()


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

    settings = get_settings()

    charge_rate = Decimal(
        str(settings.get("charge_rate", 0) or 0)
    )

    auto_calculate = bool(
        settings.get("auto_calculate", 1)
    )

    manual_override = bool(
        settings.get("manual_override", 0)
    )

    settlement_rule = str(
        settings.get("settlement", "T+3") or "T+3"
    ).strip().upper()

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

    submitted_charges = str(
        payload.get("charges", "") or ""
    ).strip()

    use_manual_charges = (
        manual_override and bool(submitted_charges)
    )

    if auto_calculate and not use_manual_charges:
        if charge_rate < 0:
            raise ZiidiTradeError(
                "Configured charge rate cannot be negative."
            )

        charges = _money(
            gross_amount
            * charge_rate
            / Decimal("100")
        )
    else:
        charges = _money(
            _decimal(
                submitted_charges or 0,
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

    submitted_settlement_date = _normalise_date(
        payload.get("settlement_date"),
        "Settlement date",
        required=False,
    )

    if manual_override and submitted_settlement_date:
        settlement_date = submitted_settlement_date
    else:
        settlement_date = _calculate_settlement_date(
            trade_date,
            settlement_rule,
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
