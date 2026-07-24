"""
Read-only application service for finalized MIP PRO signals.

Architecture:

AI Investment Committee
    -> SignalRepository
    -> SignalService
    -> Dashboard / API / Telegram / Reports / Portfolio

The service does not create, modify, or recalculate signals.
It only reads finalized committee decisions from the configured
signal repository and converts them into stable consumer payloads.
"""

from __future__ import annotations

import logging
from collections import Counter
from copy import deepcopy
from threading import Lock
from typing import Any, Dict, List, Optional

from services.signal_repository import (
    SignalRepository,
    get_signal_repository,
)


logger = logging.getLogger(__name__)


class SignalService:
    """
    Read-only service for finalized investment signals.

    Consumers should use this service rather than querying SQLite
    or SignalRepository directly.
    """

    DEFAULT_LIMIT = 20
    MAX_LIMIT = 200

    def __init__(
        self,
        repository: Optional[SignalRepository] = None,
    ) -> None:
        self._repository = (
            repository
            if repository is not None
            else get_signal_repository()
        )

    @property
    def repository(self) -> SignalRepository:
        """Return the configured repository instance."""

        return self._repository

    @classmethod
    def _normalize_limit(
        cls,
        value: Any,
        *,
        default: int = DEFAULT_LIMIT,
    ) -> int:
        """
        Convert a requested result limit into a safe integer.

        Limits are clamped to protect API and dashboard consumers
        from accidentally requesting excessive database records.
        """

        try:
            limit = int(value)
        except (TypeError, ValueError):
            limit = default

        if limit < 1:
            return 1

        return min(limit, cls.MAX_LIMIT)

    @staticmethod
    def _safe_float(
        value: Any,
        default: float = 0.0,
    ) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_int(
        value: Any,
        default: int = 0,
    ) -> int:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _normalize_symbol(value: Any) -> str:
        return str(value or "").strip().upper()

    @staticmethod
    def _normalize_decision(value: Any) -> str:
        decision = str(value or "HOLD").strip().upper()

        aliases = {
            "STRONG_BUY": "STRONG BUY",
            "STRONG-BUY": "STRONG BUY",
            "STRONG_SELL": "STRONG SELL",
            "STRONG-SELL": "STRONG SELL",
        }

        return aliases.get(decision, decision)

    @classmethod
    def _consumer_signal(
        cls,
        signal: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Convert a repository record into a stable consumer object.

        Existing repository fields are preserved while aliases are
        added for dashboard, API, Telegram, and report compatibility.
        """

        item = deepcopy(signal or {})

        symbol = cls._normalize_symbol(
            item.get("symbol")
        )

        decision = cls._normalize_decision(
            item.get(
                "decision",
                item.get(
                    "final_decision",
                    item.get("signal"),
                ),
            )
        )

        score = cls._safe_float(
            item.get(
                "committee_score",
                item.get(
                    "score",
                    item.get("rank_score"),
                ),
            )
        )

        confidence = cls._safe_int(
            item.get(
                "confidence",
                item.get("confidence_pct"),
            )
        )

        item["symbol"] = symbol
        item["decision"] = decision
        item["final_decision"] = decision
        item["signal"] = decision

        item["committee_score"] = round(score, 2)
        item["score"] = round(score, 2)
        item["confidence"] = confidence

        return item

    def get_latest_signals(
        self,
        limit: int = DEFAULT_LIMIT,
    ) -> List[Dict[str, Any]]:
        """
        Return current finalized signals.

        Repository records are sorted by committee score and then
        confidence so consumers receive deterministic ordering.
        """

        safe_limit = self._normalize_limit(limit)

        try:
            signals = self._repository.get_all_signals()
        except Exception:
            logger.exception(
                "SignalService failed to load latest signals"
            )
            return []

        normalized = [
            self._consumer_signal(signal)
            for signal in signals
            if isinstance(signal, dict)
            and self._normalize_symbol(
                signal.get("symbol")
            )
        ]

        normalized.sort(
            key=lambda item: (
                self._safe_float(
                    item.get("committee_score")
                ),
                self._safe_float(
                    item.get("confidence")
                ),
                item.get("symbol", ""),
            ),
            reverse=True,
        )

        return normalized[:safe_limit]

    def get_top_signals(
        self,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Return the highest-ranked finalized signals.

        Uses the repository's optimized top-signal query and falls
        back to the latest-signal collection if that query fails.
        """

        safe_limit = self._normalize_limit(
            limit,
            default=10,
        )

        try:
            signals = self._repository.get_top_signals(
                safe_limit
            )
        except Exception:
            logger.exception(
                "SignalService top-signal query failed; "
                "using latest-signal fallback"
            )

            return self.get_latest_signals(
                limit=safe_limit
            )

        return [
            self._consumer_signal(signal)
            for signal in signals
            if isinstance(signal, dict)
            and self._normalize_symbol(
                signal.get("symbol")
            )
        ][:safe_limit]

    def get_signal(
        self,
        symbol: str,
    ) -> Optional[Dict[str, Any]]:
        """Return the latest finalized signal for one symbol."""

        normalized_symbol = self._normalize_symbol(symbol)

        if not normalized_symbol:
            return None

        try:
            signal = self._repository.get_signal(
                normalized_symbol
            )
        except Exception:
            logger.exception(
                "SignalService failed to load signal for %s",
                normalized_symbol,
            )
            return None

        if not isinstance(signal, dict) or not signal:
            return None

        return self._consumer_signal(signal)

    def get_signals_by_decision(
        self,
        decision: str,
        limit: int = DEFAULT_LIMIT,
    ) -> List[Dict[str, Any]]:
        """Return signals matching a committee decision."""

        normalized_decision = self._normalize_decision(
            decision
        )

        safe_limit = self._normalize_limit(limit)

        if not normalized_decision:
            return []

        try:
            signals = (
                self._repository.get_signals_by_decision(
                    normalized_decision
                )
            )
        except Exception:
            logger.exception(
                "SignalService failed to load %s signals",
                normalized_decision,
            )
            return []

        normalized = [
            self._consumer_signal(signal)
            for signal in signals
            if isinstance(signal, dict)
        ]

        normalized.sort(
            key=lambda item: (
                self._safe_float(
                    item.get("committee_score")
                ),
                self._safe_float(
                    item.get("confidence")
                ),
            ),
            reverse=True,
        )

        return normalized[:safe_limit]

    def get_top_buy_signals(
        self,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Return actionable BUY signals.

        STRONG BUY and BUY are included. HOLD and SELL decisions
        remain available through the general retrieval methods.
        """

        safe_limit = self._normalize_limit(
            limit,
            default=10,
        )

        signals = self.get_latest_signals(
            limit=self.MAX_LIMIT
        )

        buy_signals = [
            signal
            for signal in signals
            if signal.get("decision")
            in {"BUY", "STRONG BUY"}
        ]

        return buy_signals[:safe_limit]

    def get_dashboard_summary(
        self,
        limit: int = DEFAULT_LIMIT,
    ) -> Dict[str, Any]:
        """
        Return a dashboard-ready snapshot of persisted signals.

        This method never triggers Prediction Center or Committee
        recalculation. It reflects the latest stored decisions only.
        """

        safe_limit = self._normalize_limit(limit)
        signals = self.get_latest_signals(
            limit=safe_limit
        )

        decisions = Counter(
            signal.get("decision", "UNKNOWN")
            for signal in signals
        )

        top_signal = signals[0] if signals else None

        try:
            repository_count = self._repository.count()
        except Exception:
            logger.exception(
                "SignalService failed to count latest signals"
            )
            repository_count = len(signals)

        try:
            history_count = self._repository.history_count()
        except Exception:
            logger.exception(
                "SignalService failed to count history"
            )
            history_count = 0

        average_score = 0.0
        average_confidence = 0.0

        if signals:
            average_score = round(
                sum(
                    self._safe_float(
                        signal.get("committee_score")
                    )
                    for signal in signals
                )
                / len(signals),
                2,
            )

            average_confidence = round(
                sum(
                    self._safe_float(
                        signal.get("confidence")
                    )
                    for signal in signals
                )
                / len(signals),
                2,
            )

        return {
            "version": "MIP PRO SignalService 1.0",
            "source": "signal_repository",
            "available": bool(signals),
            "signal_count": repository_count,
            "returned_count": len(signals),
            "history_count": history_count,
            "average_committee_score": average_score,
            "average_confidence": average_confidence,
            "decision_counts": dict(
                sorted(decisions.items())
            ),
            "top_signal": top_signal,
            "signals": signals,
        }


_SERVICE_INSTANCE: Optional[SignalService] = None
_SERVICE_LOCK = Lock()


def get_signal_service() -> SignalService:
    """
    Return the process-local SignalService singleton.

    The underlying SQLite repository remains safe across separate
    Gunicorn worker processes.
    """

    global _SERVICE_INSTANCE

    if _SERVICE_INSTANCE is None:
        with _SERVICE_LOCK:
            if _SERVICE_INSTANCE is None:
                _SERVICE_INSTANCE = SignalService()

    return _SERVICE_INSTANCE
