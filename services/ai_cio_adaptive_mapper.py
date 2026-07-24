from __future__ import annotations

"""
PHASE 12.3 PART A — AI CIO ADAPTIVE SCHEMA DISCOVERY

Read-only adaptive schema discovery and source normalization for MIP PRO.

This module does not:
- write to the Signal Repository;
- modify specialist-engine outputs;
- replace production decisions;
- mutate the supplied intelligence context.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


MappingType = Mapping[str, Any]


ENGINE_NAMES = (
    "prediction_center",
    "investment_committee",
    "risk_engine",
    "portfolio_optimizer",
    "screener",
    "market_regime",
    "learning",
    "breadth",
    "institutional_flow",
)


ENGINE_ALIASES: Dict[str, Tuple[str, ...]] = {
    "prediction_center": (
        "prediction_center",
        "predictions",
        "predictive_engine",
        "prediction_engine",
        "forecast_center",
        "forecast_engine",
        "predictive_intelligence",
    ),
    "investment_committee": (
        "investment_committee",
        "ai_investment_committee",
        "committee",
        "committee_decisions",
        "investment_decisions",
        "recommendations",
        "signals",
    ),
    "risk_engine": (
        "risk_engine",
        "market_risk",
        "risk",
        "risk_metrics",
        "stock_risk",
        "risk_analysis",
        "risk_assessment",
        "risk_controls",
        "risk_profile",
    ),
    "portfolio_optimizer": (
        "portfolio_optimizer",
        "optimized_portfolio",
        "portfolio",
        "allocations",
        "portfolio_allocations",
        "position_sizing",
        "capital_allocation",
        "recommended_positions",
    ),
    "screener": (
        "screener",
        "screener_results",
        "market_screener",
        "screening_results",
        "opportunities",
        "top_opportunities",
        "stock_profiles",
        "profiles",
    ),
    "market_regime": (
        "market_regime",
        "regime",
        "regime_analysis",
        "market_environment",
        "market_state",
        "market_phase",
        "volatility_regime",
    ),
    "learning": (
        "learning",
        "learning_engine",
        "learning_metrics",
        "adaptive_learning",
        "learning_summary",
        "performance_learning",
        "historical_accuracy",
        "model_performance",
    ),
    "breadth": (
        "breadth",
        "market_breadth",
        "breadth_summary",
        "breadth_metrics",
        "advancers_decliners",
        "market_participation",
    ),
    "institutional_flow": (
        "institutional_flow",
        "institutional",
        "institutional_intelligence",
        "smart_money",
        "accumulation",
        "distribution",
        "volume_intelligence",
        "volume_flow",
    ),
}


ENGINE_HINT_FIELDS: Dict[str, Tuple[str, ...]] = {
    "prediction_center": (
        "predictions",
        "prediction_count",
        "expected_return",
        "expected_return_pct",
        "prediction_score",
        "probability",
        "forecast",
        "target_price",
    ),
    "investment_committee": (
        "decisions",
        "committee_score",
        "final_decision",
        "decision",
        "consensus_pct",
        "agents",
        "vote_distribution",
        "confidence",
    ),
    "risk_engine": (
        "risk_status",
        "risk_score",
        "risk_veto",
        "risk_level",
        "maximum_drawdown",
        "volatility",
        "stop_loss",
        "key_risks",
    ),
    "portfolio_optimizer": (
        "position_size_pct",
        "recommended_weight",
        "allocation_pct",
        "maximum_capital",
        "recommended_units",
        "portfolio_weight",
        "exposure_pct",
    ),
    "screener": (
        "rank_score",
        "technical_score",
        "rsi",
        "macd",
        "trend",
        "price",
        "volume",
        "relative_volume",
    ),
    "market_regime": (
        "regime",
        "market_regime",
        "regime_score",
        "volatility_regime",
        "trend_regime",
        "market_state",
        "confidence",
    ),
    "learning": (
        "accuracy",
        "historical_accuracy",
        "learning_score",
        "adaptive_adjustment",
        "success_rate",
        "win_rate",
        "model_accuracy",
    ),
    "breadth": (
        "advancers",
        "decliners",
        "unchanged",
        "advancing_percentage",
        "declining_percentage",
        "breadth_score",
        "market_participation",
    ),
    "institutional_flow": (
        "institutional_score",
        "accumulation_score",
        "relative_volume",
        "volume_quality",
        "liquidity_score",
        "abnormal_volume",
        "smart_money",
    ),
}


LIST_CONTAINER_KEYS = (
    "data",
    "items",
    "results",
    "rows",
    "stocks",
    "signals",
    "decisions",
    "predictions",
    "profiles",
    "portfolio",
    "positions",
    "allocations",
    "risk_metrics",
    "recommendations",
    "opportunities",
)


@dataclass(frozen=True)
class SchemaCandidate:
    engine: str
    path: str
    score: float
    alias_matches: List[str]
    field_matches: List[str]
    value_type: str
    record_count: int
    symbol_count: int
    sample_keys: List[str]
    payload: Any = field(
        repr=False,
        compare=False,
    )

    def to_dict(
        self,
        *,
        include_payload: bool = False,
    ) -> Dict[str, Any]:
        result = {
            "engine": self.engine,
            "path": self.path,
            "score": self.score,
            "alias_matches": list(
                self.alias_matches
            ),
            "field_matches": list(
                self.field_matches
            ),
            "value_type": self.value_type,
            "record_count": self.record_count,
            "symbol_count": self.symbol_count,
            "sample_keys": list(
                self.sample_keys
            ),
        }

        if include_payload:
            result["payload"] = self.payload

        return result


@dataclass(frozen=True)
class AdaptiveSourceMap:
    sources: Dict[str, Any]
    selected_paths: Dict[str, Optional[str]]
    selected_scores: Dict[str, float]
    coverage: Dict[str, Any]
    candidates: Dict[str, List[SchemaCandidate]]
    warnings: List[str]
    metadata: Dict[str, Any]

    def to_dict(
        self,
        *,
        include_payloads: bool = False,
        include_candidates: bool = True,
    ) -> Dict[str, Any]:
        result = {
            "selected_paths": dict(
                self.selected_paths
            ),
            "selected_scores": dict(
                self.selected_scores
            ),
            "coverage": dict(
                self.coverage
            ),
            "warnings": list(
                self.warnings
            ),
            "metadata": dict(
                self.metadata
            ),
        }

        if include_payloads:
            result["sources"] = dict(
                self.sources
            )
        else:
            result["sources"] = {
                engine: {
                    "available":
                        self.sources.get(engine)
                        is not None,
                    "selected_path":
                        self.selected_paths.get(
                            engine
                        ),
                    "score":
                        self.selected_scores.get(
                            engine,
                            0.0,
                        ),
                }
                for engine in ENGINE_NAMES
            }

        if include_candidates:
            result["candidates"] = {
                engine: [
                    candidate.to_dict(
                        include_payload=False
                    )
                    for candidate in values
                ]
                for engine, values
                in self.candidates.items()
            }

        return result


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


def _normalize_token(
    value: Any,
) -> str:
    text = str(value or "").strip().lower()

    for character in (
        "-",
        " ",
        ".",
        "/",
        ":",
    ):
        text = text.replace(
            character,
            "_",
        )

    while "__" in text:
        text = text.replace(
            "__",
            "_",
        )

    return text.strip("_")


def _normalize_symbol(
    value: Any,
) -> str:
    return str(value or "").strip().upper()


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


def _mapping_keys(
    value: Any,
) -> List[str]:
    if not _is_mapping(value):
        return []

    return [
        str(key)
        for key in value.keys()
    ]


def _records_from_payload(
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

    for key in LIST_CONTAINER_KEYS:
        value = source.get(key)

        if _is_sequence(value):
            records = [
                dict(item)
                for item in value
                if _is_mapping(item)
            ]

            if records:
                return records

    symbol_records: List[
        Dict[str, Any]
    ] = []

    for key, value in source.items():
        if not _is_mapping(value):
            continue

        record = dict(value)

        if not any(
            record.get(symbol_key)
            for symbol_key in (
                "symbol",
                "ticker",
                "code",
                "security",
                "instrument",
            )
        ):
            record["symbol"] = (
                _normalize_symbol(key)
            )

        symbol_records.append(record)

    if symbol_records:
        return symbol_records

    if any(
        key in source
        for key in (
            "symbol",
            "ticker",
            "code",
            "decision",
            "regime",
            "risk_status",
            "accuracy",
        )
    ):
        return [source]

    return []


def _symbol_count(
    payload: Any,
) -> int:
    symbols = set()

    for record in _records_from_payload(
        payload
    ):
        for key in (
            "symbol",
            "ticker",
            "code",
            "security",
            "instrument",
        ):
            symbol = _normalize_symbol(
                record.get(key)
            )

            if symbol:
                symbols.add(symbol)
                break

    return len(symbols)


def _value_type_name(
    value: Any,
) -> str:
    if _is_mapping(value):
        return "mapping"

    if _is_sequence(value):
        return "sequence"

    return type(value).__name__


def _walk_payload(
    payload: Any,
    *,
    path: str = "$",
    depth: int = 0,
    max_depth: int = 8,
    visited: Optional[set[int]] = None,
) -> Iterable[Tuple[str, Any]]:
    if visited is None:
        visited = set()

    if depth > max_depth:
        return

    if _is_mapping(payload) or _is_sequence(
        payload
    ):
        object_id = id(payload)

        if object_id in visited:
            return

        visited.add(object_id)

    yield path, payload

    if depth == max_depth:
        return

    if _is_mapping(payload):
        for key, value in payload.items():
            child_path = (
                f"{path}.{key}"
            )

            yield from _walk_payload(
                value,
                path=child_path,
                depth=depth + 1,
                max_depth=max_depth,
                visited=visited,
            )

    elif _is_sequence(payload):
        limit = min(
            len(payload),
            8,
        )

        for index in range(limit):
            child_path = (
                f"{path}[{index}]"
            )

            yield from _walk_payload(
                payload[index],
                path=child_path,
                depth=depth + 1,
                max_depth=max_depth,
                visited=visited,
            )


def _path_tokens(
    path: str,
) -> List[str]:
    normalized = (
        path.replace(
            "$.",
            "",
        )
        .replace(
            "[",
            ".",
        )
        .replace(
            "]",
            "",
        )
    )

    return [
        _normalize_token(part)
        for part in normalized.split(".")
        if _normalize_token(part)
    ]


def _payload_field_tokens(
    payload: Any,
) -> set[str]:
    tokens: set[str] = set()

    if _is_mapping(payload):
        for key in payload.keys():
            tokens.add(
                _normalize_token(key)
            )

        records = _records_from_payload(
            payload
        )

        for record in records[:5]:
            for key in record.keys():
                tokens.add(
                    _normalize_token(key)
                )

    elif _is_sequence(payload):
        for item in payload[:5]:
            if not _is_mapping(item):
                continue

            for key in item.keys():
                tokens.add(
                    _normalize_token(key)
                )

    return tokens


def _alias_match_score(
    engine: str,
    path_tokens: Sequence[str],
) -> Tuple[float, List[str]]:
    aliases = ENGINE_ALIASES[
        engine
    ]

    matches: List[str] = []
    score = 0.0

    joined_path = "_".join(
        path_tokens
    )

    for alias in aliases:
        normalized_alias = (
            _normalize_token(alias)
        )

        if normalized_alias in path_tokens:
            score += 45.0

            matches.append(alias)

        elif normalized_alias in joined_path:
            score += 28.0

            matches.append(alias)

    unique_matches = list(
        dict.fromkeys(matches)
    )

    return min(score, 65.0), unique_matches


def _field_match_score(
    engine: str,
    field_tokens: set[str],
) -> Tuple[float, List[str]]:
    hints = ENGINE_HINT_FIELDS[
        engine
    ]

    matches = [
        hint
        for hint in hints
        if _normalize_token(hint)
        in field_tokens
    ]

    score = min(
        len(matches) * 7.0,
        42.0,
    )

    return score, matches


def _shape_score(
    engine: str,
    payload: Any,
) -> float:
    records = _records_from_payload(
        payload
    )

    record_count = len(records)
    symbols = _symbol_count(
        payload
    )

    score = 0.0

    if _is_mapping(payload):
        score += 4.0

    if _is_sequence(payload):
        score += 5.0

    if record_count > 0:
        score += min(
            8.0,
            2.0
            + record_count * 0.25,
        )

    if symbols > 0:
        score += min(
            10.0,
            3.0
            + symbols * 0.35,
        )

    if engine in {
        "market_regime",
        "learning",
        "breadth",
    }:
        if _is_mapping(payload):
            score += 3.0

    if engine in {
        "prediction_center",
        "investment_committee",
        "risk_engine",
        "portfolio_optimizer",
        "screener",
        "institutional_flow",
    }:
        if symbols > 0:
            score += 4.0

    return min(
        score,
        20.0,
    )


def _candidate_score(
    engine: str,
    path: str,
    payload: Any,
) -> Optional[SchemaCandidate]:
    path_tokens = _path_tokens(
        path
    )

    field_tokens = _payload_field_tokens(
        payload
    )

    alias_score, alias_matches = (
        _alias_match_score(
            engine,
            path_tokens,
        )
    )

    field_score, field_matches = (
        _field_match_score(
            engine,
            field_tokens,
        )
    )

    shape_score = _shape_score(
        engine,
        payload,
    )

    score = (
        alias_score
        + field_score
        + shape_score
    )

    if path == "$":
        score -= 10.0

    if not (
        _is_mapping(payload)
        or _is_sequence(payload)
    ):
        score -= 20.0

    score = round(
        max(0.0, min(100.0, score)),
        2,
    )

    if score < 18.0:
        return None

    records = _records_from_payload(
        payload
    )

    sample_keys = sorted(
        list(field_tokens)
    )[:20]

    return SchemaCandidate(
        engine=engine,
        path=path,
        score=score,
        alias_matches=alias_matches,
        field_matches=field_matches,
        value_type=_value_type_name(
            payload
        ),
        record_count=len(records),
        symbol_count=_symbol_count(
            payload
        ),
        sample_keys=sample_keys,
        payload=payload,
    )


def discover_schema_candidates(
    context: Any,
    *,
    max_depth: int = 8,
    maximum_candidates_per_engine: int = 12,
) -> Dict[str, List[SchemaCandidate]]:
    candidates: Dict[
        str,
        List[SchemaCandidate],
    ] = {
        engine: []
        for engine in ENGINE_NAMES
    }

    for path, payload in _walk_payload(
        context,
        max_depth=max_depth,
    ):
        for engine in ENGINE_NAMES:
            candidate = _candidate_score(
                engine,
                path,
                payload,
            )

            if candidate is not None:
                candidates[
                    engine
                ].append(candidate)

    for engine in ENGINE_NAMES:
        ordered = sorted(
            candidates[engine],
            key=lambda item: (
                -item.score,
                -item.symbol_count,
                -item.record_count,
                len(item.path),
                item.path,
            ),
        )

        unique: List[
            SchemaCandidate
        ] = []

        seen_paths = set()

        for candidate in ordered:
            if candidate.path in seen_paths:
                continue

            seen_paths.add(
                candidate.path
            )

            unique.append(
                candidate
            )

            if (
                len(unique)
                >= maximum_candidates_per_engine
            ):
                break

        candidates[engine] = unique

    return candidates


def _select_candidate(
    engine: str,
    candidates: Sequence[
        SchemaCandidate
    ],
    *,
    minimum_score: float,
) -> Optional[SchemaCandidate]:
    if not candidates:
        return None

    best = candidates[0]

    if best.score < minimum_score:
        return None

    return best


def _coverage_status(
    score: float,
    available: bool,
) -> str:
    if not available:
        return "MISSING"

    if score >= 70.0:
        return "STRONG"

    if score >= 50.0:
        return "GOOD"

    if score >= 35.0:
        return "WEAK"

    return "FALLBACK"


def build_adaptive_source_map(
    context: Any,
    *,
    minimum_score: float = 30.0,
    max_depth: int = 8,
) -> AdaptiveSourceMap:
    candidates = (
        discover_schema_candidates(
            context,
            max_depth=max_depth,
        )
    )

    sources: Dict[str, Any] = {}
    selected_paths: Dict[
        str,
        Optional[str],
    ] = {}

    selected_scores: Dict[
        str,
        float,
    ] = {}

    warnings: List[str] = []

    engine_coverage: Dict[
        str,
        Dict[str, Any],
    ] = {}

    for engine in ENGINE_NAMES:
        selected = _select_candidate(
            engine,
            candidates[engine],
            minimum_score=minimum_score,
        )

        if selected is None:
            sources[engine] = None
            selected_paths[
                engine
            ] = None

            selected_scores[
                engine
            ] = 0.0

            engine_coverage[
                engine
            ] = {
                "available": False,
                "status": "MISSING",
                "score": 0.0,
                "path": None,
                "record_count": 0,
                "symbol_count": 0,
            }

            warnings.append(
                f"{engine}: no sufficiently strong source candidate found"
            )

            continue

        sources[engine] = (
            selected.payload
        )

        selected_paths[
            engine
        ] = selected.path

        selected_scores[
            engine
        ] = selected.score

        status = _coverage_status(
            selected.score,
            True,
        )

        engine_coverage[
            engine
        ] = {
            "available": True,
            "status": status,
            "score": selected.score,
            "path": selected.path,
            "record_count":
                selected.record_count,
            "symbol_count":
                selected.symbol_count,
            "alias_matches": list(
                selected.alias_matches
            ),
            "field_matches": list(
                selected.field_matches
            ),
        }

        if selected.score < 45.0:
            warnings.append(
                f"{engine}: weak candidate selected at {selected.path} "
                f"with score {selected.score}"
            )

    available_count = sum(
        1
        for engine in ENGINE_NAMES
        if sources.get(engine)
        is not None
    )

    strong_count = sum(
        1
        for engine in ENGINE_NAMES
        if engine_coverage[
            engine
        ]["status"] == "STRONG"
    )

    coverage_pct = round(
        100.0
        * available_count
        / len(ENGINE_NAMES),
        2,
    )

    weighted_score = round(
        sum(
            selected_scores.values()
        )
        / len(ENGINE_NAMES),
        2,
    )

    required_engines = (
        "prediction_center",
        "investment_committee",
    )

    required_ready = all(
        sources.get(engine)
        is not None
        for engine in required_engines
    )

    coverage = {
        "engine_count":
            len(ENGINE_NAMES),
        "available_count":
            available_count,
        "missing_count":
            len(ENGINE_NAMES)
            - available_count,
        "strong_count":
            strong_count,
        "coverage_pct":
            coverage_pct,
        "average_discovery_score":
            weighted_score,
        "required_engines_ready":
            required_ready,
        "ready_for_ai_cio":
            required_ready
            and available_count >= 4,
        "engines":
            engine_coverage,
    }

    return AdaptiveSourceMap(
        sources=sources,
        selected_paths=selected_paths,
        selected_scores=selected_scores,
        coverage=coverage,
        candidates=candidates,
        warnings=warnings,
        metadata={
            "phase":
                "12.3-part-a",
            "mode":
                "adaptive-schema-discovery",
            "read_only":
                True,
            "repository_writes":
                False,
            "minimum_score":
                minimum_score,
            "max_depth":
                max_depth,
        },
    )


def merge_adaptive_with_static_sources(
    adaptive_map: AdaptiveSourceMap,
    static_sources: Optional[
        MappingType
    ] = None,
) -> Dict[str, Any]:
    """
    Merge adaptive sources with the existing Part 3 static extraction.

    Adaptive discovery wins when it has a source. Static extraction remains
    available as a fallback.
    """

    static = dict(
        static_sources or {}
    )

    merged: Dict[
        str,
        Any,
    ] = {}

    for engine in ENGINE_NAMES:
        adaptive_value = (
            adaptive_map.sources.get(
                engine
            )
        )

        static_value = static.get(
            engine
        )

        merged[engine] = (
            adaptive_value
            if adaptive_value is not None
            else static_value
        )

    merged["metadata"] = {
        **dict(
            static.get(
                "metadata",
                {},
            )
            if isinstance(
                static.get("metadata"),
                Mapping,
            )
            else {}
        ),
        "adaptive_mapper":
            adaptive_map.to_dict(
                include_payloads=False,
                include_candidates=False,
            ),
        "adaptive_mapper_enabled":
            True,
        "phase":
            "12.3-part-a",
    }

    return merged


def get_source_coverage_report(
    context: Any,
    *,
    minimum_score: float = 30.0,
    max_depth: int = 8,
) -> Dict[str, Any]:
    adaptive_map = (
        build_adaptive_source_map(
            context,
            minimum_score=minimum_score,
            max_depth=max_depth,
        )
    )

    return adaptive_map.to_dict(
        include_payloads=False,
        include_candidates=True,
    )


__all__ = [
    "AdaptiveSourceMap",
    "ENGINE_ALIASES",
    "ENGINE_HINT_FIELDS",
    "ENGINE_NAMES",
    "SchemaCandidate",
    "build_adaptive_source_map",
    "discover_schema_candidates",
    "get_source_coverage_report",
    "merge_adaptive_with_static_sources",
]
