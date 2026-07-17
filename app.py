from pathlib import Path
import os
from functools import wraps

from dotenv import load_dotenv
from werkzeug.security import check_password_hash

from flask import Flask, render_template, jsonify, request, redirect, send_file, session, url_for, send_from_directory
from datetime import datetime
from services.dashboard_engine import build_dashboard
from services.ai_committee import run_committee
from services.market_data import get_market_snapshot
from services.technical_analysis import analyze_market
from services.portfolio import get_portfolio
from services.telegram_bot import telegram_status, send_telegram_alert
from services.autonomous_assistant import autonomous_decision
from services.screener_engine import run_screener
from services.dashboard_charts import (
    get_dashboard_chart_data,
    get_market_breadth,
)
from services.reports import generate_daily_report
from services.prediction_center import build_prediction_center
from services.ai_investment_committee import build_ai_investment_committee
from services.predictive_engine import build_predictions
from services.risk_engine import (
    build_market_risk,
    stock_risk_metrics,
)
from services.quant_intelligence import (
    detect_market_regime,
    analyze_sector_rotation,
)
from services.performance_engine import (
    evaluate_recommendations,
    get_performance_summary,
    get_recent_performance,
)
from services.portfolio_optimizer import build_optimized_portfolio

from services.market_engine import (
    get_market_intelligence,
    get_symbol_history,
    scan_import_folder,
)
from services.indicator_engine import analyze_symbol
from services.chart_engine import get_chart_data

from services.portfolio_transactions import (
    buy_shares,
    sell_shares,
    get_transactions,
    get_cash_summary,
)
load_dotenv("/root/nse_signal_bot_v10_3/.env")

app = Flask(__name__)
app.secret_key = os.getenv("MIP_SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("MIP_SECRET_KEY is missing from .env")

PUBLIC_ENDPOINTS = {
    "login",
    "health",
    "static",
    "pwa_manifest",
    "pwa_service_worker",
    "pwa_offline",
}


@app.before_request
def require_authentication():
    endpoint = request.endpoint

    if endpoint is None:
        return None

    if endpoint in PUBLIC_ENDPOINTS:
        return None

    if session.get("authenticated"):
        return None

    if request.path.startswith("/api/"):
        return jsonify({
            "error": "authentication_required",
            "message": "Please sign in to MIP PRO.",
        }), 401

    return redirect(url_for("login", next=request.path))


from services.learning_engine import (
    apply_adaptive_confidence,
    get_learning_summary,
)
from services.control_center import get_control_center_status

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("authenticated"):
        return redirect(url_for("dashboard"))

    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        expected_username = os.getenv(
            "MIP_ADMIN_USERNAME",
            "admin",
        )

        password_hash = os.getenv(
            "MIP_ADMIN_PASSWORD_HASH",
            "",
        )

        if (
            username == expected_username
            and password_hash
            and check_password_hash(password_hash, password)
        ):
            session.clear()
            session["authenticated"] = True
            session["username"] = username
            session.permanent = True

            destination = request.args.get("next")

            if (
                not destination
                or not destination.startswith("/")
                or destination.startswith("//")
            ):
                destination = url_for("dashboard")

            return redirect(destination)

        error = "Incorrect username or password."

    return render_template(
        "login.html",
        error=error,
        version="11.5",
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/about")
def about():
    return render_template(
        "about.html",
        version="11.5",
    )

VERSION = "11.6.3 Android PWA"

@app.route("/")
def dashboard():
    dashboard_data = build_dashboard()
    screener = run_screener()
    market = get_market_snapshot()
    try:
        technicals = analyze_market(market["stocks"])
    except Exception as exc:
        print(f"Technical analysis skipped: {exc}")
        technicals = []
    portfolio = get_portfolio()
    committee = run_committee(
        market=market,
        technicals=technicals,
        portfolio=portfolio,
    )
    assistant = autonomous_decision(
        market,
        committee,
        portfolio,
        technicals,
    )

    transactions = get_transactions(20)
    cash_summary = get_cash_summary()

    logo_available = Path(
        "static/images/mip_pro_logo.png"
    ).exists()

    evaluate_recommendations()
    performance = get_performance_summary()

    learning = get_learning_summary(
        evaluate_first=False
    )

    optimizer_capital = max(
        float(cash_summary.get("cash_balance", 0) or 0),
        100000,
    )

    optimized_portfolio = build_optimized_portfolio(
        screener,
        capital=optimizer_capital,
    )

    risk_metrics = build_market_risk(
        market.get("stocks", [])
    )

    regime = detect_market_regime(
        market,
        technicals,
        risk_metrics,
    )

    sector_rotation = analyze_sector_rotation(
        market.get("stocks", [])
    )

    predictions = build_predictions(
        market.get("stocks", []),
        technicals,
        limit=len(market.get("stocks", [])),
    )

    return render_template(
        "dashboard_v115.html",
        version=VERSION,
        dashboard=dashboard_data,
        picks=dashboard_data["top_picks"],
        market=market,
        technicals=technicals,
        committee=committee,
        assistant=assistant,
        portfolio=portfolio,
        screener=screener,
        telegram_status=telegram_status(),
        now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        system_status="Online",
        transactions=transactions,
        cash_summary=cash_summary,
        logo_available=logo_available,
        performance=performance,
        learning=learning,
        optimized_portfolio=optimized_portfolio,
        risk_metrics=risk_metrics,
        regime=regime,
        sector_rotation=sector_rotation,
        predictions=predictions,
    )


@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "version": VERSION,
        "service": "MIP PRO",
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
    result = send_telegram_alert("Market Intelligence Platform V10.4 test alert: system online.")
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
    symbol = symbol.strip().upper()

    analysis = None
    chart = None
    error = None

    try:
        analysis = analyze_symbol(symbol)
    except Exception as exc:
        error = (
            f"Technical analysis is still collecting enough "
            f"history for {symbol}: {exc}"
        )

    try:
        chart = get_chart_data(symbol, 120)
    except Exception as exc:
        if error:
            error += f" Chart data is also unavailable: {exc}"
        else:
            error = f"Chart data is currently unavailable for {symbol}: {exc}"

    if not analysis and not chart:
        return render_template(
            "stocks/detail.html",
            version=VERSION,
            symbol=symbol,
            analysis=None,
            chart=None,
            error=error or f"No data is currently available for {symbol}.",
        ), 200

    return render_template(
        "stocks/detail.html",
        version=VERSION,
        symbol=symbol,
        analysis=analysis,
        chart=chart,
        error=error,
    )



@app.route("/screener")
def screener():
    results = run_screener()

    return render_template(
        "screener.html",
        version=VERSION,
        results=results,
    )



@app.route("/api/v11.3/performance")
def v113_performance():
    evaluate_recommendations()

    return jsonify({
        "summary": get_performance_summary(),
        "recent": get_recent_performance(100),
    })


@app.route("/api/v11.3/optimizer")
def v113_optimizer():
    results = run_screener()
    capital = request.args.get("capital", default=100000, type=float)

    return jsonify(
        build_optimized_portfolio(
            results,
            capital=capital,
        )
    )




@app.route("/api/v11.4/predictions")
def v114_predictions():
    market = get_market_snapshot()
    technicals = analyze_market(
        market.get("stocks", [])
    )

    return jsonify(
        build_predictions(
            market.get("stocks", []),
            technicals,
            limit=request.args.get(
                "limit",
                default=20,
                type=int,
            ),
        )
    )


@app.route("/api/v11.4/risk")
def v114_risk():
    market = get_market_snapshot()

    return jsonify(
        build_market_risk(
            market.get("stocks", [])
        )
    )


@app.route("/api/v11.4/risk/<symbol>")
def v114_symbol_risk(symbol):
    return jsonify(
        stock_risk_metrics(symbol.upper())
    )


@app.route("/api/v11.4/regime")
def v114_regime():
    market = get_market_snapshot()

    technicals = analyze_market(
        market.get("stocks", [])
    )

    risk = build_market_risk(
        market.get("stocks", [])
    )

    return jsonify(
        detect_market_regime(
            market,
            technicals,
            risk,
        )
    )


@app.route("/api/v11.4/sectors")
def v114_sectors():
    market = get_market_snapshot()

    return jsonify(
        analyze_sector_rotation(
            market.get("stocks", [])
        )
    )




@app.route("/download_report")
def download_report():
    market = get_market_snapshot()
    technicals = analyze_market(market.get("stocks", []))
    portfolio = get_portfolio()

    committee = run_committee(
        market=market,
        technicals=technicals,
        portfolio=portfolio,
    )

    assistant = autonomous_decision(
        market,
        committee,
        portfolio,
        technicals,
    )

    report = generate_daily_report(
        market,
        committee,
        portfolio,
        assistant,
    )

    return send_file(
        report["path"],
        as_attachment=True,
        download_name="MIP_PRO_Daily_Intelligence_Report_v11_5_Production.pdf",
        mimetype="application/pdf",
    )


@app.route("/api/v11.4/daily-report")
def v114_daily_report():
    market = get_market_snapshot()
    technicals = analyze_market(market.get("stocks", []))
    portfolio = get_portfolio()

    committee = run_committee(
        market=market,
        technicals=technicals,
        portfolio=portfolio,
    )

    assistant = autonomous_decision(
        market,
        committee,
        portfolio,
        technicals,
    )

    return jsonify(
        generate_daily_report(
            market,
            committee,
            portfolio,
            assistant,
        )
    )




@app.route("/api/v11.5/dashboard-charts")
def v115_dashboard_charts():
    symbol = request.args.get(
        "symbol",
        default="SCOM",
        type=str,
    )

    return jsonify(
        get_dashboard_chart_data(
            symbol=symbol.upper(),
        )
    )


@app.route("/api/v11.5/market-breadth")
def v115_market_breadth():
    return jsonify(get_market_breadth())


@app.route("/api/v11.5/screener-data")
def v115_screener_data():
    return jsonify(run_screener())




@app.route("/api/v11.6/learning")
def v116_learning():
    return jsonify(
        get_learning_summary()
    )


@app.route(
    "/api/v11.6/adaptive-confidence/<int:confidence>"
)
def v116_adaptive_confidence(confidence):
    learning = get_learning_summary(
        evaluate_first=False
    )

    return jsonify({
        "original_confidence": confidence,
        "adaptive_confidence":
            apply_adaptive_confidence(
                confidence,
                learning,
            ),
        "adjustment":
            learning["confidence_adjustment"],
        "learning_status":
            learning["status"],
        "evaluations":
            learning["evaluations"],
    })






@app.route("/control-center")
def control_center():
    return render_template(
        "control_center.html",
        version=VERSION,
        control=get_control_center_status(),
    )


@app.route("/api/v11.6.2/control-center")
@app.route("/api/v11.6.1/control-center")
def v1161_control_center():
    return jsonify(
        get_control_center_status()
    )


@app.route("/portfolio/buy", methods=["POST"])
def portfolio_buy():
    try:
        buy_shares(
            request.form["symbol"],
            request.form["shares"],
            request.form["price"],
        )
        return redirect("/?portfolio=buy-success")

    except Exception as exc:
        return redirect(f"/?portfolio_error={str(exc)}")


@app.route("/portfolio/sell", methods=["POST"])
def portfolio_sell():
    try:
        sell_shares(
            request.form["symbol"],
            request.form["shares"],
            request.form["price"],
        )
        return redirect("/?portfolio=sell-success")

    except Exception as exc:
        return redirect(f"/?portfolio_error={str(exc)}")


@app.route("/manifest.webmanifest")
def pwa_manifest():
    response = send_from_directory(
        "static/pwa",
        "manifest.webmanifest",
        mimetype="application/manifest+json",
    )
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@app.route("/service-worker.js")
def pwa_service_worker():
    response = send_from_directory(
        "static/pwa",
        "service-worker.js",
        mimetype="application/javascript",
    )
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Service-Worker-Allowed"] = "/"
    return response


@app.route("/offline")
def pwa_offline():
    return render_template("offline.html")




@app.route("/api/v11.6.4/prediction-center")
def v1164_prediction_center():
    try:
        return jsonify(
            build_prediction_center()
        )
    except Exception as exc:
        app.logger.exception(
            "Prediction Center build failed"
        )

        return jsonify({
            "error": "prediction_center_failed",
            "message": str(exc),
        }), 500




@app.route("/api/v11.7/investment-committee")
def v117_investment_committee():
    try:
        return jsonify(
            build_ai_investment_committee()
        )
    except Exception as exc:
        app.logger.exception(
            "AI Investment Committee failed"
        )

        return jsonify({
            "error": "investment_committee_failed",
            "message": str(exc),
        }), 500



if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )
