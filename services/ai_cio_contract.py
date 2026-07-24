"""
PHASE 12.1 AI CIO DECISION CONTRACT

Defines the authoritative data contract used by the AI Chief Investment
Officer layer.

This module does not calculate technical indicators, predictions, consensus,
risk, market regime, or portfolio allocation. It only validates and normalizes
outputs produced by existing specialist engines.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from typing import Any, Dict, Iterable, List, Mapping, Optional


CONTRACT_VERSION = "12.1"
CONTRACT_NAME = "mip_ai_cio_decision"


class DecisionContractError(ValueError):
    """Raised when an AI CIO decision violates the contract."""


class Decision(str, Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    SELL = "SELL"
    AVOID = "AVOID"


class Conviction(str, Enum):
    VERY_HIGH = "VERY_HIGH"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    VERY_LOW = "VERY_LOW"


class MarketRegime(str, Enum):
    STRONG_BULLISH = "STRONG_BULLISH"
    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    CAUTIOUS = "CAUTIOUS"
    BEARISH = "BEARISH"
    STRONG_BEARISH = "STRONG_BEARISH"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    NORMAL_VOLATILITY = "NORMAL_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    UNKNOWN = "UNKNOWN"


class RiskStatus(str, Enum):
    APPROVED = "APPROVED"
    APPROVED_WITH_CAUTION = "APPROVED_WITH_CAUTION"
    VETOED = "VETOED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_float(
    value: Any,
    default: float = 0.0,
    *,
    field_name: str = "value",
) -> float:
    if value is None or value == "":
        return float(default)

    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise DecisionContractError(
            f"{field_name} must be numeric; received {value!r}"
        ) from exc

    if not isfinite(result):
        raise DecisionContractError(
            f"{field_name} must be finite; received {value!r}"
        )

    return result


def _clamp(
    value: Any,
    minimum: float,
    maximum: float,
    *,
    field_name: str,
) -> float:
    numeric = _safe_float(
        value,
        field_name=field_name,
    )
    return max(minimum, min(maximum, numeric))


def _normalize_symbol(value: Any) -> str:
    symbol = str(value or "").strip().upper()

    if not symbol:
        raise DecisionContractError("symbol is required")

    if len(symbol) > 24:
        raise DecisionContractError(
            "symbol cannot exceed 24 characters"
        )

    allowed = set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    )

    if any(character not in allowed for character in symbol):
        raise DecisionContractError(
            f"symbol contains unsupported characters: {symbol!r}"
        )

    return symbol


def _normalize_text(
    value: Any,
    *,
    field_name: str,
    maximum_length: int = 500,
    allow_empty: bool = False,
) -> str:
    text = str(value or "").strip()

    if not text and not allow_empty:
        raise DecisionContractError(
            f"{field_name} cannot be empty"
        )

    if len(text) > maximum_length:
        raise DecisionContractError(
            f"{field_name} cannot exceed "
            f"{maximum_length} characters"
        )

    return text


def _normalize_string_list(
    values: Optional[Iterable[Any]],
    *,
    field_name: str,
    maximum_items: int = 20,
    maximum_item_length: int = 500,
) -> List[str]:
    if values is None:
        return []

    if isinstance(values, (str, bytes)):
        values = [values]

    normalized: List[str] = []

    for raw_value in values:
        text = str(raw_value or "").strip()

        if not text:
            continue

        if len(text) > maximum_item_length:
            raise DecisionContractError(
                f"{field_name} item cannot exceed "
                f"{maximum_item_length} characters"
            )

        if text not in normalized:
            normalized.append(text)

        if len(normalized) > maximum_items:
            raise DecisionContractError(
                f"{field_name} cannot exceed "
                f"{maximum_items} items"
            )

    return normalized


def _enum_value(
    enum_type: type[Enum],
    value: Any,
    *,
    field_name: str,
    aliases: Optional[Mapping[str, str]] = None,
) -> str:
    raw = str(value or "").strip().upper()
    raw = raw.replace(" ", "_").replace("-", "_")

    if aliases:
        raw = aliases.get(raw, raw)

    allowed = {
        member.value
        for member in enum_type
    }

    if raw not in allowed:
        raise DecisionContractError(
            f"{field_name} must be one of "
            f"{sorted(allowed)}; received {value!r}"
        )

    return raw


def _normalize_timestamp(value: Any) -> str:
    if value in (None, ""):
        return utc_now_iso()

    raw = str(value).strip()

    try:
        parsed = datetime.fromisoformat(
            raw.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise DecisionContractError(
            "generated_at must be an ISO-8601 timestamp"
        ) from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc).replace(
        microsecond=0
    ).isoformat()


def _normalize_mapping(
    value: Optional[Mapping[str, Any]],
    *,
    field_name: str,
) -> Dict[str, Any]:
    if value is None:
        return {}

    if not isinstance(value, Mapping):
        raise DecisionContractError(
            f"{field_name} must be a mapping"
        )

    return dict(value)


@dataclass(frozen=True)
class ScoreBreakdown:
    technical: float = 0.0
    volume: float = 0.0
    institutional: float = 0.0
    prediction: float = 0.0
    committee: float = 0.0
    consensus: float = 0.0
    risk: float = 0.0
    learning: float = 0.0
    market_regime: float = 0.0
    portfolio_fit: float = 0.0

    def __post_init__(self) -> None:
        fields = (
            "technical",
            "volume",
            "institutional",
            "prediction",
            "committee",
            "consensus",
            "risk",
            "learning",
            "market_regime",
            "portfolio_fit",
        )

        for field_name in fields:
            object.__setattr__(
                self,
                field_name,
                round(
                    _clamp(
                        getattr(self, field_name),
                        0.0,
                        100.0,
                        field_name=field_name,
                    ),
                    2,
                ),
            )

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class PricePlan:
    entry_price: float = 0.0
    target_price: float = 0.0
    stop_loss: float = 0.0
    risk_reward_ratio: float = 0.0
    expected_return_pct: float = 0.0
    downside_risk_pct: float = 0.0
    horizon: str = "UNSPECIFIED"

    def __post_init__(self) -> None:
        for field_name in (
            "entry_price",
            "target_price",
            "stop_loss",
            "risk_reward_ratio",
        ):
            value = _safe_float(
                getattr(self, field_name),
                field_name=field_name,
            )

            if value < 0:
                raise DecisionContractError(
                    f"{field_name} cannot be negative"
                )

            object.__setattr__(
                self,
                field_name,
                round(value, 4),
            )

        object.__setattr__(
            self,
            "expected_return_pct",
            round(
                _clamp(
                    self.expected_return_pct,
                    -100.0,
                    1000.0,
                    field_name="expected_return_pct",
                ),
                2,
            ),
        )

        object.__setattr__(
            self,
            "downside_risk_pct",
            round(
                _clamp(
                    self.downside_risk_pct,
                    0.0,
                    100.0,
                    field_name="downside_risk_pct",
                ),
                2,
            ),
        )

        object.__setattr__(
            self,
            "horizon",
            _normalize_text(
                self.horizon,
                field_name="horizon",
                maximum_length=80,
            ).upper(),
        )

        self._validate_price_relationships()

    def _validate_price_relationships(self) -> None:
        entry = self.entry_price
        target = self.target_price
        stop = self.stop_loss

        if entry <= 0:
            return

        if target > 0 and stop > 0:
            upside = target - entry
            downside = entry - stop

            if upside > 0 and downside > 0:
                calculated_ratio = upside / downside

                if self.risk_reward_ratio <= 0:
                    object.__setattr__(
                        self,
                        "risk_reward_ratio",
                        round(calculated_ratio, 4),
                    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CapitalAllocation:
    position_size_pct: float = 0.0
    maximum_capital: float = 0.0
    recommended_units: int = 0
    existing_exposure_pct: float = 0.0
    post_trade_exposure_pct: float = 0.0

    def __post_init__(self) -> None:
        for field_name in (
            "position_size_pct",
            "existing_exposure_pct",
            "post_trade_exposure_pct",
        ):
            object.__setattr__(
                self,
                field_name,
                round(
                    _clamp(
                        getattr(self, field_name),
                        0.0,
                        100.0,
                        field_name=field_name,
                    ),
                    2,
                ),
            )

        maximum_capital = _safe_float(
            self.maximum_capital,
            field_name="maximum_capital",
        )

        if maximum_capital < 0:
            raise DecisionContractError(
                "maximum_capital cannot be negative"
            )

        object.__setattr__(
            self,
            "maximum_capital",
            round(maximum_capital, 2),
        )

        try:
            recommended_units = int(
                self.recommended_units or 0
            )
        except (TypeError, ValueError) as exc:
            raise DecisionContractError(
                "recommended_units must be an integer"
            ) from exc

        if recommended_units < 0:
            raise DecisionContractError(
                "recommended_units cannot be negative"
            )

        object.__setattr__(
            self,
            "recommended_units",
            recommended_units,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AICIODecision:
    symbol: str
    decision: str
    decision_score: float
    confidence: float
    conviction: str
    market_regime: str

    risk_status: str = RiskStatus.INSUFFICIENT_DATA.value
    risk_veto: bool = False

    committee_consensus: float = 0.0
    committee_agreement: float = 0.0
    committee_disagreement: float = 0.0

    scores: ScoreBreakdown = field(
        default_factory=ScoreBreakdown
    )
    price_plan: PricePlan = field(
        default_factory=PricePlan
    )
    allocation: CapitalAllocation = field(
        default_factory=CapitalAllocation
    )

    why_now: List[str] = field(default_factory=list)
    key_risks: List[str] = field(default_factory=list)
    invalidation_conditions: List[str] = field(
        default_factory=list
    )
    ranking_reasons: List[str] = field(
        default_factory=list
    )

    supporting_engines: Dict[str, Any] = field(
        default_factory=dict
    )
    source_metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    generated_at: str = field(
        default_factory=utc_now_iso
    )
    contract_name: str = CONTRACT_NAME
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "symbol",
            _normalize_symbol(self.symbol),
        )

        object.__setattr__(
            self,
            "decision",
            _enum_value(
                Decision,
                self.decision,
                field_name="decision",
                aliases={
                    "STRONGBUY": "STRONG_BUY",
                    "STRONG_SELL": "SELL",
                    "NEUTRAL": "HOLD",
                    "WAIT": "HOLD",
                },
            ),
        )

        object.__setattr__(
            self,
            "decision_score",
            round(
                _clamp(
                    self.decision_score,
                    0.0,
                    100.0,
                    field_name="decision_score",
                ),
                2,
            ),
        )

        confidence = _safe_float(
            self.confidence,
            field_name="confidence",
        )

        if 0.0 <= confidence <= 1.0:
            confidence *= 100.0

        object.__setattr__(
            self,
            "confidence",
            round(
                _clamp(
                    confidence,
                    0.0,
                    100.0,
                    field_name="confidence",
                ),
                2,
            ),
        )

        object.__setattr__(
            self,
            "conviction",
            _enum_value(
                Conviction,
                self.conviction,
                field_name="conviction",
                aliases={
                    "VERYHIGH": "VERY_HIGH",
                    "VERYLOW": "VERY_LOW",
                    "MODERATE": "MEDIUM",
                },
            ),
        )

        object.__setattr__(
            self,
            "market_regime",
            _enum_value(
                MarketRegime,
                self.market_regime,
                field_name="market_regime",
                aliases={
                    "STRONGBULLISH": "STRONG_BULLISH",
                    "STRONGBEARISH": "STRONG_BEARISH",
                    "SIDEWAYS": "NEUTRAL",
                    "RANGE_BOUND": "NEUTRAL",
                },
            ),
        )

        object.__setattr__(
            self,
            "risk_status",
            _enum_value(
                RiskStatus,
                self.risk_status,
                field_name="risk_status",
                aliases={
                    "PASS": "APPROVED",
                    "CAUTION": "APPROVED_WITH_CAUTION",
                    "BLOCKED": "VETOED",
                    "FAIL": "VETOED",
                    "UNKNOWN": "INSUFFICIENT_DATA",
                },
            ),
        )

        object.__setattr__(
            self,
            "risk_veto",
            bool(self.risk_veto),
        )

        for field_name in (
            "committee_consensus",
            "committee_agreement",
            "committee_disagreement",
        ):
            value = _safe_float(
                getattr(self, field_name),
                field_name=field_name,
            )

            if 0.0 <= value <= 1.0:
                value *= 100.0

            object.__setattr__(
                self,
                field_name,
                round(
                    _clamp(
                        value,
                        0.0,
                        100.0,
                        field_name=field_name,
                    ),
                    2,
                ),
            )

        object.__setattr__(
            self,
            "why_now",
            _normalize_string_list(
                self.why_now,
                field_name="why_now",
            ),
        )

        object.__setattr__(
            self,
            "key_risks",
            _normalize_string_list(
                self.key_risks,
                field_name="key_risks",
            ),
        )

        object.__setattr__(
            self,
            "invalidation_conditions",
            _normalize_string_list(
                self.invalidation_conditions,
                field_name="invalidation_conditions",
            ),
        )

        object.__setattr__(
            self,
            "ranking_reasons",
            _normalize_string_list(
                self.ranking_reasons,
                field_name="ranking_reasons",
            ),
        )

        object.__setattr__(
            self,
            "supporting_engines",
            _normalize_mapping(
                self.supporting_engines,
                field_name="supporting_engines",
            ),
        )

        object.__setattr__(
            self,
            "source_metadata",
            _normalize_mapping(
                self.source_metadata,
                field_name="source_metadata",
            ),
        )

        object.__setattr__(
            self,
            "generated_at",
            _normalize_timestamp(
                self.generated_at
            ),
        )

        object.__setattr__(
            self,
            "contract_name",
            CONTRACT_NAME,
        )

        object.__setattr__(
            self,
            "contract_version",
            CONTRACT_VERSION,
        )

        self._validate_cross_field_rules()

    def _validate_cross_field_rules(self) -> None:
        if self.risk_veto:
            object.__setattr__(
                self,
                "risk_status",
                RiskStatus.VETOED.value,
            )

            if self.decision in {
                Decision.STRONG_BUY.value,
                Decision.BUY.value,
            }:
                object.__setattr__(
                    self,
                    "decision",
                    Decision.AVOID.value,
                )

        if (
            self.risk_status == RiskStatus.VETOED.value
            and self.decision in {
                Decision.STRONG_BUY.value,
                Decision.BUY.value,
            }
        ):
            raise DecisionContractError(
                "BUY decisions cannot have VETOED risk status"
            )

        if (
            self.allocation.post_trade_exposure_pct
            < self.allocation.existing_exposure_pct
            and self.decision in {
                Decision.STRONG_BUY.value,
                Decision.BUY.value,
            }
        ):
            raise DecisionContractError(
                "BUY decisions cannot reduce post-trade exposure"
            )

    @property
    def is_actionable(self) -> bool:
        return (
            not self.risk_veto
            and self.risk_status
            in {
                RiskStatus.APPROVED.value,
                RiskStatus.APPROVED_WITH_CAUTION.value,
            }
            and self.decision
            in {
                Decision.STRONG_BUY.value,
                Decision.BUY.value,
                Decision.REDUCE.value,
                Decision.SELL.value,
            }
        )

    def to_dict(
        self,
        *,
        include_supporting_engines: bool = True,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "contract": {
                "name": self.contract_name,
                "version": self.contract_version,
            },
            "symbol": self.symbol,
            "decision": self.decision,
            "decision_score": self.decision_score,
            "confidence": self.confidence,
            "conviction": self.conviction,
            "market_regime": self.market_regime,
            "risk_status": self.risk_status,
            "risk_veto": self.risk_veto,
            "is_actionable": self.is_actionable,
            "committee": {
                "consensus": self.committee_consensus,
                "agreement": self.committee_agreement,
                "disagreement": self.committee_disagreement,
            },
            "scores": self.scores.to_dict(),
            "price_plan": self.price_plan.to_dict(),
            "allocation": self.allocation.to_dict(),
            "why_now": list(self.why_now),
            "key_risks": list(self.key_risks),
            "invalidation_conditions": list(
                self.invalidation_conditions
            ),
            "ranking_reasons": list(
                self.ranking_reasons
            ),
            "source_metadata": dict(
                self.source_metadata
            ),
            "generated_at": self.generated_at,
        }

        if include_supporting_engines:
            payload["supporting_engines"] = dict(
                self.supporting_engines
            )

        return payload


def build_ai_cio_decision(
    payload: Mapping[str, Any],
) -> AICIODecision:
    """
    Build and validate an AI CIO decision from an untrusted mapping.

    Existing engine outputs should be assembled into this payload by the
    future Phase 12.2 orchestration layer.
    """

    if not isinstance(payload, Mapping):
        raise DecisionContractError(
            "AI CIO decision payload must be a mapping"
        )

    scores_payload = payload.get("scores") or {}
    price_payload = payload.get("price_plan") or {}
    allocation_payload = payload.get("allocation") or {}

    if not isinstance(scores_payload, Mapping):
        raise DecisionContractError(
            "scores must be a mapping"
        )

    if not isinstance(price_payload, Mapping):
        raise DecisionContractError(
            "price_plan must be a mapping"
        )

    if not isinstance(allocation_payload, Mapping):
        raise DecisionContractError(
            "allocation must be a mapping"
        )

    return AICIODecision(
        symbol=payload.get("symbol"),
        decision=payload.get("decision"),
        decision_score=payload.get(
            "decision_score",
            0.0,
        ),
        confidence=payload.get(
            "confidence",
            0.0,
        ),
        conviction=payload.get(
            "conviction",
            Conviction.LOW.value,
        ),
        market_regime=payload.get(
            "market_regime",
            MarketRegime.UNKNOWN.value,
        ),
        risk_status=payload.get(
            "risk_status",
            RiskStatus.INSUFFICIENT_DATA.value,
        ),
        risk_veto=payload.get(
            "risk_veto",
            False,
        ),
        committee_consensus=payload.get(
            "committee_consensus",
            payload.get(
                "committee",
                {},
            ).get(
                "consensus",
                0.0,
            )
            if isinstance(
                payload.get("committee"),
                Mapping,
            )
            else 0.0,
        ),
        committee_agreement=payload.get(
            "committee_agreement",
            payload.get(
                "committee",
                {},
            ).get(
                "agreement",
                0.0,
            )
            if isinstance(
                payload.get("committee"),
                Mapping,
            )
            else 0.0,
        ),
        committee_disagreement=payload.get(
            "committee_disagreement",
            payload.get(
                "committee",
                {},
            ).get(
                "disagreement",
                0.0,
            )
            if isinstance(
                payload.get("committee"),
                Mapping,
            )
            else 0.0,
        ),
        scores=ScoreBreakdown(
            technical=scores_payload.get(
                "technical",
                payload.get(
                    "technical_score",
                    0.0,
                ),
            ),
            volume=scores_payload.get(
                "volume",
                payload.get(
                    "volume_score",
                    0.0,
                ),
            ),
            institutional=scores_payload.get(
                "institutional",
                payload.get(
                    "institutional_score",
                    0.0,
                ),
            ),
            prediction=scores_payload.get(
                "prediction",
                payload.get(
                    "prediction_score",
                    0.0,
                ),
            ),
            committee=scores_payload.get(
                "committee",
                payload.get(
                    "committee_score",
                    0.0,
                ),
            ),
            consensus=scores_payload.get(
                "consensus",
                payload.get(
                    "consensus_score",
                    0.0,
                ),
            ),
            risk=scores_payload.get(
                "risk",
                payload.get(
                    "risk_score",
                    0.0,
                ),
            ),
            learning=scores_payload.get(
                "learning",
                payload.get(
                    "learning_score",
                    0.0,
                ),
            ),
            market_regime=scores_payload.get(
                "market_regime",
                payload.get(
                    "market_regime_score",
                    0.0,
                ),
            ),
            portfolio_fit=scores_payload.get(
                "portfolio_fit",
                payload.get(
                    "portfolio_fit_score",
                    0.0,
                ),
            ),
        ),
        price_plan=PricePlan(
            entry_price=price_payload.get(
                "entry_price",
                payload.get(
                    "entry_price",
                    0.0,
                ),
            ),
            target_price=price_payload.get(
                "target_price",
                payload.get(
                    "target_price",
                    0.0,
                ),
            ),
            stop_loss=price_payload.get(
                "stop_loss",
                payload.get(
                    "stop_loss",
                    0.0,
                ),
            ),
            risk_reward_ratio=price_payload.get(
                "risk_reward_ratio",
                payload.get(
                    "risk_reward_ratio",
                    0.0,
                ),
            ),
            expected_return_pct=price_payload.get(
                "expected_return_pct",
                payload.get(
                    "expected_return_pct",
                    0.0,
                ),
            ),
            downside_risk_pct=price_payload.get(
                "downside_risk_pct",
                payload.get(
                    "downside_risk_pct",
                    0.0,
                ),
            ),
            horizon=price_payload.get(
                "horizon",
                payload.get(
                    "horizon",
                    "UNSPECIFIED",
                ),
            ),
        ),
        allocation=CapitalAllocation(
            position_size_pct=allocation_payload.get(
                "position_size_pct",
                payload.get(
                    "position_size_pct",
                    0.0,
                ),
            ),
            maximum_capital=allocation_payload.get(
                "maximum_capital",
                payload.get(
                    "maximum_capital",
                    0.0,
                ),
            ),
            recommended_units=allocation_payload.get(
                "recommended_units",
                payload.get(
                    "recommended_units",
                    0,
                ),
            ),
            existing_exposure_pct=allocation_payload.get(
                "existing_exposure_pct",
                payload.get(
                    "existing_exposure_pct",
                    0.0,
                ),
            ),
            post_trade_exposure_pct=allocation_payload.get(
                "post_trade_exposure_pct",
                payload.get(
                    "post_trade_exposure_pct",
                    0.0,
                ),
            ),
        ),
        why_now=payload.get(
            "why_now",
            [],
        ),
        key_risks=payload.get(
            "key_risks",
            [],
        ),
        invalidation_conditions=payload.get(
            "invalidation_conditions",
            [],
        ),
        ranking_reasons=payload.get(
            "ranking_reasons",
            [],
        ),
        supporting_engines=payload.get(
            "supporting_engines",
            {},
        ),
        source_metadata=payload.get(
            "source_metadata",
            {},
        ),
        generated_at=payload.get(
            "generated_at",
            utc_now_iso(),
        ),
    )


def validate_ai_cio_decision(
    payload: Mapping[str, Any],
) -> Dict[str, Any]:
    """
    Validate a payload and return its normalized dictionary form.
    """

    return build_ai_cio_decision(
        payload
    ).to_dict()
