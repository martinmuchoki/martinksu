"""Dashboard application-context orchestration.

This module assembles the complete context consumed by the MIP dashboards.
HTTP routing and HTML rendering remain in app.py.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from services.ai_committee import run_committee
from services.autonomous_assistant import autonomous_decision
from services.dashboard_charts import get_market_breadth
from services.dashboard_engine import build_dashboard
from services.decision_engine import get_ai_decision
from services.learning_engine import get_learning_summary
from services.market_data import get_market_snapshot
from services.performance_engine import (
    evaluate_recommendations,
    get_performance_summary,
)
from services.portfolio import get_portfolio
from services.portfolio_optimizer import build_optimized_portfolio
from services.portfolio_transactions import (
    get_cash_summary,
    get_transactions,
)
from services.predictive_engine import build_predictions
from services.quant_intelligence import (
    analyze_sector_rotation,
    detect_market_regime,
)
from services.risk_engine import build_market_risk
from services.screener_engine import run_screener
from services.signal_service import get_signal_service
from services.technical_analysis import analyze_market
from services.telegram_bot import telegram_status
from services.ziidi_copilot import (
    get_portfolio_summary as get_ziidi_portfolio_summary,
)


class DashboardContextBuilder:
    """Build the complete, presentation-ready dashboard context."""

    def __init__(
        self,
        *,
        version: str,
        logger: Optional[logging.Logger] = None,
        project_root: Optional[Path] = None,
    ) -> None:
        self.version = version
        self.logger = logger or logging.getLogger(__name__)
        self.project_root = project_root or Path(__file__).resolve().parents[1]

    def build(self, ui: Optional[str] = None) -> Dict[str, Any]:
        """Return the selected template and its complete rendering context."""

        dashboard_data = build_dashboard()
        screener = run_screener()
        market = get_market_snapshot()

        try:
            technicals = analyze_market(market["stocks"])
        except Exception as exc:
            self.logger.exception(
                "Technical analysis skipped during dashboard rendering: %s",
                exc,
            )
            technicals = []

        portfolio = get_portfolio()

        committee = run_committee(
            market=market,
            technicals=technicals,
            portfolio=portfolio,
        )

        assistant = autonomous_decision(
            market,
            committee,
            portfolio,
            technicals,
        )

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

        logo_available = (
            self.project_root
            / "static"
            / "images"
            / "mip_pro_logo.png"
        ).exists()

        evaluate_recommendations()
        performance = get_performance_summary()

        learning = get_learning_summary(
            evaluate_first=False,
        )

        optimizer_capital = max(
            float(cash_summary.get("cash_balance", 0) or 0),
            100000,
        )

        optimized_portfolio = build_optimized_portfolio(
            screener,
            capital=optimizer_capital,
        )

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

        (
            persisted_signals,
            persisted_signal_summary,
        ) = self._build_signal_context()

        persisted_top_signal = (
            persisted_signals[0]
            if persisted_signals
            else None
        )

        decision = self._build_ai_decision(
            persisted_signals=persisted_signals,
            persisted_signal_summary=persisted_signal_summary,
            regime=regime,
            risk_metrics=risk_metrics,
            sector_rotation=sector_rotation,
        )

        template_name = (
            "dashboard_v117.html"
            if ui == "v117"
            else "dashboard_v115.html"
        )

        context = {
            "version": self.version,
            "dashboard": dashboard_data,
            "picks": dashboard_data["top_picks"],
            "market": market,
            "technicals": technicals,
            "committee": committee,
            "assistant": assistant,
            "portfolio": portfolio,
            "screener": screener,
            "telegram_status": telegram_status(),
            "now": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "system_status": "Online",
            "transactions": transactions,
            "cash_summary": cash_summary,
            "portfolio_return": portfolio_return,
            "summary": ziidi_summary,
            "logo_available": logo_available,
            "performance": performance,
            "learning": learning,
            "optimized_portfolio": optimized_portfolio,
            "risk_metrics": risk_metrics,
            "regime": regime,
            "sector_rotation": sector_rotation,
            "predictions": predictions,
            "persisted_signals": persisted_signals,
            "persisted_top_signal": persisted_top_signal,
            "persisted_signal_summary": persisted_signal_summary,
            "decision": decision,
        }

        return {
            "template_name": template_name,
            "data": context,
        }

    def _build_signal_context(self) -> tuple[list[Any], Dict[str, Any]]:
        """Read finalized committee decisions without blocking rendering."""

        try:
            signal_service = get_signal_service()

            persisted_signals = signal_service.get_top_signals(
                limit=10,
            )

            persisted_signal_summary = (
                signal_service.get_dashboard_summary(limit=10)
            )

            return persisted_signals, persisted_signal_summary

        except Exception:
            self.logger.exception(
                "Dashboard SignalService read failed"
            )

            return [], {
                "available": False,
                "signal_count": 0,
                "history_count": 0,
                "average_committee_score": 0,
                "average_confidence": 0,
                "decision_counts": {},
                "signals": [],
                "top_signal": None,
            }

    def _build_ai_decision(
        self,
        *,
        persisted_signals: list[Any],
        persisted_signal_summary: Dict[str, Any],
        regime: Any,
        risk_metrics: Any,
        sector_rotation: Any,
    ) -> Dict[str, Any]:
        """Build the authoritative Version 11.7 dashboard decision."""

        try:
            market_breadth = get_market_breadth()

            regime_label = (
                regime.get(
                    "label",
                    regime.get(
                        "regime",
                        regime.get(
                            "market_regime",
                            "Neutral / Selective",
                        ),
                    ),
                )
                if isinstance(regime, dict)
                else str(regime or "Neutral / Selective")
            )

            return get_ai_decision(
                signals=persisted_signals,
                market={
                    "status": regime_label,
                    "ai_confidence": (
                        persisted_signal_summary.get(
                            "average_confidence",
                            0,
                        )
                    ),
                },
                regime=(
                    regime
                    if isinstance(regime, dict)
                    else {
                        "label": str(
                            regime or "Neutral / Selective"
                        )
                    }
                ),
                risk_metrics=(
                    risk_metrics
                    if isinstance(risk_metrics, dict)
                    else {
                        "risk_level": str(
                            risk_metrics or "UNKNOWN"
                        )
                    }
                ),
                breadth=market_breadth,
                institutional=(
                    sector_rotation
                    if isinstance(sector_rotation, dict)
                    else {}
                ),
            )

        except Exception:
            self.logger.exception(
                "AI Decision Engine failed during dashboard rendering"
            )

            return {
                "market_state": "Unavailable",
                "market_risk": "UNKNOWN",
                "decision": "WAIT",
                "decision_label": "WAIT",
                "decision_headline": (
                    "Decision intelligence is temporarily unavailable."
                ),
                "decision_reason": [
                    (
                        "The Decision Engine could not process "
                        "the current market data."
                    )
                ],
                "confidence": 0,
                "qualified_opportunities": [],
                "qualified_count": 0,
                "leading_signal": None,
                "breadth": {},
                "institutional": {},
                "thresholds": {},
            }
