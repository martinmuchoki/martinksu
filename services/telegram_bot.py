from dotenv import load_dotenv
load_dotenv("/root/nse_signal_bot_v10_3/.env")
import os
import requests

def telegram_status():
    if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
        return "Configured"
    return "Not configured"

def send_telegram_alert(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return {"sent": False, "message": "Telegram token or chat ID missing."}

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    response = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
    return {"sent": response.ok, "status_code": response.status_code}
