#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="/root/nse_signal_bot_v10_3"
TARGET="$PROJECT_ROOT/services/ai_cio.py"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP="$PROJECT_ROOT/backups/phase12_4b/ai_cio.py.${STAMP}.bak"

cd "$PROJECT_ROOT"

echo "======================================================"
echo " MIP PRO — AI CIO POLICY PHASE 12.4B SHADOW MODE"
echo "======================================================"

mkdir -p backups/phase12_4b tests

cp "$TARGET" "$BACKUP"
echo "Backup created: $BACKUP"

python3 - <<'PY'
from pathlib import Path

path = Path("services/ai_cio.py")
text = path.read_text()

import_marker = """from services.ai_cio_contract import (
"""

if "from services.ai_cio_policy import (" not in text:
    policy_import = """from services.ai_cio_policy import (
    PolicyInput,
    evaluate_ai_cio_policy,
)

"""
    position = text.find(import_marker)

    if position == -1:
        raise SystemExit(
            "Could not locate ai_cio_contract import block."
        )

    text = text[:position] + policy_import + text[position:]

helper_marker = """def assemble_ai_cio_decision(
"""

if "_build_ai_cio_policy_input(" not in text:
    helpers = r'''
def _policy_first_score(
    sources: Sequence[MappingType],
    keys: Sequence[str],
) -> Optional[float]:
    """
    Find the first usable numeric score from normalized engine records.
    """

    for source in sources:
        if not isinstance(source, Mapping):
            continue

        value = _first_present(
            source,
            keys,
            None,
        )

        if value in (None, ""):
            continue

        return _normalize_percentage(value)

    return None


def _policy_mapping_score(
    source: MappingType,
    keys: Sequence[str],
) -> Optional[float]:
    """
    Find a score inside the existing AI CIO score breakdown.
    """

    for key in keys:
        if key not in source:
            continue

        value = source.get(key)

        if isinstance(value, Mapping):
            value = _first_present(
                value,
                (
                    "score",
                    "value",
                    "normalized_score",
                    "confidence",
                ),
                None,
            )

        if value in (None, ""):
            continue

        return _normalize_percentage(value)

    return None


def _build_ai_cio_policy_input(
    *,
    symbol: str,
    prediction: MappingType,
    committee: MappingType,
    risk: MappingType,
    portfolio: MappingType,
    screener: MappingType,
    learning: MappingType,
    regime: MappingType,
    breadth: MappingType,
    scores: MappingType,
    allocation: MappingType,
    risk_status: str,
    market_regime: str,
    metadata: MappingType,
) -> PolicyInput:
    """
    Adapt existing normalized AI CIO records into the Phase 12.4 policy input.

    This adapter is intentionally permissive because specialist engines may
    expose equivalent values under different field names.
    """

    prediction_score = (
        _policy_mapping_score(
            scores,
            (
                "prediction",
                "prediction_score",
                "forecast",
                "forecast_score",
                "model_score",
            ),
        )
        or _policy_first_score(
            (prediction,),
            (
                "prediction_score",
                "forecast_score",
                "model_score",
                "opportunity_score",
                "score",
                "confidence",
            ),
        )
    )

    committee_score = (
        _policy_mapping_score(
            scores,
            (
                "committee",
                "committee_score",
                "consensus",
                "consensus_score",
            ),
        )
        or _policy_first_score(
            (committee,),
            (
                "committee_score",
                "consensus_score",
                "committee_consensus",
                "agreement_pct",
                "score",
                "confidence",
            ),
        )
    )

    risk_score = (
        _policy_mapping_score(
            scores,
            (
                "risk",
                "risk_score",
                "safety",
                "safety_score",
            ),
        )
        or _policy_first_score(
            (risk, committee),
            (
                "risk_score",
                "safety_score",
                "risk_confidence",
                "score",
            ),
        )
    )

    portfolio_score = (
        _policy_mapping_score(
            scores,
            (
                "portfolio",
                "portfolio_score",
                "allocation",
                "allocation_score",
            ),
        )
        or _policy_first_score(
            (portfolio,),
            (
                "portfolio_score",
                "allocation_score",
                "fit_score",
                "suitability_score",
                "score",
            ),
        )
    )

    regime_score = (
        _policy_mapping_score(
            scores,
            (
                "market_regime",
                "regime",
                "regime_score",
            ),
        )
        or _policy_first_score(
            (regime,),
            (
                "market_regime_score",
                "regime_score",
                "confidence",
                "score",
            ),
        )
    )

    institutional_score = (
        _policy_mapping_score(
            scores,
            (
                "institutional",
                "institutional_flow",
                "volume",
                "volume_score",
                "liquidity",
            ),
        )
        or _policy_first_score(
            (screener, breadth, learning),
            (
                "institutional_score",
                "institutional_flow_score",
                "volume_score",
                "volume_intelligence_score",
                "accumulation_score",
                "liquidity_score",
            ),
        )
    )

    liquidity_score = _policy_first_score(
        (screener, breadth, prediction),
        (
            "liquidity_score",
            "volume_score",
            "volume_intelligence_score",
            "tradability_score",
            "marketability_score",
        ),
    )

    if liquidity_score is None:
        liquidity_score = institutional_score

    current_exposure = _policy_first_score(
        (allocation, portfolio),
        (
            "current_exposure_pct",
            "existing_exposure_pct",
            "portfolio_exposure_pct",
            "sector_exposure_pct",
            "current_weight_pct",
        ),
    )

    recommended_allocation = _policy_first_score(
        (allocation, portfolio, committee),
        (
            "recommended_allocation_pct",
            "allocation_pct",
            "target_weight_pct",
            "recommended_weight_pct",
            "position_size_pct",
        ),
    )

    data_age = _first_present(
        metadata,
        (
            "data_age_seconds",
            "market_data_age_seconds",
            "quote_age_seconds",
        ),
        None,
    )

    data_quality = _first_present(
        metadata,
        (
            "data_quality",
            "market_data_quality",
            "quality_status",
        ),
        "UNKNOWN",
    )

    return PolicyInput(
        symbol=symbol,
        prediction_score=prediction_score,
        committee_score=committee_score,
        risk_score=risk_score,
        portfolio_score=portfolio_score,
        market_regime_score=regime_score,
        institutional_score=institutional_score,
        risk_status=risk_status,
        market_regime=market_regime,
        liquidity_score=liquidity_score,
        current_exposure_pct=current_exposure,
        recommended_allocation_pct=recommended_allocation,
        data_age_seconds=data_age,
        data_quality=str(data_quality or "UNKNOWN"),
        metadata={
            "integration_phase": "12.4B-shadow",
        },
    )


'''
    position = text.find(helper_marker)

    if position == -1:
        raise SystemExit(
            "Could not locate assemble_ai_cio_decision()."
        )

    text = text[:position] + helpers + text[position:]

allocation_marker = """    allocation = _extract_allocation(
        portfolio_record,
        committee_record,
        screener_record,
    )
"""

shadow_block = r'''
    normalized_market_regime = _normalize_market_regime(
        regime_record
    )

    policy_result = None

    try:
        policy_input = _build_ai_cio_policy_input(
            symbol=normalized_symbol,
            prediction=prediction_record,
            committee=committee_record,
            risk=risk_record,
            portfolio=portfolio_record,
            screener=screener_record,
            learning=learning_record,
            regime=regime_record,
            breadth=breadth_record,
            scores=scores,
            allocation=allocation,
            risk_status=risk_status,
            market_regime=normalized_market_regime,
            metadata=source_metadata,
        )

        policy_result = evaluate_ai_cio_policy(
            policy_input
        )

        if policy_result.decision != decision_value:
            warnings.append(
                "AI CIO policy shadow decision differs from "
                f"current orchestration: "
                f"{decision_value} -> {policy_result.decision}"
            )

        for policy_warning in policy_result.warnings:
            warning_text = (
                f"AI CIO policy shadow: {policy_warning}"
            )

            if warning_text not in warnings:
                warnings.append(warning_text)

    except Exception as exc:
        warnings.append(
            f"AI CIO policy shadow evaluation failed: {exc}"
        )

'''

if '"policy_shadow"' not in text:
    position = text.find(allocation_marker)

    if position == -1:
        raise SystemExit(
            "Could not locate allocation extraction block."
        )

    position += len(allocation_marker)
    text = text[:position] + shadow_block + text[position:]

text = text.replace(
    '''        "market_regime": _normalize_market_regime(
            regime_record
        ),''',
    '''        "market_regime": normalized_market_regime,''',
    1,
)

metadata_marker = '''            "available_sources": {
                "prediction_center": bool(prediction_record),
'''

metadata_replacement = '''            "policy_shadow": (
                policy_result.to_dict()
                if policy_result is not None
                else None
            ),
            "policy_shadow_enabled": True,
            "policy_shadow_phase": "12.4B",
            "available_sources": {
                "prediction_center": bool(prediction_record),
'''

if '"policy_shadow_enabled": True' not in text:
    if metadata_marker not in text:
        raise SystemExit(
            "Could not locate source_metadata insertion point."
        )

    text = text.replace(
        metadata_marker,
        metadata_replacement,
        1,
    )

path.write_text(text)
print("services/ai_cio.py patched successfully.")
PY

cat > tests/test_ai_cio_policy_shadow.py <<'PY'
from services.ai_cio import assemble_ai_cio_decision


def test_policy_shadow_does_not_replace_current_decision():
    result = assemble_ai_cio_decision(
        symbol="KCB",
        prediction={
            "symbol": "KCB",
            "decision": "BUY",
            "prediction_score": 90,
            "confidence": 88,
            "price": 80,
            "target_price": 92,
        },
        committee={
            "symbol": "KCB",
            "decision": "BUY",
            "committee_score": 88,
            "consensus_score": 90,
            "confidence": 89,
        },
        risk={
            "symbol": "KCB",
            "risk_status": "APPROVED",
            "risk_score": 85,
        },
        portfolio={
            "symbol": "KCB",
            "portfolio_score": 82,
            "recommended_allocation_pct": 8,
            "current_exposure_pct": 4,
        },
        screener={
            "symbol": "KCB",
            "institutional_score": 84,
            "liquidity_score": 90,
        },
        market_regime={
            "market_regime": "BULLISH",
            "regime_score": 86,
        },
        metadata={
            "data_age_seconds": 20,
            "data_quality": "LIVE",
        },
    )

    payload = result.decision.to_dict()
    metadata = payload["source_metadata"]

    assert payload["decision"] == "BUY"
    assert metadata["policy_shadow_enabled"] is True
    assert metadata["policy_shadow"] is not None
    assert metadata["policy_shadow"]["symbol"] == "KCB"


def test_policy_shadow_risk_veto_is_observable():
    result = assemble_ai_cio_decision(
        symbol="SCOM",
        prediction={
            "decision": "STRONG_BUY",
            "prediction_score": 95,
            "confidence": 94,
        },
        committee={
            "decision": "STRONG_BUY",
            "committee_score": 92,
            "consensus_score": 93,
        },
        risk={
            "risk_status": "VETOED",
            "risk_veto": True,
            "risk_score": 90,
        },
        portfolio={
            "portfolio_score": 85,
            "recommended_allocation_pct": 8,
        },
        screener={
            "institutional_score": 90,
            "liquidity_score": 90,
        },
        market_regime={
            "market_regime": "BULLISH",
            "regime_score": 90,
        },
        metadata={
            "data_age_seconds": 10,
            "data_quality": "LIVE",
        },
    )

    payload = result.decision.to_dict()
    shadow = payload["source_metadata"]["policy_shadow"]

    assert shadow["decision"] == "AVOID"
    assert shadow["risk_status"] == "VETOED"
PY

echo
echo "Running syntax validation..."

python3 -m py_compile \
    services/ai_cio.py \
    services/ai_cio_policy.py \
    tests/test_ai_cio_policy_shadow.py

echo "Syntax validation passed."

echo
echo "Running shadow integration smoke test..."

python3 - <<'PY'
from services.ai_cio import assemble_ai_cio_decision

result = assemble_ai_cio_decision(
    symbol="KCB",
    prediction={
        "decision": "BUY",
        "prediction_score": 90,
        "confidence": 88,
        "entry_price": 80,
        "target_price": 92,
    },
    committee={
        "decision": "BUY",
        "committee_score": 88,
        "consensus_score": 90,
        "confidence": 89,
    },
    risk={
        "risk_status": "APPROVED",
        "risk_score": 85,
    },
    portfolio={
        "portfolio_score": 82,
        "recommended_allocation_pct": 8,
        "current_exposure_pct": 4,
    },
    screener={
        "institutional_score": 84,
        "liquidity_score": 90,
    },
    market_regime={
        "market_regime": "BULLISH",
        "regime_score": 86,
    },
    metadata={
        "data_age_seconds": 20,
        "data_quality": "LIVE",
    },
)

payload = result.decision.to_dict()
shadow = payload["source_metadata"]["policy_shadow"]

print("CURRENT DECISION:", payload["decision"])
print("SHADOW DECISION:", shadow["decision"])
print("SHADOW SCORE:", shadow["composite_score"])
print("SHADOW CONFIDENCE:", shadow["confidence"])
print("SHADOW ENGINES:", shadow["valid_engine_count"])
print("WARNINGS:", result.warnings)

assert payload["decision"] == "BUY"
assert shadow["decision"] in {
    "STRONG_BUY",
    "BUY",
    "HOLD",
    "REDUCE",
    "SELL",
    "AVOID",
}

print("PHASE 12.4B SHADOW INTEGRATION PASSED")
PY

if command -v pytest >/dev/null 2>&1; then
    echo
    echo "Running focused pytest validation..."

    pytest -q \
        tests/test_ai_cio_policy.py \
        tests/test_ai_cio_policy_shadow.py
else
    echo
    echo "pytest not installed; focused smoke tests completed."
fi

echo
echo "======================================================"
echo " PHASE 12.4B SHADOW INSTALLATION COMPLETE"
echo "======================================================"
echo
echo "Current production decisions remain unchanged."
echo "Policy results are stored under:"
echo "source_metadata.policy_shadow"
echo
echo "Do not restart the production service yet."
