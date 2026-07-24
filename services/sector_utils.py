"""
Canonical NSE sector normalization.

All downstream intelligence engines must consume these canonical
sector names rather than creating their own symbol-to-sector mappings.
"""

from typing import Any


SECTOR_MAP = {
    "agricultural": "Agriculture",
    "agriculture": "Agriculture",

    "banking": "Banking",
    "financials": "Banking",
    "financial services": "Banking",

    "insurance": "Insurance",

    "investment": "Investment",
    "investment services": "Investment",

    "manufacturing": "Manufacturing",
    "consumer goods": "Manufacturing",
    "consumer staples": "Manufacturing",
    "industrial gases": "Manufacturing",
    "materials": "Manufacturing",

    "energy": "Energy",
    "utilities": "Energy",

    "media": "Media",
    "media & publishing": "Media",

    "commercial and services": "Commercial Services",
    "retail": "Commercial Services",

    "construction & allied": "Construction",

    "tourism & hospitality": "Tourism",

    "telecommunications": "Telecommunications",
    "marketing & communications": "Telecommunications",

    "automotive & equipment distribution": "Automotive",

    "real estate": "Real Estate",
    "transport": "Transport",

    "other": "Other",
    "unknown": "Other",
}


def normalize_sector(value: Any) -> str:
    """Return one approved canonical NSE sector name."""
    raw_sector = str(value or "").strip()

    if not raw_sector:
        return "Other"

    return SECTOR_MAP.get(
        raw_sector.casefold(),
        raw_sector,
    )
