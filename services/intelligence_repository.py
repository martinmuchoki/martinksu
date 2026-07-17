from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from services.database import DB_PATH


REPOSITORY_VERSION = "MIP PRO Intelligence Repository 1.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    database_path = Path(DB_PATH).expanduser().resolve()

    connection = sqlite3.connect(
        database_path,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")

    return connection


def _json(value: Any) -> Optional[str]:
    if value is None:
        return None

    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            default=str,
            sort_keys=True,
        )
    except (TypeError, ValueError):
        return json.dumps(
            {"value": str(value)},
            ensure_ascii=False,
        )


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    return []


def _first(
    mapping: Mapping[str, Any],
    *keys: str,
    default: Any = None,
) -> Any:
    for key in keys:
        value = mapping.get(key)

        if value is not None:
            return value

    return default


def _float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None

    text = str(value).strip()

    return text or None


def _normalize_symbol(item: Mapping[str, Any]) -> Optional[str]:
    symbol = _first(
        item,
        "symbol",
        "ticker",
        "stock",
        "code",
    )

    return _text(symbol)


def _extract_prediction_center(
    context: Mapping[str, Any],
) -> Dict[str, Any]:
    for key in (
        "prediction_center",
        "predictions_context",
        "prediction_data",
    ):
        value = context.get(key)

        if isinstance(value, Mapping):
            return dict(value)

    return {}


def _extract_committee(
    context: Mapping[str, Any],
) -> Dict[str, Any]:
    for key in (
        "investment_committee",
        "ai_investment_committee",
        "committee",
        "committee_context",
    ):
        value = context.get(key)

        if isinstance(value, Mapping):
            return dict(value)

    return {}


def _extract_predictions(
    context: Mapping[str, Any],
    prediction_center: Mapping[str, Any],
) -> list[Any]:
    candidates = (
        prediction_center.get("predictions"),
        prediction_center.get("stocks"),
        prediction_center.get("results"),
        context.get("predictions"),
    )

    for candidate in candidates:
        values = _list(candidate)

        if values:
            return values

    return []


def _extract_decisions(
    context: Mapping[str, Any],
    committee: Mapping[str, Any],
) -> list[Any]:
    candidates = (
        committee.get("decisions"),
        committee.get("recommendations"),
        committee.get("committee_decisions"),
        committee.get("stocks"),
        context.get("decisions"),
    )

    for candidate in candidates:
        values = _list(candidate)

        if values:
            return values

    return []


def _extract_regime(
    context: Mapping[str, Any],
    prediction_center: Mapping[str, Any],
) -> Dict[str, Any]:
    candidates = (
        context.get("market_regime"),
        prediction_center.get("market_regime"),
        prediction_center.get("regime"),
    )

    for candidate in candidates:
        if isinstance(candidate, Mapping):
            return dict(candidate)

        if isinstance(candidate, str):
            return {"regime": candidate}

    return {}


def _extract_timing(
    context: Mapping[str, Any],
) -> Dict[str, Any]:
    for key in (
        "engine_timing",
        "timing",
        "performance",
    ):
        value = context.get(key)

        if isinstance(value, Mapping):
            return dict(value)

    return {}


def save_intelligence_context(
    context: Mapping[str, Any],
    *,
    run_id: Optional[str] = None,
    source: str = "intelligence_orchestrator",
    engine_version: Optional[str] = None,
    cache_hit: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Persist one complete intelligence context transactionally.

    Existing run_id values are not duplicated.
    """

    if not isinstance(context, Mapping):
        raise TypeError("context must be a mapping")

    prediction_center = _extract_prediction_center(context)
    committee = _extract_committee(context)

    predictions = _extract_predictions(
        context,
        prediction_center,
    )

    decisions = _extract_decisions(
        context,
        committee,
    )

    regime = _extract_regime(
        context,
        prediction_center,
    )

    timing = _extract_timing(context)

    generated_at = _text(
        _first(
            context,
            "generated_at",
            "timestamp",
            "created_at",
        )
    ) or _utc_now()

    completed_at = _text(
        _first(
            context,
            "completed_at",
            "finished_at",
        )
    ) or _utc_now()

    resolved_run_id = run_id or _text(
        context.get("run_id")
    ) or f"intel-{uuid.uuid4().hex}"

    resolved_cache_hit = (
        bool(cache_hit)
        if cache_hit is not None
        else bool(context.get("cache_hit", False))
    )

    market_regime = _text(
        _first(
            regime,
            "regime",
            "market_regime",
            "label",
            "name",
        )
    )

    regime_confidence = _float(
        _first(
            regime,
            "confidence",
            "regime_confidence",
            "probability",
        )
    )

    market_risk_level = _text(
        _first(
            regime,
            "risk_level",
            "market_risk_level",
            "risk",
        )
    )

    prediction_seconds = _float(
        _first(
            timing,
            "prediction_center_seconds",
            "prediction_seconds",
        )
    ) or 0.0

    committee_seconds = _float(
        _first(
            timing,
            "committee_seconds",
            "investment_committee_seconds",
        )
    ) or 0.0

    total_seconds = _float(
        _first(
            timing,
            "total_seconds",
            "elapsed_seconds",
            "duration_seconds",
        )
    ) or prediction_seconds + committee_seconds

    connection = _connect()

    try:
        existing = connection.execute(
            """
            SELECT run_id
            FROM intelligence_runs
            WHERE run_id = ?
            """,
            (resolved_run_id,),
        ).fetchone()

        if existing:
            return {
                "saved": False,
                "duplicate": True,
                "run_id": resolved_run_id,
                "prediction_count": 0,
                "committee_decision_count": 0,
                "regime_saved": False,
            }

        connection.execute("BEGIN")

        connection.execute(
            """
            INSERT INTO intelligence_runs (
                run_id,
                generated_at,
                completed_at,
                engine_version,
                source,
                market_regime,
                regime_confidence,
                market_risk_level,
                stock_count,
                prediction_count,
                committee_decision_count,
                prediction_center_seconds,
                committee_seconds,
                total_seconds,
                cache_hit,
                status,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resolved_run_id,
                generated_at,
                completed_at,
                engine_version or REPOSITORY_VERSION,
                source,
                market_regime,
                regime_confidence,
                market_risk_level,
                max(len(predictions), len(decisions)),
                len(predictions),
                len(decisions),
                prediction_seconds,
                committee_seconds,
                total_seconds,
                int(resolved_cache_hit),
                "completed",
                _json(
                    {
                        "repository_version": REPOSITORY_VERSION,
                        "context_keys": sorted(context.keys()),
                    }
                ),
            ),
        )

        saved_predictions = 0

        for rank, raw_item in enumerate(predictions, start=1):
            item = _mapping(raw_item)
            symbol = _normalize_symbol(item)

            if not symbol:
                continue

            connection.execute(
                """
                INSERT INTO prediction_snapshots (
                    run_id,
                    symbol,
                    rank_position,
                    recommendation,
                    signal,
                    prediction_score,
                    confidence,
                    probability,
                    current_price,
                    predicted_price,
                    target_price,
                    expected_return,
                    risk_level,
                    prediction_horizon,
                    reasons_json,
                    indicators_json,
                    payload_json,
                    generated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resolved_run_id,
                    symbol,
                    rank,
                    _text(
                        _first(
                            item,
                            "recommendation",
                            "action",
                            "decision",
                        )
                    ),
                    _text(
                        _first(
                            item,
                            "signal",
                            "prediction",
                        )
                    ),
                    _float(
                        _first(
                            item,
                            "prediction_score",
                            "score",
                            "ai_score",
                        )
                    ),
                    _float(
                        _first(
                            item,
                            "confidence",
                            "confidence_score",
                        )
                    ),
                    _float(
                        _first(
                            item,
                            "probability",
                            "success_probability",
                        )
                    ),
                    _float(
                        _first(
                            item,
                            "current_price",
                            "price",
                            "last_price",
                        )
                    ),
                    _float(
                        _first(
                            item,
                            "predicted_price",
                            "forecast_price",
                        )
                    ),
                    _float(
                        _first(
                            item,
                            "target_price",
                            "price_target",
                        )
                    ),
                    _float(
                        _first(
                            item,
                            "expected_return",
                            "expected_return_pct",
                            "upside",
                        )
                    ),
                    _text(
                        _first(
                            item,
                            "risk_level",
                            "risk",
                        )
                    ),
                    _text(
                        _first(
                            item,
                            "prediction_horizon",
                            "horizon",
                            "timeframe",
                        )
                    ),
                    _json(
                        _first(
                            item,
                            "reasons",
                            "reasoning",
                            "explanation",
                        )
                    ),
                    _json(
                        _first(
                            item,
                            "indicators",
                            "technical_indicators",
                        )
                    ),
                    _json(item),
                    generated_at,
                ),
            )

            saved_predictions += 1

        saved_decisions = 0

        for rank, raw_item in enumerate(decisions, start=1):
            item = _mapping(raw_item)
            symbol = _normalize_symbol(item)

            if not symbol:
                continue

            votes = _first(
                item,
                "votes",
                "committee_votes",
                default={},
            )

            votes_mapping = _mapping(votes)

            connection.execute(
                """
                INSERT INTO committee_snapshots (
                    run_id,
                    symbol,
                    rank_position,
                    decision,
                    committee_score,
                    confidence,
                    conviction_level,
                    risk_level,
                    technical_vote,
                    quantitative_vote,
                    institutional_vote,
                    risk_vote,
                    learning_vote,
                    entry_price,
                    target_price,
                    stop_loss,
                    expected_return,
                    votes_json,
                    reasons_json,
                    payload_json,
                    generated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    resolved_run_id,
                    symbol,
                    rank,
                    _text(
                        _first(
                            item,
                            "decision",
                            "recommendation",
                            "action",
                            "final_decision",
                        )
                    ),
                    _float(
                        _first(
                            item,
                            "committee_score",
                            "score",
                            "final_score",
                        )
                    ),
                    _float(
                        _first(
                            item,
                            "confidence",
                            "confidence_score",
                        )
                    ),
                    _text(
                        _first(
                            item,
                            "conviction_level",
                            "conviction",
                        )
                    ),
                    _text(
                        _first(
                            item,
                            "risk_level",
                            "risk",
                        )
                    ),
                    _text(
                        _first(
                            votes_mapping,
                            "technical",
                            "technical_vote",
                        )
                    ),
                    _text(
                        _first(
                            votes_mapping,
                            "quantitative",
                            "quantitative_vote",
                        )
                    ),
                    _text(
                        _first(
                            votes_mapping,
                            "institutional",
                            "institutional_vote",
                        )
                    ),
                    _text(
                        _first(
                            votes_mapping,
                            "risk",
                            "risk_vote",
                        )
                    ),
                    _text(
                        _first(
                            votes_mapping,
                            "learning",
                            "learning_vote",
                        )
                    ),
                    _float(
                        _first(
                            item,
                            "entry_price",
                            "current_price",
                            "price",
                        )
                    ),
                    _float(
                        _first(
                            item,
                            "target_price",
                            "price_target",
                        )
                    ),
                    _float(
                        _first(
                            item,
                            "stop_loss",
                            "stop_price",
                        )
                    ),
                    _float(
                        _first(
                            item,
                            "expected_return",
                            "expected_return_pct",
                            "upside",
                        )
                    ),
                    _json(votes),
                    _json(
                        _first(
                            item,
                            "reasons",
                            "reasoning",
                            "explanation",
                        )
                    ),
                    _json(item),
                    generated_at,
                ),
            )

            saved_decisions += 1

        regime_saved = False

        if market_regime:
            connection.execute(
                """
                INSERT INTO market_regime_history (
                    run_id,
                    generated_at,
                    regime,
                    confidence,
                    risk_level,
                    volatility_level,
                    breadth_score,
                    momentum_score,
                    trend_score,
                    bullish_count,
                    bearish_count,
                    neutral_count,
                    reasons_json,
                    payload_json
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    resolved_run_id,
                    generated_at,
                    market_regime,
                    regime_confidence,
                    market_risk_level,
                    _text(
                        _first(
                            regime,
                            "volatility_level",
                            "volatility",
                        )
                    ),
                    _float(
                        _first(
                            regime,
                            "breadth_score",
                            "market_breadth",
                        )
                    ),
                    _float(
                        _first(
                            regime,
                            "momentum_score",
                            "momentum",
                        )
                    ),
                    _float(
                        _first(
                            regime,
                            "trend_score",
                            "trend",
                        )
                    ),
                    _int(
                        _first(
                            regime,
                            "bullish_count",
                            "bullish",
                        )
                    ),
                    _int(
                        _first(
                            regime,
                            "bearish_count",
                            "bearish",
                        )
                    ),
                    _int(
                        _first(
                            regime,
                            "neutral_count",
                            "neutral",
                        )
                    ),
                    _json(
                        _first(
                            regime,
                            "reasons",
                            "reasoning",
                            "drivers",
                        )
                    ),
                    _json(regime),
                ),
            )

            regime_saved = True

        connection.execute(
            """
            UPDATE intelligence_runs
            SET prediction_count = ?,
                committee_decision_count = ?,
                stock_count = ?
            WHERE run_id = ?
            """,
            (
                saved_predictions,
                saved_decisions,
                max(saved_predictions, saved_decisions),
                resolved_run_id,
            ),
        )

        connection.commit()

        return {
            "saved": True,
            "duplicate": False,
            "run_id": resolved_run_id,
            "prediction_count": saved_predictions,
            "committee_decision_count": saved_decisions,
            "regime_saved": regime_saved,
            "cache_hit": resolved_cache_hit,
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_repository_counts() -> Dict[str, int]:
    tables = (
        "intelligence_runs",
        "prediction_snapshots",
        "committee_snapshots",
        "market_regime_history",
    )

    connection = _connect()

    try:
        return {
            table: int(
                connection.execute(
                    f'SELECT COUNT(*) FROM "{table}"'
                ).fetchone()[0]
            )
            for table in tables
        }

    finally:
        connection.close()


def delete_intelligence_run(run_id: str) -> bool:
    connection = _connect()

    try:
        cursor = connection.execute(
            """
            DELETE FROM intelligence_runs
            WHERE run_id = ?
            """,
            (run_id,),
        )

        connection.commit()

        return cursor.rowcount > 0

    finally:
        connection.close()
