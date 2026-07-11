from datetime import datetime

from services.database import get_conn


def _table_columns(conn, table_name):
    rows = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return {row["name"] for row in rows}


def init_transaction_tables():
    conn = get_conn()

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS portfolio_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            shares REAL NOT NULL,
            price REAL NOT NULL,
            total_amount REAL NOT NULL,
            transaction_date TEXT NOT NULL
        )
        """
    )

    transaction_columns = _table_columns(
        conn,
        "portfolio_transactions",
    )

    if "realized_profit" not in transaction_columns:
        conn.execute(
            """
            ALTER TABLE portfolio_transactions
            ADD COLUMN realized_profit REAL DEFAULT 0
            """
        )

    if "cash_after" not in transaction_columns:
        conn.execute(
            """
            ALTER TABLE portfolio_transactions
            ADD COLUMN cash_after REAL
            """
        )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS portfolio_account (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            starting_capital REAL NOT NULL DEFAULT 0,
            cash_balance REAL NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )
        """
    )

    account = conn.execute(
        "SELECT id FROM portfolio_account WHERE id = 1"
    ).fetchone()

    if not account:
        conn.execute(
            """
            INSERT INTO portfolio_account(
                id,
                starting_capital,
                cash_balance,
                updated_at
            )
            VALUES (1, 0, 0, ?)
            """,
            (
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            ),
        )

    conn.commit()
    conn.close()


def set_starting_capital(amount, reset_cash=False):
    amount = float(amount)

    if amount < 0:
        raise ValueError(
            "Starting capital cannot be negative"
        )

    init_transaction_tables()
    conn = get_conn()

    try:
        account = conn.execute(
            """
            SELECT starting_capital, cash_balance
            FROM portfolio_account
            WHERE id = 1
            """
        ).fetchone()

        old_starting = float(
            account["starting_capital"]
        )
        old_cash = float(account["cash_balance"])

        if reset_cash:
            new_cash = amount
        else:
            adjustment = amount - old_starting
            new_cash = old_cash + adjustment

        if new_cash < 0:
            raise ValueError(
                "The capital adjustment would make "
                "the cash balance negative"
            )

        conn.execute(
            """
            UPDATE portfolio_account
            SET starting_capital = ?,
                cash_balance = ?,
                updated_at = ?
            WHERE id = 1
            """,
            (
                round(amount, 2),
                round(new_cash, 2),
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            ),
        )

        conn.commit()

        return {
            "success": True,
            "starting_capital": round(amount, 2),
            "cash_balance": round(new_cash, 2),
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def deposit_cash(amount):
    amount = float(amount)

    if amount <= 0:
        raise ValueError(
            "Deposit amount must be greater than zero"
        )

    init_transaction_tables()
    conn = get_conn()

    try:
        conn.execute(
            """
            UPDATE portfolio_account
            SET starting_capital = starting_capital + ?,
                cash_balance = cash_balance + ?,
                updated_at = ?
            WHERE id = 1
            """,
            (
                amount,
                amount,
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            ),
        )

        conn.commit()

        return get_cash_summary()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def withdraw_cash(amount):
    amount = float(amount)

    if amount <= 0:
        raise ValueError(
            "Withdrawal amount must be greater than zero"
        )

    init_transaction_tables()
    conn = get_conn()

    try:
        account = conn.execute(
            """
            SELECT cash_balance
            FROM portfolio_account
            WHERE id = 1
            """
        ).fetchone()

        cash = float(account["cash_balance"])

        if amount > cash:
            raise ValueError(
                f"Insufficient cash. Available: "
                f"KSh {cash:,.2f}"
            )

        conn.execute(
            """
            UPDATE portfolio_account
            SET starting_capital = starting_capital - ?,
                cash_balance = cash_balance - ?,
                updated_at = ?
            WHERE id = 1
            """,
            (
                amount,
                amount,
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            ),
        )

        conn.commit()

        return get_cash_summary()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_cash_balance():
    init_transaction_tables()
    conn = get_conn()

    row = conn.execute(
        """
        SELECT cash_balance
        FROM portfolio_account
        WHERE id = 1
        """
    ).fetchone()

    conn.close()

    return round(float(row["cash_balance"]), 2)


def buy_shares(symbol, shares, price):
    symbol = symbol.strip().upper()
    shares = float(shares)
    price = float(price)

    if shares <= 0:
        raise ValueError(
            "Shares must be greater than zero"
        )

    if price <= 0:
        raise ValueError(
            "Price must be greater than zero"
        )

    init_transaction_tables()
    conn = get_conn()

    try:
        total_amount = shares * price

        account = conn.execute(
            """
            SELECT cash_balance
            FROM portfolio_account
            WHERE id = 1
            """
        ).fetchone()

        cash_balance = float(
            account["cash_balance"]
        )

        if total_amount > cash_balance:
            raise ValueError(
                f"Insufficient cash. Required: "
                f"KSh {total_amount:,.2f}; "
                f"available: KSh {cash_balance:,.2f}"
            )

        holding = conn.execute(
            """
            SELECT shares, avg_price
            FROM portfolio
            WHERE symbol = ?
            """,
            (symbol,),
        ).fetchone()

        if holding:
            old_shares = float(
                holding["shares"]
            )
            old_avg_price = float(
                holding["avg_price"]
            )

            new_shares = old_shares + shares

            new_avg_price = (
                (old_shares * old_avg_price)
                + (shares * price)
            ) / new_shares

            conn.execute(
                """
                UPDATE portfolio
                SET shares = ?, avg_price = ?
                WHERE symbol = ?
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
                INSERT INTO portfolio(
                    symbol,
                    shares,
                    avg_price
                )
                VALUES (?, ?, ?)
                """,
                (
                    symbol,
                    round(shares, 4),
                    round(price, 4),
                ),
            )

        new_cash = cash_balance - total_amount

        conn.execute(
            """
            UPDATE portfolio_account
            SET cash_balance = ?,
                updated_at = ?
            WHERE id = 1
            """,
            (
                round(new_cash, 2),
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
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
                transaction_date,
                realized_profit,
                cash_after
            )
            VALUES (?, 'BUY', ?, ?, ?, ?, 0, ?)
            """,
            (
                symbol,
                shares,
                price,
                round(total_amount, 2),
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                round(new_cash, 2),
            ),
        )

        conn.commit()

        return {
            "success": True,
            "type": "BUY",
            "symbol": symbol,
            "shares_bought": shares,
            "purchase_price": price,
            "total_shares": round(
                new_shares,
                4,
            ),
            "average_price": round(
                new_avg_price,
                4,
            ),
            "total_amount": round(
                total_amount,
                2,
            ),
            "cash_balance": round(
                new_cash,
                2,
            ),
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
        raise ValueError(
            "Shares must be greater than zero"
        )

    if price <= 0:
        raise ValueError(
            "Price must be greater than zero"
        )

    init_transaction_tables()
    conn = get_conn()

    try:
        holding = conn.execute(
            """
            SELECT shares, avg_price
            FROM portfolio
            WHERE symbol = ?
            """,
            (symbol,),
        ).fetchone()

        if not holding:
            raise ValueError(
                f"{symbol} is not in the portfolio"
            )

        current_shares = float(
            holding["shares"]
        )
        average_price = float(
            holding["avg_price"]
        )

        if shares > current_shares:
            raise ValueError(
                f"Cannot sell {shares} shares. "
                f"Only {current_shares} are available."
            )

        account = conn.execute(
            """
            SELECT cash_balance
            FROM portfolio_account
            WHERE id = 1
            """
        ).fetchone()

        old_cash = float(
            account["cash_balance"]
        )

        remaining_shares = (
            current_shares - shares
        )

        total_amount = shares * price

        realized_profit = shares * (
            price - average_price
        )

        new_cash = old_cash + total_amount

        if remaining_shares <= 0:
            conn.execute(
                """
                DELETE FROM portfolio
                WHERE symbol = ?
                """,
                (symbol,),
            )

        else:
            conn.execute(
                """
                UPDATE portfolio
                SET shares = ?
                WHERE symbol = ?
                """,
                (
                    round(
                        remaining_shares,
                        4,
                    ),
                    symbol,
                ),
            )

        conn.execute(
            """
            UPDATE portfolio_account
            SET cash_balance = ?,
                updated_at = ?
            WHERE id = 1
            """,
            (
                round(new_cash, 2),
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
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
                transaction_date,
                realized_profit,
                cash_after
            )
            VALUES (?, 'SELL', ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol,
                shares,
                price,
                round(total_amount, 2),
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                round(realized_profit, 2),
                round(new_cash, 2),
            ),
        )

        conn.commit()

        return {
            "success": True,
            "type": "SELL",
            "symbol": symbol,
            "shares_sold": shares,
            "sale_price": price,
            "remaining_shares": round(
                remaining_shares,
                4,
            ),
            "total_amount": round(
                total_amount,
                2,
            ),
            "realized_profit": round(
                realized_profit,
                2,
            ),
            "cash_balance": round(
                new_cash,
                2,
            ),
            "holding_removed": (
                remaining_shares <= 0
            ),
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_transactions(limit=100):
    init_transaction_tables()
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


def get_realized_profit():
    init_transaction_tables()
    conn = get_conn()

    row = conn.execute(
        """
        SELECT COALESCE(
            SUM(realized_profit),
            0
        ) AS realized_profit
        FROM portfolio_transactions
        WHERE transaction_type = 'SELL'
        """
    ).fetchone()

    conn.close()

    return round(
        float(row["realized_profit"]),
        2,
    )


def get_cash_summary():
    init_transaction_tables()
    conn = get_conn()

    account = conn.execute(
        """
        SELECT
            starting_capital,
            cash_balance,
            updated_at
        FROM portfolio_account
        WHERE id = 1
        """
    ).fetchone()

    holdings = conn.execute(
        """
        SELECT
            p.symbol,
            p.shares,
            p.avg_price,
            COALESCE(s.price, p.avg_price)
                AS current_price
        FROM portfolio p
        LEFT JOIN stocks s
            ON s.symbol = p.symbol
        """
    ).fetchall()

    conn.close()

    invested_cost = sum(
        float(row["shares"])
        * float(row["avg_price"])
        for row in holdings
    )

    portfolio_value = sum(
        float(row["shares"])
        * float(row["current_price"])
        for row in holdings
    )

    cash_balance = float(
        account["cash_balance"]
    )

    starting_capital = float(
        account["starting_capital"]
    )

    total_equity = (
        cash_balance + portfolio_value
    )

    unrealized_profit = (
        portfolio_value - invested_cost
    )

    realized_profit = get_realized_profit()

    total_profit = (
        total_equity - starting_capital
    )

    return {
        "starting_capital": round(
            starting_capital,
            2,
        ),
        "cash_balance": round(
            cash_balance,
            2,
        ),
        "invested_cost": round(
            invested_cost,
            2,
        ),
        "portfolio_value": round(
            portfolio_value,
            2,
        ),
        "total_equity": round(
            total_equity,
            2,
        ),
        "unrealized_profit": round(
            unrealized_profit,
            2,
        ),
        "realized_profit": round(
            realized_profit,
            2,
        ),
        "total_profit": round(
            total_profit,
            2,
        ),
        "cash_percentage": round(
            (
                cash_balance / total_equity * 100
                if total_equity > 0
                else 0
            ),
            2,
        ),
        "invested_percentage": round(
            (
                portfolio_value / total_equity * 100
                if total_equity > 0
                else 0
            ),
            2,
        ),
        "updated_at": account["updated_at"],
    }
