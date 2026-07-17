#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$HOME/nse_signal_bot_v10_3}"
cd "$PROJECT_DIR"

STAMP="$(date +%F_%H-%M-%S)"
BACKUP_DIR="backups/orchestrator/$STAMP"

mkdir -p "$BACKUP_DIR/services"

echo "=============================================="
echo "MIP PRO Intelligence Orchestrator — Phase 1"
echo "=============================================="

echo
echo "==> Creating backups"

cp services/ai_investment_committee.py \
   "$BACKUP_DIR/services/ai_investment_committee.py"

if [[ -f services/intelligence_orchestrator.py ]]; then
    cp services/intelligence_orchestrator.py \
       "$BACKUP_DIR/services/intelligence_orchestrator.py"
fi

echo "Backup: $BACKUP_DIR"

echo
echo "==> Updating Investment Committee"

venv/bin/python - <<'PY'
from pathlib import Path

path = Path("services/ai_investment_committee.py")
text = path.read_text(encoding="utf-8")

old_signature = (
    "def build_ai_investment_committee() -> Dict[str, Any]:\n"
    "    prediction_center = build_prediction_center()\n"
)

new_signature = (
    "def build_ai_investment_committee(\n"
    "    prediction_center: Dict[str, Any] | None = None,\n"
    ") -> Dict[str, Any]:\n"
    "    if prediction_center is None:\n"
    "        prediction_center = build_prediction_center()\n"
)

if old_signature in text:
    text = text.replace(
        old_signature,
        new_signature,
        1,
    )

    path.write_text(text, encoding="utf-8")
    print("Committee now accepts shared Prediction Center data.")

elif new_signature in text:
    print("Committee shared-context support already installed.")

else:
    raise SystemExit(
        "Unable to locate build_ai_investment_committee function."
    )
PY

echo
echo "==> Creating Intelligence Orchestrator"

cat > services/intelligence_orchestrator.py <<'PY'
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
PY

echo
echo "==> Compiling"

venv/bin/python -m py_compile \
    services/intelligence_orchestrator.py \
    services/ai_investment_committee.py \
    services/prediction_center.py

echo "Compilation successful."

echo
echo "==> Running functional tests"

venv/bin/python - <<'PY'
from time import perf_counter

from services.intelligence_orchestrator import (
    build_intelligence_context,
    clear_intelligence_cache,
)


clear_intelligence_cache()

started = perf_counter()

first = build_intelligence_context(
    force_refresh=True,
)

first_wall_time = perf_counter() - started

started = perf_counter()

second = build_intelligence_context()

second_wall_time = perf_counter() - started

prediction_center = first.get(
    "prediction_center",
    {},
)

committee = first.get(
    "investment_committee",
    {},
) or {}

print()
print("VERSION:", first.get("version"))
print(
    "PREDICTIONS:",
    len(
        prediction_center.get(
            "predictions",
            [],
        )
    ),
)
print(
    "DECISIONS:",
    len(
        committee.get(
            "decisions",
            [],
        )
    ),
)
print(
    "MARKET REGIME:",
    (
        first.get("market_regime")
        or {}
    ).get("regime"),
)
print(
    "TOP COMMITTEE STOCK:",
    (
        committee.get("summary")
        or {}
    ).get("top_symbol"),
)
print("ENGINE TIMING:", first.get("timing"))
print(
    "FIRST WALL TIME:",
    round(first_wall_time, 4),
)
print(
    "SECOND CACHE HIT:",
    second.get("cache", {}).get("hit"),
)
print(
    "SECOND WALL TIME:",
    round(second_wall_time, 6),
)

assert len(
    prediction_center.get(
        "predictions",
        [],
    )
) == 20

assert len(
    committee.get(
        "decisions",
        [],
    )
) == 20

assert second.get(
    "cache",
    {},
).get("hit") is True

print()
print("ORCHESTRATOR TEST: PASS")
PY

echo
echo "==> Creating Git checkpoint"

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git add \
        services/intelligence_orchestrator.py \
        services/ai_investment_committee.py \
        scripts/install_intelligence_orchestrator_phase1.sh

    if git diff --cached --quiet; then
        echo "No new Git changes to commit."
    else
        git commit -m \
            "add phase 1 intelligence orchestrator"
    fi
fi

echo
echo "=============================================="
echo "Phase 1 Intelligence Orchestrator installed"
echo "=============================================="
