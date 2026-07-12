import json

from services.history_collector import collect_daily_history


if __name__ == "__main__":
    result = collect_daily_history()
    print(json.dumps(result, indent=2))
