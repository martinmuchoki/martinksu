from datetime import datetime

from services.database import get_conn


def init_transaction_table():
    conn = get_conn()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            shares REAL NOT NULL,
            price REAL NOT NULL,
            total_amount REAL NOT NULL,
            transaction_date TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def buy_shares(symbol, shares, price):
    symbol = symbol.strip().upper()
    shares = float(shares)
    price = float(price)

    if shares <= 0:
        raise ValueError("Shares must be greater than zero")

    if price <= 0:
        raise ValueError("Price must be greater than zero")

    init_transaction_table()
    conn = get_conn()

    try:
        holding = conn.execute(
            "SELECT shares, avg_price FROM portfolio WHERE symbol=?",
            (symbol,),
        ).fetchone()

        if holding:
            old_shares = float(holding["shares"])
            old_avg_price = float(holding["avg_price"])

            new_shares = old_shares + shares

            new_avg_price = (
                (old_shares * old_avg_price) + (shares * price)
            ) / new_shares

            conn.execute(
                """
                UPDATE portfolio
                SET shares=?, avg_price=?
                WHERE symbol=?
                """,
                (
                    round(new_shares, 4),
                    round(new_avg_price, 4),
                    symbol,
                ),
            )

        else:
            new_shares = shares
            new_avg_price = price

            conn.execute(
                """
                INSERT INTO portfolio(symbol, shares, avg_price)
                VALUES (?, ?, ?)
                """,
                (
                    symbol,
                    round(shares, 4),
                    round(price, 4),
                ),
            )

        total_amount = shares * price

        conn.execute(
            """
            INSERT INTO portfolio_transactions(
                symbol,
                transaction_type,
                shares,
                price,
                total_amount,
                transaction_date
            )
            VALUES (?, 'BUY', ?, ?, ?, ?)
            """,
            (
                symbol,
                shares,
                price,
                round(total_amount, 2),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )

        conn.commit()

        return {
            "success": True,
            "type": "BUY",
            "symbol": symbol,
            "shares_bought": shares,
            "purchase_price": price,
            "total_shares": round(new_shares, 4),
            "average_price": round(new_avg_price, 4),
            "total_amount": round(total_amount, 2),
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def sell_shares(symbol, shares, price):
    symbol = symbol.strip().upper()
    shares = float(shares)
    price = float(price)

    if shares <= 0:
        raise ValueError("Shares must be greater than zero")

    if price <= 0:
        raise ValueError("Price must be greater than zero")

    init_transaction_table()
    conn = get_conn()

    try:
        holding = conn.execute(
            "SELECT shares, avg_price FROM portfolio WHERE symbol=?",
            (symbol,),
        ).fetchone()

        if not holding:
            raise ValueError(f"{symbol} is not in the portfolio")

        current_shares = float(holding["shares"])
        average_price = float(holding["avg_price"])

        if shares > current_shares:
            raise ValueError(
                f"Cannot sell {shares} shares. "
                f"Only {current_shares} shares are available."
            )

        remaining_shares = current_shares - shares
        total_amount = shares * price
        realized_profit = shares * (price - average_price)

        if remaining_shares <= 0:
            conn.execute(
                "DELETE FROM portfolio WHERE symbol=?",
                (symbol,),
            )
        else:
            conn.execute(
                """
                UPDATE portfolio
                SET shares=?
                WHERE symbol=?
                """,
                (
                    round(remaining_shares, 4),
                    symbol,
                ),
            )

        conn.execute(
            """
            INSERT INTO portfolio_transactions(
                symbol,
                transaction_type,
                shares,
                price,
                total_amount,
                transaction_date
            )
            VALUES (?, 'SELL', ?, ?, ?, ?)
            """,
            (
                symbol,
                shares,
                price,
                round(total_amount, 2),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )

        conn.commit()

        return {
            "success": True,
            "type": "SELL",
            "symbol": symbol,
            "shares_sold": shares,
            "sale_price": price,
            "remaining_shares": round(remaining_shares, 4),
            "total_amount": round(total_amount, 2),
            "realized_profit": round(realized_profit, 2),
            "holding_removed": remaining_shares <= 0,
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_transactions(limit=100):
    init_transaction_table()
    conn = get_conn()

    rows = conn.execute(
        """
        SELECT *
        FROM portfolio_transactions
        ORDER BY id DESC
        LIMIT ?
        """,
        (int(limit),),
    ).fetchall()

    conn.close()
    return [dict(row) for row in rows]
