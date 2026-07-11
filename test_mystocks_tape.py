import requests

urls = [
    "https://live.mystocks.co.ke/ticker/tape$",
    "https://tickers.mystocks.co.ke/ticker/tape$",
    "https://tickers.mystocks.co.ke/ticker/RMWX$?app=FIB;f=mslFrame0;d=fib.co.ke",
]

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://fib.co.ke/live-markets/",
}

session = requests.Session()
session.headers.update(headers)

for url in urls:
    print("\n" + "=" * 70)
    print("URL:", url)

    try:
        response = session.get(
            url,
            timeout=20,
            allow_redirects=True,
        )

        print("Status:", response.status_code)
        print("Final URL:", response.url)
        print("Content-Type:", response.headers.get("content-type"))
        print("Content-Length header:", response.headers.get("content-length"))
        print("Actual bytes:", len(response.content))
        print("Redirect history:", [
            f"{item.status_code} {item.url}"
            for item in response.history
        ])
        print("Preview:", repr(response.text[:300]))

    except Exception as exc:
        print("ERROR:", repr(exc))
