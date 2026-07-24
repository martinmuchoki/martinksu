#!/usr/bin/env python3

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from services.intelligence_orchestrator import get_ai_cio_context


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = PROJECT_ROOT / "reports"


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

    current_counts: Counter[str] = Counter()
    shadow_counts: Counter[str] = Counter()
    risk_status_counts: Counter[str] = Counter()
    agreement_counts: Counter[str] = Counter()
    transition_counts: Counter[str] = Counter()
    failed_gate_counts: Counter[str] = Counter()

    records: list[dict[str, Any]] = []
    disagreement_records: list[dict[str, Any]] = []

    for wrapper in ranked:
        wrapper = as_mapping(wrapper)
        decision = as_mapping(wrapper.get("decision"))

        symbol = str(
            decision.get("symbol")
            or wrapper.get("symbol")
            or "UNKNOWN"
        )

        current_decision = str(
            decision.get("decision") or "UNKNOWN"
        ).upper()

        metadata = as_mapping(decision.get("source_metadata"))
        shadow = as_mapping(metadata.get("policy_shadow"))
        gates = as_mapping(shadow.get("gates"))

        shadow_decision = str(
            shadow.get("decision") or "UNKNOWN"
        ).upper()

        risk_status = str(
            decision.get("risk_status")
            or shadow.get("risk_status")
            or "UNKNOWN"
        ).upper()

        current_confidence = safe_float(
            decision.get("confidence")
            or decision.get("confidence_score")
        )

        shadow_confidence = safe_float(
            shadow.get("confidence")
            or shadow.get("confidence_score")
        )

        supporting = as_mapping(
            decision.get("supporting_engines")
        )
        risk_engine = as_mapping(
            supporting.get("risk_engine")
        )

        risk_level = risk_engine.get("risk_level")
        risk_veto = bool(
            decision.get("risk_veto")
            or shadow.get("risk_veto")
            or risk_engine.get("risk_veto")
            or risk_engine.get("veto")
        )

        failed_gates = [
            str(name)
            for name, passed in gates.items()
            if passed is False
        ]

        agrees = current_decision == shadow_decision
        transition = (
            f"{current_decision}->{shadow_decision}"
        )

        current_counts[current_decision] += 1
        shadow_counts[shadow_decision] += 1
        risk_status_counts[risk_status] += 1
        agreement_counts[
            "AGREE" if agrees else "DISAGREE"
        ] += 1
        transition_counts[transition] += 1

        for gate in failed_gates:
            failed_gate_counts[gate] += 1

        record = {
            "rank": wrapper.get("rank"),
            "symbol": symbol,
            "current_decision": current_decision,
            "shadow_decision": shadow_decision,
            "agrees": agrees,
            "current_confidence": round(
                current_confidence, 2
            ),
            "shadow_confidence": round(
                shadow_confidence, 2
            ),
            "confidence_delta": round(
                shadow_confidence
                - current_confidence,
                2,
            ),
            "risk_status": risk_status,
            "risk_level": risk_level,
            "risk_veto": risk_veto,
            "failed_gates": failed_gates,
            "executive_score": wrapper.get(
                "executive_score"
            ),
            "policy_reason": (
                shadow.get("reason")
                or shadow.get("primary_reason")
                or shadow.get("explanation")
            ),
        }

        records.append(record)

        if not agrees:
            disagreement_records.append(record)

    total = len(records)
    agreements = agreement_counts["AGREE"]
    disagreements = agreement_counts["DISAGREE"]

    agreement_rate = (
        round((agreements / total) * 100, 2)
        if total
        else 0.0
    )

    disagreement_rate = (
        round((disagreements / total) * 100, 2)
        if total
        else 0.0
    )

    generated_at = datetime.now(
        timezone.utc
    ).isoformat()

    report = {
        "generated_at_utc": generated_at,
        "total_decisions": total,
        "agreements": agreements,
        "disagreements": disagreements,
        "agreement_rate_pct": agreement_rate,
        "disagreement_rate_pct": disagreement_rate,
        "current_decision_counts": dict(
            current_counts
        ),
        "shadow_decision_counts": dict(
            shadow_counts
        ),
        "risk_status_counts": dict(
            risk_status_counts
        ),
        "failed_gate_counts": dict(
            failed_gate_counts
        ),
        "decision_transitions": dict(
            transition_counts
        ),
        "disagreement_records": disagreement_records,
        "all_records": records,
    }

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d_%H%M%S")

    latest_path = (
        REPORT_DIR
        / "ai_cio_policy_shadow_latest.json"
    )

    timestamped_path = (
        REPORT_DIR
        / f"ai_cio_policy_shadow_{timestamp}.json"
    )

    report_json = json.dumps(
        report,
        indent=2,
        default=str,
    )

    latest_path.write_text(report_json)
    timestamped_path.write_text(report_json)

    print("=" * 72)
    print("AI CIO DETERMINISTIC POLICY VALIDATION")
    print("=" * 72)
    print(f"Generated UTC      : {generated_at}")
    print(f"Total decisions    : {total}")
    print(f"Agreements         : {agreements}")
    print(f"Disagreements      : {disagreements}")
    print(f"Agreement rate     : {agreement_rate:.2f}%")
    print(
        f"Disagreement rate  : "
        f"{disagreement_rate:.2f}%"
    )

    print("\nCURRENT DECISIONS")
    for name, count in current_counts.most_common():
        print(f"  {name:18} {count}")

    print("\nSHADOW DECISIONS")
    for name, count in shadow_counts.most_common():
        print(f"  {name:18} {count}")

    print("\nRISK STATUS")
    for name, count in risk_status_counts.most_common():
        print(f"  {name:28} {count}")

    print("\nFAILED POLICY GATES")
    if failed_gate_counts:
        for name, count in failed_gate_counts.most_common():
            print(f"  {name:32} {count}")
    else:
        print("  None")

    print("\nDECISION TRANSITIONS")
    for name, count in transition_counts.most_common():
        print(f"  {name:26} {count}")

    print("\nDISAGREEMENTS")
    if not disagreement_records:
        print("  None")
    else:
        for item in disagreement_records:
            print(
                f"  {item['symbol']:7} "
                f"{item['current_decision']:8} -> "
                f"{item['shadow_decision']:8} "
                f"risk={item['risk_status']:24} "
                f"failed_gates={item['failed_gates']}"
            )

    print("\nREPORT FILES")
    print(f"  {latest_path}")
    print(f"  {timestamped_path}")


if __name__ == "__main__":
    main()
