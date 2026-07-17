#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$HOME/nse_signal_bot_v10_3}"
cd "$PROJECT_DIR"

STAMP="$(date +%F_%H-%M-%S)"
BACKUP_DIR="backups/intelligence_database/$STAMP"

mkdir -p "$BACKUP_DIR" migrations

echo "======================================================"
echo "MIP PRO Intelligence Database — Phase 1"
echo "======================================================"

echo
echo "==> Resolving current database"

DB_PATH="$(
    venv/bin/python - <<'PY'
from pathlib import Path
from services.database import DB_PATH

print(Path(DB_PATH).expanduser().resolve())
PY
)"

echo "Database: $DB_PATH"

if [[ ! -f "$DB_PATH" ]]; then
    echo "ERROR: Database file does not exist: $DB_PATH"
    exit 1
fi

echo
echo "==> Creating safety backup"

cp "$DB_PATH" "$BACKUP_DIR/$(basename "$DB_PATH")"
cp services/database.py "$BACKUP_DIR/database.py"

echo "Backup saved in: $BACKUP_DIR"

echo
echo "==> Running pre-migration integrity check"

venv/bin/python - "$DB_PATH" <<'PY'
import sqlite3
import sys

database_path = sys.argv[1]

with sqlite3.connect(database_path) as connection:
    result = connection.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]

print("Integrity:", result)

if result != "ok":
    raise SystemExit(
        f"Database integrity check failed: {result}"
    )
PY

echo
echo "==> Creating SQL migration"

cat > migrations/001_intelligence_history.sql <<'SQL'
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS intelligence_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    run_id TEXT NOT NULL UNIQUE,

    generated_at TEXT NOT NULL,
    completed_at TEXT,

    engine_version TEXT,
    source TEXT NOT NULL DEFAULT 'intelligence_orchestrator',

    market_regime TEXT,
    regime_confidence REAL,
    market_risk_level TEXT,

    stock_count INTEGER NOT NULL DEFAULT 0,
    prediction_count INTEGER NOT NULL DEFAULT 0,
    committee_decision_count INTEGER NOT NULL DEFAULT 0,

    prediction_center_seconds REAL NOT NULL DEFAULT 0,
    committee_seconds REAL NOT NULL DEFAULT 0,
    total_seconds REAL NOT NULL DEFAULT 0,

    cache_hit INTEGER NOT NULL DEFAULT 0
        CHECK (cache_hit IN (0, 1)),

    status TEXT NOT NULL DEFAULT 'completed'
        CHECK (
            status IN (
                'started',
                'completed',
                'partial',
                'failed'
            )
        ),

    error_message TEXT,
    metadata_json TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS
idx_intelligence_runs_generated_at
ON intelligence_runs(generated_at);

CREATE INDEX IF NOT EXISTS
idx_intelligence_runs_market_regime
ON intelligence_runs(market_regime);

CREATE INDEX IF NOT EXISTS
idx_intelligence_runs_status
ON intelligence_runs(status);


CREATE TABLE IF NOT EXISTS prediction_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    run_id TEXT NOT NULL,
    symbol TEXT NOT NULL,

    rank_position INTEGER,

    recommendation TEXT,
    signal TEXT,

    prediction_score REAL,
    confidence REAL,
    probability REAL,

    current_price REAL,
    predicted_price REAL,
    target_price REAL,
    expected_return REAL,

    risk_level TEXT,
    prediction_horizon TEXT,

    reasons_json TEXT,
    indicators_json TEXT,
    payload_json TEXT,

    generated_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (run_id)
        REFERENCES intelligence_runs(run_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    UNIQUE (run_id, symbol)
);

CREATE INDEX IF NOT EXISTS
idx_prediction_snapshots_symbol
ON prediction_snapshots(symbol);

CREATE INDEX IF NOT EXISTS
idx_prediction_snapshots_generated_at
ON prediction_snapshots(generated_at);

CREATE INDEX IF NOT EXISTS
idx_prediction_snapshots_recommendation
ON prediction_snapshots(recommendation);

CREATE INDEX IF NOT EXISTS
idx_prediction_snapshots_score
ON prediction_snapshots(prediction_score);


CREATE TABLE IF NOT EXISTS committee_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    run_id TEXT NOT NULL,
    symbol TEXT NOT NULL,

    rank_position INTEGER,

    decision TEXT,
    committee_score REAL,
    confidence REAL,
    conviction_level TEXT,
    risk_level TEXT,

    technical_vote TEXT,
    quantitative_vote TEXT,
    institutional_vote TEXT,
    risk_vote TEXT,
    learning_vote TEXT,

    entry_price REAL,
    target_price REAL,
    stop_loss REAL,
    expected_return REAL,

    votes_json TEXT,
    reasons_json TEXT,
    payload_json TEXT,

    generated_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (run_id)
        REFERENCES intelligence_runs(run_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    UNIQUE (run_id, symbol)
);

CREATE INDEX IF NOT EXISTS
idx_committee_snapshots_symbol
ON committee_snapshots(symbol);

CREATE INDEX IF NOT EXISTS
idx_committee_snapshots_generated_at
ON committee_snapshots(generated_at);

CREATE INDEX IF NOT EXISTS
idx_committee_snapshots_decision
ON committee_snapshots(decision);

CREATE INDEX IF NOT EXISTS
idx_committee_snapshots_score
ON committee_snapshots(committee_score);


CREATE TABLE IF NOT EXISTS market_regime_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    run_id TEXT NOT NULL UNIQUE,

    generated_at TEXT NOT NULL,

    regime TEXT NOT NULL,
    confidence REAL,

    risk_level TEXT,
    volatility_level TEXT,
    breadth_score REAL,
    momentum_score REAL,
    trend_score REAL,

    bullish_count INTEGER,
    bearish_count INTEGER,
    neutral_count INTEGER,

    reasons_json TEXT,
    payload_json TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (run_id)
        REFERENCES intelligence_runs(run_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS
idx_market_regime_history_generated_at
ON market_regime_history(generated_at);

CREATE INDEX IF NOT EXISTS
idx_market_regime_history_regime
ON market_regime_history(regime);
SQL

echo
echo "==> Applying migration"

venv/bin/python - "$DB_PATH" <<'PY'
from pathlib import Path
import sqlite3
import sys

database_path = Path(sys.argv[1])
migration_path = Path(
    "migrations/001_intelligence_history.sql"
)

sql = migration_path.read_text(encoding="utf-8")

connection = sqlite3.connect(
    database_path,
    timeout=30,
)

try:
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")

    connection.executescript(sql)
    connection.commit()

finally:
    connection.close()

print("Migration applied successfully.")
PY

echo
echo "==> Verifying tables, columns and indexes"

venv/bin/python - "$DB_PATH" <<'PY'
from __future__ import annotations

import sqlite3
import sys

database_path = sys.argv[1]

required_tables = {
    "intelligence_runs": {
        "run_id",
        "generated_at",
        "market_regime",
        "prediction_count",
        "committee_decision_count",
        "total_seconds",
        "status",
    },
    "prediction_snapshots": {
        "run_id",
        "symbol",
        "recommendation",
        "prediction_score",
        "confidence",
        "payload_json",
    },
    "committee_snapshots": {
        "run_id",
        "symbol",
        "decision",
        "committee_score",
        "confidence",
        "votes_json",
        "payload_json",
    },
    "market_regime_history": {
        "run_id",
        "generated_at",
        "regime",
        "confidence",
        "payload_json",
    },
}

connection = sqlite3.connect(database_path)
connection.row_factory = sqlite3.Row
connection.execute("PRAGMA foreign_keys = ON")

try:
    existing_tables = {
        row["name"]
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        )
    }

    for table_name, required_columns in required_tables.items():
        if table_name not in existing_tables:
            raise AssertionError(
                f"Missing table: {table_name}"
            )

        columns = {
            row["name"]
            for row in connection.execute(
                f'PRAGMA table_info("{table_name}")'
            )
        }

        missing_columns = required_columns - columns

        if missing_columns:
            raise AssertionError(
                f"{table_name} missing columns: "
                f"{sorted(missing_columns)}"
            )

        row_count = connection.execute(
            f'SELECT COUNT(*) FROM "{table_name}"'
        ).fetchone()[0]

        indexes = [
            row["name"]
            for row in connection.execute(
                f'PRAGMA index_list("{table_name}")'
            )
        ]

        print()
        print("TABLE:", table_name)
        print("ROWS:", row_count)
        print("COLUMNS:", len(columns))
        print("INDEXES:", len(indexes))

    foreign_keys = connection.execute(
        "PRAGMA foreign_keys"
    ).fetchone()[0]

    integrity = connection.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]

    print()
    print("FOREIGN KEYS:", foreign_keys)
    print("INTEGRITY:", integrity)

    assert foreign_keys == 1
    assert integrity == "ok"

finally:
    connection.close()

print()
print("INTELLIGENCE DATABASE MIGRATION: PASS")
PY

echo
echo "==> Running foreign-key transaction test"

venv/bin/python - "$DB_PATH" <<'PY'
from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
import sys
import uuid

database_path = sys.argv[1]
run_id = f"migration-test-{uuid.uuid4().hex}"

connection = sqlite3.connect(
    database_path,
    timeout=30,
)

try:
    connection.execute("PRAGMA foreign_keys = ON")

    now = datetime.now(timezone.utc).isoformat()

    connection.execute(
        """
        INSERT INTO intelligence_runs (
            run_id,
            generated_at,
            completed_at,
            engine_version,
            market_regime,
            stock_count,
            prediction_count,
            committee_decision_count,
            status,
            metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            now,
            now,
            "migration-test",
            "SIDEWAYS",
            1,
            1,
            1,
            "completed",
            json.dumps(
                {"temporary_test": True}
            ),
        ),
    )

    connection.execute(
        """
        INSERT INTO prediction_snapshots (
            run_id,
            symbol,
            rank_position,
            recommendation,
            prediction_score,
            confidence,
            generated_at,
            payload_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            "TEST",
            1,
            "HOLD",
            50.0,
            50.0,
            now,
            json.dumps({"test": True}),
        ),
    )

    connection.execute(
        """
        INSERT INTO committee_snapshots (
            run_id,
            symbol,
            rank_position,
            decision,
            committee_score,
            confidence,
            generated_at,
            payload_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            "TEST",
            1,
            "HOLD",
            50.0,
            50.0,
            now,
            json.dumps({"test": True}),
        ),
    )

    connection.execute(
        """
        INSERT INTO market_regime_history (
            run_id,
            generated_at,
            regime,
            confidence,
            payload_json
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            run_id,
            now,
            "SIDEWAYS",
            50.0,
            json.dumps({"test": True}),
        ),
    )

    prediction_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM prediction_snapshots
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()[0]

    committee_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM committee_snapshots
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()[0]

    regime_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM market_regime_history
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()[0]

    assert prediction_count == 1
    assert committee_count == 1
    assert regime_count == 1

    # Deleting the parent should cascade to all test children.
    connection.execute(
        """
        DELETE FROM intelligence_runs
        WHERE run_id = ?
        """,
        (run_id,),
    )

    remaining_children = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM prediction_snapshots
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()[0]
        +
        connection.execute(
            """
            SELECT COUNT(*)
            FROM committee_snapshots
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()[0]
        +
        connection.execute(
            """
            SELECT COUNT(*)
            FROM market_regime_history
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()[0]
    )

    assert remaining_children == 0

    connection.commit()

finally:
    connection.close()

print("INSERT TEST: PASS")
print("CASCADE DELETE TEST: PASS")
PY

echo
echo "==> Creating schema report"

venv/bin/python - "$DB_PATH" <<'PY'
from pathlib import Path
import sqlite3
import sys

database_path = sys.argv[1]
report_path = Path(
    "reports/intelligence_database_phase1_schema.txt"
)

tables = (
    "intelligence_runs",
    "prediction_snapshots",
    "committee_snapshots",
    "market_regime_history",
)

connection = sqlite3.connect(database_path)
connection.row_factory = sqlite3.Row

with report_path.open("w", encoding="utf-8") as report:
    report.write("MIP PRO INTELLIGENCE DATABASE PHASE 1\n")
    report.write("=" * 60 + "\n\n")

    for table_name in tables:
        count = connection.execute(
            f'SELECT COUNT(*) FROM "{table_name}"'
        ).fetchone()[0]

        report.write(
            f"{table_name}: {count} rows\n"
        )

        columns = connection.execute(
            f'PRAGMA table_info("{table_name}")'
        ).fetchall()

        for column in columns:
            report.write(
                f"  - {column['name']} "
                f"{column['type']}\n"
            )

        report.write("\n")

connection.close()

print(f"Schema report: {report_path}")
PY

echo
echo "==> Creating Git checkpoint"

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git add \
        migrations/001_intelligence_history.sql \
        scripts/install_intelligence_database_phase1.sh

    if git diff --cached --quiet; then
        echo "No new Git changes to commit."
    else
        git commit -m \
            "add intelligence history database schema"
    fi
fi

echo
echo "======================================================"
echo "MIP PRO Intelligence Database Phase 1: COMPLETE"
echo "======================================================"
echo
echo "Existing operational tables were not modified."
echo "New history tables are ready for orchestrator data."
echo
echo "Backup: $BACKUP_DIR"
