import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from providers.mystocks_snapshot import MyStocksSnapshot


def main() -> int:
    """Run the MyStocks snapshot endpoint diagnostic."""

    provider = MyStocksSnapshot()

    try:
        quotes = provider.fetch_quotes()
    except ValueError as exc:
        print()
        print("SNAPSHOT DIAGNOSTIC RESULT")
        print(f"Status: unavailable")
        print(f"Reason: {exc}")
        print(
            "The endpoint returned HTTP 204 with no content. "
            "No live_quotes.json file was overwritten."
        )
        return 2
    except Exception as exc:
        print()
        print("SNAPSHOT DIAGNOSTIC FAILED")
        print(f"{type(exc).__name__}: {exc}")
        return 1

    print()
    print("Quote Count:", len(quotes))
    print("First 10 Symbols:", list(quotes.keys())[:10])

    for symbol in ["KCB", "SCOM", "EQTY"]:
        print(f"\n{symbol}:")
        print(json.dumps(quotes.get(symbol), indent=2))

    output_file = PROJECT_ROOT / "data" / "live_quotes.json"

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(
            quotes,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\nSaved: {output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
