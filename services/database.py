import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import random

DB_PATH = Path("database/nse.db")

def get_conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def rows_to_dicts(rows):
    return [dict(r) for r in rows]

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS stocks (
        symbol TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        sector TEXT,
        price REAL,
        change_pct REAL,
        volume INTEGER,
        updated_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS price_history (
        symbol TEXT,
        trade_date TEXT,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume INTEGER,
        PRIMARY KEY(symbol, trade_date)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS portfolio (
        symbol TEXT PRIMARY KEY,
        shares REAL,
        avg_price REAL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ai_decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        decision TEXT,
        confidence INTEGER,
        reason TEXT,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        content TEXT,
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()

def seed_data():
    init_db()
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    stocks = [
        ("KCB", "KCB Group", "Banking", 44.25, 2.4, 1250000),
        ("EQTY", "Equity Group", "Banking", 51.00, 1.8, 980000),
        ("SCOM", "Safaricom", "Telecom", 23.75, -0.6, 2100000),
        ("NCBA", "NCBA Group", "Banking", 47.50, 1.2, 420000),
        ("BAT", "BAT Kenya", "Manufacturing", 410.00, 0.4, 85000),
        ("EABL", "East African Breweries", "Manufacturing", 172.00, -1.1, 160000),
        ("COOP", "Co-operative Bank", "Banking", 15.80, 0.9, 760000),
        ("ABSA", "Absa Bank Kenya", "Banking", 16.25, 1.5, 530000)
    ]

    for row in stocks:
        cur.execute("""
        INSERT OR REPLACE INTO stocks(symbol,name,sector,price,change_pct,volume,updated_at)
        VALUES(?,?,?,?,?,?,?)
        """, (*row, now))

    portfolio = [
        ("KCB", 100, 38.0),
        ("EQTY", 80, 45.0),
        ("SCOM", 300, 21.5),
        ("COOP", 200, 13.5)
    ]

    for row in portfolio:
        cur.execute("INSERT OR REPLACE INTO portfolio(symbol,shares,avg_price) VALUES(?,?,?)", row)

    conn.commit()
    conn.close()

def seed_price_history(days=260):
    seed_data()
    conn = get_conn()
    cur = conn.cursor()
    stocks = cur.execute("SELECT symbol, price, volume FROM stocks").fetchall()

    for stock in stocks:
        existing = cur.execute("SELECT COUNT(*) AS c FROM price_history WHERE symbol=?", (stock["symbol"],)).fetchone()["c"]
        if existing >= 200:
            continue

        random.seed(stock["symbol"])
        close = float(stock["price"]) * 0.75
        start = datetime.now().date() - timedelta(days=days * 2)

        inserted = 0
        for i in range(days * 2):
            d = start + timedelta(days=i)
            if d.weekday() >= 5:
                continue

            drift = random.uniform(-0.025, 0.03)
            open_p = close * (1 + random.uniform(-0.01, 0.01))
            close = max(1, close * (1 + drift))
            high = max(open_p, close) * (1 + random.uniform(0.002, 0.018))
            low = min(open_p, close) * (1 - random.uniform(0.002, 0.018))
            volume = int(float(stock["volume"]) * random.uniform(0.4, 1.6))

            cur.execute("""
            INSERT OR REPLACE INTO price_history(symbol, trade_date, open, high, low, close, volume)
            VALUES(?,?,?,?,?,?,?)
            """, (stock["symbol"], d.isoformat(), round(open_p,2), round(high,2), round(low,2), round(close,2), volume))

            inserted += 1
            if inserted >= days:
                break

        cur.execute("UPDATE stocks SET price=?, updated_at=? WHERE symbol=?", (round(close,2), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), stock["symbol"]))

    conn.commit()
    conn.close()
