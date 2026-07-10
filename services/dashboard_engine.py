from services.market_engine import get_market_intelligence
from services.ai_committee import run_stock_committee
from services.portfolio import get_portfolio

WATCHLIST = [
    "KCB",
    "EQTY",
    "SCOM",
    "NCBA",
    "ABSA",
]


def build_dashboard():
    market = get_market_intelligence()
    portfolio = get_portfolio()
    picks = []

    for symbol in WATCHLIST:
        try:
            committee = run_stock_committee(
                symbol,
                market=market,
                portfolio=portfolio,
            )

            if committee:
                picks.append({
                    "symbol": committee["symbol"],
                    "name": committee["name"],
                    "decision": committee["final_decision"],
                    "confidence": committee["confidence"],
                    "price": committee["price"],
                    "risk": committee["risk_level"],
                    "position_pct": committee["suggested_position_pct"],
                })

        except Exception as exc:
            picks.append({
                "symbol": symbol,
                "error": str(exc),
            })

    valid_picks = [
        item for item in picks
        if "error" not in item
    ]

    valid_picks.sort(
        key=lambda item: item["confidence"],
        reverse=True,
    )

    return {
        "market": market,
        "portfolio": portfolio,
        "top_picks": valid_picks[:5],
        "errors": [
            item for item in picks
            if "error" in item
        ],
    }
