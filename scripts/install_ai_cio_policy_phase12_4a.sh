#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="/root/nse_signal_bot_v10_3"
TARGET="$PROJECT_ROOT/services/ai_cio_policy.py"
TEST_FILE="$PROJECT_ROOT/tests/test_ai_cio_policy.py"
STAMP="$(date +%Y%m%d_%H%M%S)"

cd "$PROJECT_ROOT"

echo "======================================================"
echo " MIP PRO — AI CIO POLICY ENGINE PHASE 12.4A"
echo "======================================================"

mkdir -p services tests backups/phase12_4a

if [[ -f "$TARGET" ]]; then
    cp "$TARGET" \
       "backups/phase12_4a/ai_cio_policy.py.${STAMP}.bak"
    echo "Existing policy engine backed up."
fi

if [[ -f "$TEST_FILE" ]]; then
    cp "$TEST_FILE" \
       "backups/phase12_4a/test_ai_cio_policy.py.${STAMP}.bak"
    echo "Existing policy tests backed up."
fi

cat > "$TARGET" <<'PY'
"""
MIP PRO — PHASE 12.4A
AI CIO DETERMINISTIC DECISION POLICY ENGINE

Purpose
-------
Convert normalized specialist-engine intelligence into one deterministic,
auditable AI CIO policy result.

This module:
- calculates a weighted composite score;
- applies data-quality, liquidity, risk and portfolio gates;
- determines BUY/HOLD/REDUCE/SELL/AVOID decisions;
- calculates confidence and conviction;
- generates human-readable reasons and warnings.

This module does not:
- fetch market data;
- write to repositories;
- expose Flask routes;
- modify source-engine payloads;
- execute trades.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import isfinite
from statistics import pstdev
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


MappingType = Mapping[str, Any]


DEFAULT_WEIGHTS: Dict[str, float] = {
    "prediction": 0.30,
    "committee": 0.20,
    "risk": 0.20,
    "portfolio": 0.10,
    "market_regime": 0.10,
    "institutional_flow": 0.10,
}

VALID_DECISIONS = {
    "STRONG_BUY",
    "BUY",
    "HOLD",
    "REDUCE",
    "SELL",
    "AVOID",
}

VALID_RISK_STATUSES = {
    "APPROVED",
    "APPROVED_WITH_CAUTION",
    "VETOED",
    "INSUFFICIENT_DATA",
}

POSITIVE_REGIMES = {
    "STRONG_BULLISH",
    "BULLISH",
    "LOW_VOLATILITY",
}

NEGATIVE_REGIMES = {
    "STRONG_BEARISH",
    "BEARISH",
    "HIGH_VOLATILITY",
}

NEUTRAL_REGIMES = {
    "NEUTRAL",
    "CAUTIOUS",
    "NORMAL_VOLATILITY",
    "UNKNOWN",
}


@dataclass(frozen=True)
class AICIOPolicyConfig:
    minimum_valid_engines: int = 3
    minimum_liquidity_score: float = 35.0
    maximum_portfolio_exposure_pct: float = 20.0
    maximum_data_age_seconds: int = 300

    strong_buy_threshold: float = 85.0
    buy_threshold: float = 75.0
    hold_threshold: float = 60.0
    reduce_threshold: float = 45.0
    sell_threshold: float = 30.0

    very_high_conviction_threshold: float = 90.0
    high_conviction_threshold: float = 80.0
    medium_conviction_threshold: float = 65.0
    low_conviction_threshold: float = 50.0

    weights: Dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_WEIGHTS)
    )


@dataclass(frozen=True)
class PolicyInput:
    symbol: str

    prediction_score: Optional[float] = None
    committee_score: Optional[float] = None
    risk_score: Optional[float] = None
    portfolio_score: Optional[float] = None
    market_regime_score: Optional[float] = None
    institutional_score: Optional[float] = None

    risk_status: str = "INSUFFICIENT_DATA"
    market_regime: str = "UNKNOWN"

    liquidity_score: Optional[float] = None
    current_exposure_pct: Optional[float] = None
    recommended_allocation_pct: Optional[float] = None

    data_age_seconds: Optional[int] = None
    data_quality: str = "UNKNOWN"

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PolicyResult:
    symbol: str
    decision: str
    confidence: float
    conviction: str
    composite_score: float

    risk_status: str
    market_regime: str

    recommended_allocation_pct: float
    valid_engine_count: int

    score_breakdown: Dict[str, float]
    weighted_breakdown: Dict[str, float]

    gates: Dict[str, bool]
    reasons: List[str]
    warnings: List[str]

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AICIOPolicyError(ValueError):
    """Raised when an AI CIO policy input or configuration is invalid."""


def _safe_float(
    value: Any,
    default: Optional[float] = None,
) -> Optional[float]:
    if value in (None, ""):
        return default

    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    if not isfinite(number):
        return default

    return number


def _clamp(
    value: Any,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    number = _safe_float(value, minimum)

    if number is None:
        number = minimum

    return max(minimum, min(maximum, number))


def _normalize_symbol(value: Any) -> str:
    symbol = str(value or "").strip().upper()

    if not symbol:
        raise AICIOPolicyError("symbol is required")

    return symbol


def _normalize_token(
    value: Any,
    default: str,
) -> str:
    token = str(value or default).strip().upper()
    return token.replace(" ", "_").replace("-", "_")


def _normalize_weights(
    weights: MappingType,
) -> Dict[str, float]:
    expected = set(DEFAULT_WEIGHTS)
    supplied = set(weights)

    missing = expected - supplied
    extra = supplied - expected

    if missing:
        raise AICIOPolicyError(
            f"Missing policy weights: {sorted(missing)}"
        )

    if extra:
        raise AICIOPolicyError(
            f"Unsupported policy weights: {sorted(extra)}"
        )

    normalized: Dict[str, float] = {}

    for name in DEFAULT_WEIGHTS:
        weight = _safe_float(weights.get(name))

        if weight is None or weight < 0:
            raise AICIOPolicyError(
                f"Weight {name!r} must be non-negative"
            )

        normalized[name] = weight

    total = sum(normalized.values())

    if total <= 0:
        raise AICIOPolicyError(
            "Policy weights must have a positive total"
        )

    return {
        name: weight / total
        for name, weight in normalized.items()
    }


def _score_map(
    policy_input: PolicyInput,
) -> Dict[str, Optional[float]]:
    return {
        "prediction": _safe_float(
            policy_input.prediction_score
        ),
        "committee": _safe_float(
            policy_input.committee_score
        ),
        "risk": _safe_float(
            policy_input.risk_score
        ),
        "portfolio": _safe_float(
            policy_input.portfolio_score
        ),
        "market_regime": _safe_float(
            policy_input.market_regime_score
        ),
        "institutional_flow": _safe_float(
            policy_input.institutional_score
        ),
    }


def _weighted_score(
    scores: Mapping[str, Optional[float]],
    weights: Mapping[str, float],
) -> tuple[float, Dict[str, float], Dict[str, float]]:
    available = {
        name: _clamp(score)
        for name, score in scores.items()
        if score is not None
    }

    if not available:
        return 0.0, {}, {}

    available_weight = sum(
        weights[name]
        for name in available
    )

    if available_weight <= 0:
        return 0.0, available, {}

    effective_weights = {
        name: weights[name] / available_weight
        for name in available
    }

    weighted = {
        name: round(
            available[name] * effective_weights[name],
            4,
        )
        for name in available
    }

    composite = round(sum(weighted.values()), 2)

    return composite, available, weighted


def _agreement_confidence(
    scores: Sequence[float],
    composite_score: float,
    valid_engine_count: int,
    required_engine_count: int,
) -> float:
    if not scores:
        return 0.0

    if len(scores) == 1:
        agreement = 50.0
    else:
        dispersion = pstdev(scores)
        agreement = _clamp(
            100.0 - (dispersion * 2.0)
        )

    coverage = _clamp(
        (
            valid_engine_count
            / max(required_engine_count, 1)
        ) * 100.0
    )

    confidence = (
        composite_score * 0.45
        + agreement * 0.35
        + coverage * 0.20
    )

    return round(_clamp(confidence), 2)


def _conviction(
    confidence: float,
    config: AICIOPolicyConfig,
) -> str:
    if confidence >= config.very_high_conviction_threshold:
        return "VERY_HIGH"

    if confidence >= config.high_conviction_threshold:
        return "HIGH"

    if confidence >= config.medium_conviction_threshold:
        return "MEDIUM"

    if confidence >= config.low_conviction_threshold:
        return "LOW"

    return "VERY_LOW"


def _base_decision(
    composite_score: float,
    config: AICIOPolicyConfig,
) -> str:
    if composite_score >= config.strong_buy_threshold:
        return "STRONG_BUY"

    if composite_score >= config.buy_threshold:
        return "BUY"

    if composite_score >= config.hold_threshold:
        return "HOLD"

    if composite_score >= config.reduce_threshold:
        return "REDUCE"

    if composite_score >= config.sell_threshold:
        return "SELL"

    return "AVOID"


def _append_unique(
    target: List[str],
    values: Iterable[str],
) -> None:
    for value in values:
        text = str(value or "").strip()

        if text and text not in target:
            target.append(text)


def evaluate_ai_cio_policy(
    policy_input: PolicyInput,
    config: Optional[AICIOPolicyConfig] = None,
) -> PolicyResult:
    """
    Evaluate one normalized symbol through the deterministic AI CIO policy.

    The function is pure and has no external side effects.
    """

    config = config or AICIOPolicyConfig()
    symbol = _normalize_symbol(policy_input.symbol)
    weights = _normalize_weights(config.weights)

    risk_status = _normalize_token(
        policy_input.risk_status,
        "INSUFFICIENT_DATA",
    )

    if risk_status not in VALID_RISK_STATUSES:
        risk_status = "INSUFFICIENT_DATA"

    market_regime = _normalize_token(
        policy_input.market_regime,
        "UNKNOWN",
    )

    scores = _score_map(policy_input)

    (
        composite_score,
        available_scores,
        weighted_breakdown,
    ) = _weighted_score(scores, weights)

    valid_engine_count = len(available_scores)

    liquidity_score = _safe_float(
        policy_input.liquidity_score
    )

    exposure_pct = _safe_float(
        policy_input.current_exposure_pct
    )

    allocation_pct = _safe_float(
        policy_input.recommended_allocation_pct,
        0.0,
    )

    data_age_seconds = _safe_float(
        policy_input.data_age_seconds
    )

    data_quality = _normalize_token(
        policy_input.data_quality,
        "UNKNOWN",
    )

    gates = {
        "minimum_engine_coverage": (
            valid_engine_count
            >= config.minimum_valid_engines
        ),
        "risk_approved": (
            risk_status
            not in {"VETOED", "INSUFFICIENT_DATA"}
        ),
        "liquidity_approved": (
            liquidity_score is not None
            and liquidity_score
            >= config.minimum_liquidity_score
        ),
        "portfolio_exposure_approved": (
            exposure_pct is None
            or exposure_pct
            <= config.maximum_portfolio_exposure_pct
        ),
        "data_fresh": (
            data_age_seconds is None
            or data_age_seconds
            <= config.maximum_data_age_seconds
        ),
        "data_quality_approved": (
            data_quality
            not in {
                "INVALID",
                "STALE",
                "UNAVAILABLE",
            }
        ),
    }

    reasons: List[str] = []
    warnings: List[str] = []

    if available_scores.get("prediction", 0.0) >= 75.0:
        reasons.append(
            "Prediction Center score supports the opportunity."
        )

    if available_scores.get("committee", 0.0) >= 70.0:
        reasons.append(
            "Investment Committee consensus is positive."
        )

    if available_scores.get("risk", 0.0) >= 65.0:
        reasons.append(
            "Risk assessment score is within an acceptable range."
        )

    if available_scores.get("portfolio", 0.0) >= 65.0:
        reasons.append(
            "Portfolio allocation conditions support the position."
        )

    if available_scores.get(
        "institutional_flow",
        0.0,
    ) >= 65.0:
        reasons.append(
            "Institutional and volume intelligence is supportive."
        )

    if market_regime in POSITIVE_REGIMES:
        reasons.append(
            f"Market regime is supportive: {market_regime}."
        )
    elif market_regime in NEGATIVE_REGIMES:
        warnings.append(
            f"Market regime is adverse: {market_regime}."
        )
    elif market_regime not in NEUTRAL_REGIMES:
        warnings.append(
            f"Unrecognized market regime: {market_regime}."
        )

    if risk_status == "APPROVED_WITH_CAUTION":
        warnings.append(
            "Risk engine approved the position with caution."
        )

    if not gates["minimum_engine_coverage"]:
        warnings.append(
            "Insufficient validated specialist-engine coverage."
        )

    if not gates["liquidity_approved"]:
        warnings.append(
            "Liquidity score is missing or below the minimum threshold."
        )

    if not gates["portfolio_exposure_approved"]:
        warnings.append(
            "Current portfolio exposure exceeds the configured limit."
        )

    if not gates["data_fresh"]:
        warnings.append(
            "Market intelligence is older than the permitted limit."
        )

    if not gates["data_quality_approved"]:
        warnings.append(
            f"Data quality is not approved: {data_quality}."
        )

    decision = _base_decision(
        composite_score,
        config,
    )

    hard_avoid = any(
        not gates[name]
        for name in (
            "minimum_engine_coverage",
            "risk_approved",
            "liquidity_approved",
            "data_fresh",
            "data_quality_approved",
        )
    )

    if risk_status == "VETOED":
        decision = "AVOID"
        warnings.append(
            "Risk engine vetoed the investment decision."
        )
        reasons.append(
            "Capital preservation override applied."
        )

    elif hard_avoid:
        decision = "AVOID"
        reasons.append(
            "AI CIO safety gate prevented an actionable recommendation."
        )

    elif not gates["portfolio_exposure_approved"]:
        if decision in {"STRONG_BUY", "BUY", "HOLD"}:
            decision = "REDUCE"

        reasons.append(
            "Portfolio concentration control reduced the recommendation."
        )

    elif (
        market_regime in NEGATIVE_REGIMES
        and decision == "STRONG_BUY"
    ):
        decision = "BUY"
        warnings.append(
            "Strong-buy conviction was reduced by the adverse regime."
        )

    elif (
        market_regime in NEGATIVE_REGIMES
        and decision == "BUY"
    ):
        decision = "HOLD"
        warnings.append(
            "Buy conviction was reduced by the adverse regime."
        )

    confidence = _agreement_confidence(
        list(available_scores.values()),
        composite_score,
        valid_engine_count,
        len(DEFAULT_WEIGHTS),
    )

    if risk_status == "APPROVED_WITH_CAUTION":
        confidence = max(0.0, confidence - 7.5)

    if market_regime in NEGATIVE_REGIMES:
        confidence = max(0.0, confidence - 5.0)

    if decision == "AVOID" and hard_avoid:
        confidence = min(confidence, 49.99)

    confidence = round(confidence, 2)
    conviction = _conviction(
        confidence,
        config,
    )

    if decision not in VALID_DECISIONS:
        raise AICIOPolicyError(
            f"Policy generated unsupported decision: {decision}"
        )

    if decision in {
        "AVOID",
        "SELL",
        "REDUCE",
    }:
        recommended_allocation = 0.0
    else:
        recommended_allocation = _clamp(
            allocation_pct,
            0.0,
            config.maximum_portfolio_exposure_pct,
        )

    if not reasons:
        reasons.append(
            "Decision was derived from the weighted specialist-engine scores."
        )

    return PolicyResult(
        symbol=symbol,
        decision=decision,
        confidence=confidence,
        conviction=conviction,
        composite_score=composite_score,
        risk_status=risk_status,
        market_regime=market_regime,
        recommended_allocation_pct=round(
            recommended_allocation,
            2,
        ),
        valid_engine_count=valid_engine_count,
        score_breakdown={
            key: round(value, 2)
            for key, value in available_scores.items()
        },
        weighted_breakdown={
            key: round(value, 4)
            for key, value in weighted_breakdown.items()
        },
        gates=dict(gates),
        reasons=reasons,
        warnings=warnings,
        metadata={
            **dict(policy_input.metadata),
            "policy_version": "12.4A",
            "data_quality": data_quality,
            "liquidity_score": liquidity_score,
            "current_exposure_pct": exposure_pct,
            "data_age_seconds": data_age_seconds,
        },
    )


def evaluate_ai_cio_policy_payload(
    payload: MappingType,
    config: Optional[AICIOPolicyConfig] = None,
) -> Dict[str, Any]:
    """
    Convenience adapter for dictionary-based normalized payloads.
    """

    if not isinstance(payload, Mapping):
        raise AICIOPolicyError(
            "AI CIO policy payload must be a mapping"
        )

    policy_input = PolicyInput(
        symbol=payload.get("symbol"),
        prediction_score=payload.get(
            "prediction_score"
        ),
        committee_score=payload.get(
            "committee_score"
        ),
        risk_score=payload.get(
            "risk_score"
        ),
        portfolio_score=payload.get(
            "portfolio_score"
        ),
        market_regime_score=payload.get(
            "market_regime_score"
        ),
        institutional_score=payload.get(
            "institutional_score"
        ),
        risk_status=payload.get(
            "risk_status",
            "INSUFFICIENT_DATA",
        ),
        market_regime=payload.get(
            "market_regime",
            "UNKNOWN",
        ),
        liquidity_score=payload.get(
            "liquidity_score"
        ),
        current_exposure_pct=payload.get(
            "current_exposure_pct"
        ),
        recommended_allocation_pct=payload.get(
            "recommended_allocation_pct"
        ),
        data_age_seconds=payload.get(
            "data_age_seconds"
        ),
        data_quality=payload.get(
            "data_quality",
            "UNKNOWN",
        ),
        metadata=dict(
            payload.get("metadata") or {}
        ),
    )

    return evaluate_ai_cio_policy(
        policy_input,
        config,
    ).to_dict()
PY

cat > "$TEST_FILE" <<'PY'
from services.ai_cio_policy import (
    PolicyInput,
    evaluate_ai_cio_policy,
)


def test_strong_buy():
    result = evaluate_ai_cio_policy(
        PolicyInput(
            symbol="KCB",
            prediction_score=92,
            committee_score=90,
            risk_score=88,
            portfolio_score=85,
            market_regime_score=90,
            institutional_score=89,
            risk_status="APPROVED",
            market_regime="BULLISH",
            liquidity_score=85,
            current_exposure_pct=4,
            recommended_allocation_pct=8,
            data_age_seconds=20,
            data_quality="LIVE",
        )
    )

    assert result.decision == "STRONG_BUY"
    assert result.composite_score >= 85
    assert result.recommended_allocation_pct == 8


def test_risk_veto():
    result = evaluate_ai_cio_policy(
        PolicyInput(
            symbol="SCOM",
            prediction_score=95,
            committee_score=94,
            risk_score=90,
            portfolio_score=90,
            market_regime_score=90,
            institutional_score=90,
            risk_status="VETOED",
            market_regime="BULLISH",
            liquidity_score=90,
            data_age_seconds=10,
            data_quality="LIVE",
        )
    )

    assert result.decision == "AVOID"
    assert result.recommended_allocation_pct == 0


def test_insufficient_engines():
    result = evaluate_ai_cio_policy(
        PolicyInput(
            symbol="EQTY",
            prediction_score=90,
            committee_score=85,
            risk_status="APPROVED",
            market_regime="BULLISH",
            liquidity_score=80,
            data_age_seconds=15,
            data_quality="LIVE",
        )
    )

    assert result.decision == "AVOID"
    assert result.valid_engine_count == 2


def test_low_liquidity():
    result = evaluate_ai_cio_policy(
        PolicyInput(
            symbol="TEST",
            prediction_score=90,
            committee_score=85,
            risk_score=80,
            portfolio_score=80,
            market_regime_score=80,
            institutional_score=20,
            risk_status="APPROVED",
            market_regime="BULLISH",
            liquidity_score=15,
            data_age_seconds=20,
            data_quality="LIVE",
        )
    )

    assert result.decision == "AVOID"


def test_exposure_override():
    result = evaluate_ai_cio_policy(
        PolicyInput(
            symbol="COOP",
            prediction_score=90,
            committee_score=88,
            risk_score=85,
            portfolio_score=80,
            market_regime_score=85,
            institutional_score=82,
            risk_status="APPROVED",
            market_regime="BULLISH",
            liquidity_score=80,
            current_exposure_pct=25,
            recommended_allocation_pct=8,
            data_age_seconds=20,
            data_quality="LIVE",
        )
    )

    assert result.decision == "REDUCE"
    assert result.recommended_allocation_pct == 0
PY

echo
echo "Running syntax checks..."

python3 -m py_compile \
    services/ai_cio_policy.py \
    tests/test_ai_cio_policy.py

echo "Syntax checks passed."

echo
echo "Running built-in policy validation..."

python3 - <<'PY'
from services.ai_cio_policy import (
    PolicyInput,
    evaluate_ai_cio_policy,
)

cases = {
    "strong_buy": PolicyInput(
        symbol="KCB",
        prediction_score=92,
        committee_score=90,
        risk_score=88,
        portfolio_score=85,
        market_regime_score=90,
        institutional_score=89,
        risk_status="APPROVED",
        market_regime="BULLISH",
        liquidity_score=85,
        current_exposure_pct=4,
        recommended_allocation_pct=8,
        data_age_seconds=20,
        data_quality="LIVE",
    ),
    "risk_veto": PolicyInput(
        symbol="SCOM",
        prediction_score=95,
        committee_score=94,
        risk_score=90,
        portfolio_score=90,
        market_regime_score=90,
        institutional_score=90,
        risk_status="VETOED",
        market_regime="BULLISH",
        liquidity_score=90,
        data_age_seconds=10,
        data_quality="LIVE",
    ),
    "insufficient_data": PolicyInput(
        symbol="EQTY",
        prediction_score=90,
        committee_score=85,
        risk_status="APPROVED",
        market_regime="BULLISH",
        liquidity_score=80,
        data_age_seconds=15,
        data_quality="LIVE",
    ),
}

results = {
    name: evaluate_ai_cio_policy(case)
    for name, case in cases.items()
}

assert results["strong_buy"].decision == "STRONG_BUY"
assert results["risk_veto"].decision == "AVOID"
assert results["insufficient_data"].decision == "AVOID"

for name, result in results.items():
    print(
        f"{name}: "
        f"{result.symbol} | "
        f"{result.decision} | "
        f"score={result.composite_score} | "
        f"confidence={result.confidence} | "
        f"engines={result.valid_engine_count}"
    )

print("AI CIO POLICY VALIDATION PASSED")
PY

echo
echo "Installation complete:"
echo "  $TARGET"
echo "  $TEST_FILE"
echo
echo "No production routes or services were modified."
