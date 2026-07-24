"""Reusable market intelligence application context."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from services.market_data import get_market_snapshot
from services.portfolio_optimizer import build_optimized_portfolio
from services.predictive_engine import build_predictions
from services.quant_intelligence import (
    analyze_sector_rotation,
    detect_market_regime,
)
from services.risk_engine import build_market_risk
from services.screener_engine import run_screener
from services.technical_analysis import analyze_market


class MarketContextBuilder:
    """Build canonical market intelligence for all consumers."""

    def __init__(
        self,
        *,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)

    def build(
        self,
        *,
        optimizer_capital: float = 100000,
    ) -> Dict[str, Any]:
        """Build market, technical, risk and prediction intelligence."""

        screener = run_screener()
        market = get_market_snapshot()

        try:
            technicals = analyze_market(
                market.get("stocks", [])
            )
        except Exception as exc:
            self.logger.exception(
                "Technical analysis failed: %s",
                exc,
            )
            technicals = []

        stocks = market.get("stocks", [])

        risk_metrics = build_market_risk(stocks)

        regime = detect_market_regime(
            market,
            technicals,
            risk_metrics,
        )

        sector_rotation = analyze_sector_rotation(stocks)

        predictions = build_predictions(
            stocks,
            technicals,
            limit=len(stocks),
        )

        optimized_portfolio = build_optimized_portfolio(
            screener,
            capital=max(float(optimizer_capital or 0), 100000),
        )

        return {
            "market": market,
            "technicals": technicals,
            "screener": screener,
            "risk_metrics": risk_metrics,
            "regime": regime,
            "sector_rotation": sector_rotation,
            "predictions": predictions,
            "optimized_portfolio": optimized_portfolio,
        }
