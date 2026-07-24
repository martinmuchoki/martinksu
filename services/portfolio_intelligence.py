"""
MIP PRO v12.1
Portfolio Intelligence Engine

Combines:
- Ziidi Co-Pilot portfolio positions
- Live NSE market prices
- Portfolio valuation and performance analytics
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from services.market_data import get_market_snapshot
from services.ziidi_copilot import (
    get_portfolio_summary,
    get_positions,
)


MONEY_PLACES = Decimal("0.01")
PERCENT_PLACES = Decimal("0.01")


def _decimal(value: Any, default: str = "0") -> Decimal:
    """Safely convert values to Decimal."""
    if value is None:
        return Decimal(default)

    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _money(value: Any) -> Decimal:
    """Round monetary values to two decimal places."""
    return _decimal(value).quantize(
        MONEY_PLACES,
        rounding=ROUND_HALF_UP,
    )


def _percent(value: Any) -> Decimal:
    """Round percentage values to two decimal places."""
    return _decimal(value).quantize(
        PERCENT_PLACES,
        rounding=ROUND_HALF_UP,
    )


def _normalise_symbol(value: Any) -> str:
    """Normalise an NSE trading symbol."""
    return str(value or "").strip().upper()


def _build_market_index(
    stocks: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Create a symbol-indexed live market lookup."""
    market_index: dict[str, dict[str, Any]] = {}

    for stock in stocks:
        if not isinstance(stock, dict):
            continue

        symbol = _normalise_symbol(stock.get("symbol"))

        if not symbol:
            continue

        market_index[symbol] = stock

    return market_index


def _calculate_holding(
    position: dict[str, Any],
    market_stock: dict[str, Any] | None,
) -> dict[str, Any]:
    """Calculate live intelligence for one portfolio holding."""
    symbol = _normalise_symbol(position.get("symbol"))
    quantity = int(position.get("quantity") or 0)

    average_cost = _money(position.get("average_cost"))
    cost_basis = _money(position.get("cost_basis"))
    realized_pl = _money(
        position.get("realized_profit_loss")
    )

    market_stock = market_stock or {}

    live_price = _money(market_stock.get("price"))
    previous_close = _money(
        market_stock.get("previous_close")
    )

    has_live_price = live_price > 0

    market_value = (
        _money(live_price * quantity)
        if has_live_price
        else Decimal("0.00")
    )

    unrealized_pl = (
        _money(market_value - cost_basis)
        if has_live_price
        else Decimal("0.00")
    )

    unrealized_pct = (
        _percent(
            unrealized_pl
            / cost_basis
            * Decimal("100")
        )
        if has_live_price and cost_basis > 0
        else Decimal("0.00")
    )

    daily_price_change = (
        _money(live_price - previous_close)
        if has_live_price and previous_close > 0
        else Decimal("0.00")
    )

    daily_pl = _money(
        daily_price_change * quantity
    )

    daily_change_pct = (
        _percent(
            daily_price_change
            / previous_close
            * Decimal("100")
        )
        if previous_close > 0
        else _percent(
            market_stock.get("change_pct")
        )
    )

    total_pl = _money(
        unrealized_pl + realized_pl
    )

    total_return_pct = (
        _percent(
            total_pl
            / cost_basis
            * Decimal("100")
        )
        if cost_basis > 0
        else Decimal("0.00")
    )

    return {
        "symbol": symbol,
        "company_name": (
            position.get("company_name")
            or market_stock.get("name")
            or symbol
        ),
        "quantity": quantity,
        "shares": quantity,
        "average_cost": float(average_cost),
        "cost_basis": float(cost_basis),
        "live_price": (
            float(live_price)
            if has_live_price
            else None
        ),
        "previous_close": (
            float(previous_close)
            if previous_close > 0
            else None
        ),
        "market_value": float(market_value),
        "unrealized_profit_loss": float(
            unrealized_pl
        ),
        "unrealized_return_pct": float(
            unrealized_pct
        ),
        "realized_profit_loss": float(
            realized_pl
        ),
        "total_profit_loss": float(total_pl),
        "total_return_pct": float(
            total_return_pct
        ),
        "daily_price_change": float(
            daily_price_change
        ),
        "daily_change_pct": float(
            daily_change_pct
        ),
        "daily_profit_loss": float(daily_pl),
        "volume": int(
            _decimal(market_stock.get("volume"))
        ),
        "sector": (
            market_stock.get("sector")
            or "Unknown"
        ),
        "currency": (
            market_stock.get("currency")
            or "KES"
        ),
        "market_source": market_stock.get(
            "source"
        ),
        "market_updated_at": market_stock.get(
            "updated_at"
        ),
        "price_status": (
            "LIVE"
            if has_live_price
            else "MISSING"
        ),
        "buy_count": int(
            position.get("buy_count") or 0
        ),
        "sell_count": int(
            position.get("sell_count") or 0
        ),
    }


def get_portfolio_intelligence() -> dict[str, Any]:
    """
    Return complete live portfolio intelligence.

    This function does not modify trades or portfolio records.
    """
    positions = get_positions()
    ledger_summary = get_portfolio_summary()
    market = get_market_snapshot()

    stocks = market.get("stocks", [])

    if not isinstance(stocks, list):
        stocks = []

    market_index = _build_market_index(stocks)

    holdings = [
        _calculate_holding(
            position,
            market_index.get(
                _normalise_symbol(
                    position.get("symbol")
                )
            ),
        )
        for position in positions
    ]

    total_cost_basis = sum(
        (
            _decimal(item["cost_basis"])
            for item in holdings
        ),
        Decimal("0"),
    )

    total_market_value = sum(
        (
            _decimal(item["market_value"])
            for item in holdings
        ),
        Decimal("0"),
    )

    total_unrealized_pl = sum(
        (
            _decimal(
                item["unrealized_profit_loss"]
            )
            for item in holdings
        ),
        Decimal("0"),
    )

    total_daily_pl = sum(
        (
            _decimal(
                item["daily_profit_loss"]
            )
            for item in holdings
        ),
        Decimal("0"),
    )

    total_realized_pl = _decimal(
        ledger_summary.get(
            "realized_profit_loss"
        )
    )

    total_profit_loss = _money(
        total_unrealized_pl + total_realized_pl
    )

    portfolio_return_pct = (
        _percent(
            total_profit_loss
            / total_cost_basis
            * Decimal("100")
        )
        if total_cost_basis > 0
        else Decimal("0.00")
    )

    previous_portfolio_value = _money(
        total_market_value - total_daily_pl
    )

    daily_return_pct = (
        _percent(
            total_daily_pl
            / previous_portfolio_value
            * Decimal("100")
        )
        if previous_portfolio_value > 0
        else Decimal("0.00")
    )

    priced_holdings = [
        item
        for item in holdings
        if item["price_status"] == "LIVE"
    ]

    missing_price_symbols = [
        item["symbol"]
        for item in holdings
        if item["price_status"] == "MISSING"
    ]

    best_performer = (
        max(
            priced_holdings,
            key=lambda item: item[
                "unrealized_return_pct"
            ],
        )
        if priced_holdings
        else None
    )

    worst_performer = (
        min(
            priced_holdings,
            key=lambda item: item[
                "unrealized_return_pct"
            ],
        )
        if priced_holdings
        else None
    )

    sector_exposure: dict[str, Decimal] = {}

    for holding in holdings:
        sector = str(
            holding.get("sector") or "Unknown"
        )

        sector_exposure[sector] = (
            sector_exposure.get(
                sector,
                Decimal("0"),
            )
            + _decimal(
                holding.get("market_value")
            )
        )

    sector_breakdown = []

    for sector, value in sorted(
        sector_exposure.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        weight = (
            _percent(
                value
                / total_market_value
                * Decimal("100")
            )
            if total_market_value > 0
            else Decimal("0.00")
        )

        sector_breakdown.append(
            {
                "sector": sector,
                "market_value": float(
                    _money(value)
                ),
                "weight_pct": float(weight),
            }
        )

    holdings.sort(
        key=lambda item: item["market_value"],
        reverse=True,
    )

    return {
        "generated_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "market_generated_at": market.get(
            "generated_at"
        ),
        "market_provider": market.get(
            "provider"
        ),
        "market_status": market.get(
            "market_status"
        ),
        "security_count": market.get(
            "security_count",
            len(stocks),
        ),
        "summary": {
            "open_positions": len(holdings),
            "total_trades": int(
                ledger_summary.get(
                    "total_trades",
                    0,
                )
            ),
            "invested_capital": float(
                _money(total_cost_basis)
            ),
            "portfolio_value": float(
                _money(total_market_value)
            ),
            "unrealized_profit_loss": float(
                _money(total_unrealized_pl)
            ),
            "realized_profit_loss": float(
                _money(total_realized_pl)
            ),
            "total_profit_loss": float(
                total_profit_loss
            ),
            "portfolio_return_pct": float(
                portfolio_return_pct
            ),
            "daily_profit_loss": float(
                _money(total_daily_pl)
            ),
            "daily_return_pct": float(
                daily_return_pct
            ),
            "total_charges": float(
                _money(
                    ledger_summary.get(
                        "total_charges",
                        0,
                    )
                )
            ),
            "priced_positions": len(
                priced_holdings
            ),
            "missing_price_count": len(
                missing_price_symbols
            ),
        },
        "holdings": holdings,
        "sector_exposure": sector_breakdown,
        "best_performer": best_performer,
        "worst_performer": worst_performer,
        "warnings": {
            "missing_price_symbols": (
                missing_price_symbols
            ),
            "has_missing_prices": bool(
                missing_price_symbols
            ),
        },
    }
