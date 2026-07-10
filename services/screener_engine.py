from services.market_data import get_market_snapshot
from services.ai_committee import run_stock_committee
from services.portfolio import get_portfolio


def run_screener():
    market = get_market_snapshot()
    portfolio = get_portfolio()

    results = []

    for stock in market["stocks"]:
        try:
            committee = run_stock_committee(
                stock["symbol"],
                market=market,
                portfolio=portfolio,
            )

            if committee:
                results.append({
                    "symbol": committee["symbol"],
                    "name": committee["name"],
                    "price": committee["price"],
                    "decision": committee["final_decision"],
                    "confidence": committee["confidence"],
                    "risk": committee["risk_level"],
                    "position": committee["suggested_position_pct"],
                })

        except Exception as exc:
            print(f"Skipping {stock['symbol']}: {exc}")

    results.sort(
        key=lambda item: item["confidence"],
        reverse=True,
    )

    return results
