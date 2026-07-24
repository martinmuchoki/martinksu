"""
NSE Signal Bot Enterprise
AI Decision Engine — Version 11.7

Creates one authoritative Decision Object for the dashboard.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


BUY_SIGNALS = {"BUY", "STRONG BUY", "STRONG_BUY"}
HIGH_RISK_VALUES = {"HIGH", "VERY HIGH", "CRITICAL"}
BEARISH_STATES = {"BEARISH", "STRONGLY BEARISH", "RISK-OFF", "RISK OFF"}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _normalise_text(value: Any, default: str = "") -> str:
    text = str(value or default).strip()
    return text.upper()


def _first_value(data: Dict[str, Any], keys: Iterable[str], default: Any = None) -> Any:
    for key in keys:
        value = data.get(key)
        if value is not None and value != "":
            return value
    return default


def _normalise_signal(signal: Dict[str, Any]) -> Dict[str, Any]:
    symbol = _first_value(signal, ("symbol", "ticker", "code"), "UNKNOWN")

    signal_name = _first_value(
        signal,
        ("final_signal", "signal", "recommendation", "action"),
        "HOLD",
    )

    confidence = _safe_float(
        _first_value(
            signal,
            ("confidence", "confidence_score", "signal_confidence"),
            0,
        )
    )

    committee_score = _safe_float(
        _first_value(
            signal,
            ("committee_score", "score", "ai_score", "final_score"),
            0,
        )
    )

    risk = _normalise_text(
        _first_value(
            signal,
            ("risk", "risk_level", "institutional_risk"),
            "UNKNOWN",
        )
    )

    volume_confirmed = bool(
        _first_value(
            signal,
            (
                "volume_confirmed",
                "volume_confirmation",
                "volume_breakout",
                "volume_support",
            ),
            False,
        )
    )

    institutional_support = bool(
        _first_value(
            signal,
            (
                "institutional_support",
                "institutional_confirmed",
                "institutional_accumulation",
            ),
            False,
        )
    )

    return {
        "symbol": str(symbol).strip().upper(),
        "signal": _normalise_text(signal_name, "HOLD").replace("_", " "),
        "confidence": round(confidence, 2),
        "committee_score": round(committee_score, 2),
        "risk": risk,
        "volume_confirmed": volume_confirmed,
        "institutional_support": institutional_support,
        "raw": signal,
    }


def _extract_market_state(
    market: Optional[Dict[str, Any]],
    regime: Optional[Dict[str, Any]],
) -> str:
    market = market or {}
    regime = regime or {}

    value = _first_value(
        regime,
        ("regime", "market_regime", "state", "label"),
        None,
    )

    if value is None:
        value = _first_value(
            market,
            ("market_state", "status", "regime", "sentiment"),
            "Neutral / Selective",
        )

    return str(value).strip() or "Neutral / Selective"


def _extract_market_risk(
    risk_metrics: Optional[Dict[str, Any]],
    market: Optional[Dict[str, Any]],
) -> str:
    risk_metrics = risk_metrics or {}
    market = market or {}

    value = _first_value(
        risk_metrics,
        ("risk_level", "market_risk", "level", "classification"),
        None,
    )

    if value is None:
        value = _first_value(
            market,
            ("risk", "risk_level", "market_risk"),
            "UNKNOWN",
        )

    return _normalise_text(value, "UNKNOWN")


def _extract_ai_confidence(
    market: Optional[Dict[str, Any]],
    regime: Optional[Dict[str, Any]],
) -> float:
    market = market or {}
    regime = regime or {}

    value = _first_value(
        market,
        ("ai_confidence", "confidence", "market_confidence"),
        None,
    )

    if value is None:
        value = _first_value(
            regime,
            ("confidence", "regime_confidence"),
            0,
        )

    return round(_safe_float(value), 2)


def _normalise_breadth(breadth: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    breadth = breadth or {}

    advancers = _safe_int(
        _first_value(breadth, ("advancers", "gainers", "advancing"), 0)
    )
    decliners = _safe_int(
        _first_value(breadth, ("decliners", "losers", "declining"), 0)
    )
    unchanged = _safe_int(
        _first_value(breadth, ("unchanged", "flat", "neutral"), 0)
    )

    total = advancers + decliners + unchanged

    if total == 0:
        condition = "Unavailable"
    elif advancers > decliners * 1.25:
        condition = "Bullish"
    elif decliners > advancers * 1.25:
        condition = "Bearish"
    else:
        condition = "Mixed"

    return {
        "advancers": advancers,
        "decliners": decliners,
        "unchanged": unchanged,
        "total": total,
        "condition": condition,
    }


def _normalise_institutional(
    institutional: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    institutional = institutional or {}

    phase = _first_value(
        institutional,
        ("phase", "institutional_phase", "rotation_phase", "status"),
        "Neutral",
    )

    strength = _safe_float(
        _first_value(
            institutional,
            ("strength", "rotation_strength", "score"),
            0,
        )
    )

    return {
        "phase": str(phase).strip() or "Neutral",
        "strength": round(strength, 2),
    }


def _is_qualified_opportunity(
    signal: Dict[str, Any],
    minimum_confidence: float,
    minimum_committee_score: float,
    require_volume_confirmation: bool,
    require_institutional_support: bool,
) -> bool:
    if signal["signal"] not in BUY_SIGNALS:
        return False

    if signal["confidence"] < minimum_confidence:
        return False

    if signal["committee_score"] < minimum_committee_score:
        return False

    if signal["risk"] in HIGH_RISK_VALUES:
        return False

    if require_volume_confirmation and not signal["volume_confirmed"]:
        return False

    if require_institutional_support and not signal["institutional_support"]:
        return False

    return True


def build_decision_object(
    *,
    signals: Optional[List[Dict[str, Any]]] = None,
    market: Optional[Dict[str, Any]] = None,
    regime: Optional[Dict[str, Any]] = None,
    risk_metrics: Optional[Dict[str, Any]] = None,
    breadth: Optional[Dict[str, Any]] = None,
    institutional: Optional[Dict[str, Any]] = None,
    minimum_confidence: float = 80.0,
    minimum_committee_score: float = 75.0,
    require_volume_confirmation: bool = False,
    require_institutional_support: bool = False,
) -> Dict[str, Any]:
    """
    Build the single authoritative AI Decision Object.

    Volume and institutional confirmation are initially optional because
    older persisted signal records may not yet contain those fields.
    """

    normalised_signals = [
        _normalise_signal(item)
        for item in (signals or [])
        if isinstance(item, dict)
    ]

    normalised_signals.sort(
        key=lambda item: (
            item["committee_score"],
            item["confidence"],
        ),
        reverse=True,
    )

    market_state = _extract_market_state(market, regime)
    market_risk = _extract_market_risk(risk_metrics, market)
    ai_confidence = _extract_ai_confidence(market, regime)
    breadth_data = _normalise_breadth(breadth)
    institutional_data = _normalise_institutional(institutional)

    qualified = [
        signal
        for signal in normalised_signals
        if _is_qualified_opportunity(
            signal=signal,
            minimum_confidence=minimum_confidence,
            minimum_committee_score=minimum_committee_score,
            require_volume_confirmation=require_volume_confirmation,
            require_institutional_support=require_institutional_support,
        )
    ]

    leading_signal = normalised_signals[0] if normalised_signals else None

    risk_is_high = market_risk in HIGH_RISK_VALUES
    state_is_bearish = _normalise_text(market_state) in BEARISH_STATES

    reasons: List[str] = []

    if risk_is_high:
        decision = "WAIT"
        reasons.append(f"Market risk remains {market_risk}.")
    elif qualified:
        decision = "BUY"
        reasons.append(
            f"{len(qualified)} qualified BUY "
            f"{'opportunity' if len(qualified) == 1 else 'opportunities'} identified."
        )
    elif state_is_bearish:
        decision = "REDUCE"
        reasons.append("The market regime is bearish.")
    else:
        decision = "WAIT"
        reasons.append("No signal currently satisfies the qualified BUY criteria.")

    if not qualified and not any("qualified BUY" in reason for reason in reasons):
        reasons.append("No signal currently satisfies the qualified BUY criteria.")

    if breadth_data["condition"] == "Bearish":
        reasons.append("Market breadth is bearish.")
    elif breadth_data["condition"] == "Bullish":
        reasons.append("Market breadth is supportive.")

    institutional_phase = _normalise_text(institutional_data["phase"])

    if institutional_phase in {"NEUTRAL", "BALANCED", "MIXED"}:
        reasons.append("Institutional positioning is neutral.")
    elif institutional_phase in {"ACCUMULATION", "BULLISH", "BUYING"}:
        reasons.append("Institutional accumulation is supportive.")
    elif institutional_phase in {"DISTRIBUTION", "BEARISH", "SELLING"}:
        reasons.append("Institutional distribution is present.")

    if decision == "BUY" and qualified:
        headline = (
            f"Qualified BUY opportunity identified: {qualified[0]['symbol']}."
        )
    elif decision == "REDUCE":
        headline = "Reduce exposure and prioritise capital preservation."
    else:
        headline = "Wait for stronger confirmation before taking new positions."

    public_qualified = [
        {key: value for key, value in signal.items() if key != "raw"}
        for signal in qualified
    ]

    public_leading = None
    if leading_signal:
        public_leading = {
            key: value
            for key, value in leading_signal.items()
            if key != "raw"
        }

    return {
        "market_state": market_state,
        "market_risk": market_risk,
        "decision": decision,
        "decision_label": decision,
        "decision_headline": headline,
        "decision_reason": reasons,
        "confidence": ai_confidence,
        "qualified_opportunities": public_qualified,
        "qualified_count": len(public_qualified),
        "leading_signal": public_leading,
        "breadth": breadth_data,
        "institutional": institutional_data,
        "thresholds": {
            "minimum_confidence": minimum_confidence,
            "minimum_committee_score": minimum_committee_score,
            "require_volume_confirmation": require_volume_confirmation,
            "require_institutional_support": require_institutional_support,
        },
    }


# Backward-friendly alias.
get_ai_decision = build_decision_object
