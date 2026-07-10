import os
import requests
from dotenv import load_dotenv

load_dotenv()

def telegram_status():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    return "Configured" if token and chat_id else "Not configured"

def send_telegram_alert(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        return {
            "sent": False,
            "message": "Telegram token or chat ID missing."
        }

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    try:
        response = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            },
            timeout=15
        )

        return {
            "sent": response.ok,
            "status_code": response.status_code,
            "response": response.text[:300]
        }

    except Exception as e:
        return {
            "sent": False,
            "error": str(e)
        }

def build_market_alert(committee, assistant, portfolio):
    return f"""
<b>NSE Signal Bot V11 Alert</b>

Decision: <b>{committee['final_decision']}</b>
Confidence: <b>{committee['confidence']}%</b>

Assistant: <b>{assistant['action']}</b>
{assistant['summary']}

Portfolio Value: KSh {portfolio['total_value']}
P/L: {portfolio['pnl_pct']}%

Best Opportunity:
{assistant['best_opportunity']['symbol'] if assistant.get('best_opportunity') else 'None'}
"""
