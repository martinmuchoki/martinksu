from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from threading import RLock
from time import monotonic
from typing import Any, Dict
from uuid import uuid4
from zoneinfo import ZoneInfo

from services.ai_investment_committee import (
    build_ai_investment_committee,
)
from services.prediction_center import (
    build_prediction_center,
)
from services.intelligence_repository import (
    save_intelligence_context,
)
import logging
from services.signal_repository import get_signal_repository

logger = logging.getLogger(__name__)


KENYA_TIMEZONE = ZoneInfo("Africa/Nairobi")

_CACHE_LOCK = RLock()
_CONTEXT_CACHE: Dict[str, Any] = {
    "payload": None,
    "created_monotonic": 0.0,
}

DEFAULT_CACHE_SECONDS = 60


def _publish_committee_decisions(committee):
    """
    Publish finalized committee decisions to SignalRepository.

    Repository failures are isolated so they cannot stop the
    intelligence pipeline or prevent dashboard results.
    """
    if not isinstance(committee, dict):
        return 0

    decisions = committee.get("decisions", [])

    if not isinstance(decisions, list) or not decisions:
        return 0

    valid_decisions = [
        decision
        for decision in decisions
        if isinstance(decision, dict)
        and str(decision.get("symbol") or "").strip()
    ]

    if not valid_decisions:
        return 0

    try:
        repository = get_signal_repository()
        saved = repository.save_signals(valid_decisions)
        return len(saved)
    except Exception:
        logger.exception(
            "Failed to publish AI committee decisions "
            "to SignalRepository"
        )
        return 0
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

            previous_repository = cached.get(
                "repository",
                {},
            )

            cached["repository"] = {
                "saved": False,
                "duplicate": False,
                "cache_hit": True,
                "run_id": previous_repository.get(
                    "run_id",
                ),
                "persisted_run_id":
                    previous_repository.get(
                        "run_id",
                    ),
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

            _publish_committee_decisions(committee)

            committee_seconds = (
                monotonic() - committee_started
            )

        total_seconds = monotonic() - started

        payload: Dict[str, Any] = {
            "version":
                "MIP PRO Intelligence Orchestrator Phase 2",
            "run_id": f"intel-{uuid4().hex}",
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
            "risk_engine":
                prediction_center.get(
                    "risk_engine",
                    {},
                ),
            "portfolio_optimizer":
                prediction_center.get(
                    "portfolio_optimizer",
                    {},
                ),
            "screener":
                prediction_center.get(
                    "screener",
                    {},
                ),
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

        try:
            repository_result = save_intelligence_context(
                payload,
                run_id=payload["run_id"],
                source="intelligence_orchestrator",
                engine_version=payload.get("version"),
                cache_hit=False,
            )

            payload["repository"] = repository_result

        except Exception as exc:
            # Persistence failure must not take down the
            # live dashboard or intelligence APIs.
            payload["repository"] = {
                "saved": False,
                "duplicate": False,
                "cache_hit": False,
                "run_id": payload.get("run_id"),
                "error": str(exc),
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

# ============================================================================
# PHASE 12.2 PART 3 — AI CIO ORCHESTRATOR INTEGRATION AND COMPARISON MODE
# ============================================================================

from copy import deepcopy as _ai_cio_deepcopy
from os import getenv as _ai_cio_getenv
from threading import RLock as _AICIORLock
from time import monotonic as _ai_cio_monotonic
from typing import Mapping as _AICIOMapping
from typing import Optional as _AICIOOptional
from typing import Sequence as _AICIOSequence

from services.ai_cio import (
    AICIOExecutiveResult as _AICIOExecutiveResult,
    build_ai_cio_executive_result as _build_ai_cio_executive_result,
)


_AI_CIO_COMPARISON_CACHE = {
    "payload": None,
    "created_monotonic": 0.0,
}

_AI_CIO_COMPARISON_LOCK = _AICIORLock()

_AI_CIO_DEFAULT_CACHE_SECONDS = max(
    0,
    int(
        _ai_cio_getenv(
            "AI_CIO_COMPARISON_CACHE_SECONDS",
            "60",
        )
        or 60
    ),
)

_AI_CIO_COMPARISON_ENABLED = (
    str(
        _ai_cio_getenv(
            "AI_CIO_COMPARISON_MODE",
            "true",
        )
    )
    .strip()
    .lower()
    in {
        "1",
        "true",
        "yes",
        "on",
        "enabled",
    }
)


def _ai_cio_safe_float(
    value: object,
    default: float = 0.0,
) -> float:
    if value in (None, ""):
        return float(default)

    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)

    if result != result:
        return float(default)

    if result in (
        float("inf"),
        float("-inf"),
    ):
        return float(default)

    return result


def _ai_cio_percentage(
    value: object,
    default: float = 0.0,
) -> float:
    number = _ai_cio_safe_float(
        value,
        default,
    )

    if 0.0 <= number <= 1.0:
        number *= 100.0

    return round(
        max(
            0.0,
            min(100.0, number),
        ),
        2,
    )


def _ai_cio_symbol(
    value: object,
) -> str:
    return str(value or "").strip().upper()


def _ai_cio_normalize_action(
    value: object,
) -> str:
    raw = (
        str(value or "HOLD")
        .strip()
        .upper()
        .replace("-", "_")
        .replace(" ", "_")
    )

    aliases = {
        "STRONGBUY": "STRONG_BUY",
        "ACCUMULATE": "BUY",
        "LONG": "BUY",
        "POSITIVE": "BUY",
        "WATCH": "HOLD",
        "WAIT": "HOLD",
        "NEUTRAL": "HOLD",
        "NO_ACTION": "HOLD",
        "TAKE_PROFIT": "REDUCE",
        "UNDERWEIGHT": "REDUCE",
        "EXIT": "SELL",
        "SHORT": "SELL",
        "NEGATIVE": "SELL",
        "BLOCK": "AVOID",
        "BLOCKED": "AVOID",
        "REJECT": "AVOID",
    }

    normalized = aliases.get(
        raw,
        raw,
    )

    allowed = {
        "STRONG_BUY",
        "BUY",
        "HOLD",
        "REDUCE",
        "SELL",
        "AVOID",
    }

    return (
        normalized
        if normalized in allowed
        else "HOLD"
    )


def _ai_cio_action_direction(
    value: object,
) -> str:
    action = _ai_cio_normalize_action(
        value
    )

    if action in {
        "STRONG_BUY",
        "BUY",
    }:
        return "BULLISH"

    if action in {
        "REDUCE",
        "SELL",
        "AVOID",
    }:
        return "BEARISH"

    return "NEUTRAL"


def _ai_cio_first_present(
    source: object,
    keys: _AICIOSequence[str],
    default: object = None,
) -> object:
    if not isinstance(
        source,
        _AICIOMapping,
    ):
        return default

    for key in keys:
        value = source.get(key)

        if value not in (
            None,
            "",
        ):
            return value

    return default


def _ai_cio_first_mapping(
    source: object,
    keys: _AICIOSequence[str],
) -> dict:
    if not isinstance(
        source,
        _AICIOMapping,
    ):
        return {}

    for key in keys:
        value = source.get(key)

        if isinstance(
            value,
            _AICIOMapping,
        ):
            return dict(value)

    return {}


def _ai_cio_first_list(
    source: object,
    keys: _AICIOSequence[str],
) -> list:
    if not isinstance(
        source,
        _AICIOMapping,
    ):
        return []

    for key in keys:
        value = source.get(key)

        if isinstance(
            value,
            (list, tuple),
        ):
            return list(value)

    return []


def _ai_cio_records(
    payload: object,
    *,
    preferred_keys: _AICIOSequence[str] = (),
) -> list[dict]:
    if payload is None:
        return []

    if isinstance(
        payload,
        (list, tuple),
    ):
        return [
            dict(item)
            for item in payload
            if isinstance(
                item,
                _AICIOMapping,
            )
        ]

    if not isinstance(
        payload,
        _AICIOMapping,
    ):
        return []

    source = dict(payload)

    keys = list(
        preferred_keys
    ) + [
        "decisions",
        "committee_decisions",
        "recommendations",
        "signals",
        "predictions",
        "profiles",
        "results",
        "rows",
        "stocks",
        "items",
        "data",
        "opportunities",
        "portfolio",
        "positions",
        "allocations",
        "risk_metrics",
    ]

    for key in keys:
        value = source.get(key)

        if isinstance(
            value,
            (list, tuple),
        ):
            return [
                dict(item)
                for item in value
                if isinstance(
                    item,
                    _AICIOMapping,
                )
            ]

    records = []

    for key, value in source.items():
        if not isinstance(
            value,
            _AICIOMapping,
        ):
            continue

        record = dict(value)

        symbol = _ai_cio_symbol(
            _ai_cio_first_present(
                record,
                (
                    "symbol",
                    "ticker",
                    "code",
                    "security",
                ),
            )
        )

        if not symbol:
            record["symbol"] = (
                _ai_cio_symbol(key)
            )

        records.append(record)

    return records


def _ai_cio_index_records(
    records: _AICIOSequence[dict],
) -> dict[str, dict]:
    indexed: dict[str, dict] = {}

    for raw_record in records:
        if not isinstance(
            raw_record,
            _AICIOMapping,
        ):
            continue

        record = dict(raw_record)

        symbol = _ai_cio_symbol(
            _ai_cio_first_present(
                record,
                (
                    "symbol",
                    "ticker",
                    "code",
                    "security",
                    "instrument",
                ),
            )
        )

        if not symbol:
            continue

        existing = indexed.get(
            symbol,
            {},
        )

        indexed[symbol] = {
            **existing,
            **record,
            "symbol": symbol,
        }

    return indexed


def _ai_cio_nested_source(
    context: object,
    prediction_center: object,
    committee: object,
    keys: _AICIOSequence[str],
) -> object:
    """
    Locate an engine output without invoking the engine again.

    Search order:
    1. top-level intelligence context;
    2. Prediction Center payload;
    3. Investment Committee payload.
    """

    for source in (
        context,
        prediction_center,
        committee,
    ):
        if not isinstance(
            source,
            _AICIOMapping,
        ):
            continue

        for key in keys:
            value = source.get(key)

            if value not in (
                None,
                "",
            ):
                return value

    return None


def _extract_ai_cio_sources(
    context: object,
) -> dict:
    """
    Adapt the existing intelligence context into AI CIO input sources.

    This function is read-only and does not call specialist engines directly.
    """

    source = (
        dict(context)
        if isinstance(
            context,
            _AICIOMapping,
        )
        else {}
    )

    prediction_center = (
        _ai_cio_first_mapping(
            source,
            (
                "prediction_center",
                "predictions",
            ),
        )
    )

    committee = (
        _ai_cio_first_mapping(
            source,
            (
                "investment_committee",
                "committee",
                "ai_investment_committee",
            ),
        )
    )

    market_regime = (
        _ai_cio_nested_source(
            source,
            prediction_center,
            committee,
            (
                "market_regime",
                "regime",
                "regime_analysis",
            ),
        )
    )

    learning = (
        _ai_cio_nested_source(
            source,
            prediction_center,
            committee,
            (
                "learning",
                "learning_metrics",
                "learning_summary",
                "adaptive_learning",
            ),
        )
    )

    risk_engine = (
        _ai_cio_nested_source(
            source,
            prediction_center,
            committee,
            (
                "risk_engine",
                "risk",
                "market_risk",
                "risk_metrics",
                "stock_risk",
            ),
        )
    )

    portfolio_optimizer = (
        _ai_cio_nested_source(
            source,
            prediction_center,
            committee,
            (
                "portfolio_optimizer",
                "optimized_portfolio",
                "portfolio",
                "allocations",
            ),
        )
    )

    screener = (
        _ai_cio_nested_source(
            source,
            prediction_center,
            committee,
            (
                "screener",
                "screener_results",
                "market_screener",
                "opportunities",
            ),
        )
    )

    breadth = (
        _ai_cio_nested_source(
            source,
            prediction_center,
            committee,
            (
                "market_breadth",
                "breadth",
                "breadth_summary",
            ),
        )
    )

    return {
        "prediction_center":
            prediction_center,
        "investment_committee":
            committee,
        "risk_engine":
            risk_engine,
        "portfolio_optimizer":
            portfolio_optimizer,
        "screener":
            screener,
        "market_regime":
            market_regime,
        "learning":
            learning,
        "breadth":
            breadth,
        "metadata": {
            "source":
                "intelligence_orchestrator",
            "mode":
                "comparison",
            "authoritative":
                False,
            "repository_writes":
                False,
            "context_run_id":
                source.get("run_id"),
            "context_version":
                source.get("version"),
            "context_generated_at":
                source.get(
                    "generated_at",
                    source.get("timestamp"),
                ),
        },
    }


def _ai_cio_committee_decisions(
    committee: object,
) -> list[dict]:
    return _ai_cio_records(
        committee,
        preferred_keys=(
            "decisions",
            "committee_decisions",
            "recommendations",
            "signals",
        ),
    )


def _ai_cio_cio_decisions(
    executive_result: _AICIOExecutiveResult,
) -> list[dict]:
    records = []

    for item in getattr(
        executive_result,
        "ranked_decisions",
        [],
    ):
        decision = item.decision

        if hasattr(
            decision,
            "to_dict",
        ):
            payload = decision.to_dict()
        else:
            payload = {
                key: getattr(
                    decision,
                    key,
                )
                for key in dir(decision)
                if not key.startswith("_")
                and not callable(
                    getattr(
                        decision,
                        key,
                    )
                )
            }

        if not isinstance(
            payload,
            _AICIOMapping,
        ):
            payload = {}

        records.append(
            {
                **dict(payload),
                "rank": item.rank,
                "executive_score":
                    item.executive_score,
                "ranking_reasons":
                    list(
                        item.ranking_reasons
                    ),
            }
        )

    return records


def _build_ai_cio_symbol_comparison(
    committee_record: object,
    cio_record: object,
) -> dict:
    committee_source = (
        dict(committee_record)
        if isinstance(
            committee_record,
            _AICIOMapping,
        )
        else {}
    )

    cio_source = (
        dict(cio_record)
        if isinstance(
            cio_record,
            _AICIOMapping,
        )
        else {}
    )

    symbol = _ai_cio_symbol(
        _ai_cio_first_present(
            cio_source,
            (
                "symbol",
                "ticker",
                "code",
            ),
            _ai_cio_first_present(
                committee_source,
                (
                    "symbol",
                    "ticker",
                    "code",
                ),
            ),
        )
    )

    committee_action = (
        _ai_cio_normalize_action(
            _ai_cio_first_present(
                committee_source,
                (
                    "final_decision",
                    "decision",
                    "recommendation",
                    "signal",
                    "action",
                ),
                "HOLD",
            )
        )
    )

    cio_action = (
        _ai_cio_normalize_action(
            _ai_cio_first_present(
                cio_source,
                (
                    "decision",
                    "final_decision",
                    "recommendation",
                    "signal",
                ),
                "HOLD",
            )
        )
    )

    committee_direction = (
        _ai_cio_action_direction(
            committee_action
        )
    )

    cio_direction = (
        _ai_cio_action_direction(
            cio_action
        )
    )

    exact_agreement = (
        committee_action
        == cio_action
    )

    directional_agreement = (
        committee_direction
        == cio_direction
    )

    committee_confidence = (
        _ai_cio_percentage(
            _ai_cio_first_present(
                committee_source,
                (
                    "confidence",
                    "confidence_pct",
                    "committee_confidence",
                ),
                0.0,
            )
        )
    )

    cio_confidence = (
        _ai_cio_percentage(
            _ai_cio_first_present(
                cio_source,
                (
                    "confidence",
                    "confidence_pct",
                ),
                0.0,
            )
        )
    )

    executive_score = (
        _ai_cio_percentage(
            cio_source.get(
                "executive_score",
                0.0,
            )
        )
    )

    risk_veto = bool(
        _ai_cio_first_present(
            cio_source,
            (
                "risk_veto",
                "veto",
                "blocked",
            ),
            False,
        )
    )

    is_actionable = bool(
        _ai_cio_first_present(
            cio_source,
            (
                "is_actionable",
                "actionable",
            ),
            False,
        )
    )

    confidence_delta = round(
        cio_confidence
        - committee_confidence,
        2,
    )

    if risk_veto:
        comparison_status = (
            "RISK_VETO"
        )
    elif exact_agreement:
        comparison_status = (
            "EXACT_AGREEMENT"
        )
    elif directional_agreement:
        comparison_status = (
            "DIRECTIONAL_AGREEMENT"
        )
    else:
        comparison_status = (
            "DISAGREEMENT"
        )

    return {
        "symbol": symbol,

        "committee_decision":
            committee_action,
        "ai_cio_decision":
            cio_action,

        "committee_direction":
            committee_direction,
        "ai_cio_direction":
            cio_direction,

        "exact_agreement":
            exact_agreement,
        "directional_agreement":
            directional_agreement,

        "committee_confidence":
            committee_confidence,
        "ai_cio_confidence":
            cio_confidence,
        "confidence_delta":
            confidence_delta,

        "executive_score":
            executive_score,
        "executive_rank":
            int(
                _ai_cio_safe_float(
                    cio_source.get(
                        "rank",
                        0,
                    )
                )
            ),

        "risk_status":
            _ai_cio_first_present(
                cio_source,
                (
                    "risk_status",
                    "approval_status",
                ),
                "INSUFFICIENT_DATA",
            ),
        "risk_veto":
            risk_veto,
        "is_actionable":
            is_actionable,

        "comparison_status":
            comparison_status,
        "authoritative_source":
            "AI_INVESTMENT_COMMITTEE",
        "comparison_source":
            "AI_CIO",
    }


def _build_ai_cio_comparison_summary(
    comparisons: _AICIOSequence[dict],
    executive_result: _AICIOExecutiveResult,
) -> dict:
    total = len(comparisons)

    exact_count = sum(
        1
        for item in comparisons
        if item.get(
            "exact_agreement"
        )
    )

    directional_count = sum(
        1
        for item in comparisons
        if item.get(
            "directional_agreement"
        )
    )

    disagreement_count = sum(
        1
        for item in comparisons
        if not item.get(
            "directional_agreement"
        )
    )

    veto_count = sum(
        1
        for item in comparisons
        if item.get(
            "risk_veto"
        )
    )

    actionable_count = sum(
        1
        for item in comparisons
        if item.get(
            "is_actionable"
        )
    )

    confidence_deltas = [
        _ai_cio_safe_float(
            item.get(
                "confidence_delta"
            )
        )
        for item in comparisons
    ]

    average_confidence_delta = (
        round(
            sum(confidence_deltas)
            / len(confidence_deltas),
            2,
        )
        if confidence_deltas
        else 0.0
    )

    executive_summary = getattr(
        executive_result,
        "summary",
        None,
    )

    if (
        executive_summary is not None
        and hasattr(
            executive_summary,
            "to_dict",
        )
    ):
        cio_summary = (
            executive_summary.to_dict()
        )
    else:
        cio_summary = {}

    return {
        "comparison_mode":
            True,
        "authoritative_engine":
            "AI Investment Committee",
        "comparison_engine":
            "AI CIO",
        "production_replacement":
            False,

        "total_compared":
            total,
        "exact_agreement_count":
            exact_count,
        "directional_agreement_count":
            directional_count,
        "disagreement_count":
            disagreement_count,
        "risk_veto_count":
            veto_count,
        "actionable_count":
            actionable_count,

        "exact_agreement_pct":
            round(
                100.0
                * exact_count
                / total,
                2,
            )
            if total
            else 0.0,

        "directional_agreement_pct":
            round(
                100.0
                * directional_count
                / total,
                2,
            )
            if total
            else 0.0,

        "disagreement_pct":
            round(
                100.0
                * disagreement_count
                / total,
                2,
            )
            if total
            else 0.0,

        "average_confidence_delta":
            average_confidence_delta,

        "ai_cio_top_symbol":
            cio_summary.get(
                "top_symbol"
            ),
        "ai_cio_top_decision":
            cio_summary.get(
                "top_decision"
            ),
        "ai_cio_market_regime":
            cio_summary.get(
                "market_regime"
            ),
        "ai_cio_deployment_posture":
            cio_summary.get(
                "deployment_posture"
            ),
        "ai_cio_recommended_exposure_pct":
            cio_summary.get(
                "recommended_exposure_pct",
                0.0,
            ),
    }


def _build_ai_cio_comparison_payload(
    context: object,
    executive_result: _AICIOExecutiveResult,
) -> dict:
    source = (
        dict(context)
        if isinstance(
            context,
            _AICIOMapping,
        )
        else {}
    )

    committee = (
        _ai_cio_first_mapping(
            source,
            (
                "investment_committee",
                "committee",
                "ai_investment_committee",
            ),
        )
    )

    committee_records = (
        _ai_cio_committee_decisions(
            committee
        )
    )

    cio_records = (
        _ai_cio_cio_decisions(
            executive_result
        )
    )

    committee_index = (
        _ai_cio_index_records(
            committee_records
        )
    )

    cio_index = (
        _ai_cio_index_records(
            cio_records
        )
    )

    symbols = []

    for record_set in (
        committee_records,
        cio_records,
    ):
        for record in record_set:
            symbol = _ai_cio_symbol(
                _ai_cio_first_present(
                    record,
                    (
                        "symbol",
                        "ticker",
                        "code",
                    ),
                )
            )

            if (
                symbol
                and symbol not in symbols
            ):
                symbols.append(symbol)

    comparisons = [
        _build_ai_cio_symbol_comparison(
            committee_index.get(
                symbol,
                {},
            ),
            cio_index.get(
                symbol,
                {},
            ),
        )
        for symbol in symbols
    ]

    comparisons.sort(
        key=lambda item: (
            item.get(
                "executive_rank",
                0,
            )
            if item.get(
                "executive_rank",
                0,
            ) > 0
            else 999999,
            item.get(
                "symbol",
                "",
            ),
        )
    )

    summary = (
        _build_ai_cio_comparison_summary(
            comparisons,
            executive_result,
        )
    )

    if hasattr(
        executive_result,
        "to_dict",
    ):
        ai_cio_payload = (
            executive_result.to_dict()
        )
    else:
        ai_cio_payload = {}

    return {
        "version":
            "MIP PRO Phase 12.2 Part 3",
        "mode":
            "comparison",
        "enabled":
            True,
        "authoritative":
            False,
        "production_replacement":
            False,
        "repository_writes":
            False,

        "generated_at":
            _now_iso()
            if "_now_iso" in globals()
            else datetime.now(
                timezone.utc
            ).isoformat(),

        "context_run_id":
            source.get("run_id"),
        "context_version":
            source.get("version"),

        "summary":
            summary,
        "comparisons":
            comparisons,
        "ai_cio":
            ai_cio_payload,

        "validation":
            dict(
                getattr(
                    executive_result,
                    "validation",
                    {},
                )
            ),

        "errors":
            list(
                getattr(
                    getattr(
                        executive_result,
                        "source_result",
                        None,
                    ),
                    "errors",
                    [],
                )
            ),

        "cache": {
            "hit": False,
            "ttl_seconds":
                _AI_CIO_DEFAULT_CACHE_SECONDS,
        },
    }


def _ai_cio_comparison_cache_valid(
    cache_seconds: int,
) -> bool:
    payload = (
        _AI_CIO_COMPARISON_CACHE.get(
            "payload"
        )
    )

    created = (
        _AI_CIO_COMPARISON_CACHE.get(
            "created_monotonic",
            0.0,
        )
    )

    if payload is None:
        return False

    age = (
        _ai_cio_monotonic()
        - created
    )

    return age <= max(
        0,
        cache_seconds,
    )


def clear_ai_cio_comparison_cache() -> None:
    """
    Clear only the AI CIO comparison cache.

    The existing intelligence-context cache remains unchanged.
    """

    with _AI_CIO_COMPARISON_LOCK:
        _AI_CIO_COMPARISON_CACHE[
            "payload"
        ] = None

        _AI_CIO_COMPARISON_CACHE[
            "created_monotonic"
        ] = 0.0


def get_ai_cio_context(
    *,
    force_refresh: bool = False,
    context: _AICIOOptional[dict] = None,
) -> dict:
    """
    Build the AI CIO executive result from the live intelligence context.

    This is a read-only adapter. It does not replace committee decisions.
    """

    if context is None:
        intelligence_context = (
            build_intelligence_context(
                force_refresh=force_refresh,
                include_committee=True,
            )
        )
    else:
        intelligence_context = dict(
            context
        )

    sources = _extract_ai_cio_sources(
        intelligence_context
    )

    result = (
        _build_ai_cio_executive_result(
            prediction_center=sources[
                "prediction_center"
            ],
            investment_committee=sources[
                "investment_committee"
            ],
            risk_engine=sources[
                "risk_engine"
            ],
            portfolio_optimizer=sources[
                "portfolio_optimizer"
            ],
            screener=sources[
                "screener"
            ],
            market_regime=sources[
                "market_regime"
            ],
            learning=sources[
                "learning"
            ],
            breadth=sources[
                "breadth"
            ],
            metadata=sources[
                "metadata"
            ],
            strict=False,
            validate=True,
            strict_validation=False,
        )
    )

    return (
        result.to_dict()
        if hasattr(
            result,
            "to_dict",
        )
        else {}
    )


def get_ai_cio_comparison(
    *,
    force_refresh: bool = False,
    cache_seconds: int =
        _AI_CIO_DEFAULT_CACHE_SECONDS,
    context: _AICIOOptional[dict] = None,
    enabled: _AICIOOptional[bool] = None,
) -> dict:
    """
    Compare current committee decisions against AI CIO decisions.

    Current committee decisions remain authoritative.

    `context` may be supplied by tests or future application integration to
    prevent rebuilding the intelligence context.
    """

    comparison_enabled = (
        _AI_CIO_COMPARISON_ENABLED
        if enabled is None
        else bool(enabled)
    )

    if not comparison_enabled:
        return {
            "version":
                "MIP PRO Phase 12.2 Part 3",
            "mode":
                "comparison",
            "enabled":
                False,
            "authoritative":
                False,
            "production_replacement":
                False,
            "repository_writes":
                False,
            "summary": {
                "comparison_mode":
                    False,
                "authoritative_engine":
                    "AI Investment Committee",
                "comparison_engine":
                    "AI CIO",
            },
            "comparisons": [],
            "ai_cio": {},
            "validation": {
                "valid": True,
                "skipped": True,
            },
            "errors": [],
            "cache": {
                "hit": False,
                "ttl_seconds":
                    cache_seconds,
            },
        }

    use_cache = (
        context is None
        and not force_refresh
    )

    with _AI_CIO_COMPARISON_LOCK:
        if (
            use_cache
            and _ai_cio_comparison_cache_valid(
                cache_seconds
            )
        ):
            cached = (
                _ai_cio_deepcopy(
                    _AI_CIO_COMPARISON_CACHE[
                        "payload"
                    ]
                )
            )

            cached["cache"] = {
                "hit": True,
                "ttl_seconds":
                    cache_seconds,
            }

            return cached

        if context is None:
            intelligence_context = (
                build_intelligence_context(
                    force_refresh=
                        force_refresh,
                    include_committee=True,
                )
            )
        else:
            intelligence_context = (
                dict(context)
            )

        sources = (
            _extract_ai_cio_sources(
                intelligence_context
            )
        )

        executive_result = (
            _build_ai_cio_executive_result(
                prediction_center=sources[
                    "prediction_center"
                ],
                investment_committee=sources[
                    "investment_committee"
                ],
                risk_engine=sources[
                    "risk_engine"
                ],
                portfolio_optimizer=sources[
                    "portfolio_optimizer"
                ],
                screener=sources[
                    "screener"
                ],
                market_regime=sources[
                    "market_regime"
                ],
                learning=sources[
                    "learning"
                ],
                breadth=sources[
                    "breadth"
                ],
                metadata=sources[
                    "metadata"
                ],
                strict=False,
                validate=True,
                strict_validation=False,
            )
        )

        payload = (
            _build_ai_cio_comparison_payload(
                intelligence_context,
                executive_result,
            )
        )

        payload["cache"] = {
            "hit": False,
            "ttl_seconds":
                cache_seconds,
        }

        if context is None:
            _AI_CIO_COMPARISON_CACHE[
                "payload"
            ] = _ai_cio_deepcopy(
                payload
            )

            _AI_CIO_COMPARISON_CACHE[
                "created_monotonic"
            ] = _ai_cio_monotonic()

        return payload


def get_ai_cio_comparison_summary(
    *,
    force_refresh: bool = False,
    cache_seconds: int =
        _AI_CIO_DEFAULT_CACHE_SECONDS,
    context: _AICIOOptional[dict] = None,
) -> dict:
    """
    Return only the lightweight comparison summary.
    """

    payload = get_ai_cio_comparison(
        force_refresh=force_refresh,
        cache_seconds=cache_seconds,
        context=context,
    )

    return dict(
        payload.get(
            "summary",
            {},
        )
    )

# ============================================================================
# PHASE 12.3 PART A — AI CIO ADAPTIVE MAPPER INTEGRATION
# ============================================================================

from services.ai_cio_adaptive_mapper import (
    build_adaptive_source_map as _build_adaptive_source_map,
    get_source_coverage_report as _get_source_coverage_report,
    merge_adaptive_with_static_sources as _merge_adaptive_with_static_sources,
)


def get_ai_cio_source_coverage(
    *,
    force_refresh: bool = False,
    context: _AICIOOptional[dict] = None,
    minimum_score: float = 30.0,
    max_depth: int = 8,
) -> dict:
    """
    Return adaptive source-discovery diagnostics for the live context.

    This function is read-only.
    """

    if context is None:
        intelligence_context = (
            build_intelligence_context(
                force_refresh=force_refresh,
                include_committee=True,
            )
        )
    else:
        intelligence_context = dict(
            context
        )

    return _get_source_coverage_report(
        intelligence_context,
        minimum_score=minimum_score,
        max_depth=max_depth,
    )


def _extract_ai_cio_sources_adaptive(
    context: object,
    *,
    minimum_score: float = 30.0,
    max_depth: int = 8,
) -> dict:
    """
    Combine Phase 12.2 static extraction with Phase 12.3 adaptive discovery.
    """

    static_sources = (
        _extract_ai_cio_sources(
            context
        )
    )

    adaptive_map = (
        _build_adaptive_source_map(
            context,
            minimum_score=minimum_score,
            max_depth=max_depth,
        )
    )

    return (
        _merge_adaptive_with_static_sources(
            adaptive_map,
            static_sources,
        )
    )


def get_ai_cio_adaptive_context(
    *,
    force_refresh: bool = False,
    context: _AICIOOptional[dict] = None,
    minimum_score: float = 30.0,
    max_depth: int = 8,
) -> dict:
    """
    Build an AI CIO executive result using adaptive source discovery.
    """

    if context is None:
        intelligence_context = (
            build_intelligence_context(
                force_refresh=force_refresh,
                include_committee=True,
            )
        )
    else:
        intelligence_context = dict(
            context
        )

    sources = (
        _extract_ai_cio_sources_adaptive(
            intelligence_context,
            minimum_score=minimum_score,
            max_depth=max_depth,
        )
    )

    result = (
        _build_ai_cio_executive_result(
            prediction_center=sources.get(
                "prediction_center"
            ),
            investment_committee=sources.get(
                "investment_committee"
            ),
            risk_engine=sources.get(
                "risk_engine"
            ),
            portfolio_optimizer=sources.get(
                "portfolio_optimizer"
            ),
            screener=sources.get(
                "screener"
            ),
            market_regime=sources.get(
                "market_regime"
            ),
            learning=sources.get(
                "learning"
            ),
            breadth=sources.get(
                "breadth"
            ),
            metadata=sources.get(
                "metadata"
            ),
            strict=False,
            validate=True,
            strict_validation=False,
        )
    )

    payload = (
        result.to_dict()
        if hasattr(
            result,
            "to_dict",
        )
        else {}
    )

    payload["source_coverage"] = (
        sources.get(
            "metadata",
            {},
        ).get(
            "adaptive_mapper",
            {},
        )
    )

    payload["adaptive_mapper"] = {
        "enabled": True,
        "phase": "12.3-part-a",
        "read_only": True,
        "repository_writes": False,
    }

    return payload


def get_ai_cio_adaptive_comparison(
    *,
    force_refresh: bool = False,
    context: _AICIOOptional[dict] = None,
    minimum_score: float = 30.0,
    max_depth: int = 8,
) -> dict:
    """
    Compare committee decisions with AI CIO decisions after adaptive mapping.

    Committee decisions remain authoritative.
    """

    if context is None:
        intelligence_context = (
            build_intelligence_context(
                force_refresh=force_refresh,
                include_committee=True,
            )
        )
    else:
        intelligence_context = dict(
            context
        )

    sources = (
        _extract_ai_cio_sources_adaptive(
            intelligence_context,
            minimum_score=minimum_score,
            max_depth=max_depth,
        )
    )

    executive_result = (
        _build_ai_cio_executive_result(
            prediction_center=sources.get(
                "prediction_center"
            ),
            investment_committee=sources.get(
                "investment_committee"
            ),
            risk_engine=sources.get(
                "risk_engine"
            ),
            portfolio_optimizer=sources.get(
                "portfolio_optimizer"
            ),
            screener=sources.get(
                "screener"
            ),
            market_regime=sources.get(
                "market_regime"
            ),
            learning=sources.get(
                "learning"
            ),
            breadth=sources.get(
                "breadth"
            ),
            metadata=sources.get(
                "metadata"
            ),
            strict=False,
            validate=True,
            strict_validation=False,
        )
    )

    payload = (
        _build_ai_cio_comparison_payload(
            intelligence_context,
            executive_result,
        )
    )

    payload["source_coverage"] = (
        sources.get(
            "metadata",
            {},
        ).get(
            "adaptive_mapper",
            {},
        )
    )

    payload["adaptive_mapper"] = {
        "enabled": True,
        "phase": "12.3-part-a",
        "read_only": True,
        "repository_writes": False,
    }

    payload["production_replacement"] = False
    payload["authoritative"] = False
    payload["repository_writes"] = False

    return payload

# ============================================================================
# PHASE 12.3 PART B — AI CIO NORMALIZED ADAPTIVE INTEGRATION
# ============================================================================

from services.ai_cio_source_normalizer import (
    build_normalized_ai_cio_sources as _build_normalized_ai_cio_sources,
)


def get_ai_cio_normalization_report(
    *,
    force_refresh: bool = False,
    context: _AICIOOptional[dict] = None,
    minimum_score: float = 25.0,
    max_depth: int = 8,
    include_sources: bool = False,
) -> dict:
    """
    Return Part B normalization diagnostics without repository writes.
    """

    if context is None:
        intelligence_context = (
            build_intelligence_context(
                force_refresh=force_refresh,
                include_committee=True,
            )
        )
    else:
        intelligence_context = dict(
            context
        )

    adaptive_sources = (
        _extract_ai_cio_sources_adaptive(
            intelligence_context,
            minimum_score=minimum_score,
            max_depth=max_depth,
        )
    )

    normalized = (
        _build_normalized_ai_cio_sources(
            adaptive_sources
        )
    )

    return normalized.to_dict(
        include_sources=include_sources,
    )


def _extract_ai_cio_sources_normalized(
    context: object,
    *,
    minimum_score: float = 25.0,
    max_depth: int = 8,
) -> dict:
    """
    Discover, adapt and normalize all AI CIO source payloads.
    """

    adaptive_sources = (
        _extract_ai_cio_sources_adaptive(
            context,
            minimum_score=minimum_score,
            max_depth=max_depth,
        )
    )

    normalized = (
        _build_normalized_ai_cio_sources(
            adaptive_sources
        )
    )

    sources = dict(
        normalized.sources
    )

    metadata = dict(
        sources.get(
            "metadata",
            {},
        )
    )

    metadata[
        "normalization"
    ] = normalized.to_dict(
        include_sources=False,
    )

    sources["metadata"] = metadata

    return sources


def get_ai_cio_normalized_context(
    *,
    force_refresh: bool = False,
    context: _AICIOOptional[dict] = None,
    minimum_score: float = 25.0,
    max_depth: int = 8,
) -> dict:
    """
    Build AI CIO executive output from normalized adaptive sources.
    """

    if context is None:
        intelligence_context = (
            build_intelligence_context(
                force_refresh=force_refresh,
                include_committee=True,
            )
        )
    else:
        intelligence_context = dict(
            context
        )

    sources = (
        _extract_ai_cio_sources_normalized(
            intelligence_context,
            minimum_score=minimum_score,
            max_depth=max_depth,
        )
    )

    result = (
        _build_ai_cio_executive_result(
            prediction_center=sources.get(
                "prediction_center"
            ),
            investment_committee=sources.get(
                "investment_committee"
            ),
            risk_engine=sources.get(
                "risk_engine"
            ),
            portfolio_optimizer=sources.get(
                "portfolio_optimizer"
            ),
            screener=sources.get(
                "screener"
            ),
            market_regime=sources.get(
                "market_regime"
            ),
            learning=sources.get(
                "learning"
            ),
            breadth=sources.get(
                "breadth"
            ),
            metadata=sources.get(
                "metadata"
            ),
            strict=False,
            validate=True,
            strict_validation=False,
        )
    )

    payload = (
        result.to_dict()
        if hasattr(
            result,
            "to_dict",
        )
        else {}
    )

    normalization = (
        sources.get(
            "metadata",
            {},
        ).get(
            "normalization",
            {},
        )
    )

    payload[
        "normalization"
    ] = normalization

    payload[
        "normalizer"
    ] = {
        "enabled": True,
        "phase": "12.3-part-b",
        "read_only": True,
        "repository_writes": False,
    }

    return payload


def get_ai_cio_normalized_comparison(
    *,
    force_refresh: bool = False,
    context: _AICIOOptional[dict] = None,
    minimum_score: float = 25.0,
    max_depth: int = 8,
) -> dict:
    """
    Compare production committee decisions with the normalized AI CIO output.

    The Investment Committee remains authoritative.
    """

    if context is None:
        intelligence_context = (
            build_intelligence_context(
                force_refresh=force_refresh,
                include_committee=True,
            )
        )
    else:
        intelligence_context = dict(
            context
        )

    sources = (
        _extract_ai_cio_sources_normalized(
            intelligence_context,
            minimum_score=minimum_score,
            max_depth=max_depth,
        )
    )

    executive_result = (
        _build_ai_cio_executive_result(
            prediction_center=sources.get(
                "prediction_center"
            ),
            investment_committee=sources.get(
                "investment_committee"
            ),
            risk_engine=sources.get(
                "risk_engine"
            ),
            portfolio_optimizer=sources.get(
                "portfolio_optimizer"
            ),
            screener=sources.get(
                "screener"
            ),
            market_regime=sources.get(
                "market_regime"
            ),
            learning=sources.get(
                "learning"
            ),
            breadth=sources.get(
                "breadth"
            ),
            metadata=sources.get(
                "metadata"
            ),
            strict=False,
            validate=True,
            strict_validation=False,
        )
    )

    payload = (
        _build_ai_cio_comparison_payload(
            intelligence_context,
            executive_result,
        )
    )

    normalization = (
        sources.get(
            "metadata",
            {},
        ).get(
            "normalization",
            {},
        )
    )

    payload[
        "normalization"
    ] = normalization

    payload[
        "normalizer"
    ] = {
        "enabled": True,
        "phase": "12.3-part-b",
        "read_only": True,
        "repository_writes": False,
    }

    payload[
        "production_replacement"
    ] = False

    payload[
        "authoritative"
    ] = False

    payload[
        "repository_writes"
    ] = False

    return payload
