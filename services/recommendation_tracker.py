from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from services.database import get_conn, init_db


NAIROBI_TZ = ZoneInfo("Africa/Nairobi")


def ensure_recommendation_table() -> None:
    init_db()
    conn = get_conn()

    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                recommendation_date TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                price REAL NOT NULL,
                decision TEXT NOT NULL,
                confidence INTEGER NOT NULL,
                risk TEXT,
                position_pct INTEGER DEFAULT 0,
                source TEXT,
                UNIQUE(symbol, recommendation_date)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def save_recommendations(
    recommendations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    ensure_recommendation_table()

    now = datetime.now(NAIROBI_TZ)
    recommendation_date = now.date().isoformat()

    saved = 0
    skipped = 0

    conn = get_conn()

    try:
        for item in recommendations:
            symbol = str(item.get("symbol") or "").strip().upper()
            price = float(item.get("price") or 0)
            decision = str(item.get("decision") or "HOLD")
            confidence = int(item.get("confidence") or 0)

            if not symbol or price <= 0:
                skipped += 1
                continue

            conn.execute(
                """
                INSERT INTO ai_recommendations (
                    symbol,
                    recommendation_date,
                    generated_at,
                    price,
                    decision,
                    confidence,
                    risk,
                    position_pct,
                    source
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, recommendation_date)
                DO UPDATE SET
                    generated_at = excluded.generated_at,
                    price = excluded.price,
                    decision = excluded.decision,
                    confidence = excluded.confidence,
                    risk = excluded.risk,
                    position_pct = excluded.position_pct,
                    source = excluded.source
                """,
                (
                    symbol,
                    recommendation_date,
                    now.isoformat(),
                    price,
                    decision,
                    confidence,
                    item.get("risk"),
                    int(item.get("position") or 0),
                    item.get("source") or "NSE Signal Bot",
                ),
            )
            saved += 1

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return {
        "success": True,
        "date": recommendation_date,
        "saved": saved,
        "skipped": skipped,
    }


def get_recent_recommendations(
    limit: int = 100,
) -> List[Dict[str, Any]]:
    ensure_recommendation_table()

    conn = get_conn()

    try:
        rows = conn.execute(
            """
            SELECT *
            FROM ai_recommendations
            ORDER BY recommendation_date DESC, confidence DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()
