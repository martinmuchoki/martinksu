#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="/root/nse_signal_bot_v10_3"
REPORT_SCRIPT="$PROJECT_ROOT/scripts/report_ai_cio_policy_shadow.py"

cd "$PROJECT_ROOT"

echo "======================================================"
echo " MIP PRO — AI CIO POLICY PHASE 12.4C OBSERVABILITY"
echo "======================================================"

mkdir -p scripts logs/ai_cio_policy

cat > "$REPORT_SCRIPT" <<'PY'
#!/usr/bin/env python3

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from services.intelligence_orchestrator import (
    get_ai_cio_normalized_comparison,
)


DECISIONS = {
    "STRONG_BUY",
    "BUY",
    "HOLD",
    "REDUCE",
    "SELL",
    "AVOID",
}


def normalize_decision(value: Any) -> str:
    normalized = str(value or "UNKNOWN").strip().upper()
    normalized = normalized.replace(" ", "_").replace("-", "_")

    aliases = {
        "STRONGBUY": "STRONG_BUY",
        "STRONG_BUY": "STRONG_BUY",
        "ACCUMULATE": "BUY",
        "WATCH": "HOLD",
        "WAIT": "HOLD",
        "EXIT": "SELL",
    }

    normalized = aliases.get(normalized, normalized)

    return (
        normalized
        if normalized in DECISIONS
        else "UNKNOWN"
    )


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        if value is None:
            return default

        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        if value is None:
            return default

        return int(float(value))
    except (TypeError, ValueError):
        return default


def first_present(
    source: Dict[str, Any],
    keys: Iterable[str],
    default: Any = None,
) -> Any:
    for key in keys:
        value = source.get(key)

        if value not in (None, ""):
            return value

    return default


def find_policy_records(
    value: Any,
    *,
    path: str = "root",
    seen: Optional[Set[int]] = None,
) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Recursively locate AI CIO decisions containing source_metadata.policy_shadow.

    The production comparison payload may evolve, so this scanner avoids
    relying on one fixed list path.
    """

    if seen is None:
        seen = set()

    results: List[Tuple[str, Dict[str, Any]]] = []

    if isinstance(value, dict):
        object_id = id(value)

        if object_id in seen:
            return results

        seen.add(object_id)

        source_metadata = value.get("source_metadata")

        if isinstance(source_metadata, dict):
            shadow = source_metadata.get("policy_shadow")

            if isinstance(shadow, dict):
                results.append((path, value))

        for key, child in value.items():
            results.extend(
                find_policy_records(
                    child,
                    path=f"{path}.{key}",
                    seen=seen,
                )
            )

    elif isinstance(value, list):
        object_id = id(value)

        if object_id in seen:
            return results

        seen.add(object_id)

        for index, child in enumerate(value):
            results.extend(
                find_policy_records(
                    child,
                    path=f"{path}[{index}]",
                    seen=seen,
                )
            )

    return results


def deduplicate_records(
    records: List[Tuple[str, Dict[str, Any]]],
) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Remove duplicate appearances of the same symbol and decision payload.
    """

    unique: List[Tuple[str, Dict[str, Any]]] = []
    seen: Set[Tuple[str, str, str, float]] = set()

    for path, record in records:
        metadata = record.get("source_metadata") or {}
        shadow = metadata.get("policy_shadow") or {}

        symbol = str(
            first_present(
                record,
                ("symbol", "ticker", "security"),
                first_present(
                    shadow,
                    ("symbol", "ticker"),
                    "",
                ),
            )
        ).strip().upper()

        current = normalize_decision(
            first_present(
                record,
                (
                    "decision",
                    "final_decision",
                    "recommendation",
                    "action",
                ),
            )
        )

        shadow_decision = normalize_decision(
            first_present(
                shadow,
                (
                    "decision",
                    "final_decision",
                    "recommendation",
                    "action",
                ),
            )
        )

        score = safe_float(
            first_present(
                shadow,
                (
                    "composite_score",
                    "decision_score",
                    "score",
                ),
                0.0,
            )
        )

        key = (
            symbol,
            current,
            shadow_decision,
            round(score, 4),
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append((path, record))

    return unique


def build_row(
    path: str,
    record: Dict[str, Any],
) -> Dict[str, Any]:
    metadata = record.get("source_metadata") or {}
    shadow = metadata.get("policy_shadow") or {}

    symbol = str(
        first_present(
            record,
            ("symbol", "ticker", "security"),
            first_present(
                shadow,
                ("symbol", "ticker"),
                "UNKNOWN",
            ),
        )
    ).strip().upper()

    current = normalize_decision(
        first_present(
            record,
            (
                "decision",
                "final_decision",
                "recommendation",
                "action",
            ),
        )
    )

    shadow_decision = normalize_decision(
        first_present(
            shadow,
            (
                "decision",
                "final_decision",
                "recommendation",
                "action",
            ),
        )
    )

    risk_status = str(
        first_present(
            shadow,
            ("risk_status",),
            first_present(
                record,
                ("risk_status",),
                "UNKNOWN",
            ),
        )
    ).strip().upper()

    risk_veto = bool(
        first_present(
            shadow,
            ("risk_veto",),
            first_present(
                record,
                ("risk_veto",),
                risk_status == "VETOED",
            ),
        )
    )

    return {
        "symbol": symbol,
        "current_decision": current,
        "shadow_decision": shadow_decision,
        "match": current == shadow_decision,
        "composite_score": safe_float(
            first_present(
                shadow,
                (
                    "composite_score",
                    "decision_score",
                    "score",
                ),
                0.0,
            )
        ),
        "confidence": safe_float(
            shadow.get("confidence", 0.0)
        ),
        "conviction": str(
            shadow.get("conviction", "UNKNOWN")
        ).strip().upper(),
        "valid_engine_count": safe_int(
            first_present(
                shadow,
                (
                    "valid_engine_count",
                    "engine_count",
                    "supporting_engine_count",
                ),
                0,
            )
        ),
        "risk_status": risk_status,
        "risk_veto": risk_veto,
        "warnings": list(
            shadow.get("warnings") or []
        ),
        "reasons": list(
            shadow.get("reasons") or []
        ),
        "payload_path": path,
    }


def render_report(
    rows: List[Dict[str, Any]],
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    current_counts = Counter()
    shadow_counts = Counter()
    transitions = Counter()
    risk_counts = Counter()

    matches = 0

    print("=" * 112)
    print("AI CIO POLICY PHASE 12.4C — LIVE SHADOW OBSERVABILITY")
    print("=" * 112)
    print(
        f"{'SYMBOL':<10}"
        f"{'CURRENT':<15}"
        f"{'SHADOW':<15}"
        f"{'SCORE':<10}"
        f"{'CONF':<10}"
        f"{'ENGINES':<10}"
        f"{'RISK':<14}"
        f"STATUS"
    )
    print("-" * 112)

    for row in sorted(
        rows,
        key=lambda item: (
            not item["risk_veto"],
            not item["match"],
            -item["composite_score"],
            item["symbol"],
        ),
    ):
        current = row["current_decision"]
        shadow = row["shadow_decision"]

        current_counts[current] += 1
        shadow_counts[shadow] += 1
        transitions[(current, shadow)] += 1
        risk_counts[row["risk_status"]] += 1

        if row["match"]:
            matches += 1

        status = (
            "MATCH"
            if row["match"]
            else "DIFF"
        )

        if row["risk_veto"]:
            status = f"{status}/VETO"

        print(
            f"{row['symbol']:<10}"
            f"{current:<15}"
            f"{shadow:<15}"
            f"{row['composite_score']:<10.2f}"
            f"{row['confidence']:<10.2f}"
            f"{row['valid_engine_count']:<10}"
            f"{row['risk_status']:<14}"
            f"{status}"
        )

    total = len(rows)
    differences = total - matches

    match_rate = (
        matches / total * 100.0
        if total
        else 0.0
    )

    veto_count = sum(
        1
        for row in rows
        if row["risk_veto"]
    )

    print()
    print("=" * 112)
    print("OBSERVABILITY SUMMARY")
    print("=" * 112)
    print(f"Shadow records:       {total}")
    print(f"Matches:              {matches}")
    print(f"Differences:          {differences}")
    print(f"Agreement rate:       {match_rate:.2f}%")
    print(f"Risk vetoes:          {veto_count}")

    print()
    print("Current decision distribution:")

    for decision, count in sorted(
        current_counts.items()
    ):
        print(f"  {decision:<16} {count}")

    print()
    print("Shadow decision distribution:")

    for decision, count in sorted(
        shadow_counts.items()
    ):
        print(f"  {decision:<16} {count}")

    print()
    print("Decision transitions:")

    for (current, shadow), count in sorted(
        transitions.items(),
        key=lambda item: (
            -item[1],
            item[0][0],
            item[0][1],
        ),
    ):
        print(
            f"  {current:<16} -> "
            f"{shadow:<16} {count}"
        )

    print()
    print("Risk-status distribution:")

    for status, count in sorted(
        risk_counts.items()
    ):
        print(f"  {status:<16} {count}")

    source_summary = payload.get("summary")

    if isinstance(source_summary, dict):
        print()
        print("Production comparison summary:")
        print(
            json.dumps(
                source_summary,
                indent=2,
                default=str,
            )
        )

    return {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "phase": "12.4C",
        "mode": "shadow-observability",
        "production_decisions_unchanged": True,
        "record_count": total,
        "matches": matches,
        "differences": differences,
        "agreement_rate_pct": round(
            match_rate,
            2,
        ),
        "risk_veto_count": veto_count,
        "current_distribution": dict(
            current_counts
        ),
        "shadow_distribution": dict(
            shadow_counts
        ),
        "risk_distribution": dict(
            risk_counts
        ),
        "transitions": {
            f"{current}->{shadow}": count
            for (current, shadow), count
            in transitions.items()
        },
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate the AI CIO Phase 12.4C "
            "policy-shadow observability report."
        )
    )

    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force rebuilding the production intelligence context.",
    )

    parser.add_argument(
        "--minimum-score",
        type=float,
        default=25.0,
        help="Adaptive source-normalization minimum score.",
    )

    parser.add_argument(
        "--max-depth",
        type=int,
        default=8,
        help="Maximum adaptive source-discovery depth.",
    )

    parser.add_argument(
        "--output",
        default="",
        help="Optional JSON report output path.",
    )

    args = parser.parse_args()

    payload = get_ai_cio_normalized_comparison(
        force_refresh=args.force_refresh,
        minimum_score=args.minimum_score,
        max_depth=args.max_depth,
    )

    if not isinstance(payload, dict):
        print(
            "ERROR: Production comparison did not return a mapping.",
            file=sys.stderr,
        )
        return 1

    discovered = find_policy_records(payload)
    unique_records = deduplicate_records(discovered)

    rows = [
        build_row(path, record)
        for path, record in unique_records
    ]

    if not rows:
        print("=" * 90)
        print("AI CIO PHASE 12.4C — NO SHADOW RECORDS FOUND")
        print("=" * 90)
        print(
            "The production normalized comparison returned no decisions "
            "containing source_metadata.policy_shadow."
        )
        print()
        print(
            "This may mean the live intelligence context contains no "
            "decisions, or the comparison payload strips source metadata."
        )
        print()
        print("Top-level payload keys:")
        print(sorted(payload.keys()))
        return 2

    report = render_report(
        rows,
        payload,
    )

    if args.output:
        output_path = Path(args.output)

        if not output_path.is_absolute():
            output_path = (
                PROJECT_ROOT / output_path
            )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_path.write_text(
            json.dumps(
                report,
                indent=2,
                default=str,
            )
            + "\n"
        )

        print()
        print(f"JSON report saved: {output_path}")

    print()
    print(
        "PHASE 12.4C LIVE SHADOW OBSERVABILITY COMPLETED"
    )
    print(
        "Production decisions remain authoritative and unchanged."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PY

chmod +x "$REPORT_SCRIPT"

echo
echo "Running syntax validation..."

python3 -m py_compile \
    scripts/report_ai_cio_policy_shadow.py

echo "Syntax validation passed."

STAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT="logs/ai_cio_policy/shadow_report_${STAMP}.json"

echo
echo "Running live normalized comparison..."

PYTHONPATH="$PROJECT_ROOT" \
python3 scripts/report_ai_cio_policy_shadow.py \
    --force-refresh \
    --output "$OUTPUT"

echo
echo "======================================================"
echo " PHASE 12.4C OBSERVABILITY INSTALLATION COMPLETE"
echo "======================================================"
echo
echo "Report location:"
echo "$PROJECT_ROOT/$OUTPUT"
echo
echo "No production decision enforcement was enabled."
echo "No service restart was performed."
