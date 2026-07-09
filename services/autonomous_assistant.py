def rank_opportunities(technicals):
    ranked = sorted(technicals, key=lambda x: x["score"], reverse=True)
    return ranked[:5]

def autonomous_decision(market, committee, portfolio, technicals):
    top = rank_opportunities(technicals)
    best = top[0] if top else None

    if committee["final_decision"] == "BUY" and best and best["score"] >= 75:
        action = "ACCUMULATE"
    elif portfolio["pnl_pct"] < -8:
        action = "DEFEND CAPITAL"
    else:
        action = "HOLD / WATCH"

    return {
        "action": action,
        "confidence": committee["confidence"],
        "best_opportunity": best,
        "summary": f"Autonomous assistant recommends {action}. Best opportunity: {best['symbol'] if best else 'None'}.",
        "next_steps": [
            "Review top-ranked opportunities.",
            "Avoid over-concentration in one sector.",
            "Keep 20–25% cash available.",
            "Send Telegram alert for high-confidence BUY signals.",
            "Generate daily report after market update."
        ],
        "ranked_opportunities": top
    }
