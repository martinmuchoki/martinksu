from datetime import datetime
from pathlib import Path

REPORT_DIR = Path("reports")
REPORT_DIR.mkdir(exist_ok=True)

def generate_daily_report(market, committee, portfolio, assistant):
    content = f"""
NSE Signal Bot V10.5 Daily Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Market Status: {market['market_status']}
Average Change: {market['average_change']}%

AI Committee Decision: {committee['final_decision']}
Confidence: {committee['confidence']}%

Portfolio Value: KSh {portfolio['total_value']}
Portfolio P/L: {portfolio['pnl_pct']}%

Autonomous Assistant:
{assistant['summary']}

Top Opportunities:
"""
    for item in assistant["ranked_opportunities"]:
        content += f"- {item['symbol']}: {item['signal']} | Score {item['score']} | RSI {item['rsi']}\n"

    path = REPORT_DIR / "daily_report_v10_5.txt"
    path.write_text(content)
    return {"path": str(path), "content": content}
