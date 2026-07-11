import json

from providers.mystocks_provider import MyStocksProvider


provider = MyStocksProvider()

sectors = provider.fetch_sectors()
master = provider.fetch_security_master()

print("Sector Count:", len(sectors))
print("Security Count:", len(master))
print("First 10 Symbols:", list(master.keys())[:10])

print("\nKCB:")
print(json.dumps(master.get("KCB"), indent=2))

print("\nSCOM:")
print(json.dumps(master.get("SCOM"), indent=2))

with open("data/nse_master.json", "w", encoding="utf-8") as file:
    json.dump(master, file, indent=2, ensure_ascii=False)

print("\nSaved: data/nse_master.json")
