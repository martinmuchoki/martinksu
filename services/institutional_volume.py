from typing import Dict


def _clamp(value: float, minimum: float = 0, maximum: float = 100):
    return max(minimum, min(maximum, value))


def classify_stock(stock: Dict) -> Dict:
    """
    Build an institutional trading profile for one stock.
    """

    ai_score = float(stock.get("score", 50))

    rvol = float(stock.get("relative_volume", 1))

    change = float(stock.get("change_pct", 0))

    trend = stock.get("trend", "Neutral")

    momentum = "Normal"

    if change >= 5:
        momentum = "Very Strong"
    elif change >= 2:
        momentum = "Strong"
    elif change <= -2:
        momentum = "Weak"

    confidence = (
        ai_score * 0.35 +
        min(rvol * 10, 100) * 0.25 +
        (100 if trend == "Bullish" else 50) * 0.15 +
        (90 if momentum == "Very Strong"
            else 75 if momentum == "Strong"
            else 40 if momentum == "Weak"
            else 60) * 0.10 +
        (50 + change * 10) * 0.15
    )

    confidence = round(_clamp(confidence))

    if confidence >= 90:
        badge = "🔥"
        signal = "Institutional Breakout"

    elif confidence >= 80:
        badge = "🟢"
        signal = "Institutional Buying"

    elif confidence >= 70:
        badge = "🟢"
        signal = "Strong Accumulation"

    elif confidence >= 60:
        badge = "🟡"
        signal = "Accumulation"

    elif confidence >= 40:
        badge = "⚪"
        signal = "Normal Trading"

    else:
        badge = "🔴"
        signal = "Weak Participation"

    result = dict(stock)

    result.update({
        "confidence": confidence,
        "badge": badge,
        "signal": signal,
        "momentum": momentum,
    })

    return result
