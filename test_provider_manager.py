from providers.provider_manager import ProviderManager
from providers.test_provider import TestProvider


manager = ProviderManager(primary_provider=TestProvider())

quotes = manager.get_live_quotes()
status = manager.get_market_status()

print("Quotes:")
print(quotes)

print("\nMarket status:")
print(status)

print("\nProvider information:")
print(manager.get_provider_info())
