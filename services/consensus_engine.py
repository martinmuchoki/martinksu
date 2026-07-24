"""
Phase 8.4 — Cross-Committee Consensus Intelligence.

This module analyses agreement, disagreement, confidence,
conviction, stability and committee conflicts without changing
the existing committee voting implementation.
"""

from __future__ import annotations

import math
import statistics
from typing import Any, Dict, Iterable, List, Mapping, Optional


FORMULA_VERSION = "8.4"

POSITIVE_SIGNALS = {
    "BUY",
    "STRONG BUY",
    "ACCUMULATE",
    "BULLISH",
    "POSITIVE",
}

NEGATIVE_SIGNALS = {
    "SELL",
    "STRONG SELL",
    "REDUCE",
    "BEARISH",
    "NEGATIVE",
}

NEUTRAL_SIGNALS = {
    "HOLD",
    "NEUTRAL",
    "WAIT",
    "AVOID",
}


def _safe_float(
    value: Any,
    default: float = 50.0,
) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    if not math.isfinite(number):
        return default

    return number


def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(minimum, min(maximum, value))


def _normalise_signal(
    signal: Any,
    score: float,
) -> str:
    text = str(signal or "").strip().upper()

    if text in POSITIVE_SIGNALS:
        return "BUY"

    if text in NEGATIVE_SIGNALS:
        return "SELL"

    if text in NEUTRAL_SIGNALS:
        return "HOLD"

    if score >= 60:
        return "BUY"

    if score <= 40:
        return "SELL"

    return "HOLD"


def _extract_votes(
    votes: Mapping[str, Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    extracted: List[Dict[str, Any]] = []

    for committee_name, payload in votes.items():
        if not isinstance(payload, Mapping):
            continue

        score = _clamp(
            _safe_float(payload.get("score"), 50.0)
        )

        signal = _normalise_signal(
            payload.get(
                "signal",
                payload.get(
                    "recommendation",
                    payload.get("decision"),
                ),
            ),
            score,
        )

        weight = max(
            0.0,
            _safe_float(payload.get("weight"), 1.0),
        )

        extracted.append(
            {
                "committee": str(committee_name),
                "score": round(score, 2),
                "signal": signal,
                "weight": weight,
            }
        )

    if not extracted:
        raise ValueError(
            "At least one valid committee vote is required."
        )

    return extracted


def _weighted_score(
    votes: Iterable[Mapping[str, Any]],
) -> float:
    vote_list = list(votes)

    total_weight = sum(
        _safe_float(vote.get("weight"), 1.0)
        for vote in vote_list
    )

    if total_weight <= 0:
        return round(
            statistics.fmean(
                _safe_float(vote.get("score"), 50.0)
                for vote in vote_list
            ),
            2,
        )

    score = sum(
        _safe_float(vote.get("score"), 50.0)
        * _safe_float(vote.get("weight"), 1.0)
        for vote in vote_list
    ) / total_weight

    return round(_clamp(score), 2)


def _majority_signal(
    votes: Iterable[Mapping[str, Any]],
) -> str:
    totals = {
        "BUY": 0.0,
        "HOLD": 0.0,
        "SELL": 0.0,
    }

    for vote in votes:
        signal = str(vote.get("signal", "HOLD"))
        weight = _safe_float(vote.get("weight"), 1.0)

        if signal not in totals:
            signal = "HOLD"

        totals[signal] += weight

    ordered = sorted(
        totals.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    if (
        len(ordered) > 1
        and ordered[0][1] == ordered[1][1]
    ):
        return "HOLD"

    return ordered[0][0]


def _consensus_score(
    votes: Iterable[Mapping[str, Any]],
) -> float:
    scores = [
        _safe_float(vote.get("score"), 50.0)
        for vote in votes
    ]

    if len(scores) == 1:
        return 100.0

    spread = statistics.pstdev(scores)

    score_agreement = _clamp(
        100.0 - (spread * 2.0)
    )

    return round(score_agreement, 2)


def _alignment(
    consensus_score: float,
) -> str:
    if consensus_score >= 90:
        return "VERY_STRONG"

    if consensus_score >= 75:
        return "STRONG"

    if consensus_score >= 60:
        return "MODERATE"

    if consensus_score >= 40:
        return "WEAK"

    return "CONFLICTED"


def _conviction(
    confidence: float,
) -> str:
    if confidence >= 90:
        return "VERY_HIGH"

    if confidence >= 78:
        return "HIGH"

    if confidence >= 62:
        return "MEDIUM"

    if confidence >= 45:
        return "LOW"

    return "VERY_LOW"


def _decision_stability(
    weighted_score: float,
    consensus_score: float,
) -> str:
    distance_from_boundary = min(
        abs(weighted_score - 40.0),
        abs(weighted_score - 60.0),
    )

    if (
        consensus_score >= 80
        and distance_from_boundary >= 15
    ):
        return "HIGH"

    if (
        consensus_score >= 60
        and distance_from_boundary >= 7
    ):
        return "MEDIUM"

    return "LOW"


def _risk_veto(
    votes: Iterable[Mapping[str, Any]],
) -> bool:
    for vote in votes:
        name = str(
            vote.get("committee", "")
        ).upper()

        signal = str(
            vote.get("signal", "HOLD")
        ).upper()

        score = _safe_float(
            vote.get("score"),
            50.0,
        )

        if (
            "RISK" in name
            and (
                signal == "SELL"
                or score <= 30
            )
        ):
            return True

    return False


def _build_explanation(
    majority_signal: str,
    agreeing: int,
    total: int,
    alignment: str,
    conflicts: List[str],
    risk_veto: bool,
) -> str:
    if risk_veto:
        return (
            "Risk control issued a veto. "
            "The final recommendation requires additional "
            "risk review despite broader committee support."
        )

    if conflicts:
        conflict_text = ", ".join(conflicts)

        return (
            f"{agreeing} of {total} committees support "
            f"{majority_signal}. Consensus alignment is "
            f"{alignment.lower().replace('_', ' ')}. "
            f"Conflicting committee votes: {conflict_text}."
        )

    return (
        f"All evaluated committees are aligned with "
        f"{majority_signal}. Consensus alignment is "
        f"{alignment.lower().replace('_', ' ')}."
    )


def analyse_consensus(
    votes: Mapping[str, Mapping[str, Any]],
    weighted_score: Optional[float] = None,
    decision: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyse cross-committee agreement.

    Parameters
    ----------
    votes:
        Mapping of committee names to vote dictionaries.

        Each vote may contain:
        - score
        - signal, recommendation or decision
        - weight

    weighted_score:
        Existing committee weighted score. When omitted, it is
        calculated from the supplied vote weights.

    decision:
        Existing final decision. When omitted, the majority
        committee signal is used.
    """

    extracted = _extract_votes(votes)

    base_score = (
        _clamp(_safe_float(weighted_score))
        if weighted_score is not None
        else _weighted_score(extracted)
    )

    majority = _normalise_signal(
        decision,
        base_score,
    ) if decision else _majority_signal(extracted)

    consensus = _consensus_score(extracted)
    alignment = _alignment(consensus)

    conflicts = [
        vote["committee"]
        for vote in extracted
        if vote["signal"] != majority
    ]

    agreeing = len(extracted) - len(conflicts)
    disagreeing = len(conflicts)

    calibrated_confidence = _clamp(
        (base_score * 0.65)
        + (consensus * 0.35)
    )

    veto = _risk_veto(extracted)

    if veto:
        calibrated_confidence = min(
            calibrated_confidence,
            60.0,
        )

    calibrated_confidence = round(
        calibrated_confidence,
        2,
    )

    stability = _decision_stability(
        base_score,
        consensus,
    )

    explanation = _build_explanation(
        majority_signal=majority,
        agreeing=agreeing,
        total=len(extracted),
        alignment=alignment,
        conflicts=conflicts,
        risk_veto=veto,
    )

    return {
        "formula_version": FORMULA_VERSION,
        "score": consensus,
        "consensus_score": consensus,
        "alignment": alignment,
        "confidence": calibrated_confidence,
        "calibrated_confidence": calibrated_confidence,
        "conviction": _conviction(
            calibrated_confidence
        ),
        "stability": stability,
        "decision": majority,
        "weighted_score": round(base_score, 2),
        "conflicting_committees": conflicts,
        "committee_agreement": agreeing,
        "committee_disagreement": disagreeing,
        "committee_count": len(extracted),
        "risk_veto": veto,
        "explanation": explanation,
        "votes": extracted,
    }


def analyze_consensus(
    votes: Mapping[str, Mapping[str, Any]],
    weighted_score: Optional[float] = None,
    decision: Optional[str] = None,
) -> Dict[str, Any]:
    """
    American-English alias for analyse_consensus.
    """

    return analyse_consensus(
        votes=votes,
        weighted_score=weighted_score,
        decision=decision,
    )
