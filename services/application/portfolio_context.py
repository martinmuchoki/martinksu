"""Reusable portfolio application context."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from services.learning_engine import get_learning_summary
from services.performance_engine import (
    evaluate_recommendations,
    get_performance_summary,
)
from services.portfolio import get_portfolio
from services.portfolio_transactions import (
    get_cash_summary,
    get_transactions,
)
from services.ziidi_copilot import (
    get_portfolio_summary as get_ziidi_portfolio_summary,
)


class PortfolioContextBuilder:
    """Build portfolio, capital and performance intelligence."""

    def __init__(
        self,
        *,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)

    def build(self) -> Dict[str, Any]:
        """Build the canonical portfolio context."""

        portfolio = get_portfolio()
        transactions = get_transactions(20)
        cash_summary = get_cash_summary()
        ziidi_summary = get_ziidi_portfolio_summary()

        invested_capital = float(
            ziidi_summary.get("invested_capital", 0) or 0
        )

        if isinstance(portfolio, dict):
            current_market_value = float(
                portfolio.get("total_value", 0) or 0
            )
        else:
            current_market_value = float(
                getattr(portfolio, "total_value", 0) or 0
            )

        cash_summary["portfolio_value"] = current_market_value
        cash_summary["invested_capital"] = invested_capital
        cash_summary["unrealized_gain"] = (
            current_market_value - invested_capital
        )

        portfolio_return = (
            (
                current_market_value - invested_capital
            )
            / invested_capital
            * 100
            if invested_capital > 0
            else 0.0
        )

        evaluate_recommendations()

        performance = get_performance_summary()

        learning = get_learning_summary(
            evaluate_first=False,
        )

        optimizer_capital = max(
            float(cash_summary.get("cash_balance", 0) or 0),
            100000,
        )

        return {
            "portfolio": portfolio,
            "transactions": transactions,
            "cash_summary": cash_summary,
            "portfolio_return": portfolio_return,
            "summary": ziidi_summary,
            "performance": performance,
            "learning": learning,
            "optimizer_capital": optimizer_capital,
        }
