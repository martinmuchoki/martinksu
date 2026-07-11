from datetime import datetime, timezone
from typing import Any, Dict


class TestProvider:
    name = "Test Provider"

    def health_check(self) -> bool:
        return True

    def fetch_quotes(self) -> Dict[str, Dict[str, Any]]:
        return {
            "KCB": {
                "symbol": "KCB",
                "name": "KCB Group Plc",
                "price": 0.0,
                "previous_close": 0.0,
                "change": 0.0,
                "change_percent": 0.0,
                "high": 0.0,
                "low": 0.0,
                "average_price": 0.0,
                "volume": 0,
                "last_trade_time": None,
                "source": self.name,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        }

    def fetch_market_status(self) -> Dict[str, Any]:
        return {
            "status": "TEST",
            "provider": self.name,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
