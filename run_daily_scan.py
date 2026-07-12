from __future__ import annotations

from pprint import pprint

from services.institutional_brief import send_institutional_brief
from services.market_data import get_market_snapshot
from services.performance_engine import (
    evaluate_recommendations,
    get_performance_summary,
)
from services.portfolio_optimizer import build_optimized_portfolio
from services.recommendation_tracker import save_recommendations
from services.scheduler_engine import run_daily_automation
from services.screener_engine import run_screener


def run_v113_daily_scan():
    automation = run_daily_automation()

    market = get_market_snapshot()
    screener = run_screener()

    tracking = save_recommendations(screener)
    evaluation = evaluate_recommendations()
    performance = get_performance_summary()

    optimizer = build_optimized_portfolio(
        screener,
        capital=100_000,
    )

    telegram = send_institutional_brief(
        market,
        screener,
        performance,
        optimizer,
    )

    return {
        "version": "11.3",
        "automation": automation,
        "market_status": market.get("market_status"),
        "ranked_results": len(screener),
        "tracking": tracking,
        "evaluation": evaluation,
        "performance": performance,
        "optimizer": optimizer,
        "telegram": telegram,
    }


if __name__ == "__main__":
    pprint(run_v113_daily_scan())
