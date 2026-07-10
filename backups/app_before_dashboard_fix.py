from flask import Flask, render_template, jsonify
from datetime import datetime
from services.dashboard_engine import build_dashboard
from services.ai_committee import run_committee
from services.market_data import get_market_snapshot
from services.technical_analysis import analyze_market
from services.portfolio import get_portfolio
from services.telegram_bot import telegram_status, send_telegram_alert
from services.autonomous_assistant import autonomous_decision


from services.market_engine import (
    get_market_intelligence,
    get_symbol_history,
    scan_import_folder,
)
from services.indicator_engine import analyze_symbol
from services.chart_engine import get_chart_data

app = Flask(__name__)
VERSION = "10.4 Enterprise"

@app.route("/")
def dashboard():
    dashboard = build_dashboard()

    return render_template(
        "dashboard.html",
        version=VERSION,
        dashboard=dashboard,
        market=dashboard["market"],
        picks=dashboard["top_picks"],
        portfolio=dashboard["portfolio"],
        now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        system_status="Online",)

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

@app.route("/")
def dashboard():
    dashboard_data = build_dashboard()

    return render_template(
        "dashboard.html",
        version=VERSION,
        dashboard=dashboard_data,
        market=dashboard_data["market"],
        picks=dashboard_data["top_picks"],
        portfolio=dashboard_data["portfolio"],
        now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        system_status="Online",
    )@app.route("/health")
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


@app.route("/api/v11.2/market")
def v112_market():
    return jsonify(get_market_intelligence())


@app.route("/api/v11.2/stock/<symbol>")
def v112_stock(symbol):
    analysis = analyze_symbol(symbol.upper())

    if not analysis:
        return jsonify({"error": "Symbol not found"}), 404

    return jsonify(analysis)


@app.route("/api/v11.2/chart/<symbol>")
def v112_chart(symbol):
    chart = get_chart_data(symbol.upper(), 120)

    if not chart:
        return jsonify({"error": "Symbol not found"}), 404

    return jsonify(chart)


@app.route("/api/v11.2/history/<symbol>")
def v112_history(symbol):
    result = get_symbol_history(symbol.upper(), 260)

    if not result:
        return jsonify({"error": "Symbol not found"}), 404

    return jsonify(result)


@app.route("/api/v11.2/import", methods=["POST"])
def v112_import():
    return jsonify(scan_import_folder())


@app.route("/stocks/<symbol>")
def stock_detail(symbol):
    symbol = symbol.upper()
    analysis = analyze_symbol(symbol)
    chart = get_chart_data(symbol, 120)

    if not analysis or not chart:
        return jsonify({"error": "Symbol not found"}), 404

    return render_template(
        "stocks/detail.html",
        version=VERSION,
        analysis=analysis,
        chart=chart,
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
