from __future__ import annotations

import json
import os
import sqlite3
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional

from services.interfaces import ISignalRepository


class SignalRepository(ISignalRepository):
    """
    SQLite-backed repository for finalized investment signals.

    Characteristics:
    - Shared by all Gunicorn workers.
    - Persists across application restarts.
    - Stores one authoritative latest signal per symbol.
    - Retains signal history for learning and performance analysis.
    - Normalizes incomplete or inconsistent engine output.
    """

    VALID_DECISIONS = {
        "STRONG BUY",
        "BUY",
        "HOLD",
        "WATCH",
        "SELL",
        "STRONG SELL",
        "AVOID",
    }

    def __init__(
        self,
        database_path: Optional[str] = None,
    ) -> None:
        project_root = Path(__file__).resolve().parent.parent

        configured_path = (
            database_path
            or os.getenv("SIGNAL_REPOSITORY_DB")
            or str(project_root / "data" / "signal_repository.db")
        )

        self._database_path = Path(configured_path).expanduser().resolve()
        self._database_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = RLock()
        self._initialize_database()

    @property
    def database_path(self) -> str:
        return str(self._database_path)

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _safe_float(
        value: Any,
        default: float = 0.0,
    ) -> float:
        try:
            if value is None:
                return float(default or 0.0)

            if isinstance(value, str):
                cleaned = value.strip().replace(",", "").replace("%", "")

                if not cleaned:
                    return float(default or 0.0)

                value = cleaned

            return float(value)
        except (TypeError, ValueError, OverflowError):
            try:
                return float(default or 0.0)
            except (TypeError, ValueError, OverflowError):
                return 0.0

    @classmethod
    def _safe_int(
        cls,
        value: Any,
        default: int = 0,
    ) -> int:
        try:
            return int(round(cls._safe_float(value, default)))
        except (TypeError, ValueError, OverflowError):
            return int(default or 0)

    @staticmethod
    def _clamp_score(value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            number = 0.0

        return round(max(0.0, min(100.0, number)), 2)

    @classmethod
    def _normalize_decision(cls, value: Any) -> str:
        decision = str(value or "HOLD").strip().upper()
        decision = decision.replace("-", " ")
        decision = " ".join(decision.split())

        aliases = {
            "ACCUMULATE": "BUY",
            "STRONG_BUY": "STRONG BUY",
            "STRONGBUY": "STRONG BUY",
            "NEUTRAL": "HOLD",
            "WAIT": "WATCH",
            "NO TRADE": "WATCH",
            "STRONG_SELL": "STRONG SELL",
            "STRONGSELL": "STRONG SELL",
            "REDUCE": "SELL",
        }

        decision = aliases.get(decision, decision)

        if decision not in cls.VALID_DECISIONS:
            return "HOLD"

        return decision

    @staticmethod
    def _normalize_symbol(value: Any) -> str:
        symbol = str(value or "").strip().upper()

        if not symbol:
            raise ValueError("Signal symbol is required.")

        return symbol

    @classmethod
    def _first_numeric(
        cls,
        signal: Dict[str, Any],
        keys: tuple[str, ...],
        default: float = 0.0,
    ) -> float:
        for key in keys:
            value = signal.get(key)

            if value is None:
                continue

            if isinstance(value, str) and not value.strip():
                continue

            return cls._safe_float(value, default)

        return cls._safe_float(default)

    @classmethod
    def _extract_rank_score(
        cls,
        signal: Dict[str, Any],
    ) -> float:
        value = cls._first_numeric(
            signal,
            (
                "rank_score",
                "committee_score",
                "final_score",
                "conviction_score",
                "confidence",
                "score",
                "ai_score",
                "technical_score",
                "prediction_score",
            ),
            0.0,
        )

        return cls._clamp_score(value)

    @classmethod
    def _normalize_signal(
        cls,
        signal: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not isinstance(signal, dict):
            raise TypeError("Signal must be supplied as a dictionary.")

        symbol = cls._normalize_symbol(signal.get("symbol"))

        decision = cls._normalize_decision(
            signal.get("decision")
            or signal.get("signal")
            or signal.get("final_decision")
            or signal.get("recommendation")
        )

        committee_score = cls._first_numeric(
            signal,
            (
                "committee_score",
                "final_score",
                "score",
                "ai_score",
                "confidence",
            ),
            0.0,
        )

        conviction_score = cls._first_numeric(
            signal,
            (
                "conviction_score",
                "ai_conviction_score",
            ),
            committee_score,
        )

        technical_score = cls._first_numeric(
            signal,
            (
                "technical_score",
                "technical_analysis_score",
                "score",
            ),
            0.0,
        )

        prediction_score = cls._first_numeric(
            signal,
            (
                "prediction_score",
                "predictive_score",
                "forecast_score",
            ),
            0.0,
        )

        confidence = cls._first_numeric(
            signal,
            (
                "confidence",
                "confidence_score",
                "committee_score",
                "final_score",
                "score",
            ),
            committee_score,
        )

        generated_timestamp = (
            signal.get("timestamp")
            or signal.get("generated_at")
            or signal.get("created_at")
            or cls._utc_now()
        )

        normalized = deepcopy(signal)

        normalized.update(
            {
                "symbol": symbol,
                "decision": decision,
                "signal": decision,
                "committee_score": cls._clamp_score(committee_score),
                "conviction_score": cls._clamp_score(conviction_score),
                "technical_score": cls._clamp_score(technical_score),
                "prediction_score": cls._clamp_score(prediction_score),
                "confidence": cls._safe_int(
                    cls._clamp_score(confidence)
                ),
                "institutional_signal": str(
                    signal.get("institutional_signal")
                    or signal.get("institutional")
                    or ""
                ).strip(),
                "market_regime": str(
                    signal.get("market_regime")
                    or signal.get("regime")
                    or ""
                ).strip(),
                "source": str(
                    signal.get("source")
                    or "AI Investment Committee"
                ).strip(),
                "timestamp": str(generated_timestamp),
                "stored_at": cls._utc_now(),
            }
        )

        normalized["rank_score"] = cls._extract_rank_score(normalized)

        return normalized

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self._database_path),
            timeout=30.0,
            isolation_level=None,
        )

        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute("PRAGMA foreign_keys = ON")

        return connection

    def _initialize_database(self) -> None:
        with self._lock:
            connection = self._connect()

            try:
                connection.execute("PRAGMA journal_mode = WAL")
                connection.execute("PRAGMA synchronous = NORMAL")

                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS latest_signals (
                        symbol TEXT PRIMARY KEY,
                        decision TEXT NOT NULL,
                        committee_score REAL NOT NULL DEFAULT 0,
                        conviction_score REAL NOT NULL DEFAULT 0,
                        technical_score REAL NOT NULL DEFAULT 0,
                        prediction_score REAL NOT NULL DEFAULT 0,
                        confidence INTEGER NOT NULL DEFAULT 0,
                        rank_score REAL NOT NULL DEFAULT 0,
                        institutional_signal TEXT NOT NULL DEFAULT '',
                        market_regime TEXT NOT NULL DEFAULT '',
                        source TEXT NOT NULL DEFAULT '',
                        signal_timestamp TEXT NOT NULL,
                        stored_at TEXT NOT NULL,
                        payload_json TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS
                        idx_latest_signals_decision
                    ON latest_signals(decision);

                    CREATE INDEX IF NOT EXISTS
                        idx_latest_signals_rank
                    ON latest_signals(rank_score DESC);

                    CREATE TABLE IF NOT EXISTS signal_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        decision TEXT NOT NULL,
                        committee_score REAL NOT NULL DEFAULT 0,
                        conviction_score REAL NOT NULL DEFAULT 0,
                        technical_score REAL NOT NULL DEFAULT 0,
                        prediction_score REAL NOT NULL DEFAULT 0,
                        confidence INTEGER NOT NULL DEFAULT 0,
                        rank_score REAL NOT NULL DEFAULT 0,
                        institutional_signal TEXT NOT NULL DEFAULT '',
                        market_regime TEXT NOT NULL DEFAULT '',
                        source TEXT NOT NULL DEFAULT '',
                        signal_timestamp TEXT NOT NULL,
                        stored_at TEXT NOT NULL,
                        payload_json TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS
                        idx_signal_history_symbol
                    ON signal_history(symbol);

                    CREATE INDEX IF NOT EXISTS
                        idx_signal_history_timestamp
                    ON signal_history(signal_timestamp);
                    """
                )
            finally:
                connection.close()

    @staticmethod
    def _serialize(signal: Dict[str, Any]) -> str:
        return json.dumps(
            signal,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        )

    @staticmethod
    def _deserialize(payload: str) -> Dict[str, Any]:
        try:
            data = json.loads(payload)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}

        if not isinstance(data, dict):
            return {}

        return data

    @classmethod
    def _row_to_signal(
        cls,
        row: sqlite3.Row,
    ) -> Dict[str, Any]:
        signal = cls._deserialize(row["payload_json"])

        signal.update(
            {
                "symbol": row["symbol"],
                "decision": row["decision"],
                "signal": row["decision"],
                "committee_score": float(row["committee_score"]),
                "conviction_score": float(row["conviction_score"]),
                "technical_score": float(row["technical_score"]),
                "prediction_score": float(row["prediction_score"]),
                "confidence": int(row["confidence"]),
                "rank_score": float(row["rank_score"]),
                "institutional_signal": row["institutional_signal"],
                "market_regime": row["market_regime"],
                "source": row["source"],
                "timestamp": row["signal_timestamp"],
                "stored_at": row["stored_at"],
            }
        )

        return signal

    @staticmethod
    def _database_values(
        signal: Dict[str, Any],
    ) -> tuple[Any, ...]:
        payload = SignalRepository._serialize(signal)

        return (
            signal["symbol"],
            signal["decision"],
            signal["committee_score"],
            signal["conviction_score"],
            signal["technical_score"],
            signal["prediction_score"],
            signal["confidence"],
            signal["rank_score"],
            signal["institutional_signal"],
            signal["market_regime"],
            signal["source"],
            signal["timestamp"],
            signal["stored_at"],
            payload,
        )

    def _save_normalized_signal(
        self,
        connection: sqlite3.Connection,
        signal: Dict[str, Any],
    ) -> None:
        values = self._database_values(signal)

        connection.execute(
            """
            INSERT INTO signal_history (
                symbol,
                decision,
                committee_score,
                conviction_score,
                technical_score,
                prediction_score,
                confidence,
                rank_score,
                institutional_signal,
                market_regime,
                source,
                signal_timestamp,
                stored_at,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )

        connection.execute(
            """
            INSERT INTO latest_signals (
                symbol,
                decision,
                committee_score,
                conviction_score,
                technical_score,
                prediction_score,
                confidence,
                rank_score,
                institutional_signal,
                market_regime,
                source,
                signal_timestamp,
                stored_at,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                decision = excluded.decision,
                committee_score = excluded.committee_score,
                conviction_score = excluded.conviction_score,
                technical_score = excluded.technical_score,
                prediction_score = excluded.prediction_score,
                confidence = excluded.confidence,
                rank_score = excluded.rank_score,
                institutional_signal = excluded.institutional_signal,
                market_regime = excluded.market_regime,
                source = excluded.source,
                signal_timestamp = excluded.signal_timestamp,
                stored_at = excluded.stored_at,
                payload_json = excluded.payload_json
            """,
            values,
        )

    def save_signal(
        self,
        signal: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized = self._normalize_signal(signal)

        with self._lock:
            connection = self._connect()

            try:
                connection.execute("BEGIN IMMEDIATE")
                self._save_normalized_signal(connection, normalized)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

        return deepcopy(normalized)

    def save_signals(
        self,
        signals: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if signals is None:
            return []

        if not isinstance(signals, list):
            raise TypeError("Signals must be supplied as a list.")

        normalized_signals = [
            self._normalize_signal(signal)
            for signal in signals
        ]

        if not normalized_signals:
            return []

        with self._lock:
            connection = self._connect()

            try:
                connection.execute("BEGIN IMMEDIATE")

                for signal in normalized_signals:
                    self._save_normalized_signal(connection, signal)

                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

        return deepcopy(normalized_signals)

    def get_signal(
        self,
        symbol: str,
    ) -> Optional[Dict[str, Any]]:
        normalized_symbol = self._normalize_symbol(symbol)

        connection = self._connect()

        try:
            row = connection.execute(
                """
                SELECT *
                FROM latest_signals
                WHERE symbol = ?
                LIMIT 1
                """,
                (normalized_symbol,),
            ).fetchone()
        finally:
            connection.close()

        if row is None:
            return None

        return self._row_to_signal(row)

    def get_all_signals(self) -> List[Dict[str, Any]]:
        connection = self._connect()

        try:
            rows = connection.execute(
                """
                SELECT *
                FROM latest_signals
                ORDER BY
                    rank_score DESC,
                    committee_score DESC,
                    confidence DESC,
                    symbol ASC
                """
            ).fetchall()
        finally:
            connection.close()

        return [
            self._row_to_signal(row)
            for row in rows
        ]

    def get_signals_by_decision(
        self,
        decision: str,
    ) -> List[Dict[str, Any]]:
        normalized_decision = self._normalize_decision(decision)

        connection = self._connect()

        try:
            rows = connection.execute(
                """
                SELECT *
                FROM latest_signals
                WHERE decision = ?
                ORDER BY
                    rank_score DESC,
                    committee_score DESC,
                    confidence DESC,
                    symbol ASC
                """,
                (normalized_decision,),
            ).fetchall()
        finally:
            connection.close()

        return [
            self._row_to_signal(row)
            for row in rows
        ]

    def get_top_signals(
        self,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        try:
            normalized_limit = int(limit)
        except (TypeError, ValueError):
            normalized_limit = 10

        if normalized_limit <= 0:
            return []

        connection = self._connect()

        try:
            rows = connection.execute(
                """
                SELECT *
                FROM latest_signals
                ORDER BY
                    rank_score DESC,
                    committee_score DESC,
                    confidence DESC,
                    symbol ASC
                LIMIT ?
                """,
                (normalized_limit,),
            ).fetchall()
        finally:
            connection.close()

        return [
            self._row_to_signal(row)
            for row in rows
        ]

    def get_signal_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        try:
            normalized_limit = max(1, int(limit))
        except (TypeError, ValueError):
            normalized_limit = 100

        connection = self._connect()

        try:
            if symbol:
                normalized_symbol = self._normalize_symbol(symbol)

                rows = connection.execute(
                    """
                    SELECT *
                    FROM signal_history
                    WHERE symbol = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (normalized_symbol, normalized_limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM signal_history
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (normalized_limit,),
                ).fetchall()
        finally:
            connection.close()

        return [
            self._row_to_signal(row)
            for row in rows
        ]

    def count(self) -> int:
        connection = self._connect()

        try:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM latest_signals"
            ).fetchone()
        finally:
            connection.close()

        return int(row["total"] if row else 0)

    def history_count(self) -> int:
        connection = self._connect()

        try:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM signal_history"
            ).fetchone()
        finally:
            connection.close()

        return int(row["total"] if row else 0)

    def clear(self) -> None:
        with self._lock:
            connection = self._connect()

            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("DELETE FROM latest_signals")
                connection.execute("DELETE FROM signal_history")
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()


_default_signal_repository = SignalRepository()


def get_signal_repository() -> SignalRepository:
    """
    Return the shared SQLite-backed signal repository.
    """
    return _default_signal_repository
