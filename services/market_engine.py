import csv
import shutil
from datetime import datetime
from pathlib import Path

from services.database import get_conn, init_db
from services.market_data import get_market_snapshot, get_price_history, get_stock

IMPORT_DIR = Path("data/imports")
ARCHIVE_DIR = Path("data/archive")

REQUIRED_COLUMNS = {
    "symbol",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
}


def ensure_directories():
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)


def validate_row(row):
    missing = REQUIRED_COLUMNS.difference(row.keys())

    if missing:
        raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")

    symbol = row["symbol"].strip().upper()
    trade_date = row["trade_date"].strip()

    if not symbol:
        raise ValueError("Symbol is empty")

    datetime.strptime(trade_date, "%Y-%m-%d")

    open_price = float(row["open"])
    high_price = float(row["high"])
    low_price = float(row["low"])
    close_price = float(row["close"])
    volume = int(float(row["volume"]))

    if min(open_price, high_price, low_price, close_price) <= 0:
        raise ValueError("Prices must be greater than zero")

    if high_price < max(open_price, close_price):
        raise ValueError("High price is below open or close")

    if low_price > min(open_price, close_price):
        raise ValueError("Low price is above open or close")

    if volume < 0:
        raise ValueError("Volume cannot be negative")

    return {
        "symbol": symbol,
        "trade_date": trade_date,
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
        "volume": volume,
    }


def import_ohlcv_csv(file_path):
    init_db()
    ensure_directories()

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    imported = 0
    rejected = []

    conn = get_conn()

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)

            if not reader.fieldnames:
                raise ValueError("CSV has no header row")

            normalized_headers = {
                header.strip().lower() for header in reader.fieldnames if header
            }

            missing_headers = REQUIRED_COLUMNS.difference(normalized_headers)

            if missing_headers:
                raise ValueError(
                    "CSV missing required headers: "
                    + ", ".join(sorted(missing_headers))
                )

            for line_number, raw_row in enumerate(reader, start=2):
                normalized_row = {
                    str(key).strip().lower(): str(value).strip()
                    for key, value in raw_row.items()
                    if key is not None and value is not None
                }

                try:
                    row = validate_row(normalized_row)

                    conn.execute(
                        """
                        INSERT OR REPLACE INTO price_history(
                            symbol,
                            trade_date,
                            open,
                            high,
                            low,
                            close,
                            volume
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            row["symbol"],
                            row["trade_date"],
                            row["open"],
                            row["high"],
                            row["low"],
                            row["close"],
                            row["volume"],
                        ),
                    )

                    conn.execute(
                        """
                        UPDATE stocks
                        SET price = ?, volume = ?, updated_at = ?
                        WHERE symbol = ?
                        """,
                        (
                            row["close"],
                            row["volume"],
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            row["symbol"],
                        ),
                    )

                    imported += 1

                except Exception as exc:
                    rejected.append(
                        {
                            "line": line_number,
                            "error": str(exc),
                        }
                    )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    archive_name = (
        f"{path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{path.suffix}"
    )

    archive_path = ARCHIVE_DIR / archive_name
    shutil.copy2(path, archive_path)

    return {
        "success": True,
        "imported": imported,
        "rejected_count": len(rejected),
        "rejected": rejected[:20],
        "archive_path": str(archive_path),
    }


def scan_import_folder():
    ensure_directories()
    results = []

    for path in sorted(IMPORT_DIR.glob("*.csv")):
        try:
            result = import_ohlcv_csv(path)
            result["file"] = path.name
            results.append(result)

        except Exception as exc:
            results.append(
                {
                    "file": path.name,
                    "success": False,
                    "error": str(exc),
                }
            )

    return results


def get_market_intelligence():
    snapshot = get_market_snapshot()

    return {
        "market_status": snapshot["market_status"],
        "average_change": snapshot["average_change"],
        "generated_at": snapshot["generated_at"],
        "stock_count": len(snapshot["stocks"]),
        "top_gainers": snapshot["top_gainers"],
        "top_losers": snapshot["top_losers"],
    }


def get_symbol_history(symbol, limit=260):
    stock = get_stock(symbol)

    if not stock:
        return None

    return {
        "stock": stock,
        "history": get_price_history(symbol, limit),
    }
