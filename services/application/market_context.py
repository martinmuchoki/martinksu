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

        self._market_cache: Optional[Dict[str, Any]] = None
        self._technicals_cache: Optional[Any] = None
        self._risk_cache: Optional[Any] = None
        self._regime_cache: Optional[Any] = None
        self._sector_rotation_cache: Optional[Any] = None



    def _market(self) -> Dict[str, Any]:
        """Return one market snapshot for this builder instance."""

        if self._market_cache is None:
            self._market_cache = get_market_snapshot()

        return self._market_cache

    def _stocks(self) -> Any:
        """Return normalized stock records from the market snapshot."""

        return self._market().get("stocks", [])

    def _technicals(self) -> Any:
        """Return technical analysis, computed once per context."""

        if self._technicals_cache is None:
            try:
                self._technicals_cache = analyze_market(
                    self._stocks()
                )
            except Exception as exc:
                self.logger.exception(
                    "Technical analysis failed: %s",
                    exc,
                )
                self._technicals_cache = []

        return self._technicals_cache

    def _risk(self) -> Any:
        """Return market risk metrics, computed once per context."""

        if self._risk_cache is None:
            self._risk_cache = build_market_risk(
                self._stocks()
            )

        return self._risk_cache

    def _regime(self) -> Any:
        """Return market regime, computed once per context."""

        if self._regime_cache is None:
            self._regime_cache = detect_market_regime(
                self._market(),
                self._technicals(),
                self._risk(),
            )

        return self._regime_cache

    def _sector_rotation(self) -> Any:
        """Return sector rotation, computed once per context."""

        if self._sector_rotation_cache is None:
            self._sector_rotation_cache = (
                analyze_sector_rotation(
                    self._stocks()
                )
            )

        return self._sector_rotation_cache

    def market_snapshot(self) -> Dict[str, Any]:
        """Return the canonical live market snapshot."""

        return self._market()

    def technical_analysis(self) -> Any:
        """Return market-wide technical analysis."""

        return self._technicals()

    def predictions(self, *, limit: int = 20) -> Any:
        """Return predictions while preserving the route limit."""

        normalized_limit = max(int(limit or 0), 0)

        return build_predictions(
            self._stocks(),
            self._technicals(),
            limit=normalized_limit,
        )

    def market_risk(self) -> Any:
        """Return market-wide risk intelligence."""

        return self._risk()

    def market_regime(self) -> Any:
        """Return the detected market regime."""

        return self._regime()

    def sector_rotation(self) -> Any:
        """Return sector rotation intelligence."""

        return self._sector_rotation()
    def build_decision_context(self) -> Dict[str, Any]:
        """Build only the market intelligence required for decisions."""

        market = self._market()
        technicals = self._technicals()
        risk_metrics = self._risk()
        regime = self._regime()
        sector_rotation = self._sector_rotation()

        return {
            "market": market,
            "technicals": technicals,
            "risk_metrics": risk_metrics,
            "regime": regime,
            "sector_rotation": sector_rotation,
        }
    def build(
        self,
        *,
        optimizer_capital: float = 100000,
    ) -> Dict[str, Any]:
        """Build market, technical, risk and prediction intelligence."""

        screener = run_screener()
        market = self._market()
        stocks = self._stocks()
        technicals = self._technicals()
        risk_metrics = self._risk()
        regime = self._regime()
        sector_rotation = self._sector_rotation()

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
