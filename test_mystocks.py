from providers.mystocks_provider import MyStocksProvider

provider = MyStocksProvider()

print("Health Check:", provider.health_check())
print(provider.fetch_market_status())
