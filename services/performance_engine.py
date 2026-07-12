from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.database import get_conn, init_db
from services.recommendation_tracker import ensure_recommendation_table


HORIZONS = (1, 5, 20, 60)


def ensure_performance_table() -> None:
    init_db()
    ensure_recommendation_table()

    conn = get_conn()

    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_recommendation_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recommendation_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                recommendation_date TEXT NOT NULL,
                horizon_days INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                evaluation_date TEXT NOT NULL,
                evaluation_price REAL NOT NULL,
                return_pct REAL NOT NULL,
                decision TEXT NOT NULL,
                successful INTEGER NOT NULL,
                evaluated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(recommendation_id, horizon_days)
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_ai_performance_symbol
            ON ai_recommendation_performance(symbol)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_ai_performance_horizon
            ON ai_recommendation_performance(horizon_days)
            """
        )

        conn.commit()

    finally:
        conn.close()


def _is_successful(decision: str, return_pct: float) -> bool:
    normalized = decision.upper().strip()

    if normalized in {"BUY", "STRONG BUY", "ACCUMULATE"}:
        return return_pct > 0

    if normalized in {"SELL", "STRONG SELL"}:
        return return_pct < 0

    if normalized in {"HOLD", "WATCH"}:
        return abs(return_pct) <= 3

    return return_pct >= 0


def _future_price(
    conn,
    symbol: str,
    recommendation_date: str,
    horizon: int,
) -> Optional[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT trade_date, close
        FROM price_history
        WHERE symbol = ?
          AND trade_date > ?
        ORDER BY trade_date ASC
        LIMIT ?
        """,
        (symbol, recommendation_date, horizon),
    ).fetchall()

    if len(rows) < horizon:
        return None

    row = rows[horizon - 1]

    return {
        "trade_date": row["trade_date"],
        "close": float(row["close"]),
    }


def evaluate_recommendations() -> Dict[str, Any]:
    ensure_performance_table()

    conn = get_conn()
    evaluated = 0
    pending = 0

    try:
        recommendations = conn.execute(
            """
            SELECT *
            FROM ai_recommendations
            ORDER BY recommendation_date ASC, id ASC
            """
        ).fetchall()

        for recommendation in recommendations:
            entry_price = float(recommendation["price"] or 0)

            if entry_price <= 0:
                continue

            for horizon in HORIZONS:
                existing = conn.execute(
                    """
                    SELECT id
                    FROM ai_recommendation_performance
                    WHERE recommendation_id = ?
                      AND horizon_days = ?
                    """,
                    (recommendation["id"], horizon),
                ).fetchone()

                if existing:
                    continue

                future = _future_price(
                    conn,
                    recommendation["symbol"],
                    recommendation["recommendation_date"],
                    horizon,
                )

                if not future:
                    pending += 1
                    continue

                return_pct = round(
                    (
                        (future["close"] - entry_price)
                        / entry_price
                    )
                    * 100,
                    4,
                )

                successful = int(
                    _is_successful(
                        recommendation["decision"],
                        return_pct,
                    )
                )

                conn.execute(
                    """
                    INSERT OR IGNORE INTO ai_recommendation_performance (
                        recommendation_id,
                        symbol,
                        recommendation_date,
                        horizon_days,
                        entry_price,
                        evaluation_date,
                        evaluation_price,
                        return_pct,
                        decision,
                        successful
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        recommendation["id"],
                        recommendation["symbol"],
                        recommendation["recommendation_date"],
                        horizon,
                        entry_price,
                        future["trade_date"],
                        future["close"],
                        return_pct,
                        recommendation["decision"],
                        successful,
                    ),
                )

                evaluated += 1

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return {
        "success": True,
        "evaluated": evaluated,
        "pending": pending,
    }


def get_performance_summary() -> Dict[str, Any]:
    ensure_performance_table()

    conn = get_conn()

    try:
        totals = conn.execute(
            """
            SELECT
                COUNT(*) AS evaluations,
                SUM(successful) AS successful,
                AVG(return_pct) AS average_return,
                MAX(return_pct) AS best_return,
                MIN(return_pct) AS worst_return
            FROM ai_recommendation_performance
            """
        ).fetchone()

        recommendation_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM ai_recommendations
            """
        ).fetchone()[0]

        best = conn.execute(
            """
            SELECT
                symbol,
                decision,
                horizon_days,
                entry_price,
                evaluation_price,
                return_pct
            FROM ai_recommendation_performance
            ORDER BY return_pct DESC
            LIMIT 1
            """
        ).fetchone()

        horizon_rows = conn.execute(
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
        ).fetchall()

        decision_rows = conn.execute(
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
        ).fetchall()

        evaluations = int(totals["evaluations"] or 0)
        successful = int(totals["successful"] or 0)

        accuracy = (
            round((successful / evaluations) * 100, 2)
            if evaluations
            else 0.0
        )

        return {
            "recommendations": int(recommendation_count or 0),
            "evaluations": evaluations,
            "successful": successful,
            "accuracy": accuracy,
            "average_return": round(
                float(totals["average_return"] or 0),
                2,
            ),
            "best_return": round(
                float(totals["best_return"] or 0),
                2,
            ),
            "worst_return": round(
                float(totals["worst_return"] or 0),
                2,
            ),
            "best_performer": dict(best) if best else None,
            "by_horizon": [dict(row) for row in horizon_rows],
            "by_decision": [dict(row) for row in decision_rows],
            "status": (
                "ACTIVE"
                if evaluations
                else "COLLECTING DATA"
            ),
        }

    finally:
        conn.close()


def get_recent_performance(
    limit: int = 50,
) -> List[Dict[str, Any]]:
    ensure_performance_table()

    conn = get_conn()

    try:
        rows = conn.execute(
            """
            SELECT *
            FROM ai_recommendation_performance
            ORDER BY evaluation_date DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()
