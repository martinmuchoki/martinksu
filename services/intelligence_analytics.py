from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.database import DB_PATH


ANALYTICS_VERSION = "MIP PRO Intelligence Analytics 1.0"


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


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default

        return int(float(value))

    except (TypeError, ValueError):
        return default


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default

    text = str(value).strip()

    return text or default


def _round(value: Any, digits: int = 2) -> float:
    return round(
        _float(value),
        digits,
    )


def _fetch_one(
    connection: sqlite3.Connection,
    query: str,
    parameters: tuple[Any, ...] = (),
) -> Optional[sqlite3.Row]:
    return connection.execute(
        query,
        parameters,
    ).fetchone()


def _fetch_all(
    connection: sqlite3.Connection,
    query: str,
    parameters: tuple[Any, ...] = (),
) -> List[sqlite3.Row]:
    return connection.execute(
        query,
        parameters,
    ).fetchall()


def get_activity_statistics() -> Dict[str, Any]:
    now = _utc_now()
    today_start = datetime(
        now.year,
        now.month,
        now.day,
        tzinfo=timezone.utc,
    )
    week_start = today_start - timedelta(
        days=today_start.weekday(),
    )
    month_start = datetime(
        now.year,
        now.month,
        1,
        tzinfo=timezone.utc,
    )

    with _connect() as connection:
        row = _fetch_one(
            connection,
            """
            SELECT
                COUNT(*) AS total_runs,
                SUM(
                    CASE
                        WHEN generated_at >= ?
                        THEN 1
                        ELSE 0
                    END
                ) AS today_runs,
                SUM(
                    CASE
                        WHEN generated_at >= ?
                        THEN 1
                        ELSE 0
                    END
                ) AS week_runs,
                SUM(
                    CASE
                        WHEN generated_at >= ?
                        THEN 1
                        ELSE 0
                    END
                ) AS month_runs,
                SUM(
                    CASE
                        WHEN status = 'completed'
                        THEN 1
                        ELSE 0
                    END
                ) AS completed_runs,
                SUM(
                    CASE
                        WHEN status != 'completed'
                        THEN 1
                        ELSE 0
                    END
                ) AS failed_runs
            FROM intelligence_runs
            """,
            (
                _iso(today_start),
                _iso(week_start),
                _iso(month_start),
            ),
        )

    total_runs = _int(row["total_runs"] if row else 0)
    completed_runs = _int(
        row["completed_runs"] if row else 0
    )
    failed_runs = _int(
        row["failed_runs"] if row else 0
    )

    success_rate = (
        completed_runs / total_runs * 100
        if total_runs
        else 0.0
    )

    return {
        "total_runs": total_runs,
        "today_runs": _int(
            row["today_runs"] if row else 0
        ),
        "week_runs": _int(
            row["week_runs"] if row else 0
        ),
        "month_runs": _int(
            row["month_runs"] if row else 0
        ),
        "completed_runs": completed_runs,
        "failed_runs": failed_runs,
        "success_rate": round(success_rate, 2),
    }


def get_engine_statistics(
    *,
    history_limit: int = 30,
) -> Dict[str, Any]:
    history_limit = max(
        1,
        min(history_limit, 500),
    )

    with _connect() as connection:
        row = _fetch_one(
            connection,
            """
            SELECT
                COUNT(*) AS run_count,
                AVG(total_seconds) AS average_total_seconds,
                MIN(total_seconds) AS fastest_total_seconds,
                MAX(total_seconds) AS slowest_total_seconds,
                AVG(
                    prediction_center_seconds
                ) AS average_prediction_center_seconds,
                AVG(
                    committee_seconds
                ) AS average_committee_seconds
            FROM intelligence_runs
            WHERE status = 'completed'
            """
        )

        history = _fetch_all(
            connection,
            """
            SELECT
                run_id,
                generated_at,
                prediction_center_seconds,
                committee_seconds,
                total_seconds,
                status
            FROM intelligence_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (history_limit,),
        )

    return {
        "run_count": _int(
            row["run_count"] if row else 0
        ),
        "average_total_seconds": _round(
            row["average_total_seconds"] if row else 0
        ),
        "fastest_total_seconds": _round(
            row["fastest_total_seconds"] if row else 0
        ),
        "slowest_total_seconds": _round(
            row["slowest_total_seconds"] if row else 0
        ),
        "average_prediction_center_seconds": _round(
            row[
                "average_prediction_center_seconds"
            ] if row else 0
        ),
        "average_committee_seconds": _round(
            row["average_committee_seconds"] if row else 0,
            4,
        ),
        "history": [
            {
                "run_id": _text(item["run_id"]),
                "generated_at": _text(
                    item["generated_at"]
                ),
                "prediction_center_seconds": _round(
                    item["prediction_center_seconds"]
                ),
                "committee_seconds": _round(
                    item["committee_seconds"],
                    4,
                ),
                "total_seconds": _round(
                    item["total_seconds"]
                ),
                "status": _text(
                    item["status"],
                    "unknown",
                ),
            }
            for item in history
        ],
    }


def get_market_regime_statistics(
    *,
    history_limit: int = 100,
) -> Dict[str, Any]:
    history_limit = max(
        1,
        min(history_limit, 500),
    )

    with _connect() as connection:
        latest = _fetch_one(
            connection,
            """
            SELECT
                run_id,
                generated_at,
                regime,
                confidence,
                risk_level,
                volatility_level,
                breadth_score,
                momentum_score,
                trend_score
            FROM market_regime_history
            ORDER BY id DESC
            LIMIT 1
            """
        )

        distribution_rows = _fetch_all(
            connection,
            """
            SELECT
                COALESCE(
                    NULLIF(TRIM(regime), ''),
                    'UNKNOWN'
                ) AS regime,
                COUNT(*) AS regime_count,
                AVG(confidence) AS average_confidence
            FROM market_regime_history
            GROUP BY COALESCE(
                NULLIF(TRIM(regime), ''),
                'UNKNOWN'
            )
            ORDER BY regime_count DESC
            """
        )

        total_row = _fetch_one(
            connection,
            """
            SELECT COUNT(*) AS total
            FROM market_regime_history
            """
        )

        history = _fetch_all(
            connection,
            """
            SELECT
                run_id,
                generated_at,
                regime,
                confidence,
                risk_level,
                volatility_level,
                breadth_score,
                momentum_score,
                trend_score
            FROM market_regime_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (history_limit,),
        )

    total = _int(
        total_row["total"] if total_row else 0
    )

    distribution = []

    for row in distribution_rows:
        count = _int(row["regime_count"])

        percentage = (
            count / total * 100
            if total
            else 0.0
        )

        distribution.append({
            "regime": _text(
                row["regime"],
                "UNKNOWN",
            ),
            "count": count,
            "percentage": round(
                percentage,
                2,
            ),
            "average_confidence": _round(
                row["average_confidence"]
            ),
        })

    return {
        "current": {
            "run_id": _text(
                latest["run_id"]
                if latest
                else None
            ),
            "generated_at": _text(
                latest["generated_at"]
                if latest
                else None
            ),
            "regime": _text(
                latest["regime"]
                if latest
                else None,
                "UNKNOWN",
            ),
            "confidence": _round(
                latest["confidence"]
                if latest
                else 0
            ),
            "risk_level": _text(
                latest["risk_level"]
                if latest
                else None,
                "UNKNOWN",
            ),
            "volatility_level": _text(
                latest["volatility_level"]
                if latest
                else None,
                "UNKNOWN",
            ),
            "breadth_score": _round(
                latest["breadth_score"]
                if latest
                else 0
            ),
            "momentum_score": _round(
                latest["momentum_score"]
                if latest
                else 0
            ),
            "trend_score": _round(
                latest["trend_score"]
                if latest
                else 0
            ),
        },
        "total_records": total,
        "distribution": distribution,
        "history": [
            {
                "run_id": _text(item["run_id"]),
                "generated_at": _text(
                    item["generated_at"]
                ),
                "regime": _text(
                    item["regime"],
                    "UNKNOWN",
                ),
                "confidence": _round(
                    item["confidence"]
                ),
                "risk_level": _text(
                    item["risk_level"],
                    "UNKNOWN",
                ),
                "volatility_level": _text(
                    item["volatility_level"],
                    "UNKNOWN",
                ),
                "breadth_score": _round(
                    item["breadth_score"]
                ),
                "momentum_score": _round(
                    item["momentum_score"]
                ),
                "trend_score": _round(
                    item["trend_score"]
                ),
            }
            for item in history
        ],
    }


def get_recommendation_statistics(
    *,
    limit: int = 10,
) -> Dict[str, Any]:
    limit = max(
        1,
        min(limit, 100),
    )

    with _connect() as connection:
        top_symbols = _fetch_all(
            connection,
            """
            SELECT
                symbol,
                COUNT(*) AS recommendation_count,
                AVG(confidence) AS average_confidence,
                AVG(committee_score) AS average_score,
                AVG(expected_return) AS average_expected_return
            FROM committee_snapshots
            WHERE symbol IS NOT NULL
              AND TRIM(symbol) != ''
            GROUP BY symbol
            ORDER BY
                recommendation_count DESC,
                average_confidence DESC
            LIMIT ?
            """,
            (limit,),
        )

        decision_distribution = _fetch_all(
            connection,
            """
            SELECT
                COALESCE(
                    NULLIF(TRIM(decision), ''),
                    'UNKNOWN'
                ) AS decision,
                COUNT(*) AS decision_count
            FROM committee_snapshots
            GROUP BY COALESCE(
                NULLIF(TRIM(decision), ''),
                'UNKNOWN'
            )
            ORDER BY decision_count DESC
            """
        )

        summary = _fetch_one(
            connection,
            """
            SELECT
                COUNT(*) AS total_decisions,
                AVG(confidence) AS average_confidence,
                AVG(committee_score) AS average_score,
                AVG(expected_return) AS average_expected_return
            FROM committee_snapshots
            """
        )

        latest = _fetch_one(
            connection,
            """
            SELECT
                run_id,
                symbol,
                decision,
                committee_score,
                confidence,
                conviction_level,
                risk_level,
                expected_return,
                generated_at
            FROM committee_snapshots
            ORDER BY id DESC
            LIMIT 1
            """
        )

    top = [
        {
            "symbol": _text(row["symbol"]),
            "recommendation_count": _int(
                row["recommendation_count"]
            ),
            "average_confidence": _round(
                row["average_confidence"]
            ),
            "average_score": _round(
                row["average_score"]
            ),
            "average_expected_return": _round(
                row["average_expected_return"]
            ),
        }
        for row in top_symbols
    ]

    most_recommended = (
        top[0]["symbol"]
        if top
        else None
    )

    return {
        "total_decisions": _int(
            summary["total_decisions"]
            if summary
            else 0
        ),
        "average_confidence": _round(
            summary["average_confidence"]
            if summary
            else 0
        ),
        "average_score": _round(
            summary["average_score"]
            if summary
            else 0
        ),
        "average_expected_return": _round(
            summary["average_expected_return"]
            if summary
            else 0
        ),
        "most_recommended_stock": most_recommended,
        "top_symbols": top,
        "decision_distribution": [
            {
                "decision": _text(
                    row["decision"],
                    "UNKNOWN",
                ),
                "count": _int(
                    row["decision_count"]
                ),
            }
            for row in decision_distribution
        ],
        "latest_decision": {
            "run_id": _text(
                latest["run_id"]
                if latest
                else None
            ),
            "symbol": _text(
                latest["symbol"]
                if latest
                else None
            ),
            "decision": _text(
                latest["decision"]
                if latest
                else None,
                "UNKNOWN",
            ),
            "committee_score": _round(
                latest["committee_score"]
                if latest
                else 0
            ),
            "confidence": _round(
                latest["confidence"]
                if latest
                else 0
            ),
            "conviction_level": _text(
                latest["conviction_level"]
                if latest
                else None,
                "UNKNOWN",
            ),
            "risk_level": _text(
                latest["risk_level"]
                if latest
                else None,
                "UNKNOWN",
            ),
            "expected_return": _round(
                latest["expected_return"]
                if latest
                else 0
            ),
            "generated_at": _text(
                latest["generated_at"]
                if latest
                else None
            ),
        },
    }


def get_repository_health() -> Dict[str, Any]:
    with _connect() as connection:
        integrity = _fetch_one(
            connection,
            "PRAGMA integrity_check",
        )

        latest = _fetch_one(
            connection,
            """
            SELECT
                run_id,
                generated_at,
                completed_at,
                market_regime,
                prediction_count,
                committee_decision_count,
                total_seconds,
                status,
                error_message
            FROM intelligence_runs
            ORDER BY id DESC
            LIMIT 1
            """
        )

    integrity_result = (
        _text(integrity[0], "unknown")
        if integrity
        else "unknown"
    )

    status = (
        "healthy"
        if integrity_result == "ok"
        else "degraded"
    )

    return {
        "status": status,
        "integrity": integrity_result,
        "latest_run": {
            "run_id": _text(
                latest["run_id"]
                if latest
                else None
            ),
            "generated_at": _text(
                latest["generated_at"]
                if latest
                else None
            ),
            "completed_at": _text(
                latest["completed_at"]
                if latest
                else None
            ),
            "market_regime": _text(
                latest["market_regime"]
                if latest
                else None,
                "UNKNOWN",
            ),
            "prediction_count": _int(
                latest["prediction_count"]
                if latest
                else 0
            ),
            "committee_decision_count": _int(
                latest["committee_decision_count"]
                if latest
                else 0
            ),
            "total_seconds": _round(
                latest["total_seconds"]
                if latest
                else 0
            ),
            "status": _text(
                latest["status"]
                if latest
                else None,
                "unknown",
            ),
            "error_message": _text(
                latest["error_message"]
                if latest
                else None
            ),
        },
    }


def get_dashboard_summary() -> Dict[str, Any]:
    activity = get_activity_statistics()
    engine = get_engine_statistics(
        history_limit=20,
    )
    regimes = get_market_regime_statistics(
        history_limit=30,
    )
    recommendations = get_recommendation_statistics(
        limit=10,
    )
    health = get_repository_health()

    current_regime = regimes.get(
        "current",
        {},
    )

    return {
        "version": ANALYTICS_VERSION,
        "generated_at": _iso(_utc_now()),
        "status": health.get(
            "status",
            "unknown",
        ),
        "activity": activity,
        "engine": engine,
        "market": {
            "current_regime": current_regime.get(
                "regime",
                "UNKNOWN",
            ),
            "regime_confidence": current_regime.get(
                "confidence",
                0.0,
            ),
            "risk_level": current_regime.get(
                "risk_level",
                "UNKNOWN",
            ),
            "volatility_level": current_regime.get(
                "volatility_level",
                "UNKNOWN",
            ),
        },
        "recommendations": {
            "most_recommended_stock":
                recommendations.get(
                    "most_recommended_stock"
                ),
            "average_confidence":
                recommendations.get(
                    "average_confidence",
                    0.0,
                ),
            "average_score":
                recommendations.get(
                    "average_score",
                    0.0,
                ),
            "average_expected_return":
                recommendations.get(
                    "average_expected_return",
                    0.0,
                ),
            "top_symbols":
                recommendations.get(
                    "top_symbols",
                    [],
                ),
            "decision_distribution":
                recommendations.get(
                    "decision_distribution",
                    [],
                ),
        },
        "repository": health,
        "regimes": regimes,
    }


def get_summary() -> Dict[str, Any]:
    return get_dashboard_summary()
