from datetime import datetime

from services.indicator_engine import analyze_symbol


def clamp(value, minimum=0, maximum=100):
    return max(minimum, min(maximum, int(round(value))))


def score_to_decision(score):
    if score >= 80:
        return "STRONG BUY"
    if score >= 65:
        return "BUY"
    if score >= 45:
        return "HOLD"
    if score >= 30:
        return "WATCH"
    return "SELL"


def technical_analyst(analysis):
    score = analysis["score"]
    reasons = list(analysis.get("reasons", []))

    if analysis["rsi"] < 35:
        reasons.append("RSI suggests the stock may be oversold")
    elif analysis["rsi"] > 70:
        reasons.append("RSI indicates overbought conditions")

    if analysis["price"] > analysis["ema50"]:
        reasons.append("Price is trading above EMA50")
    else:
        reasons.append("Price is below EMA50")

    return {
        "name": "Technical Analyst",
        "role": "RSI, MACD, moving averages and trend",
        "decision": score_to_decision(score),
        "confidence": clamp(score),
        "score": clamp(score),
        "comment": "; ".join(reasons[:5]),
    }


def momentum_analyst(analysis):
    score = 50
    reasons = []

    if analysis["momentum10"] > 0:
        score += 20
        reasons.append("Positive 10-day momentum")
    else:
        score -= 15
        reasons.append("Negative 10-day momentum")

    if analysis["macd"] > analysis["macd_signal"]:
        score += 15
        reasons.append("MACD is above the signal line")
    else:
        score -= 10
        reasons.append("MACD is below the signal line")

    if analysis["volume_ratio"] >= 1.25:
        score += 10
        reasons.append("Above-average volume confirms the move")
    elif analysis["volume_ratio"] < 0.75:
        score -= 5
        reasons.append("Volume participation is weak")

    if analysis["trend"] == "Uptrend":
        score += 10
        reasons.append("Trend remains positive")

    score = clamp(score)

    return {
        "name": "Momentum Analyst",
        "role": "Momentum, breakout strength and volume",
        "decision": score_to_decision(score),
        "confidence": score,
        "score": score,
        "comment": "; ".join(reasons),
    }


def risk_manager(analysis, portfolio=None):
    score = 75
    reasons = []

    atr_pct = (
        (analysis["atr14"] / analysis["price"]) * 100
        if analysis["price"]
        else 0
    )

    if atr_pct > 6:
        score -= 25
        reasons.append("High price volatility")
    elif atr_pct > 3:
        score -= 10
        reasons.append("Moderate price volatility")
    else:
        reasons.append("Price volatility is controlled")

    if analysis["rsi"] > 75:
        score -= 10
        reasons.append("Overbought risk is elevated")

    portfolio_pnl = (portfolio or {}).get("pnl_pct", 0)

    if portfolio_pnl < -8:
        score -= 15
        reasons.append("Portfolio drawdown requires caution")
    else:
        reasons.append("Portfolio drawdown is within limits")

    score = clamp(score)

    if score >= 70:
        decision = "LOW RISK"
    elif score >= 45:
        decision = "MODERATE RISK"
    else:
        decision = "HIGH RISK"

    return {
        "name": "Risk Manager",
        "role": "Volatility, drawdown and capital protection",
        "decision": decision,
        "confidence": score,
        "score": score,
        "comment": "; ".join(reasons),
        "atr_percentage": round(atr_pct, 2),
    }


def portfolio_manager(analysis, portfolio=None):
    portfolio = portfolio or {}
    score = 60
    reasons = []

    holdings = portfolio.get("holdings", [])
    existing = next(
        (
            holding
            for holding in holdings
            if holding.get("symbol") == analysis["symbol"]
        ),
        None,
    )

    if existing:
        reasons.append("Stock already exists in the portfolio")

        if existing.get("pnl_pct", 0) > 10:
            score -= 5
            reasons.append("Existing position has a strong gain")
        elif existing.get("pnl_pct", 0) < -10:
            score -= 10
            reasons.append("Existing position has a material loss")
    else:
        score += 10
        reasons.append("Stock may improve diversification")

    if analysis["score"] >= 75:
        score += 15
        reasons.append("Technical score supports selective allocation")

    if analysis["trend"] != "Uptrend":
        score -= 10
        reasons.append("Weak trend limits position size")

    score = clamp(score)

    return {
        "name": "Portfolio Manager",
        "role": "Allocation, diversification and position sizing",
        "decision": score_to_decision(score),
        "confidence": score,
        "score": score,
        "comment": "; ".join(reasons),
        "suggested_position_pct": (
            10 if score >= 75 else
            5 if score >= 60 else
            0
        ),
    }


def market_strategist(analysis, market=None):
    market = market or {}
    average_change = float(market.get("average_change", 0))
    market_status = market.get("market_status", "Neutral")

    score = 55
    reasons = [f"Overall market status: {market_status}"]

    if average_change > 1:
        score += 20
        reasons.append("Broad market momentum is positive")
    elif average_change < -1:
        score -= 20
        reasons.append("Broad market momentum is negative")
    else:
        reasons.append("Market breadth is mixed")

    if analysis["price"] > analysis["sma200"]:
        score += 15
        reasons.append("Stock remains above its long-term trend")
    else:
        score -= 10
        reasons.append("Stock is below its long-term trend")

    score = clamp(score)

    return {
        "name": "Market Strategist",
        "role": "Market regime and long-term positioning",
        "decision": score_to_decision(score),
        "confidence": score,
        "score": score,
        "comment": "; ".join(reasons),
    }


def sentiment_analyst():
    return {
        "name": "News & Sentiment Analyst",
        "role": "Company news and investor sentiment",
        "decision": "HOLD",
        "confidence": 50,
        "score": 50,
        "comment": (
            "Neutral placeholder until a verified news and sentiment "
            "data source is connected."
        ),
    }


def chief_investment_officer(agents):
    weighted_scores = {
        "Technical Analyst": 0.25,
        "Momentum Analyst": 0.20,
        "Risk Manager": 0.20,
        "Portfolio Manager": 0.15,
        "Market Strategist": 0.15,
        "News & Sentiment Analyst": 0.05,
    }

    combined_score = sum(
        agent["score"] * weighted_scores.get(agent["name"], 0)
        for agent in agents
    )

    combined_score = clamp(combined_score)
    decision = score_to_decision(combined_score)

    positive_agents = [
        agent["name"]
        for agent in agents
        if agent["decision"] in {"BUY", "STRONG BUY", "LOW RISK"}
    ]

    cautious_agents = [
        agent["name"]
        for agent in agents
        if agent["decision"] in {
            "WATCH",
            "SELL",
            "HIGH RISK",
            "MODERATE RISK",
        }
    ]

    comment = (
        f"Positive support from {len(positive_agents)} committee members. "
        f"{len(cautious_agents)} members recommend caution."
    )

    return {
        "name": "Chief Investment Officer",
        "role": "Final committee decision and oversight",
        "decision": decision,
        "confidence": combined_score,
        "score": combined_score,
        "comment": comment,
    }


def run_stock_committee(symbol, market=None, portfolio=None):
    analysis = analyze_symbol(symbol.upper())

    if not analysis:
        return None

    agents = [
        technical_analyst(analysis),
        momentum_analyst(analysis),
        risk_manager(analysis, portfolio),
        portfolio_manager(analysis, portfolio),
        market_strategist(analysis, market),
        sentiment_analyst(),
    ]

    cio = chief_investment_officer(agents)
    agents.append(cio)

    risk_agent = next(
        agent for agent in agents if agent["name"] == "Risk Manager"
    )

    portfolio_agent = next(
        agent for agent in agents if agent["name"] == "Portfolio Manager"
    )

    return {
        "version": "11.2",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "symbol": analysis["symbol"],
        "name": analysis["name"],
        "price": analysis["price"],
        "technical_analysis": analysis,
        "agents": agents,
        "final_decision": cio["decision"],
        "confidence": cio["confidence"],
        "risk_level": risk_agent["decision"],
        "suggested_position_pct": portfolio_agent[
            "suggested_position_pct"
        ],
        "summary": (
            f"AI Committee decision for {analysis['symbol']}: "
            f"{cio['decision']} with {cio['confidence']}% confidence."
        ),
    }


def run_committee(market=None, technicals=None, portfolio=None):
    """
    Backward-compatible market-wide committee used by the existing dashboard.
    """
    valid_technicals = [
        item
        for item in technicals or []
        if isinstance(item, dict) and not item.get("error")
    ]

    if not valid_technicals:
        return {
            "version": "11.2",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "agents": [],
            "final_decision": "HOLD",
            "confidence": 50,
            "summary": "No valid technical results were available.",
        }

    strongest = max(
        valid_technicals,
        key=lambda item: item.get("score", 0),
    )

    return run_stock_committee(
        strongest["symbol"],
        market=market,
        portfolio=portfolio,
    )
