from pprint import pprint
from services.scheduler_engine import run_daily_automation

if __name__ == "__main__":
    result = run_daily_automation()
    pprint(result)
