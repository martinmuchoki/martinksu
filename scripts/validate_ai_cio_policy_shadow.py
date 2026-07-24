#!/usr/bin/env python3

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.intelligence_orchestrator import get_ai_cio_context


def as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def main() -> None:
    context = get_ai_cio_context()

    ranked = context.get("ranked_decisions") or []
    validation = context.get("validation") or {}
    source_counts = context.get("source_counts") or {}

    current_counts: Counter[str] = Counter()
    shadow_counts: Counter[str] = Counter()
    transitions: Counter[tuple[str, str]] = Counter()

    compared = 0
    missing_shadow = 0

    print("=" * 110)
    print("AI CIO DETERMINISTIC POLICY SHADOW VALIDATION")
    print("=" * 110)
    print(
        f"{'SYMBOL':<10}"
        f"{'CURRENT':<16}"
        f"{'SHADOW':<16}"
        f"{'SCORE':<12}"
        f"{'CONFIDENCE':<14}"
        f"{'ENGINES':<10}"
        f"{'RISK STATUS'}"
    )
    print("-" * 110)

    for wrapper_value in ranked:
        wrapper = as_mapping(wrapper_value)
        decision = as_mapping(wrapper.get("decision"))

        symbol = str(
            decision.get("symbol")
            or wrapper.get("symbol")
            or "UNKNOWN"
        )

        current = str(
            decision.get("decision")
            or "UNKNOWN"
        ).upper()

        metadata = as_mapping(
            decision.get("source_metadata")
        )

        shadow = as_mapping(
            metadata.get("policy_shadow")
        )

        current_counts[current] += 1

        if not shadow:
            missing_shadow += 1

            print(
                f"{symbol:<10}"
                f"{current:<16}"
                f"{'MISSING':<16}"
                f"{'-':<12}"
                f"{'-':<14}"
                f"{'-':<10}"
                f"MISSING POLICY SHADOW"
            )
            continue

        shadow_decision = str(
            shadow.get("decision")
            or "UNKNOWN"
        ).upper()

        shadow_counts[shadow_decision] += 1
        transitions[(current, shadow_decision)] += 1
        compared += 1

        executive_score = safe_float(
            wrapper.get("executive_score")
        )

        confidence = safe_float(
            decision.get("confidence")
            or decision.get("confidence_score")
        )

        supporting_engines = as_mapping(
            decision.get("supporting_engines")
        )

        engine_count = len(supporting_engines)

        risk_status = str(
            decision.get("risk_status")
            or shadow.get("risk_status")
            or "UNKNOWN"
        ).upper()

        print(
            f"{symbol:<10}"
            f"{current:<16}"
            f"{shadow_decision:<16}"
            f"{executive_score:<12.2f}"
            f"{confidence:<14.2f}"
            f"{engine_count:<10}"
            f"{risk_status}"
        )

    matches = sum(
        count
        for (current, shadow), count in transitions.items()
        if current == shadow
    )

    differences = compared - matches

    match_rate = (
        matches / compared * 100.0
        if compared
        else 0.0
    )

    print()
    print("=" * 110)
    print("SUMMARY")
    print("=" * 110)
    print("Ranked decisions :", len(ranked))
    print("Compared         :", compared)
    print("Missing shadow   :", missing_shadow)
    print("Matches          :", matches)
    print("Differences      :", differences)
    print(f"Match rate       : {match_rate:.2f}%")

    print()
    print("Current decision distribution:")
    for decision_name, count in sorted(current_counts.items()):
        print(f"  {decision_name:<20}{count}")

    print()
    print("Policy shadow distribution:")
    for decision_name, count in sorted(shadow_counts.items()):
        print(f"  {decision_name:<20}{count}")

    print()
    print("Decision transitions:")
    for (current, shadow), count in sorted(
        transitions.items(),
        key=lambda item: (-item[1], item[0]),
    ):
        print(
            f"  {current:<16} -> "
            f"{shadow:<16} {count}"
        )

    print()
    print("Source counts:")
    print(source_counts)

    print()
    print("Executive validation:")
    print(validation)

    assert len(ranked) > 0, (
        "No ranked AI CIO decisions were returned."
    )

    assert compared > 0, (
        "No AI CIO policy-shadow comparisons were produced."
    )

    assert missing_shadow == 0, (
        f"{missing_shadow} decisions are missing policy shadow data."
    )

    assert validation.get("valid", True), (
        f"AI CIO executive validation failed: {validation}"
    )

    print()
    print("AI CIO DETERMINISTIC POLICY VALIDATION PASSED")


if __name__ == "__main__":
    main()
