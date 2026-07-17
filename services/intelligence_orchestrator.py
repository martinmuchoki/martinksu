from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from threading import RLock
from time import monotonic
from typing import Any, Dict
from zoneinfo import ZoneInfo

from services.ai_investment_committee import (
    build_ai_investment_committee,
)
from services.prediction_center import (
    build_prediction_center,
)


KENYA_TIMEZONE = ZoneInfo("Africa/Nairobi")

_CACHE_LOCK = RLock()
_CONTEXT_CACHE: Dict[str, Any] = {
    "payload": None,
    "created_monotonic": 0.0,
}

DEFAULT_CACHE_SECONDS = 60


def _now_iso() -> str:
    return datetime.now(
        KENYA_TIMEZONE
    ).isoformat()


def clear_intelligence_cache() -> None:
    """Clear the in-process intelligence cache."""

    with _CACHE_LOCK:
        _CONTEXT_CACHE["payload"] = None
        _CONTEXT_CACHE["created_monotonic"] = 0.0


def _cache_is_valid(
    cache_seconds: int,
) -> bool:
    payload = _CONTEXT_CACHE.get("payload")

    if not isinstance(payload, dict):
        return False

    created = float(
        _CONTEXT_CACHE.get(
            "created_monotonic",
            0.0,
        )
    )

    age = monotonic() - created

    return age <= max(0, cache_seconds)


def build_intelligence_context(
    *,
    force_refresh: bool = False,
    include_committee: bool = True,
    cache_seconds: int = DEFAULT_CACHE_SECONDS,
) -> Dict[str, Any]:
    """
    Build one shared MIP PRO intelligence context.

    Prediction Center is calculated once and reused by
    the AI Investment Committee.
    """

    with _CACHE_LOCK:
        if (
            not force_refresh
            and _cache_is_valid(cache_seconds)
        ):
            cached = deepcopy(
                _CONTEXT_CACHE["payload"]
            )

            cached["cache"] = {
                "hit": True,
                "ttl_seconds": cache_seconds,
            }

            return cached

        started = monotonic()

        prediction_started = monotonic()
        prediction_center = build_prediction_center()
        prediction_seconds = (
            monotonic() - prediction_started
        )

        committee = None
        committee_seconds = 0.0

        if include_committee:
            committee_started = monotonic()

            committee = build_ai_investment_committee(
                prediction_center=prediction_center,
            )

            committee_seconds = (
                monotonic() - committee_started
            )

        total_seconds = monotonic() - started

        payload: Dict[str, Any] = {
            "version":
                "MIP PRO Intelligence Orchestrator Phase 1",
            "generated_at": _now_iso(),
            "stock_count":
                prediction_center.get(
                    "stock_count",
                    0,
                ),
            "prediction_count":
                prediction_center.get(
                    "prediction_count",
                    len(
                        prediction_center.get(
                            "predictions",
                            [],
                        )
                    ),
                ),
            "market_regime":
                prediction_center.get(
                    "market_regime",
                    {},
                ),
            "learning":
                prediction_center.get(
                    "learning",
                    {},
                ),
            "prediction_center":
                prediction_center,
            "investment_committee":
                committee,
            "timing": {
                "prediction_center_seconds":
                    round(
                        prediction_seconds,
                        4,
                    ),
                "committee_seconds":
                    round(
                        committee_seconds,
                        4,
                    ),
                "total_seconds":
                    round(
                        total_seconds,
                        4,
                    ),
            },
            "cache": {
                "hit": False,
                "ttl_seconds": cache_seconds,
            },
        }

        _CONTEXT_CACHE["payload"] = deepcopy(
            payload
        )
        _CONTEXT_CACHE[
            "created_monotonic"
        ] = monotonic()

        return payload


def get_prediction_center(
    *,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    context = build_intelligence_context(
        force_refresh=force_refresh,
        include_committee=True,
    )

    return context.get(
        "prediction_center",
        {},
    )


def get_investment_committee(
    *,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    context = build_intelligence_context(
        force_refresh=force_refresh,
        include_committee=True,
    )

    return context.get(
        "investment_committee",
        {},
    )
