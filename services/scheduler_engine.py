from datetime import datetime

from services.market_engine import get_market_intelligence
from services.screener_engine import run_screener
from services.telegram_bot import send_telegram_alert
from services.signal_presenter import get_signal_presenter
from services.logger import log_info, log_warning, log_exception


def run_daily_market_scan():
    log_info("Daily market scan started")

    market = get_market_intelligence()
    results = run_screener()
    top = results[0] if results else None

    report = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "market": market["market_status"],
        "average_change": market["average_change"],
        "stocks_scanned": len(results),
        "top_pick": top,
    }

    log_info(
        f"Daily market scan completed: "
        f"{len(results)} stocks scanned, "
        f"top pick={top['symbol'] if top else 'none'}"
    )

    return report
def run_daily_automation():
    try:
        report = run_daily_market_scan()
        message = (
            get_signal_presenter()
            .build_telegram_digest(limit=5)
        )
        telegram = send_telegram_alert(message)

        if telegram.get("sent"):
            log_info("Daily Telegram market report sent successfully")
        else:
            log_warning(f"Telegram report failed: {telegram}")

        return {
            "report": report,
            "telegram": telegram,
        }

    except Exception:
        log_exception("Daily automation failed")
        raise
