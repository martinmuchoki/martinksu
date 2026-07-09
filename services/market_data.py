from datetime import datetime
from services.database import get_conn, rows_to_dicts, init_db, seed_data

def ensure_market_data():
    init_db()
    seed_data()

def get_stocks():
    ensure_market_data()
    conn = get_conn()
    rows = conn.execute("SELECT * FROM stocks ORDER BY symbol").fetchall()
    conn.close()
    return rows_to_dicts(rows)

def get_stock(symbol):
    ensure_market_data()
    conn = get_conn()
    row = conn.execute("SELECT * FROM stocks WHERE symbol=?", (symbol.upper(),)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_market_snapshot():
    stocks = get_stocks()
    gainers = sorted(stocks, key=lambda x: x["change_pct"], reverse=True)[:5]
    losers = sorted(stocks, key=lambda x: x["change_pct"])[:5]
    avg_change = round(sum(s["change_pct"] for s in stocks) / len(stocks), 2) if stocks else 0

    if avg_change > 1:
        status = "Bullish"
    elif avg_change < -1:
        status = "Bearish"
    else:
        status = "Neutral / selective"

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "market_status": status,
        "average_change": avg_change,
        "stocks": stocks,
        "top_gainers": gainers,
        "top_losers": losers
    }
