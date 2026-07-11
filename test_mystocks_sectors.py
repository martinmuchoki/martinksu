import json
from datetime import datetime

import requests


BASE_URL = "https://live.mystocks.co.ke"


def sector_url() -> str:
    now = datetime.now()

    # Matches the unusual date-key format used by the myStocks page:
    # year + zero-based month + weekday + hour
    key = (
        f"{now.year}"
        f"{now.month - 1:02d}"
        f"{now.weekday() + 1:02d}"
        f"{now.hour:02d}"
    )

    return f"{BASE_URL}/ajax/stocksectors/{key}"


url = sector_url()

response = requests.get(
    url,
    timeout=15,
    headers={
        "User-Agent": "Mozilla/5.0 NSE-Signal-Bot/10.4",
        "Accept": "application/json",
        "Referer": "https://tickers.mystocks.co.ke/",
    },
)

response.raise_for_status()
data = response.json()

print("URL:", url)
print("HTTP Status:", response.status_code)
print("Content Type:", response.headers.get("content-type"))
print("Sector Count:", len(data))
print("Sectors:", list(data.keys()))

with open("data/mystocks_sectors_raw.json", "w", encoding="utf-8") as file:
    json.dump(data, file, indent=2, ensure_ascii=False)

print("Saved: data/mystocks_sectors_raw.json")
