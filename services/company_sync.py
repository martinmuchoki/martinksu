import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup, Tag

from services.database import get_conn
from services.logger import log_info, log_warning, log_exception


NSE_LISTED_COMPANIES_URL = "https://www.nse.co.ke/listed-companies/"


def init_company_table():
    conn = get_conn()

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS listed_companies (
            symbol TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            sector TEXT NOT NULL,
            isin TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            source_url TEXT,
            last_seen_at TEXT,
            updated_at TEXT
        )
        """
    )

    conn.commit()
    conn.close()


def clean_text(value):
    return " ".join(str(value or "").split()).strip()


def extract_company_records(html):
    soup = BeautifulSoup(html, "html.parser")

    records = {}
    current_sector = None

    for node in soup.find_all(["h3", "h6"]):
        if node.name == "h3":
            current_sector = clean_text(node.get_text(" ", strip=True)).title()
            continue

        if node.name != "h6" or not current_sector:
            continue

        company_name = clean_text(node.get_text(" ", strip=True))
        nearby_text = []

        for item in node.next_elements:
            if isinstance(item, Tag) and item is not node:
                if item.name in {"h3", "h6"}:
                    break

            if isinstance(item, str):
                value = clean_text(item)

                if value:
                    nearby_text.append(value)

        block = " ".join(nearby_text)

        symbol_match = re.search(
            r"Trading\s+Symbol\s*:\s*([A-Z0-9.]+)",
            block,
            flags=re.IGNORECASE,
        )

        if not symbol_match:
            continue

        isin_match = re.search(
            r"ISIN(?:\s+CODE)?\s*:\s*([A-Z0-9]+)",
            block,
            flags=re.IGNORECASE,
        )

        symbol = symbol_match.group(1).strip().upper()
        isin = isin_match.group(1).strip().upper() if isin_match else None

        records[symbol] = {
            "symbol": symbol,
            "name": company_name,
            "sector": current_sector,
            "isin": isin,
        }

    return sorted(
        records.values(),
        key=lambda item: (item["sector"], item["name"]),
    )


def fetch_official_company_list():
    response = requests.get(
        NSE_LISTED_COMPANIES_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 NSE-Signal-Bot/11.5 "
                "Company-Metadata-Sync"
            )
        },
        timeout=30,
    )

    response.raise_for_status()

    records = extract_company_records(response.text)

    if len(records) < 30:
        raise RuntimeError(
            f"Only {len(records)} instruments were parsed; "
            "the NSE page structure may have changed."
        )

    return records


def sync_listed_companies():
    init_company_table()
    records = fetch_official_company_list()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    conn = get_conn()

    try:
        conn.execute("UPDATE listed_companies SET is_active = 0")

        for company in records:
            conn.execute(
                """
                INSERT INTO listed_companies (
                    symbol,
                    name,
                    sector,
                    isin,
                    is_active,
                    source_url,
                    last_seen_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    name = excluded.name,
                    sector = excluded.sector,
                    isin = excluded.isin,
                    is_active = 1,
                    source_url = excluded.source_url,
                    last_seen_at = excluded.last_seen_at,
                    updated_at = excluded.updated_at
                """,
                (
                    company["symbol"],
                    company["name"],
                    company["sector"],
                    company["isin"],
                    NSE_LISTED_COMPANIES_URL,
                    now,
                    now,
                ),
            )

        conn.commit()

        log_info(
            f"Official NSE company sync completed: {len(records)} instruments"
        )

        return {
            "success": True,
            "count": len(records),
            "updated_at": now,
            "source": NSE_LISTED_COMPANIES_URL,
        }

    except Exception:
        conn.rollback()
        log_exception("Official NSE company sync failed")
        raise

    finally:
        conn.close()


def get_listed_companies(active_only=True):
    init_company_table()
    conn = get_conn()

    query = """
        SELECT symbol, name, sector, isin, is_active
        FROM listed_companies
    """

    if active_only:
        query += " WHERE is_active = 1"

    query += " ORDER BY sector, name"

    rows = conn.execute(query).fetchall()
    conn.close()

    return [dict(row) for row in rows]
