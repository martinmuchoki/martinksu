from services.database import get_conn, rows_to_dicts, init_db, seed_data
from services.market_data import get_stock

def get_portfolio():
    init_db()
    seed_data()
    conn = get_conn()
    rows = conn.execute("SELECT * FROM portfolio ORDER BY symbol").fetchall()
    conn.close()

    holdings = []
    for r in rows_to_dicts(rows):
        stock = get_stock(r["symbol"])
        current_price = stock["price"] if stock else r["avg_price"]
        value = r["shares"] * current_price
        cost = r["shares"] * r["avg_price"]
        pnl = value - cost
        holdings.append({
            "symbol": r["symbol"],
            "shares": r["shares"],
            "avg_price": r["avg_price"],
            "current_price": current_price,
            "value": round(value, 2),
            "cost": round(cost, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round((pnl / cost) * 100, 2) if cost else 0
        })

    total_cost = sum(h["cost"] for h in holdings)
    total_value = sum(h["value"] for h in holdings)
    pnl = total_value - total_cost

    return {
        "holdings": holdings,
        "total_cost": round(total_cost, 2),
        "total_value": round(total_value, 2),
        "pnl": round(pnl, 2),
        "pnl_pct": round((pnl / total_cost) * 100, 2) if total_cost else 0,
        "allocation": "75% stocks / 25% cash",
        "risk_level": "Moderate",
        "recommendation": "Maintain core holdings and add selectively to high-confidence signals."
    }
