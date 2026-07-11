import json

from providers.mystocks_snapshot import MyStocksSnapshot


provider = MyStocksSnapshot()

quotes = provider.fetch_quotes()

print("Quote Count:", len(quotes))
print("First 10 Symbols:", list(quotes.keys())[:10])

for symbol in ["KCB", "SCOM", "EQTY"]:
    print(f"\n{symbol}:")
    print(json.dumps(quotes.get(symbol), indent=2))

with open("data/live_quotes.json", "w", encoding="utf-8") as file:
    json.dump(quotes, file, indent=2, ensure_ascii=False)

print("\nSaved: data/live_quotes.json")
