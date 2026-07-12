from __future__ import annotations

from math import log10
from typing import Any, Dict, List

from services.database import get_conn
from services.performance_engine import (
    ensure_performance_table,
    evaluate_recommendations,
    get_performance_summary,
)

MIN_SAMPLE_FOR_ACTIVE = 20


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _accuracy(successful: Any, evaluations: Any) -> float:
    evaluations = _safe_int(evaluations)

    if evaluations <= 0:
        return 0.0

    return round(
        (_safe_int(successful) / evaluations) * 100,
        2,
    )


def _confidence_adjustment(
    accuracy: float,
    evaluations: int,
) -> float:
    if evaluations <= 0:
        return 0.0

    sample_strength = min(
        1.0,
        log10(evaluations + 1) / log10(101),
    )

    raw_adjustment = (accuracy - 50.0) * 0.20
    adjusted = raw_adjustment * sample_strength

    return round(
        max(-8.0, min(8.0, adjusted)),
        2,
    )


def apply_adaptive_confidence(
    confidence: Any,
    learning_summary: Dict[str, Any] | None = None,
) -> int:
    summary = learning_summary or get_learning_summary(
        evaluate_first=False
    )

    updated = round(
        _safe_float(confidence)
        + _safe_float(summary.get("confidence_adjustment"))
    )

    return max(0, min(100, updated))


def _group_rows(
    query: str,
    parameters: tuple = (),
) -> List[Dict[str, Any]]:
    conn = get_conn()

    try:
        rows = conn.execute(
            query,
            parameters,
        ).fetchall()

        result = []

        for row in rows:
            item = dict(row)

            evaluations = _safe_int(
                item.get("evaluations")
            )

            successful = _safe_int(
                item.get("successful")
            )

            item["evaluations"] = evaluations
            item["successful"] = successful
            item["accuracy"] = _accuracy(
                successful,
                evaluations,
            )

            item["average_return"] = round(
                _safe_float(item.get("average_return")),
                2,
            )

            result.append(item)

        return result

    finally:
        conn.close()


def get_learning_by_horizon() -> List[Dict[str, Any]]:
    ensure_performance_table()

    return _group_rows(
        """
        SELECT
            horizon_days,
            COUNT(*) AS evaluations,
            SUM(successful) AS successful,
            AVG(return_pct) AS average_return
        FROM ai_recommendation_performance
        GROUP BY horizon_days
        ORDER BY horizon_days
        """
    )


def get_learning_by_decision() -> List[Dict[str, Any]]:
    ensure_performance_table()

    return _group_rows(
        """
        SELECT
            decision,
            COUNT(*) AS evaluations,
            SUM(successful) AS successful,
            AVG(return_pct) AS average_return
        FROM ai_recommendation_performance
        GROUP BY decision
        ORDER BY evaluations DESC
        """
    )


def get_learning_by_sector() -> List[Dict[str, Any]]:
    ensure_performance_table()

    return _group_rows(
        """
        SELECT
            COALESCE(s.sector, 'Unknown') AS sector,
            COUNT(*) AS evaluations,
            SUM(p.successful) AS successful,
            AVG(p.return_pct) AS average_return
        FROM ai_recommendation_performance AS p
        LEFT JOIN stocks AS s
            ON s.symbol = p.symbol
        GROUP BY COALESCE(s.sector, 'Unknown')
        ORDER BY average_return DESC, evaluations DESC
        """
    )


def get_learning_summary(
    evaluate_first: bool = True,
) -> Dict[str, Any]:
    ensure_performance_table()

    if evaluate_first:
        evaluation_update = evaluate_recommendations()
    else:
        evaluation_update = {
            "success": True,
            "evaluated": 0,
            "pending": 0,
        }

    performance = get_performance_summary()

    evaluations = _safe_int(
        performance.get("evaluations")
    )

    accuracy = _safe_float(
        performance.get("accuracy")
    )

    average_return = _safe_float(
        performance.get("average_return")
    )

    by_horizon = get_learning_by_horizon()
    by_decision = get_learning_by_decision()
    by_sector = get_learning_by_sector()

    best_horizon = max(
        by_horizon,
        key=lambda item: (
            item.get("accuracy", 0),
            item.get("average_return", 0),
        ),
        default=None,
    )

    best_decision = max(
        by_decision,
        key=lambda item: (
            item.get("accuracy", 0),
            item.get("average_return", 0),
        ),
        default=None,
    )

    best_sector = max(
        by_sector,
        key=lambda item: (
            item.get("accuracy", 0),
            item.get("average_return", 0),
        ),
        default=None,
    )

    confidence_adjustment = _confidence_adjustment(
        accuracy,
        evaluations,
    )

    sample_progress = min(
        100.0,
        round(
            (evaluations / MIN_SAMPLE_FOR_ACTIVE) * 100,
            2,
        ),
    )

    if evaluations <= 0:
        learning_score = 0.0
        status = "COLLECTING DATA"
    else:
        return_component = max(
            0.0,
            min(
                100.0,
                50.0 + average_return * 2.5,
            ),
        )

        sample_component = min(
            100.0,
            evaluations
            / MIN_SAMPLE_FOR_ACTIVE
            * 100,
        )

        learning_score = round(
            accuracy * 0.60
            + return_component * 0.25
            + sample_component * 0.15,
            2,
        )

        status = (
            "ACTIVE"
            if evaluations >= MIN_SAMPLE_FOR_ACTIVE
            else "EARLY LEARNING"
        )

    return {
        "version": "11.6 Enterprise Intelligence",
        "status": status,
        "learning_score": learning_score,
        "recommendations": _safe_int(
            performance.get("recommendations")
        ),
        "evaluations": evaluations,
        "successful": _safe_int(
            performance.get("successful")
        ),
        "accuracy": round(accuracy, 2),
        "average_return": round(
            average_return,
            2,
        ),
        "best_return": round(
            _safe_float(
                performance.get("best_return")
            ),
            2,
        ),
        "worst_return": round(
            _safe_float(
                performance.get("worst_return")
            ),
            2,
        ),
        "confidence_adjustment":
            confidence_adjustment,
        "sample_progress_pct":
            sample_progress,
        "minimum_active_sample":
            MIN_SAMPLE_FOR_ACTIVE,
        "best_horizon": best_horizon,
        "best_decision": best_decision,
        "best_sector": best_sector,
        "by_horizon": by_horizon,
        "by_decision": by_decision,
        "by_sector": by_sector,
        "evaluation_update": evaluation_update,
    }
