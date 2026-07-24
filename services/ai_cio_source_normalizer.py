from __future__ import annotations

"""
PHASE 12.3 PART B — AI CIO SOURCE NORMALIZATION

Canonical translation layer between adaptively discovered MIP PRO outputs and
the Phase 12 AI CIO adapters.

This module is read-only. It performs no repository writes and does not modify
the supplied source payloads.
"""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


MappingType = Mapping[str, Any]


SYMBOL_KEYS = (
    "symbol",
    "ticker",
    "code",
    "security",
    "instrument",
)


DECISION_KEYS = (
    "final_decision",
    "decision",
    "recommendation",
    "signal",
    "action",
)


CONTAINER_KEYS = (
    "decisions",
    "committee_decisions",
    "recommendations",
    "signals",
    "predictions",
    "profiles",
    "all_profiles",
    "results",
    "rows",
    "items",
    "data",
    "stocks",
    "opportunities",
    "portfolio",
    "positions",
    "allocations",
    "risk_metrics",
    "risk_market_summary",
    "market_risk",
)


@dataclass(frozen=True)
class NormalizationResult:
    sources: Dict[str, Any]
    diagnostics: Dict[str, Any]
    warnings: List[str]
    metadata: Dict[str, Any]

    def to_dict(
        self,
        *,
        include_sources: bool = False,
    ) -> Dict[str, Any]:
        result = {
            "diagnostics": dict(
                self.diagnostics
            ),
            "warnings": list(
                self.warnings
            ),
            "metadata": dict(
                self.metadata
            ),
        }

        if include_sources:
            result["sources"] = dict(
                self.sources
            )
        else:
            result["sources"] = {
                key: {
                    "available":
                        value is not None,
                    "type":
                        type(value).__name__
                        if value is not None
                        else None,
                    "record_count":
                        len(
                            _records(value)
                        ),
                }
                for key, value
                in self.sources.items()
                if key != "metadata"
            }

        return result


def _is_mapping(
    value: Any,
) -> bool:
    return isinstance(
        value,
        Mapping,
    )


def _is_sequence(
    value: Any,
) -> bool:
    return isinstance(
        value,
        (list, tuple),
    )


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    if value in (
        None,
        "",
    ):
        return float(default)

    try:
        number = float(value)
    except (
        TypeError,
        ValueError,
    ):
        return float(default)

    if number != number:
        return float(default)

    if number in (
        float("inf"),
        float("-inf"),
    ):
        return float(default)

    return number


def _clamp(
    value: Any,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(
        minimum,
        min(
            maximum,
            _safe_float(value),
        ),
    )


def _percentage(
    value: Any,
    default: float = 0.0,
) -> float:
    number = _safe_float(
        value,
        default,
    )

    if 0.0 <= number <= 1.0:
        number *= 100.0

    return round(
        _clamp(number),
        2,
    )


def _symbol(
    value: Any,
) -> str:
    return (
        str(value or "")
        .strip()
        .upper()
    )


def _first(
    source: Any,
    keys: Sequence[str],
    default: Any = None,
) -> Any:
    if not _is_mapping(source):
        return default

    for key in keys:
        value = source.get(key)

        if value not in (
            None,
            "",
        ):
            return value

    return default


def _records(
    payload: Any,
) -> List[Dict[str, Any]]:
    if payload is None:
        return []

    if _is_sequence(payload):
        return [
            dict(item)
            for item in payload
            if _is_mapping(item)
        ]

    if not _is_mapping(payload):
        return []

    source = dict(payload)

    for key in CONTAINER_KEYS:
        value = source.get(key)

        if _is_sequence(value):
            records = [
                dict(item)
                for item in value
                if _is_mapping(item)
            ]

            if records:
                return records

        if _is_mapping(value):
            nested_records = _records(
                value
            )

            if nested_records:
                return nested_records

    symbol_records: List[
        Dict[str, Any]
    ] = []

    for key, value in source.items():
        if not _is_mapping(value):
            continue

        record = dict(value)

        if not any(
            _symbol(
                record.get(symbol_key)
            )
            for symbol_key in SYMBOL_KEYS
        ):
            record["symbol"] = _symbol(
                key
            )

        symbol_records.append(
            record
        )

    if symbol_records:
        return symbol_records

    if any(
        key in source
        for key in (
            *SYMBOL_KEYS,
            *DECISION_KEYS,
            "regime",
            "market_regime",
            "risk_level",
            "risk_status",
            "accuracy",
            "learning_score",
        )
    ):
        return [source]

    return []


def _index(
    payload: Any,
) -> Dict[str, Dict[str, Any]]:
    indexed: Dict[
        str,
        Dict[str, Any],
    ] = {}

    for record in _records(
        payload
    ):
        symbol = _symbol(
            _first(
                record,
                SYMBOL_KEYS,
            )
        )

        if not symbol:
            continue

        existing = indexed.get(
            symbol,
            {},
        )

        indexed[symbol] = {
            **existing,
            **record,
            "symbol": symbol,
        }

    return indexed


def _normalize_decision(
    value: Any,
) -> str:
    raw = (
        str(value or "HOLD")
        .strip()
        .upper()
        .replace("-", "_")
        .replace(" ", "_")
    )

    aliases = {
        "STRONGBUY": "STRONG_BUY",
        "ACCUMULATE": "BUY",
        "LONG": "BUY",
        "POSITIVE": "BUY",
        "WATCH": "HOLD",
        "WAIT": "HOLD",
        "NEUTRAL": "HOLD",
        "NO_ACTION": "HOLD",
        "TAKE_PROFIT": "REDUCE",
        "UNDERWEIGHT": "REDUCE",
        "EXIT": "SELL",
        "SHORT": "SELL",
        "NEGATIVE": "SELL",
        "BLOCK": "AVOID",
        "BLOCKED": "AVOID",
        "REJECT": "AVOID",
    }

    normalized = aliases.get(
        raw,
        raw,
    )

    if normalized not in {
        "STRONG_BUY",
        "BUY",
        "HOLD",
        "REDUCE",
        "SELL",
        "AVOID",
    }:
        return "HOLD"

    return normalized


def _normalize_regime_name(
    value: Any,
) -> str:
    raw = (
        str(value or "")
        .strip()
        .upper()
        .replace("-", "_")
        .replace(" ", "_")
    )

    if not raw:
        return "UNKNOWN"

    if (
        "BULL" in raw
        or "RISK_ON" in raw
        or "EXPANSION" in raw
        or "UPTREND" in raw
    ):
        if (
            "STRONG" in raw
            or "HIGH_CONVICTION" in raw
        ):
            return "STRONG_BULLISH"

        return "BULLISH"

    if (
        "BEAR" in raw
        or "RISK_OFF" in raw
        or "CONTRACTION" in raw
        or "DOWNTREND" in raw
    ):
        if (
            "STRONG" in raw
            or "HIGH_CONVICTION" in raw
        ):
            return "STRONG_BEARISH"

        return "BEARISH"

    if (
        "VOLAT" in raw
        or "TURBUL" in raw
        or "STRESS" in raw
    ):
        return "HIGH_VOLATILITY"

    if (
        "SIDEWAYS" in raw
        or "RANGE" in raw
        or "CONSOLID" in raw
    ):
        return "SIDEWAYS"

    if (
        "NEUTRAL" in raw
        or "MIXED" in raw
        or "BALANCED" in raw
    ):
        return "NEUTRAL"

    return raw


def _risk_level(
    value: Any,
) -> str:
    raw = (
        str(value or "")
        .strip()
        .upper()
        .replace("-", "_")
        .replace(" ", "_")
    )

    aliases = {
        "VERYLOW": "VERY_LOW",
        "VERYHIGH": "VERY_HIGH",
        "MODERATE": "MEDIUM",
        "ELEVATED": "HIGH",
        "CRITICAL": "VERY_HIGH",
        "SEVERE": "VERY_HIGH",
        "SAFE": "LOW",
    }

    raw = aliases.get(
        raw,
        raw,
    )

    if raw in {
        "VERY_LOW",
        "LOW",
        "MEDIUM",
        "HIGH",
        "VERY_HIGH",
    }:
        return raw

    if "VERY" in raw and "HIGH" in raw:
        return "VERY_HIGH"

    if "HIGH" in raw:
        return "HIGH"

    if (
        "MEDIUM" in raw
        or "MODERATE" in raw
    ):
        return "MEDIUM"

    if "LOW" in raw:
        return "LOW"

    return "UNKNOWN"


def _risk_score_from_level(
    level: str,
) -> float:
    """
    AI CIO risk score represents risk quality/safety, where a higher score is
    safer. This is deliberately inverse to raw risk severity.
    """

    return {
        "VERY_LOW": 92.0,
        "LOW": 82.0,
        "MEDIUM": 62.0,
        "HIGH": 38.0,
        "VERY_HIGH": 15.0,
        "UNKNOWN": 45.0,
    }.get(
        level,
        45.0,
    )


def _risk_status_from_level(
    level: str,
    veto: bool,
) -> str:
    if veto:
        return "VETOED"

    return {
        "VERY_LOW": "APPROVED",
        "LOW": "APPROVED",
        "MEDIUM":
            "APPROVED_WITH_CAUTION",
        "HIGH":
            "RESTRICTED",
        "VERY_HIGH":
            "VETOED",
        "UNKNOWN":
            "INSUFFICIENT_DATA",
    }.get(
        level,
        "INSUFFICIENT_DATA",
    )


def normalize_market_regime(
    payload: Any,
) -> Dict[str, Any]:
    source = (
        dict(payload)
        if _is_mapping(payload)
        else {}
    )

    records = _records(
        payload
    )

    if records:
        merged = {
            **source,
            **records[0],
        }
    else:
        merged = source

    regime = _normalize_regime_name(
        _first(
            merged,
            (
                "market_regime",
                "regime",
                "market_state",
                "state",
                "phase",
                "trend_regime",
                "volatility_regime",
            ),
            "UNKNOWN",
        )
    )

    score = _percentage(
        _first(
            merged,
            (
                "regime_score",
                "score",
                "market_score",
                "confidence",
            ),
            0.0,
        )
    )

    confidence = _percentage(
        _first(
            merged,
            (
                "confidence",
                "confidence_pct",
                "regime_confidence",
                "score",
            ),
            score,
        )
    )

    volatility = str(
        _first(
            merged,
            (
                "volatility_regime",
                "volatility",
                "volatility_state",
            ),
            "",
        )
        or ""
    ).strip().upper()

    return {
        **merged,
        "market_regime": regime,
        "regime": regime,
        "regime_score": score,
        "score": score,
        "confidence": confidence,
        "regime_confidence":
            confidence,
        "volatility_regime":
            volatility,
        "available":
            regime != "UNKNOWN",
        "normalized":
            True,
        "normalizer_phase":
            "12.3-part-b",
    }


def normalize_learning(
    payload: Any,
) -> Dict[str, Any]:
    source = (
        dict(payload)
        if _is_mapping(payload)
        else {}
    )

    records = _records(
        payload
    )

    if records:
        source = {
            **source,
            **records[0],
        }

    accuracy = _percentage(
        _first(
            source,
            (
                "historical_accuracy",
                "accuracy",
                "model_accuracy",
                "success_rate",
                "win_rate",
            ),
            0.0,
        )
    )

    learning_score = _percentage(
        _first(
            source,
            (
                "learning_score",
                "adaptive_score",
                "performance_score",
                "model_score",
            ),
            accuracy,
        )
    )

    adjustment = _safe_float(
        _first(
            source,
            (
                "adaptive_adjustment",
                "confidence_adjustment",
                "adjustment",
            ),
            0.0,
        )
    )

    return {
        **source,
        "accuracy": accuracy,
        "historical_accuracy":
            accuracy,
        "model_accuracy": accuracy,
        "learning_score":
            learning_score,
        "adaptive_adjustment":
            adjustment,
        "available":
            accuracy > 0.0
            or learning_score > 0.0,
        "normalized":
            True,
        "normalizer_phase":
            "12.3-part-b",
    }


def normalize_breadth(
    payload: Any,
) -> Dict[str, Any]:
    source = (
        dict(payload)
        if _is_mapping(payload)
        else {}
    )

    records = _records(
        payload
    )

    if records:
        source = {
            **source,
            **records[0],
        }

    advancers = int(
        _safe_float(
            _first(
                source,
                (
                    "advancers",
                    "gainers",
                    "advancing",
                ),
                0,
            )
        )
    )

    decliners = int(
        _safe_float(
            _first(
                source,
                (
                    "decliners",
                    "losers",
                    "declining",
                ),
                0,
            )
        )
    )

    unchanged = int(
        _safe_float(
            _first(
                source,
                (
                    "unchanged",
                    "flat",
                    "neutral",
                ),
                0,
            )
        )
    )

    total = max(
        0,
        advancers
        + decliners
        + unchanged,
    )

    advancing_pct = _percentage(
        _first(
            source,
            (
                "advancing_percentage",
                "advancers_pct",
                "advance_pct",
                "breadth_pct",
            ),
            (
                100.0
                * advancers
                / total
                if total
                else 0.0
            ),
        )
    )

    declining_pct = _percentage(
        _first(
            source,
            (
                "declining_percentage",
                "decliners_pct",
                "decline_pct",
            ),
            (
                100.0
                * decliners
                / total
                if total
                else 0.0
            ),
        )
    )

    breadth_score = round(
        _clamp(
            advancing_pct
            - declining_pct
            + 50.0
        ),
        2,
    )

    return {
        **source,
        "advancers": advancers,
        "decliners": decliners,
        "unchanged": unchanged,
        "total": total,
        "advancing_percentage":
            advancing_pct,
        "declining_percentage":
            declining_pct,
        "breadth_score":
            _percentage(
                _first(
                    source,
                    (
                        "breadth_score",
                        "participation_score",
                    ),
                    breadth_score,
                )
            ),
        "market_participation":
            advancing_pct,
        "normalized":
            True,
        "normalizer_phase":
            "12.3-part-b",
    }


def normalize_committee(
    payload: Any,
) -> Dict[str, Any]:
    normalized: List[
        Dict[str, Any]
    ] = []

    for raw in _records(
        payload
    ):
        symbol = _symbol(
            _first(
                raw,
                SYMBOL_KEYS,
            )
        )

        if not symbol:
            continue

        decision = _normalize_decision(
            _first(
                raw,
                DECISION_KEYS,
                "HOLD",
            )
        )

        confidence = _percentage(
            _first(
                raw,
                (
                    "confidence",
                    "confidence_pct",
                    "committee_confidence",
                ),
                0.0,
            )
        )

        committee_score = _percentage(
            _first(
                raw,
                (
                    "committee_score",
                    "score",
                    "rank_score",
                    "overall_score",
                ),
                confidence,
            )
        )

        consensus = _percentage(
            _first(
                raw,
                (
                    "consensus_pct",
                    "consensus",
                    "agreement_pct",
                    "agreement",
                ),
                confidence,
            )
        )

        normalized.append(
            {
                **raw,
                "symbol": symbol,
                "decision": decision,
                "final_decision":
                    decision,
                "recommendation":
                    decision,
                "signal": decision,
                "confidence":
                    confidence,
                "committee_score":
                    committee_score,
                "score":
                    committee_score,
                "consensus_pct":
                    consensus,
                "technical_score":
                    _percentage(
                        _first(
                            raw,
                            (
                                "technical_score",
                                "technical",
                            ),
                            0.0,
                        )
                    ),
                "prediction_score":
                    _percentage(
                        _first(
                            raw,
                            (
                                "prediction_score",
                                "quant_score",
                                "predictive_score",
                            ),
                            0.0,
                        )
                    ),
                "institutional_score":
                    _percentage(
                        _first(
                            raw,
                            (
                                "institutional_score",
                                "institutional",
                                "flow_score",
                            ),
                            0.0,
                        )
                    ),
                "volume_score":
                    _percentage(
                        _first(
                            raw,
                            (
                                "volume_score",
                                "volume_quality",
                            ),
                            0.0,
                        )
                    ),
                "normalized": True,
            }
        )

    return {
        "decisions": normalized,
        "committee_decisions":
            normalized,
        "recommendations":
            normalized,
        "decision_count":
            len(normalized),
        "normalized":
            True,
        "normalizer_phase":
            "12.3-part-b",
    }


def normalize_predictions(
    payload: Any,
    allowed_symbols: Optional[
        Set[str]
    ] = None,
) -> Dict[str, Any]:
    normalized: List[
        Dict[str, Any]
    ] = []

    for raw in _records(
        payload
    ):
        symbol = _symbol(
            _first(
                raw,
                SYMBOL_KEYS,
            )
        )

        if not symbol:
            continue

        if (
            allowed_symbols
            and symbol
            not in allowed_symbols
        ):
            continue

        probability = _percentage(
            _first(
                raw,
                (
                    "probability",
                    "prediction_probability",
                    "confidence",
                    "confidence_pct",
                ),
                0.0,
            )
        )

        score = _percentage(
            _first(
                raw,
                (
                    "prediction_score",
                    "score",
                    "forecast_score",
                    "conviction_score",
                ),
                probability,
            )
        )

        expected_return = _safe_float(
            _first(
                raw,
                (
                    "expected_return_pct",
                    "expected_return",
                    "potential_return",
                    "return_pct",
                ),
                0.0,
            )
        )

        normalized.append(
            {
                **raw,
                "symbol": symbol,
                "prediction_score":
                    score,
                "score": score,
                "probability":
                    probability,
                "confidence":
                    probability,
                "expected_return":
                    expected_return,
                "expected_return_pct":
                    expected_return,
                "entry_price":
                    _safe_float(
                        _first(
                            raw,
                            (
                                "entry_price",
                                "price",
                                "current_price",
                            ),
                            0.0,
                        )
                    ),
                "target_price":
                    _safe_float(
                        _first(
                            raw,
                            (
                                "target_price",
                                "predicted_price",
                                "forecast_price",
                            ),
                            0.0,
                        )
                    ),
                "normalized": True,
            }
        )

    return {
        "predictions": normalized,
        "data": normalized,
        "prediction_count":
            len(normalized),
        "normalized":
            True,
        "normalizer_phase":
            "12.3-part-b",
    }


def normalize_screener(
    payload: Any,
    allowed_symbols: Optional[
        Set[str]
    ] = None,
) -> Dict[str, Any]:
    normalized: List[
        Dict[str, Any]
    ] = []

    for raw in _records(
        payload
    ):
        symbol = _symbol(
            _first(
                raw,
                SYMBOL_KEYS,
            )
        )

        if not symbol:
            continue

        if (
            allowed_symbols
            and symbol
            not in allowed_symbols
        ):
            continue

        normalized.append(
            {
                **raw,
                "symbol": symbol,
                "price":
                    _safe_float(
                        _first(
                            raw,
                            (
                                "price",
                                "current_price",
                                "last_price",
                            ),
                            0.0,
                        )
                    ),
                "technical_score":
                    _percentage(
                        _first(
                            raw,
                            (
                                "technical_score",
                                "score",
                                "rank_score",
                            ),
                            0.0,
                        )
                    ),
                "institutional_score":
                    _percentage(
                        _first(
                            raw,
                            (
                                "institutional_score",
                                "accumulation_score",
                                "flow_score",
                            ),
                            0.0,
                        )
                    ),
                "volume_score":
                    _percentage(
                        _first(
                            raw,
                            (
                                "volume_score",
                                "volume_quality",
                                "liquidity_score",
                            ),
                            0.0,
                        )
                    ),
                "relative_volume":
                    _safe_float(
                        _first(
                            raw,
                            (
                                "relative_volume",
                                "relative_volume_ratio",
                                "rvol",
                            ),
                            0.0,
                        )
                    ),
                "normalized": True,
            }
        )

    return {
        "profiles": normalized,
        "all_profiles": normalized,
        "results": normalized,
        "profile_count":
            len(normalized),
        "normalized":
            True,
        "normalizer_phase":
            "12.3-part-b",
    }


def normalize_risk(
    payload: Any,
    allowed_symbols: Optional[
        Set[str]
    ] = None,
) -> Dict[str, Any]:
    normalized: List[
        Dict[str, Any]
    ] = []

    for raw in _records(
        payload
    ):
        symbol = _symbol(
            _first(
                raw,
                SYMBOL_KEYS,
            )
        )

        if not symbol:
            continue

        if (
            allowed_symbols
            and symbol
            not in allowed_symbols
        ):
            continue

        level = _risk_level(
            _first(
                raw,
                (
                    "risk_level",
                    "level",
                    "severity",
                    "risk_category",
                ),
                "UNKNOWN",
            )
        )

        explicit_veto = bool(
            _first(
                raw,
                (
                    "risk_veto",
                    "veto",
                    "blocked",
                    "reject",
                ),
                False,
            )
        )

        veto = (
            explicit_veto
            or level == "VERY_HIGH"
        )

        raw_score = _first(
            raw,
            (
                "risk_score",
                "risk_quality_score",
                "safety_score",
            ),
            None,
        )

        if raw_score in (
            None,
            "",
        ):
            risk_score = (
                _risk_score_from_level(
                    level
                )
            )
            score_derived = True
        else:
            risk_score = _percentage(
                raw_score
            )
            score_derived = False

        status = str(
            _first(
                raw,
                (
                    "risk_status",
                    "approval_status",
                    "status",
                ),
                "",
            )
            or ""
        ).strip().upper()

        if not status:
            status = (
                _risk_status_from_level(
                    level,
                    veto,
                )
            )

        if status in {
            "VETO",
            "BLOCKED",
            "REJECTED",
            "DECLINED",
        }:
            status = "VETOED"
            veto = True

        normalized.append(
            {
                **raw,
                "symbol": symbol,
                "risk_level": level,
                "risk_status": status,
                "approval_status":
                    status,
                "risk_score":
                    round(
                        risk_score,
                        2,
                    ),
                "risk_quality_score":
                    round(
                        risk_score,
                        2,
                    ),
                "risk_veto": veto,
                "veto": veto,
                "score_derived":
                    score_derived,
                "normalized": True,
            }
        )

    return {
        "risk_metrics": normalized,
        "risk_market_summary":
            normalized,
        "data": normalized,
        "risk_count":
            len(normalized),
        "normalized":
            True,
        "normalizer_phase":
            "12.3-part-b",
    }


def _derived_position_size(
    committee: Dict[str, Any],
    prediction: Dict[str, Any],
    risk: Dict[str, Any],
) -> float:
    decision = _normalize_decision(
        _first(
            committee,
            DECISION_KEYS,
            "HOLD",
        )
    )

    confidence = _percentage(
        _first(
            committee,
            (
                "confidence",
                "committee_score",
            ),
            0.0,
        )
    )

    prediction_score = _percentage(
        _first(
            prediction,
            (
                "prediction_score",
                "score",
                "confidence",
            ),
            0.0,
        )
    )

    risk_score = _percentage(
        _first(
            risk,
            (
                "risk_score",
                "risk_quality_score",
            ),
            45.0,
        )
    )

    veto = bool(
        _first(
            risk,
            (
                "risk_veto",
                "veto",
            ),
            False,
        )
    )

    if veto:
        return 0.0

    base = {
        "STRONG_BUY": 7.0,
        "BUY": 5.0,
        "HOLD": 1.5,
        "REDUCE": 0.5,
        "SELL": 0.0,
        "AVOID": 0.0,
    }.get(
        decision,
        0.0,
    )

    quality = (
        0.40
        * confidence
        + 0.30
        * prediction_score
        + 0.30
        * risk_score
    ) / 100.0

    position = base * quality

    return round(
        max(
            0.0,
            min(10.0, position),
        ),
        2,
    )


def normalize_portfolio(
    payload: Any,
    *,
    symbols: Sequence[str],
    committee_index: Mapping[
        str,
        Dict[str, Any]
    ],
    prediction_index: Mapping[
        str,
        Dict[str, Any]
    ],
    risk_index: Mapping[
        str,
        Dict[str, Any]
    ],
) -> Dict[str, Any]:
    existing_index = _index(
        payload
    )

    normalized: List[
        Dict[str, Any]
    ] = []

    derived_count = 0

    for symbol in symbols:
        raw = dict(
            existing_index.get(
                symbol,
                {},
            )
        )

        explicit_size = _first(
            raw,
            (
                "position_size_pct",
                "recommended_weight",
                "allocation_pct",
                "weight_pct",
                "portfolio_weight",
                "exposure_pct",
            ),
            None,
        )

        if explicit_size in (
            None,
            "",
        ):
            position_size = (
                _derived_position_size(
                    committee_index.get(
                        symbol,
                        {},
                    ),
                    prediction_index.get(
                        symbol,
                        {},
                    ),
                    risk_index.get(
                        symbol,
                        {},
                    ),
                )
            )

            derived = True
            derived_count += 1
        else:
            position_size = (
                _percentage(
                    explicit_size
                )
            )
            derived = False

        normalized.append(
            {
                **raw,
                "symbol": symbol,
                "position_size_pct":
                    position_size,
                "recommended_weight":
                    position_size,
                "allocation_pct":
                    position_size,
                "portfolio_weight":
                    position_size,
                "exposure_pct":
                    position_size,
                "allocation_derived":
                    derived,
                "normalized": True,
            }
        )

    total_exposure = round(
        sum(
            _safe_float(
                item.get(
                    "position_size_pct"
                )
            )
            for item in normalized
        ),
        2,
    )

    return {
        "allocations": normalized,
        "portfolio": normalized,
        "positions": normalized,
        "allocation_count":
            len(normalized),
        "derived_count":
            derived_count,
        "total_exposure_pct":
            total_exposure,
        "derived_optimizer":
            payload is None
            or not bool(
                existing_index
            ),
        "normalized":
            True,
        "normalizer_phase":
            "12.3-part-b",
    }


def normalize_institutional_flow(
    payload: Any,
    screener_payload: Any,
    allowed_symbols: Optional[
        Set[str]
    ] = None,
) -> Dict[str, Any]:
    primary = _index(
        payload
    )

    screener = _index(
        screener_payload
    )

    symbols = set(
        primary
    ) | set(
        screener
    )

    if allowed_symbols:
        symbols &= allowed_symbols

    records: List[
        Dict[str, Any]
    ] = []

    for symbol in sorted(
        symbols
    ):
        merged = {
            **screener.get(
                symbol,
                {},
            ),
            **primary.get(
                symbol,
                {},
            ),
        }

        institutional_score = (
            _percentage(
                _first(
                    merged,
                    (
                        "institutional_score",
                        "accumulation_score",
                        "smart_money_score",
                        "flow_score",
                    ),
                    0.0,
                )
            )
        )

        records.append(
            {
                **merged,
                "symbol": symbol,
                "institutional_score":
                    institutional_score,
                "accumulation_score":
                    _percentage(
                        _first(
                            merged,
                            (
                                "accumulation_score",
                                "institutional_score",
                            ),
                            institutional_score,
                        )
                    ),
                "liquidity_score":
                    _percentage(
                        _first(
                            merged,
                            (
                                "liquidity_score",
                                "volume_quality",
                            ),
                            0.0,
                        )
                    ),
                "relative_volume":
                    _safe_float(
                        _first(
                            merged,
                            (
                                "relative_volume",
                                "relative_volume_ratio",
                                "rvol",
                            ),
                            0.0,
                        )
                    ),
                "normalized": True,
            }
        )

    return {
        "institutional_flow":
            records,
        "profiles": records,
        "data": records,
        "record_count":
            len(records),
        "normalized":
            True,
        "normalizer_phase":
            "12.3-part-b",
    }


def build_normalized_ai_cio_sources(
    sources: MappingType,
) -> NormalizationResult:
    source = dict(
        sources or {}
    )

    warnings: List[str] = []

    committee = normalize_committee(
        source.get(
            "investment_committee"
        )
    )

    committee_records = (
        committee.get(
            "decisions",
            [],
        )
    )

    committee_symbols = [
        _symbol(
            item.get("symbol")
        )
        for item in committee_records
        if _symbol(
            item.get("symbol")
        )
    ]

    allowed_symbols = set(
        committee_symbols
    )

    if not allowed_symbols:
        warnings.append(
            "No committee symbols found; normalization will use all discovered symbols."
        )
        allowed_symbols = set()

    prediction_center = (
        normalize_predictions(
            source.get(
                "prediction_center"
            ),
            allowed_symbols or None,
        )
    )

    screener = normalize_screener(
        source.get(
            "screener"
        ),
        allowed_symbols or None,
    )

    risk_engine = normalize_risk(
        source.get(
            "risk_engine"
        ),
        allowed_symbols or None,
    )

    market_regime = (
        normalize_market_regime(
            source.get(
                "market_regime"
            )
        )
    )

    learning = normalize_learning(
        source.get(
            "learning"
        )
    )

    breadth = normalize_breadth(
        source.get(
            "breadth"
        )
    )

    institutional_flow = (
        normalize_institutional_flow(
            source.get(
                "institutional_flow"
            ),
            screener,
            allowed_symbols or None,
        )
    )

    prediction_index = _index(
        prediction_center
    )

    risk_index = _index(
        risk_engine
    )

    committee_index = _index(
        committee
    )

    portfolio_optimizer = (
        normalize_portfolio(
            source.get(
                "portfolio_optimizer"
            ),
            symbols=committee_symbols,
            committee_index=
                committee_index,
            prediction_index=
                prediction_index,
            risk_index=
                risk_index,
        )
    )

    # Merge normalized institutional fields into screener profiles because the
    # existing AI CIO adapter already consumes screener fields.
    institutional_index = _index(
        institutional_flow
    )

    merged_profiles = []

    for profile in screener.get(
        "profiles",
        [],
    ):
        symbol = _symbol(
            profile.get("symbol")
        )

        merged_profiles.append(
            {
                **profile,
                **institutional_index.get(
                    symbol,
                    {},
                ),
                "symbol": symbol,
            }
        )

    screener[
        "profiles"
    ] = merged_profiles

    screener[
        "all_profiles"
    ] = merged_profiles

    screener[
        "results"
    ] = merged_profiles

    prediction_records = (
        prediction_center.get(
            "predictions",
            [],
        )
    )

    # Attach global context to Prediction Center as additional compatibility
    # fields for adapters that look inside Prediction Center.
    prediction_center[
        "market_regime"
    ] = market_regime

    prediction_center[
        "regime"
    ] = market_regime

    prediction_center[
        "learning"
    ] = learning

    prediction_center[
        "breadth"
    ] = breadth

    prediction_center[
        "market_breadth"
    ] = breadth

    prediction_center[
        "risk_metrics"
    ] = risk_engine.get(
        "risk_metrics",
        [],
    )

    prediction_center[
        "risk_market_summary"
    ] = risk_engine.get(
        "risk_metrics",
        [],
    )

    prediction_center[
        "portfolio"
    ] = portfolio_optimizer.get(
        "allocations",
        [],
    )

    prediction_center[
        "allocations"
    ] = portfolio_optimizer.get(
        "allocations",
        [],
    )

    prediction_center[
        "all_profiles"
    ] = merged_profiles

    prediction_center[
        "profiles"
    ] = merged_profiles

    normalized_sources = {
        "prediction_center":
            prediction_center,
        "investment_committee":
            committee,
        "risk_engine":
            risk_engine,
        "portfolio_optimizer":
            portfolio_optimizer,
        "screener":
            screener,
        "market_regime":
            market_regime,
        "learning":
            learning,
        "breadth":
            breadth,
        "institutional_flow":
            institutional_flow,
        "metadata": {
            **(
                dict(
                    source.get(
                        "metadata",
                        {},
                    )
                )
                if _is_mapping(
                    source.get(
                        "metadata"
                    )
                )
                else {}
            ),
            "normalized":
                True,
            "normalizer_phase":
                "12.3-part-b",
            "read_only":
                True,
            "repository_writes":
                False,
        },
    }

    risk_records = (
        risk_engine.get(
            "risk_metrics",
            [],
        )
    )

    risk_status_count: Dict[
        str,
        int,
    ] = {}

    for item in risk_records:
        status = str(
            item.get(
                "risk_status",
                "UNKNOWN",
            )
        )

        risk_status_count[
            status
        ] = (
            risk_status_count.get(
                status,
                0,
            )
            + 1
        )

    missing_prediction_symbols = sorted(
        allowed_symbols
        - set(
            prediction_index
        )
    )

    missing_risk_symbols = sorted(
        allowed_symbols
        - set(
            risk_index
        )
    )

    diagnostics = {
        "phase":
            "12.3-part-b",
        "committee_symbol_count":
            len(allowed_symbols),
        "prediction_count":
            len(prediction_records),
        "screener_profile_count":
            len(merged_profiles),
        "risk_record_count":
            len(risk_records),
        "portfolio_allocation_count":
            len(
                portfolio_optimizer.get(
                    "allocations",
                    [],
                )
            ),
        "portfolio_derived_count":
            portfolio_optimizer.get(
                "derived_count",
                0,
            ),
        "portfolio_total_exposure_pct":
            portfolio_optimizer.get(
                "total_exposure_pct",
                0.0,
            ),
        "market_regime":
            market_regime.get(
                "market_regime",
                "UNKNOWN",
            ),
        "market_regime_available":
            market_regime.get(
                "available",
                False,
            ),
        "learning_available":
            learning.get(
                "available",
                False,
            ),
        "risk_status_counts":
            risk_status_count,
        "missing_prediction_symbols":
            missing_prediction_symbols,
        "missing_risk_symbols":
            missing_risk_symbols,
        "universe_filtered_to_committee":
            bool(allowed_symbols),
        "read_only":
            True,
        "repository_writes":
            False,
    }

    if missing_prediction_symbols:
        warnings.append(
            "Missing normalized predictions for: "
            + ", ".join(
                missing_prediction_symbols
            )
        )

    if missing_risk_symbols:
        warnings.append(
            "Missing normalized risk for: "
            + ", ".join(
                missing_risk_symbols
            )
        )

    if (
        market_regime.get(
            "market_regime"
        )
        == "UNKNOWN"
    ):
        warnings.append(
            "Market regime remains UNKNOWN after normalization."
        )

    if portfolio_optimizer.get(
        "derived_optimizer"
    ):
        warnings.append(
            "Portfolio optimizer source was unavailable; conservative derived allocations were used."
        )

    return NormalizationResult(
        sources=normalized_sources,
        diagnostics=diagnostics,
        warnings=warnings,
        metadata={
            "phase":
                "12.3-part-b",
            "mode":
                "source-normalization",
            "read_only":
                True,
            "repository_writes":
                False,
        },
    )


__all__ = [
    "NormalizationResult",
    "build_normalized_ai_cio_sources",
    "normalize_breadth",
    "normalize_committee",
    "normalize_institutional_flow",
    "normalize_learning",
    "normalize_market_regime",
    "normalize_portfolio",
    "normalize_predictions",
    "normalize_risk",
    "normalize_screener",
]
