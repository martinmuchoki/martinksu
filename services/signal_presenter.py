"""
Central presentation layer for finalized MIP PRO trading signals.

Architecture:

AI Investment Committee
    -> SignalRepository
    -> SignalService
    -> SignalPresenter
    -> Dashboard / Telegram / Reports / Institutional Brief

The presenter is read-only.

It does not:
- calculate trading signals;
- run market analysis;
- persist decisions;
- send Telegram messages;
- generate PDF files.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from services.signal_service import (
    SignalService,
    get_signal_service,
)


NAIROBI_TZ = ZoneInfo("Africa/Nairobi")


def _first_value(
    mapping: Dict[str, Any],
    *keys: str,
    default: Any = None,
) -> Any:
    """
    Return the first available non-empty value.
    """

    for key in keys:
        value = mapping.get(key)

        if value is not None and value != "":
            return value

    return default


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Convert a value to float safely.
    """

    try:
        if value is None or value == "":
            return default

        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    """
    Convert a value to integer safely.
    """

    try:
        if value is None or value == "":
            return default

        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _format_number(
    value: Any,
    decimals: int = 2,
) -> str:
    """
    Format numeric output without unnecessary trailing zeros.
    """

    number = _safe_float(value)

    formatted = f"{number:,.{decimals}f}"

    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")

    return formatted


def _format_percentage(
    value: Any,
    decimals: int = 2,
) -> str:
    """
    Format a numeric value as a percentage.
    """

    return f"{_format_number(value, decimals)}%"


def _normalise_symbol(
    signal: Dict[str, Any],
) -> str:
    symbol = _first_value(
        signal,
        "symbol",
        "ticker",
        "security",
        default="UNKNOWN",
    )

    return str(symbol).strip().upper() or "UNKNOWN"


def _normalise_decision(
    signal: Dict[str, Any],
) -> str:
    decision = _first_value(
        signal,
        "final_decision",
        "decision",
        "signal",
        "recommendation",
        default="WATCH",
    )

    return str(decision).strip().upper() or "WATCH"


def _normalise_risk(
    signal: Dict[str, Any],
) -> str:
    risk = _first_value(
        signal,
        "risk_level",
        "risk",
        "risk_rating",
        default="N/A",
    )

    return str(risk).strip().upper() or "N/A"


def _normalise_institutional_flow(
    signal: Dict[str, Any],
) -> str:
    flow = _first_value(
        signal,
        "institutional_signal",
        "institutional_flow",
        "smart_money_signal",
        "volume_signal",
        default="N/A",
    )

    return str(flow).strip().upper() or "N/A"


class SignalPresenter:
    """
    Read-only presentation facade for finalized persisted signals.
    """

    def __init__(
        self,
        signal_service: Optional[SignalService] = None,
    ) -> None:
        self.signal_service = (
            signal_service
            if signal_service is not None
            else get_signal_service()
        )

    def present_signal(
        self,
        signal: Dict[str, Any],
        rank: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Normalize one persisted signal for downstream consumers.
        """

        symbol = _normalise_symbol(signal)
        decision = _normalise_decision(signal)

        committee_score = _safe_float(
            _first_value(
                signal,
                "committee_score",
                "score",
                default=0,
            )
        )

        confidence = _safe_float(
            _first_value(
                signal,
                "confidence",
                "confidence_score",
                default=0,
            )
        )

        price = _safe_float(
            _first_value(
                signal,
                "price",
                "current_price",
                "last_price",
                default=0,
            )
        )

        expected_return = _safe_float(
            _first_value(
                signal,
                "expected_return",
                "predicted_return",
                "return_pct",
                default=0,
            )
        )

        risk_level = _normalise_risk(signal)

        institutional_flow = (
            _normalise_institutional_flow(signal)
        )

        timestamp = _first_value(
            signal,
            "stored_at",
            "updated_at",
            "created_at",
            "timestamp",
            default=None,
        )

        return {
            "rank": rank,
            "symbol": symbol,
            "decision": decision,
            "committee_score": round(
                committee_score,
                2,
            ),
            "confidence": round(
                confidence,
                2,
            ),
            "price": round(
                price,
                4,
            ),
            "expected_return": round(
                expected_return,
                2,
            ),
            "risk_level": risk_level,
            "institutional_flow": institutional_flow,
            "timestamp": timestamp,
            "score_display": _format_number(
                committee_score,
                2,
            ),
            "confidence_display": _format_percentage(
                confidence,
                2,
            ),
            "price_display": _format_number(
                price,
                2,
            ),
            "expected_return_display": (
                _format_percentage(
                    expected_return,
                    2,
                )
            ),
        }

    def get_presented_signals(
        self,
        limit: int = 10,
        decision: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return normalized persisted signals.
        """

        safe_limit = max(
            1,
            min(_safe_int(limit, 10), 100),
        )

        if decision:
            raw_signals = (
                self.signal_service
                .get_signals_by_decision(
                    decision=str(decision).upper(),
                    limit=safe_limit,
                )
            )
        else:
            raw_signals = (
                self.signal_service
                .get_top_signals(
                    limit=safe_limit
                )
            )

        return [
            self.present_signal(
                signal,
                rank=index,
            )
            for index, signal in enumerate(
                raw_signals,
                start=1,
            )
        ]

    def get_summary(
        self,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Return a normalized repository presentation summary.
        """

        safe_limit = max(
            1,
            min(_safe_int(limit, 10), 100),
        )

        raw_summary = (
            self.signal_service
            .get_dashboard_summary(
                limit=safe_limit
            )
        )

        signals = self.get_presented_signals(
            limit=safe_limit
        )

        top_signal = (
            signals[0]
            if signals
            else None
        )

        average_score = _first_value(
            raw_summary,
            "average_committee_score",
            "average_score",
            default=0,
        )

        return {
            "available": bool(
                raw_summary.get("available")
            ),
            "signal_count": _safe_int(
                raw_summary.get("signal_count")
            ),
            "history_count": _safe_int(
                raw_summary.get("history_count")
            ),
            "average_committee_score": round(
                _safe_float(average_score),
                2,
            ),
            "average_confidence": round(
                _safe_float(
                    raw_summary.get(
                        "average_confidence"
                    )
                ),
                2,
            ),
            "top_signal": top_signal,
            "generated_at": datetime.now(
                NAIROBI_TZ
            ).isoformat(),
        }

    def build_telegram_signal_message(
        self,
        signal: Dict[str, Any],
        include_header: bool = True,
    ) -> str:
        """
        Format one finalized signal as Telegram-compatible text.
        """

        presented = self.present_signal(signal)

        lines: List[str] = []

        if include_header:
            lines.extend(
                [
                    "MIP PRO SIGNAL",
                    "",
                ]
            )

        lines.extend(
            [
                (
                    f"{presented['symbol']} "
                    f"— {presented['decision']}"
                ),
                (
                    "Committee score: "
                    f"{presented['score_display']}"
                ),
                (
                    "Confidence: "
                    f"{presented['confidence_display']}"
                ),
                (
                    "Price: KSh "
                    f"{presented['price_display']}"
                ),
                (
                    "Expected return: "
                    f"{presented['expected_return_display']}"
                ),
                (
                    "Risk: "
                    f"{presented['risk_level']}"
                ),
                (
                    "Institutional flow: "
                    f"{presented['institutional_flow']}"
                ),
            ]
        )

        return "\n".join(lines)

    def build_telegram_digest(
        self,
        limit: int = 5,
        decision: Optional[str] = None,
    ) -> str:
        """
        Format finalized persisted signals as one Telegram digest.
        """

        signals = self.get_presented_signals(
            limit=limit,
            decision=decision,
        )

        summary = self.get_summary(
            limit=limit
        )

        now = datetime.now(
            NAIROBI_TZ
        ).strftime("%Y-%m-%d %H:%M EAT")

        lines = [
            "MIP PRO",
            "Persisted Committee Signal Digest",
            now,
            "",
            (
                "Finalized signals: "
                f"{summary['signal_count']}"
            ),
            (
                "Average committee score: "
                f"{_format_number(summary['average_committee_score'])}"
            ),
            (
                "Average confidence: "
                f"{_format_percentage(summary['average_confidence'])}"
            ),
            "",
        ]

        if not signals:
            lines.append(
                "No finalized persisted signals are available."
            )

            return "\n".join(lines)

        for signal in signals:
            lines.extend(
                [
                    (
                        f"{signal['rank']}. "
                        f"{signal['symbol']} "
                        f"— {signal['decision']}"
                    ),
                    (
                        "   Score "
                        f"{signal['score_display']} | "
                        "Confidence "
                        f"{signal['confidence_display']}"
                    ),
                    (
                        "   Price KSh "
                        f"{signal['price_display']} | "
                        "Expected "
                        f"{signal['expected_return_display']}"
                    ),
                    (
                        "   Risk "
                        f"{signal['risk_level']} | "
                        "Flow "
                        f"{signal['institutional_flow']}"
                    ),
                    "",
                ]
            )

        lines.extend(
            [
                (
                    "Source: SignalRepository "
                    "via SignalService"
                ),
                (
                    "Decisions are finalized committee outputs, "
                    "not newly recalculated alerts."
                ),
            ]
        )

        return "\n".join(lines).rstrip()

    def build_institutional_brief(
        self,
        market: Dict[str, Any],
        screener: List[Dict[str, Any]],
        performance: Dict[str, Any],
        optimizer: Dict[str, Any],
    ) -> str:
        """
        Format the institutional market brief.

        This method only presents supplied report data. It does not
        run analysis, persist signals, or send Telegram messages.
        """
        now = datetime.now(NAIROBI_TZ)

        lines = [
            "MIP PRO",
            "",
            (
                "Market: "
                f"{market.get('market_status', 'Unknown')}"
            ),
            (
                "Average change: "
                f"{market.get('average_change', 0)}%"
            ),
            (
                "Securities: "
                f"{len(market.get('stocks', []))}"
            ),
            "",
            "Top Opportunities",
        ]

        for index, item in enumerate(
            screener[:5],
            start=1,
        ):
            lines.append(
                f"{index}. {item.get('symbol')} "
                f"{item.get('decision')} "
                f"{item.get('confidence')}% "
                f"@ KSh {item.get('price')}"
            )

        lines.extend(
            [
                "",
                "AI Performance",
                (
                    "Recommendations: "
                    f"{performance.get('recommendations', 0)}"
                ),
                (
                    "Accuracy: "
                    f"{performance.get('accuracy', 0)}%"
                ),
                (
                    "Average return: "
                    f"{performance.get('average_return', 0)}%"
                ),
                "",
                "Portfolio Optimizer",
                (
                    "Positions: "
                    f"{optimizer.get('position_count', 0)}"
                ),
                (
                    "Invested: "
                    f"{optimizer.get('invested_percentage', 0)}%"
                ),
                (
                    "Cash: "
                    f"{optimizer.get('cash_percentage', 100)}%"
                ),
                (
                    "Risk: "
                    f"{optimizer.get('risk_level', 'Unknown')}"
                ),
                "",
                (
                    "Generated: "
                    f"{now.strftime('%Y-%m-%d %H:%M EAT')}"
                ),
            ]
        )

        return "\n".join(lines)

    def build_institutional_summary(
        self,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Return report-ready structured signal content.
        """

        signals = self.get_presented_signals(
            limit=limit
        )

        summary = self.get_summary(
            limit=limit
        )

        decisions: Dict[str, int] = {}

        for signal in signals:
            decision = signal["decision"]

            decisions[decision] = (
                decisions.get(decision, 0) + 1
            )

        return {
            "title": (
                "MIP PRO Institutional Signal Summary"
            ),
            "source": (
                "SignalRepository via SignalService"
            ),
            "generated_at": summary["generated_at"],
            "repository_available": (
                summary["available"]
            ),
            "signal_count": (
                summary["signal_count"]
            ),
            "history_count": (
                summary["history_count"]
            ),
            "average_committee_score": (
                summary["average_committee_score"]
            ),
            "average_confidence": (
                summary["average_confidence"]
            ),
            "decision_distribution": decisions,
            "top_signal": summary["top_signal"],
            "signals": signals,
        }


_signal_presenter: Optional[SignalPresenter] = None


def get_signal_presenter() -> SignalPresenter:
    """
    Return the process-local SignalPresenter singleton.
    """

    global _signal_presenter

    if _signal_presenter is None:
        _signal_presenter = SignalPresenter()

    return _signal_presenter
