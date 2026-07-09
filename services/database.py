import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path("database/nse.db")

def get_conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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
    conn = get_conn()
    cur = conn.cursor()

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

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
        cur.execute("""
        INSERT OR REPLACE INTO portfolio(symbol,shares,avg_price)
        VALUES(?,?,?)
        """, row)

    conn.commit()
    conn.close()

def rows_to_dicts(rows):
    return [dict(r) for r in rows]
