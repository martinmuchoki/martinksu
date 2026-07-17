#!/usr/bin/env bash
set -euo pipefail

cd "${PROJECT_DIR:-$HOME/nse_signal_bot_v10_3}"

STAMP="$(date +%F_%H-%M-%S)"
BACKUP_DIR="backups/orchestrator_repository_integration/$STAMP"

mkdir -p "$BACKUP_DIR" scripts reports

echo "======================================================"
echo "MIP PRO Orchestrator Repository Integration"
echo "======================================================"

cp services/intelligence_orchestrator.py \
   "$BACKUP_DIR/intelligence_orchestrator.py"

echo "Backup: $BACKUP_DIR/intelligence_orchestrator.py"

python3 - <<'PY'
from pathlib import Path

path = Path("services/intelligence_orchestrator.py")
text = path.read_text(encoding="utf-8")

if "save_intelligence_context" in text:
    raise SystemExit(
        "Repository integration already appears to be installed."
    )

# -----------------------------------------------------
# 1. Add UUID import
# -----------------------------------------------------

old = '''from typing import Any, Dict
from zoneinfo import ZoneInfo
'''

new = '''from typing import Any, Dict
from uuid import uuid4
from zoneinfo import ZoneInfo
'''

if old not in text:
    raise SystemExit("Unable to locate standard import block.")

text = text.replace(old, new, 1)

# -----------------------------------------------------
# 2. Add repository import
# -----------------------------------------------------

old = '''from services.prediction_center import (
    build_prediction_center,
)
'''

new = '''from services.prediction_center import (
    build_prediction_center,
)
from services.intelligence_repository import (
    save_intelligence_context,
)
'''

if old not in text:
    raise SystemExit("Unable to locate prediction center import.")

text = text.replace(old, new, 1)

# -----------------------------------------------------
# 3. Mark cached responses without persisting again
# -----------------------------------------------------

old = '''            cached["cache"] = {
                "hit": True,
                "ttl_seconds": cache_seconds,
            }

            return cached
'''

new = '''            cached["cache"] = {
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
'''

if old not in text:
    raise SystemExit("Unable to locate cache-hit return block.")

text = text.replace(old, new, 1)

# -----------------------------------------------------
# 4. Add run_id to every fresh context
# -----------------------------------------------------

old = '''        payload: Dict[str, Any] = {
            "version":
                "MIP PRO Intelligence Orchestrator Phase 1",
            "generated_at": _now_iso(),
'''

new = '''        payload: Dict[str, Any] = {
            "version":
                "MIP PRO Intelligence Orchestrator Phase 2",
            "run_id": f"intel-{uuid4().hex}",
            "generated_at": _now_iso(),
'''

if old not in text:
    raise SystemExit("Unable to locate payload creation block.")

text = text.replace(old, new, 1)

# -----------------------------------------------------
# 5. Persist fresh context before placing it in cache
# -----------------------------------------------------

old = '''        _CONTEXT_CACHE["payload"] = deepcopy(
            payload
        )
        _CONTEXT_CACHE[
            "created_monotonic"
        ] = monotonic()

        return payload
'''

new = '''        try:
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
'''

if old not in text:
    raise SystemExit("Unable to locate final cache and return block.")

text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")

print("Orchestrator repository integration installed.")
PY

echo
echo "==> Compiling services"

venv/bin/python -m py_compile \
    services/intelligence_orchestrator.py \
    services/intelligence_repository.py

echo "Compilation: PASS"

echo
echo "==> Showing integration points"

grep -nE \
'uuid4|save_intelligence_context|run_id|repository|Phase 2' \
services/intelligence_orchestrator.py

echo
echo "==> Running live persistence and cache test"
echo "This fresh intelligence run may take about 12 seconds."

venv/bin/python - <<'PY'
from services.intelligence_orchestrator import (
    build_intelligence_context,
    clear_intelligence_cache,
)
from services.intelligence_repository import (
    get_repository_counts,
)

before = get_repository_counts()

print("COUNTS BEFORE:", before)

clear_intelligence_cache()

fresh = build_intelligence_context(
    force_refresh=True,
    include_committee=True,
)

fresh_repository = fresh.get("repository", {})

print()
print("FRESH RUN ID:", fresh.get("run_id"))
print("FRESH CACHE:", fresh.get("cache"))
print("FRESH REPOSITORY:", fresh_repository)
print("FRESH PREDICTIONS:", fresh.get("prediction_count"))
print(
    "FRESH DECISIONS:",
    fresh.get(
        "investment_committee",
        {},
    ).get("decision_count"),
)

if not fresh_repository.get("saved"):
    raise AssertionError(
        "Fresh intelligence context was not saved: "
        f"{fresh_repository}"
    )

after_fresh = get_repository_counts()

print()
print("COUNTS AFTER FRESH:", after_fresh)

assert (
    after_fresh["intelligence_runs"]
    == before["intelligence_runs"] + 1
)

assert (
    after_fresh["prediction_snapshots"]
    > before["prediction_snapshots"]
)

assert (
    after_fresh["committee_snapshots"]
    > before["committee_snapshots"]
)

assert (
    after_fresh["market_regime_history"]
    == before["market_regime_history"] + 1
)

cached = build_intelligence_context(
    force_refresh=False,
    include_committee=True,
)

cached_repository = cached.get("repository", {})

print()
print("CACHED RUN ID:", cached.get("run_id"))
print("CACHED CACHE:", cached.get("cache"))
print("CACHED REPOSITORY:", cached_repository)

assert cached.get("cache", {}).get("hit") is True
assert cached_repository.get("saved") is False
assert cached_repository.get("cache_hit") is True
assert cached.get("run_id") == fresh.get("run_id")

after_cache = get_repository_counts()

print()
print("COUNTS AFTER CACHE:", after_cache)

assert after_cache == after_fresh

print()
print("FRESH PERSISTENCE TEST: PASS")
print("CACHE DUPLICATION TEST: PASS")
print("ORCHESTRATOR REPOSITORY INTEGRATION: PASS")
PY

echo
echo "==> Creating database summary"

venv/bin/python - <<'PY'
import sqlite3

from services.database import DB_PATH

connection = sqlite3.connect(DB_PATH)
connection.row_factory = sqlite3.Row
connection.execute("PRAGMA foreign_keys = ON")

latest = connection.execute(
    """
    SELECT
        run_id,
        generated_at,
        market_regime,
        prediction_count,
        committee_decision_count,
        total_seconds,
        status
    FROM intelligence_runs
    ORDER BY id DESC
    LIMIT 1
    """
).fetchone()

print("LATEST SAVED INTELLIGENCE RUN:")

if latest:
    for key in latest.keys():
        print(f"{key}: {latest[key]}")
else:
    print("No intelligence run found.")

integrity = connection.execute(
    "PRAGMA integrity_check"
).fetchone()[0]

print("INTEGRITY:", integrity)

connection.close()

assert integrity == "ok"
PY

echo
echo "==> Creating Git checkpoint"

git add \
    services/intelligence_orchestrator.py \
    scripts/install_orchestrator_repository_integration.sh

if git diff --cached --quiet; then
    echo "No Git changes to commit."
else
    git commit -m \
        "persist fresh orchestrator intelligence runs"
fi

echo
echo "======================================================"
echo "Orchestrator Repository Integration: COMPLETE"
echo "======================================================"
echo
echo "Fresh intelligence runs are now persisted."
echo "Cache hits do not create duplicate records."
echo "Backup: $BACKUP_DIR"
