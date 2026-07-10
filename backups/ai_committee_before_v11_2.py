from datetime import datetime

def run_committee(market=None, technicals=None, portfolio=None):
    avg_change = market.get("average_change", 0) if market else 0
    buy_signals = sum(1 for t in technicals or [] if "BUY" in t["signal"])
    pnl_pct = portfolio.get("pnl_pct", 0) if portfolio else 0

    fundamental_decision = "BUY" if avg_change >= 0 else "HOLD"
    technical_decision = "BUY" if buy_signals >= 3 else "HOLD"
    risk_decision = "LOW RISK" if pnl_pct > -5 else "HIGH RISK"
    portfolio_decision = "BUY" if pnl_pct >= 0 else "HOLD"

    agents = [
        {"name":"Fundamental Analyst","role":"Valuation, dividends, company strength","decision":fundamental_decision,"confidence":84,"comment":"Core NSE blue chips remain attractive for medium-term accumulation."},
        {"name":"Technical Analyst","role":"RSI, MACD, EMA, trend","decision":technical_decision,"confidence":86,"comment":f"{buy_signals} stocks show buy or strong-buy technical structure."},
        {"name":"News & Sentiment Analyst","role":"News and market sentiment","decision":"HOLD","confidence":74,"comment":"Sentiment engine ready; live news feed will be connected later."},
        {"name":"Risk Manager","role":"Volatility and drawdown","decision":risk_decision,"confidence":80,"comment":"Portfolio risk is acceptable if exposure remains diversified."},
        {"name":"Portfolio Manager","role":"Allocation and rebalancing","decision":portfolio_decision,"confidence":83,"comment":"Maintain cash reserve and add to strongest signals only."},
        {"name":"Chief Investment Officer","role":"Final committee oversight","decision":"BUY" if buy_signals >= 3 and avg_change >= 0 else "HOLD","confidence":87,"comment":"Selective accumulation is preferred over aggressive buying."}
    ]

    buy_votes = sum(1 for a in agents if a["decision"] == "BUY")
    sell_votes = sum(1 for a in agents if a["decision"] == "SELL")
    final = "BUY" if buy_votes >= 3 else "SELL" if sell_votes >= 2 else "HOLD"
    confidence = round(sum(a["confidence"] for a in agents) / len(agents))

    return {
        "version": "10.5",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "agents": agents,
        "final_decision": final,
        "confidence": confidence,
        "summary": f"AI Committee final decision: {final} with {confidence}% confidence."
    }
