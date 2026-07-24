"""Reusable investment decision application context."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from services.ai_committee import run_committee
from services.autonomous_assistant import autonomous_decision
from services.dashboard_charts import get_market_breadth
from services.decision_engine import get_ai_decision
from services.signal_service import get_signal_service


class DecisionContextBuilder:
    """Build committee, signal and AI decision intelligence."""

    def __init__(
        self,
        *,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)

    def build(
        self,
        *,
        market_context: Dict[str, Any],
        portfolio_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build investment decisions from canonical contexts."""

        market = market_context["market"]
        technicals = market_context["technicals"]
        portfolio = portfolio_context["portfolio"]

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
            regime=market_context["regime"],
            risk_metrics=market_context["risk_metrics"],
            sector_rotation=market_context["sector_rotation"],
        )

        return {
            "committee": committee,
            "assistant": assistant,
            "persisted_signals": persisted_signals,
            "persisted_top_signal": persisted_top_signal,
            "persisted_signal_summary": persisted_signal_summary,
            "decision": decision,
        }

    def _build_signal_context(
        self,
    ) -> tuple[list[Any], Dict[str, Any]]:
        """Read finalized committee decisions safely."""

        try:
            signal_service = get_signal_service()

            persisted_signals = signal_service.get_top_signals(
                limit=10,
            )

            persisted_signal_summary = (
                signal_service.get_dashboard_summary(limit=10)
            )

            return (
                persisted_signals,
                persisted_signal_summary,
            )

        except Exception:
            self.logger.exception(
                "SignalService context read failed"
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
        """Build the authoritative dashboard decision object."""

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
                "AI Decision Engine context failed"
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
