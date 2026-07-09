from flask import Flask, render_template, jsonify
from datetime import datetime

from services.ai_committee import run_committee
from services.market_data import get_market_snapshot
from services.technical_analysis import analyze_market
from services.portfolio import get_portfolio
from services.telegram_bot import telegram_status, send_telegram_alert
from services.autonomous_assistant import autonomous_decision

app = Flask(__name__)
VERSION = "10.4 Enterprise"

@app.route("/")
def dashboard():
    market = get_market_snapshot()
    technicals = analyze_market(market["stocks"])
    committee = run_committee()
    portfolio = get_portfolio()
    assistant = autonomous_decision(market, committee, portfolio, technicals)

    return render_template(
        "dashboard.html",
        version=VERSION,
        now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        system_status="Online",
        telegram_status=telegram_status(),
        market=market,
        technicals=technicals,
        committee=committee,
        portfolio=portfolio,
        assistant=assistant
    )

@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "version": VERSION,
        "service": "NSE Signal Bot V10.4 Enterprise",
        "time": datetime.now().isoformat()
    })

@app.route("/market")
def market():
    return jsonify(get_market_snapshot())

@app.route("/technicals")
def technicals():
    market = get_market_snapshot()
    return jsonify(analyze_market(market["stocks"]))

@app.route("/committee")
def committee():
    return jsonify(run_committee())

@app.route("/portfolio")
def portfolio():
    return jsonify(get_portfolio())

@app.route("/assistant")
def assistant():
    market = get_market_snapshot()
    technicals = analyze_market(market["stocks"])
    committee = run_committee()
    portfolio = get_portfolio()
    return jsonify(autonomous_decision(market, committee, portfolio, technicals))

@app.route("/telegram/test")
def telegram_test():
    result = send_telegram_alert("NSE Signal Bot V10.4 test alert: system online.")
    return jsonify(result)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
