from pathlib import Path
import os
from functools import wraps

from dotenv import load_dotenv
from werkzeug.security import check_password_hash

from flask import Flask, render_template, jsonify, request, redirect, send_file, session, url_for, send_from_directory
from services.decision_engine import get_ai_decision
from services.dashboard_context_builder import DashboardContextBuilder

# BEGIN MIP PRO ZIIDI COPILOT IMPORTS
from services.ziidi_copilot import (
    ZiidiTradeError,
    get_portfolio_summary as get_ziidi_portfolio_summary,
    get_positions as get_ziidi_positions,
    get_trade_history as get_ziidi_trade_history,
    init_ziidi_schema,
    record_trade as record_ziidi_trade,
)
# END MIP PRO ZIIDI COPILOT IMPORTS

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
from services.intelligence_orchestrator import (
    get_prediction_center,
    get_investment_committee,
)
from services.signal_service import get_signal_service
from services.signal_presenter import get_signal_presenter
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

from services.intelligence_analytics import (
    get_dashboard_summary,
    get_engine_statistics,
    get_market_regime_statistics,
    get_recommendation_statistics,
)


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

from services.investment_settings import (
    get_settings,
    update_settings,
)

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

VERSION = "11.6.4 RC3"

@app.route("/")
def dashboard():
    dashboard_result = DashboardContextBuilder(
        version=VERSION,
        logger=app.logger,
    ).build(
        ui=request.args.get("ui"),
    )

    return render_template(
        dashboard_result["template_name"],
        **dashboard_result["data"],
    )


@app.route("/api/v11.7/decision")
def v117_decision():
    """
    Return the authoritative Version 11.7 Decision Object.
    """
    market = get_market_snapshot()

    try:
        technicals = analyze_market(
            market.get("stocks", [])
        )
    except Exception:
        app.logger.exception(
            "Decision API technical analysis failed"
        )
        technicals = []

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

    try:
        persisted_signals = (
            get_signal_service()
            .get_top_signals(limit=10)
        )

        persisted_signal_summary = (
            get_signal_service()
            .get_dashboard_summary(limit=10)
        )
    except Exception:
        app.logger.exception(
            "Decision API SignalService read failed"
        )
        persisted_signals = []
        persisted_signal_summary = {
            "average_confidence": 0,
        }

    decision = get_ai_decision(
        signals=persisted_signals,
        market={
            "status": (
                regime.get(
                    "label",
                    regime.get(
                        "regime",
                        regime.get(
                            "market_regime",
                            "Neutral / Selective",
                        ),
                    ),
                )
                if isinstance(regime, dict)
                else str(
                    regime or "Neutral / Selective"
                )
            ),
            "ai_confidence": (
                persisted_signal_summary.get(
                    "average_confidence",
                    0,
                )
            ),
        },
        regime=(
            regime
            if isinstance(regime, dict)
            else {
                "label": str(
                    regime or "Neutral / Selective"
                )
            }
        ),
        risk_metrics=(
            risk_metrics
            if isinstance(risk_metrics, dict)
            else {
                "risk_level": str(
                    risk_metrics or "UNKNOWN"
                )
            }
        ),
        breadth=get_market_breadth(),
        institutional=(
            sector_rotation
            if isinstance(sector_rotation, dict)
            else {}
        ),
    )

    return jsonify(decision)


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
    """
    Send a Telegram digest built exclusively from finalized,
    persisted AI Investment Committee signals.

    SignalPresenter owns message formatting while
    send_telegram_alert remains the transport layer.
    """
    digest = (
        get_signal_presenter()
        .build_telegram_digest(limit=5)
    )

    result = send_telegram_alert(digest)

    return jsonify({
        **result,
        "source": "SignalRepository via SignalService",
        "signal_format": "persisted_committee_digest",
    })


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





# BEGIN MIP PRO ZIIDI COPILOT ROUTES
@app.route("/ziidi-copilot", methods=["GET", "POST"])
def ziidi_copilot():
    from datetime import date
    from services.investment_settings import (
        get_settings,
        update_settings,
    )

    init_ziidi_schema()

    settings = get_settings()

    message = request.args.get("message", "").strip()
    error = ""


    if (
        request.method == "POST"
        and request.form.get("form_action") == "settings"
    ):
        try:
            update_settings(
                broker=request.form.get(
                    "broker",
                    settings.get("broker", "Ziidi"),
                ),
                charge_rate=request.form.get(
                    "charge_rate",
                    settings.get("charge_rate", 1.5),
                ),
                auto_calculate=request.form.get(
                    "auto_calculate",
                    "1",
                ),
                manual_override=request.form.get(
                    "manual_override",
                    "0",
                ),
                currency=request.form.get(
                    "currency",
                    settings.get("currency", "KES"),
                ),
                settlement=request.form.get(
                    "settlement",
                    settings.get("settlement", "T+3"),
                ),
            )

            return redirect(
                url_for(
                    "ziidi_copilot",
                    message="Investment settings saved successfully.",
                )
            )
        except Exception as exc:
            app.logger.exception(
                "Investment settings update failed"
            )
            error = (
                "Investment settings could not be saved. "
                f"Technical detail: {exc}"
            )

    if (
        request.method == "POST"
        and request.form.get(
            "form_action",
            "trade",
        ) == "trade"
    ):
        try:
            trade = record_ziidi_trade(
                request.form.to_dict()
            )

            return redirect(
                url_for(
                    "ziidi_copilot",
                    message=(
                        f'{trade["side"]} trade for '
                        f'{trade["quantity"]} '
                        f'{trade["symbol"]} shares saved.'
                    ),
                )
            )
        except ZiidiTradeError as exc:
            error = str(exc)
        except Exception as exc:
            app.logger.exception(
                "Ziidi trade recording failed"
            )
            error = (
                "The trade could not be saved. "
                f"Technical detail: {exc}"
            )

    settings = get_settings()

    return render_template(
        "investment_portfolio.html",
        investment_settings=settings,
        today=date.today().isoformat(),
        message=message,
        error=error,
        positions=get_ziidi_positions(),
        trades=get_ziidi_trade_history(limit=100),
        summary=get_ziidi_portfolio_summary(),
        version=VERSION,
    )






@app.route("/investment-settings", methods=["GET", "POST"])
def investment_settings_page():
    message = None
    error = None

    if request.method == "POST":
        try:
            update_settings(
                broker=request.form.get(
                    "broker",
                    "Ziidi",
                ),
                charge_rate=float(
                    request.form.get(
                        "charge_rate",
                        "1.50",
                    )
                ),
                auto_calculate=(
                    request.form.get(
                        "auto_calculate",
                        "1",
                    ) == "1"
                ),
                manual_override=(
                    request.form.get(
                        "manual_override",
                        "0",
                    ) == "1"
                ),
                currency=request.form.get(
                    "currency",
                    "KES",
                ),
                settlement=request.form.get(
                    "settlement",
                    "T+3",
                ),
            )

            message = "Investment settings saved successfully."

        except (TypeError, ValueError) as exc:
            error = str(exc)

        except Exception:
            app.logger.exception(
                "Investment settings page update failed"
            )
            error = "Investment settings could not be saved."

    return render_template(
        "investment_settings.html",
        settings=get_settings(),
        message=message,
        error=error,
        version=VERSION,
    )


@app.route("/api/v12/investment/settings", methods=["GET", "POST"])
def investment_settings_api():
    if request.method == "GET":
        return jsonify(get_settings())

    data = request.get_json(silent=True)

    if data is None:
        data = request.form.to_dict()

    try:
        update_settings(
            broker=str(data.get("broker", "Ziidi")).strip(),
            charge_rate=float(data.get("charge_rate", 1.50)),
            auto_calculate=str(
                data.get("auto_calculate", "1")
            ).strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
                "enabled",
            },
            manual_override=str(
                data.get("manual_override", "0")
            ).strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
                "enabled",
            },
            currency=str(data.get("currency", "KES")).strip(),
            settlement=str(data.get("settlement", "T+3")).strip(),
        )

        return jsonify(
            {
                "success": True,
                "settings": get_settings(),
            }
        )

    except (TypeError, ValueError) as exc:
        return jsonify(
            {
                "success": False,
                "error": str(exc),
            }
        ), 400

    except Exception as exc:
        app.logger.exception(
            "Failed to update investment settings"
        )

        return jsonify(
            {
                "success": False,
                "error": "Unable to update investment settings.",
            }
        ), 500


@app.route("/api/v12/ziidi/portfolio")
def api_v12_ziidi_portfolio():
    return jsonify(
        {
            "summary": get_ziidi_portfolio_summary(),
            "positions": get_ziidi_positions(),
        }
    )


@app.route("/api/v12/ziidi/trades")
def api_v12_ziidi_trades():
    return jsonify(
        {
            "trades": get_ziidi_trade_history(
                limit=200
            )
        }
    )
# END MIP PRO ZIIDI COPILOT ROUTES

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
            get_prediction_center()
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
            get_investment_committee()
        )
    except Exception as exc:
        app.logger.exception(
            "AI Investment Committee failed"
        )

        return jsonify({
            "error": "investment_committee_failed",
            "message": str(exc),
        }), 500






# ============================================================
# BEGIN MIP PRO SIGNAL SERVICE API
# ============================================================

@app.route("/api/v12/signals")
def v12_signals():
    """
    Return finalized persisted committee signals.

    Authentication is enforced by the application-wide
    require_authentication before-request handler.
    """

    try:
        limit = request.args.get(
            "limit",
            default=20,
            type=int,
        )

        signals = (
            get_signal_service()
            .get_latest_signals(limit=limit)
        )

        return jsonify({
            "version": "MIP PRO Signal API 1.0",
            "source": "signal_service",
            "count": len(signals),
            "signals": signals,
        })

    except Exception as exc:
        app.logger.exception(
            "Signal API latest-signals request failed"
        )

        return jsonify({
            "error": "signals_failed",
            "message": str(exc),
        }), 500


@app.route("/api/v12/signals/top")
def v12_top_signals():
    """Return the highest-ranked persisted signals."""

    try:
        limit = request.args.get(
            "limit",
            default=10,
            type=int,
        )

        signals = (
            get_signal_service()
            .get_top_signals(limit=limit)
        )

        return jsonify({
            "version": "MIP PRO Signal API 1.0",
            "source": "signal_service",
            "count": len(signals),
            "signals": signals,
        })

    except Exception as exc:
        app.logger.exception(
            "Signal API top-signals request failed"
        )

        return jsonify({
            "error": "top_signals_failed",
            "message": str(exc),
        }), 500


@app.route("/api/v12/signals/summary")
def v12_signal_summary():
    """Return repository-backed signal statistics."""

    try:
        limit = request.args.get(
            "limit",
            default=20,
            type=int,
        )

        return jsonify(
            get_signal_service().get_dashboard_summary(
                limit=limit,
            )
        )

    except Exception as exc:
        app.logger.exception(
            "Signal API summary request failed"
        )

        return jsonify({
            "error": "signal_summary_failed",
            "message": str(exc),
        }), 500


@app.route("/api/v12/signals/<symbol>")
def v12_signal_by_symbol(symbol):
    """Return the persisted signal for one NSE symbol."""

    normalized_symbol = str(
        symbol or ""
    ).strip().upper()

    try:
        signal = (
            get_signal_service()
            .get_signal(normalized_symbol)
        )

        if signal is None:
            return jsonify({
                "error": "signal_not_found",
                "symbol": normalized_symbol,
            }), 404

        return jsonify({
            "version": "MIP PRO Signal API 1.0",
            "source": "signal_service",
            "signal": signal,
        })

    except Exception as exc:
        app.logger.exception(
            "Signal API lookup failed for %s",
            normalized_symbol,
        )

        return jsonify({
            "error": "signal_lookup_failed",
            "symbol": normalized_symbol,
            "message": str(exc),
        }), 500


# ============================================================
# END MIP PRO SIGNAL SERVICE API
# ============================================================

# ============================================================
# BEGIN MIP PRO INTELLIGENCE ANALYTICS API
# ============================================================

@app.route("/api/v11.7/intelligence/summary")
def v117_intelligence_summary():
    try:
        return jsonify(
            get_dashboard_summary()
        )
    except Exception as exc:
        app.logger.exception(
            "Intelligence analytics summary failed"
        )

        return jsonify({
            "error": "intelligence_summary_failed",
            "message": str(exc),
        }), 500


@app.route("/api/v11.7/intelligence/performance")
def v117_intelligence_performance():
    try:
        return jsonify(
            get_engine_statistics()
        )
    except Exception as exc:
        app.logger.exception(
            "Intelligence performance analytics failed"
        )

        return jsonify({
            "error": "intelligence_performance_failed",
            "message": str(exc),
        }), 500


@app.route("/api/v11.7/intelligence/recommendations")
def v117_intelligence_recommendations():
    try:
        return jsonify(
            get_recommendation_statistics()
        )
    except Exception as exc:
        app.logger.exception(
            "Intelligence recommendation analytics failed"
        )

        return jsonify({
            "error": "intelligence_recommendations_failed",
            "message": str(exc),
        }), 500


@app.route("/api/v11.7/intelligence/regimes")
def v117_intelligence_regimes():
    try:
        return jsonify(
            get_market_regime_statistics()
        )
    except Exception as exc:
        app.logger.exception(
            "Intelligence regime analytics failed"
        )

        return jsonify({
            "error": "intelligence_regimes_failed",
            "message": str(exc),
        }), 500


# ============================================================
# END MIP PRO INTELLIGENCE ANALYTICS API
# ============================================================


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )

# ============================================================
# PHASE 8.4D CONSENSUS INTELLIGENCE
# ============================================================

@app.route("/api/v12/consensus-intelligence", methods=["GET"])
def api_v12_consensus_intelligence():
    """
    Return persisted AI Investment Committee consensus analytics.

    Phase 8.4D:
    - summary metrics
    - consensus distribution
    - risk veto totals
    - latest per-symbol consensus decisions
    """
    try:
        from flask import jsonify
        from services.signal_repository import get_signal_repository

        repository = get_signal_repository()
        signals = repository.get_all_signals()

        if not isinstance(signals, list):
            signals = []

        def safe_float(value, default=0.0):
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        def safe_int(value, default=0):
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        def normalize_alignment(value):
            alignment = str(value or "UNKNOWN").strip().upper()

            aliases = {
                "HIGH": "STRONG",
                "STRONG CONSENSUS": "STRONG",
                "MEDIUM": "MODERATE",
                "MODERATE CONSENSUS": "MODERATE",
                "LOW": "WEAK",
                "WEAK CONSENSUS": "WEAK",
            }

            return aliases.get(alignment, alignment)

        consensus_rows = []
        alignment_counts = {
            "STRONG": 0,
            "MODERATE": 0,
            "WEAK": 0,
            "UNKNOWN": 0,
        }

        risk_veto_count = 0
        consensus_scores = []

        for signal in signals:
            if not isinstance(signal, dict):
                continue

            symbol = str(signal.get("symbol") or "").strip()

            if not symbol:
                continue

            alignment = normalize_alignment(
                signal.get("consensus_alignment")
            )

            if alignment not in alignment_counts:
                alignment_counts[alignment] = 0

            alignment_counts[alignment] += 1

            risk_veto = bool(
                signal.get("consensus_risk_veto", False)
            )

            if risk_veto:
                risk_veto_count += 1

            consensus_score = safe_float(
                signal.get("consensus_score"),
                0.0,
            )

            consensus_scores.append(consensus_score)

            conflicting = signal.get(
                "conflicting_committees",
                [],
            )

            if not isinstance(conflicting, list):
                conflicting = []

            consensus_rows.append(
                {
                    "symbol": symbol,
                    "decision": str(
                        signal.get("decision")
                        or signal.get("signal")
                        or "HOLD"
                    ).strip().upper(),
                    "consensus_formula_version":
                        signal.get(
                            "consensus_formula_version",
                            "8.4",
                        ),
                    "consensus_score":
                        round(consensus_score, 2),
                    "consensus_alignment":
                        alignment,
                    "consensus_confidence":
                        round(
                            safe_float(
                                signal.get(
                                    "consensus_confidence"
                                ),
                                0.0,
                            ),
                            2,
                        ),
                    "consensus_conviction":
                        str(
                            signal.get(
                                "consensus_conviction"
                            )
                            or "UNKNOWN"
                        ).strip().upper(),
                    "decision_stability":
                        str(
                            signal.get(
                                "decision_stability"
                            )
                            or "UNKNOWN"
                        ).strip().upper(),
                    "committee_agreement":
                        safe_int(
                            signal.get(
                                "committee_agreement"
                            ),
                            0,
                        ),
                    "committee_disagreement":
                        safe_int(
                            signal.get(
                                "committee_disagreement"
                            ),
                            0,
                        ),
                    "committee_total":
                        safe_int(
                            signal.get(
                                "committee_agreement"
                            ),
                            0,
                        )
                        + safe_int(
                            signal.get(
                                "committee_disagreement"
                            ),
                            0,
                        ),
                    "consensus_risk_veto":
                        risk_veto,
                    "conflicting_committees":
                        conflicting,
                    "consensus_explanation":
                        str(
                            signal.get(
                                "consensus_explanation"
                            )
                            or ""
                        ).strip(),
                    "timestamp":
                        signal.get("timestamp"),
                    "stored_at":
                        signal.get("stored_at"),
                }
            )

        consensus_rows.sort(
            key=lambda item: (
                item.get("consensus_score", 0.0),
                item.get("consensus_confidence", 0.0),
            ),
            reverse=True,
        )

        average_score = (
            sum(consensus_scores) / len(consensus_scores)
            if consensus_scores
            else 0.0
        )

        return jsonify(
            {
                "version":
                    "12.0 Consensus Intelligence API",
                "phase":
                    "8.4D",
                "status":
                    "ok",
                "stock_count":
                    len(consensus_rows),
                "summary": {
                    "average_consensus_score":
                        round(average_score, 2),
                    "strong_consensus_count":
                        alignment_counts.get(
                            "STRONG",
                            0,
                        ),
                    "moderate_consensus_count":
                        alignment_counts.get(
                            "MODERATE",
                            0,
                        ),
                    "weak_consensus_count":
                        alignment_counts.get(
                            "WEAK",
                            0,
                        ),
                    "risk_veto_count":
                        risk_veto_count,
                    "alignment_distribution":
                        alignment_counts,
                },
                "signals":
                    consensus_rows,
            }
        )

    except Exception as exc:
        app.logger.exception(
            "Phase 8.4D consensus intelligence failed"
        )

        return jsonify(
            {
                "version":
                    "12.0 Consensus Intelligence API",
                "phase":
                    "8.4D",
                "status":
                    "error",
                "error":
                    str(exc),
                "stock_count":
                    0,
                "summary": {},
                "signals": [],
            }
        ), 500

