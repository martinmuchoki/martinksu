from datetime import datetime

def run_committee():
    agents = [
        {
            "name": "Fundamental Analyst",
            "role": "Valuation, dividends, company strength",
            "decision": "BUY",
            "confidence": 88,
            "comment": "Strong banking and telecom fundamentals remain attractive."
        },
        {
            "name": "Technical Analyst",
            "role": "Trend, RSI, MACD, moving averages",
            "decision": "BUY",
            "confidence": 84,
            "comment": "Market trend is positive with selected stocks showing momentum."
        },
        {
            "name": "News & Sentiment Analyst",
            "role": "News, announcements, investor sentiment",
            "decision": "HOLD",
            "confidence": 76,
            "comment": "Sentiment is stable; wait for stronger confirmation."
        },
        {
            "name": "Risk Manager",
            "role": "Volatility, downside risk, position sizing",
            "decision": "LOW RISK",
            "confidence": 82,
            "comment": "Diversified allocation reduces downside exposure."
        },
        {
            "name": "Portfolio Manager",
            "role": "Allocation, diversification, cash balance",
            "decision": "BUY",
            "confidence": 86,
            "comment": "Recommended allocation: 75% stocks, 25% cash."
        }
    ]

    buy_votes = sum(1 for a in agents if a["decision"] == "BUY")
    hold_votes = sum(1 for a in agents if a["decision"] == "HOLD")
    sell_votes = sum(1 for a in agents if a["decision"] == "SELL")

    if buy_votes >= 3:
        final_decision = "BUY"
    elif sell_votes >= 2:
        final_decision = "SELL"
    else:
        final_decision = "HOLD"

    confidence = round(sum(a["confidence"] for a in agents) / len(agents))

    return {
        "version": "10.3.1",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "agents": agents,
        "final_decision": final_decision,
        "confidence": confidence,
        "summary": f"AI Committee final decision: {final_decision} with {confidence}% confidence."
    }
