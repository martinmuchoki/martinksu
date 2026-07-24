"""Dashboard application-context composition.

The dashboard builder composes reusable market, portfolio and decision
contexts while preserving the established template contract.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from services.application.decision_context import (
    DecisionContextBuilder,
)
from services.application.market_context import (
    MarketContextBuilder,
)
from services.application.portfolio_context import (
    PortfolioContextBuilder,
)
from services.dashboard_engine import build_dashboard
from services.telegram_bot import telegram_status


class DashboardContextBuilder:
    """Compose all reusable contexts for dashboard rendering."""

    def __init__(
        self,
        *,
        version: str,
        logger: Optional[logging.Logger] = None,
        project_root: Optional[Path] = None,
    ) -> None:
        self.version = version
        self.logger = logger or logging.getLogger(__name__)
        self.project_root = (
            project_root
            or Path(__file__).resolve().parents[1]
        )

    def build(
        self,
        ui: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return the template and its complete rendering context."""

        dashboard_data = build_dashboard()

        portfolio_context = PortfolioContextBuilder(
            logger=self.logger,
        ).build()

        market_context = MarketContextBuilder(
            logger=self.logger,
        ).build(
            optimizer_capital=portfolio_context[
                "optimizer_capital"
            ],
        )

        decision_context = DecisionContextBuilder(
            logger=self.logger,
        ).build(
            market_context=market_context,
            portfolio_context=portfolio_context,
        )

        logo_available = (
            self.project_root
            / "static"
            / "images"
            / "mip_pro_logo.png"
        ).exists()

        template_name = (
            "dashboard_v117.html"
            if ui == "v117"
            else "dashboard_v115.html"
        )

        context = {
            "version": self.version,
            "dashboard": dashboard_data,
            "picks": dashboard_data["top_picks"],
            "market": market_context["market"],
            "technicals": market_context["technicals"],
            "committee": decision_context["committee"],
            "assistant": decision_context["assistant"],
            "portfolio": portfolio_context["portfolio"],
            "screener": market_context["screener"],
            "telegram_status": telegram_status(),
            "now": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "system_status": "Online",
            "transactions": portfolio_context["transactions"],
            "cash_summary": portfolio_context["cash_summary"],
            "portfolio_return": portfolio_context[
                "portfolio_return"
            ],
            "summary": portfolio_context["summary"],
            "logo_available": logo_available,
            "performance": portfolio_context["performance"],
            "learning": portfolio_context["learning"],
            "optimized_portfolio": market_context[
                "optimized_portfolio"
            ],
            "risk_metrics": market_context["risk_metrics"],
            "regime": market_context["regime"],
            "sector_rotation": market_context[
                "sector_rotation"
            ],
            "predictions": market_context["predictions"],
            "persisted_signals": decision_context[
                "persisted_signals"
            ],
            "persisted_top_signal": decision_context[
                "persisted_top_signal"
            ],
            "persisted_signal_summary": decision_context[
                "persisted_signal_summary"
            ],
            "decision": decision_context["decision"],
        }

        return {
            "template_name": template_name,
            "data": context,
        }
