#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT="/root/nse_signal_bot_v10_3"
STAMP="$(date +%Y-%m-%d_%H-%M-%S)"
BACKUP="$PROJECT/backups/v11_4_$STAMP"
LOG="$PROJECT/logs/upgrade_v11_4_$STAMP.log"

cd "$PROJECT"
mkdir -p "$BACKUP/templates" "$BACKUP/services" "$PROJECT/logs"

exec > >(tee -a "$LOG") 2>&1

rollback() {
    echo "Upgrade failed — restoring V11.3 files."

    [ -f "$BACKUP/app.py" ] &&
        cp "$BACKUP/app.py" "$PROJECT/app.py"

    [ -f "$BACKUP/run_daily_scan.py" ] &&
        cp "$BACKUP/run_daily_scan.py" "$PROJECT/run_daily_scan.py"

    [ -f "$BACKUP/templates/dashboard.html" ] &&
        cp "$BACKUP/templates/dashboard.html" \
           "$PROJECT/templates/dashboard.html"

    rm -f \
        services/predictive_engine.py \
        services/risk_engine.py \
        services/quant_intelligence.py \
        test_v11_4.py

    "$PROJECT/restart.sh" || true
    exit 1
}

trap rollback ERR

echo "=========================================="
echo "Market Intelligence Platform V11.4"
echo "=========================================="

echo "Step 1: Backing up V11.3..."

cp app.py "$BACKUP/app.py"
cp run_daily_scan.py "$BACKUP/run_daily_scan.py"
cp templates/dashboard.html \
   "$BACKUP/templates/dashboard.html"

echo "Step 2: Installing predictive engine..."

cat > services/predictive_engine.py <<'PY'
from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any, Dict, List

from services.market_data import get_price_history
from services.technical_analysis import safe_float


def _returns(symbol: str) -> List[float]:
    history = get_price_history(symbol, 260)

    closes = [
        safe_float(row.get("close"))
        for row in history
        if safe_float(row.get("close")) > 0
    ]

    return [
        (current / previous) - 1
        for previous, current in zip(closes, closes[1:])
        if previous > 0
    ]


def predict_stock(
    stock: Dict[str, Any],
    technical: Dict[str, Any],
) -> Dict[str, Any]:
    symbol = str(stock.get("symbol") or "").upper()
    price = safe_float(stock.get("price"))
    change_pct = safe_float(stock.get("change_pct"))
    score = safe_float(technical.get("score"), 50)

    returns = _returns(symbol)

    if len(returns) >= 5:
        volatility = pstdev(returns) * math.sqrt(252) * 100
        recent_return = mean(returns[-20:]) * 100
        mode = "HISTORICAL HEURISTIC"
    else:
        volatility = max(abs(change_pct) * 4, 12)
        recent_return = change_pct / 10
        mode = "LIVE SNAPSHOT HEURISTIC"

    expected_return = (
        ((score - 50) / 8)
        + (change_pct * 0.55)
        + (recent_return * 4)
    )

    expected_return = max(-15, min(25, expected_return))

    probability = (
        50
        + ((score - 50) * 0.65)
        + (change_pct * 1.8)
    )

    probability = max(20, min(92, probability))

    if score >= 80:
        holding_days = 20
    elif score >= 65:
        holding_days = 15
    elif score >= 50:
        holding_days = 10
    else:
        holding_days = 5

    expected_drawdown = -max(
        2,
        min(
            20,
            (volatility / math.sqrt(252))
            * math.sqrt(holding_days),
        ),
    )

    target_price = (
        price * (1 + expected_return / 100)
        if price > 0
        else 0
    )

    return {
        "symbol": symbol,
        "name": stock.get("name"),
        "sector": stock.get("sector"),
        "price": round(price, 2),
        "signal": technical.get("signal", "HOLD"),
        "score": int(score),
        "expected_return_pct": round(expected_return, 2),
        "probability_success_pct": round(probability, 2),
        "holding_period_days": holding_days,
        "target_price": round(target_price, 2),
        "maximum_expected_drawdown_pct": round(
            expected_drawdown,
            2,
        ),
        "annualized_volatility_pct": round(volatility, 2),
        "model_mode": mode,
        "disclaimer": (
            "Heuristic estimate — not a guaranteed outcome."
        ),
    }


def build_predictions(
    stocks: List[Dict[str, Any]],
    technicals: List[Dict[str, Any]],
    limit: int = 20,
) -> List[Dict[str, Any]]:
    technical_map = {
        item.get("symbol"): item
        for item in technicals
        if isinstance(item, dict) and item.get("symbol")
    }

    predictions = [
        predict_stock(
            stock,
            technical_map.get(stock.get("symbol"), {}),
        )
        for stock in stocks
    ]

    predictions.sort(
        key=lambda item: (
            item["probability_success_pct"],
            item["expected_return_pct"],
            item["score"],
        ),
        reverse=True,
    )

    return predictions[:limit]
PY

echo "Step 3: Installing institutional risk engine..."

cat > services/risk_engine.py <<'PY'
from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any, Dict, List

from services.market_data import get_price_history
from services.technical_analysis import safe_float


def _returns(symbol: str) -> List[float]:
    history = get_price_history(symbol, 260)

    closes = [
        safe_float(row.get("close"))
        for row in history
        if safe_float(row.get("close")) > 0
    ]

    return [
        (current / previous) - 1
        for previous, current in zip(closes, closes[1:])
        if previous > 0
    ]


def _maximum_drawdown(returns: List[float]) -> float:
    equity = 1.0
    peak = 1.0
    worst = 0.0

    for value in returns:
        equity *= 1 + value
        peak = max(peak, equity)

        if peak:
            worst = min(worst, (equity / peak) - 1)

    return worst * 100


def stock_risk_metrics(symbol: str) -> Dict[str, Any]:
    symbol = symbol.upper()
    returns = _returns(symbol)

    if len(returns) < 5:
        return {
            "symbol": symbol,
            "history_rows": len(returns) + 1,
            "volatility_pct": 0,
            "sharpe_ratio": 0,
            "sortino_ratio": 0,
            "maximum_drawdown_pct": 0,
            "var_95_pct": 0,
            "cvar_95_pct": 0,
            "risk_level": "INSUFFICIENT HISTORY",
        }

    average = mean(returns)
    deviation = pstdev(returns)

    downside = [
        value
        for value in returns
        if value < 0
    ]

    downside_deviation = (
        pstdev(downside)
        if len(downside) >= 2
        else deviation
    )

    sharpe = (
        average / deviation * math.sqrt(252)
        if deviation > 0
        else 0
    )

    sortino = (
        average / downside_deviation * math.sqrt(252)
        if downside_deviation > 0
        else 0
    )

    annualized_volatility = deviation * math.sqrt(252) * 100

    ordered = sorted(returns)
    var_index = max(
        0,
        int(len(ordered) * 0.05) - 1,
    )

    var_95 = ordered[var_index] * 100

    tail = [
        value * 100
        for value in returns
        if value * 100 <= var_95
    ]

    cvar_95 = mean(tail) if tail else var_95
    drawdown = _maximum_drawdown(returns)

    if annualized_volatility >= 45 or drawdown <= -30:
        risk_level = "HIGH"
    elif annualized_volatility >= 25 or drawdown <= -15:
        risk_level = "MODERATE"
    else:
        risk_level = "LOW"

    return {
        "symbol": symbol,
        "history_rows": len(returns) + 1,
        "volatility_pct": round(annualized_volatility, 2),
        "sharpe_ratio": round(sharpe, 2),
        "sortino_ratio": round(sortino, 2),
        "maximum_drawdown_pct": round(drawdown, 2),
        "var_95_pct": round(var_95, 2),
        "cvar_95_pct": round(cvar_95, 2),
        "risk_level": risk_level,
    }


def build_market_risk(
    stocks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    selected = sorted(
        stocks,
        key=lambda item: int(item.get("volume") or 0),
        reverse=True,
    )[:20]

    metrics = [
        stock_risk_metrics(stock["symbol"])
        for stock in selected
        if stock.get("symbol")
    ]

    valid = [
        item
        for item in metrics
        if item["risk_level"] != "INSUFFICIENT HISTORY"
    ]

    if not valid:
        return {
            "market_risk_level": "COLLECTING DATA",
            "average_volatility_pct": 0,
            "average_sharpe_ratio": 0,
            "average_sortino_ratio": 0,
            "worst_drawdown_pct": 0,
            "average_var_95_pct": 0,
            "symbols_analyzed": 0,
            "stocks": metrics,
        }

    volatility = mean(
        item["volatility_pct"]
        for item in valid
    )

    drawdown = min(
        item["maximum_drawdown_pct"]
        for item in valid
    )

    if volatility >= 40 or drawdown <= -30:
        risk_level = "HIGH"
    elif volatility >= 25 or drawdown <= -15:
        risk_level = "MODERATE"
    else:
        risk_level = "LOW"

    return {
        "market_risk_level": risk_level,
        "average_volatility_pct": round(volatility, 2),
        "average_sharpe_ratio": round(
            mean(item["sharpe_ratio"] for item in valid),
            2,
        ),
        "average_sortino_ratio": round(
            mean(item["sortino_ratio"] for item in valid),
            2,
        ),
        "worst_drawdown_pct": round(drawdown, 2),
        "average_var_95_pct": round(
            mean(item["var_95_pct"] for item in valid),
            2,
        ),
        "symbols_analyzed": len(valid),
        "stocks": metrics,
    }
PY

echo "Step 4: Installing regime and sector engine..."

cat > services/quant_intelligence.py <<'PY'
from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any, Dict, List


def detect_market_regime(
    market: Dict[str, Any],
    technicals: List[Dict[str, Any]],
    risk: Dict[str, Any],
) -> Dict[str, Any]:
    valid = [
        item
        for item in technicals
        if isinstance(item, dict) and not item.get("error")
    ]

    bullish = sum(
        1 for item in valid
        if item.get("signal") in {"BUY", "STRONG BUY"}
    )

    bearish = sum(
        1 for item in valid
        if item.get("signal") in {"WATCH", "SELL"}
    )

    breadth = (
        ((bullish - bearish) / len(valid)) * 100
        if valid
        else 0
    )

    average_change = float(
        market.get("average_change") or 0
    )

    score = (
        50
        + average_change * 8
        + breadth * 0.35
    )

    score = max(0, min(100, score))

    if score >= 75:
        regime = "STRONG BULL MARKET"
    elif score >= 60:
        regime = "BULL MARKET"
    elif score >= 40:
        regime = "NEUTRAL / SELECTIVE"
    elif score >= 25:
        regime = "BEAR MARKET"
    else:
        regime = "STRONG BEAR MARKET"

    confidence = min(
        95,
        55 + abs(score - 50),
    )

    return {
        "regime": regime,
        "confidence_pct": round(confidence, 2),
        "regime_score": round(score, 2),
        "breadth_score": round(breadth, 2),
        "bullish_signals": bullish,
        "bearish_signals": bearish,
        "market_risk_level": risk.get(
            "market_risk_level",
            "COLLECTING DATA",
        ),
    }


def analyze_sector_rotation(
    stocks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    grouped = defaultdict(list)

    for stock in stocks:
        sector = stock.get("sector") or "Unknown"
        grouped[sector].append(stock)

    sectors = []

    for sector, items in grouped.items():
        changes = [
            float(item.get("change_pct") or 0)
            for item in items
        ]

        volumes = [
            int(item.get("volume") or 0)
            for item in items
        ]

        average_change = (
            mean(changes)
            if changes
            else 0
        )

        breadth = (
            sum(1 for value in changes if value > 0)
            / len(changes)
            * 100
            if changes
            else 0
        )

        sectors.append({
            "sector": sector,
            "stock_count": len(items),
            "average_change_pct": round(
                average_change,
                2,
            ),
            "positive_breadth_pct": round(
                breadth,
                2,
            ),
            "total_volume": sum(volumes),
            "rotation_score": round(
                average_change * 12
                + breadth * 0.35,
                2,
            ),
        })

    sectors.sort(
        key=lambda item: (
            item["rotation_score"],
            item["total_volume"],
        ),
        reverse=True,
    )

    return {
        "strongest_sector": (
            sectors[0] if sectors else None
        ),
        "weakest_sector": (
            sectors[-1] if sectors else None
        ),
        "sectors": sectors,
    }
PY

echo "Step 5: Updating Flask application..."

python - <<'PY'
from pathlib import Path

path = Path("app.py")
text = path.read_text(encoding="utf-8")

anchor = "from services.screener_engine import run_screener\n"

imports = """from services.screener_engine import run_screener
from services.predictive_engine import build_predictions
from services.risk_engine import (
    build_market_risk,
    stock_risk_metrics,
)
from services.quant_intelligence import (
    detect_market_regime,
    analyze_sector_rotation,
)
"""

if "from services.predictive_engine import" not in text:
    if anchor not in text:
        raise SystemExit("app.py import anchor not found")

    text = text.replace(anchor, imports, 1)

text = text.replace(
    'VERSION = "11.3 Institutional AI"',
    'VERSION = "11.4 Institutional Quant Engine"',
)

text = text.replace(
    'VERSION = "Market Intelligence Platform V11.3"',
    'VERSION = "11.4 Institutional Quant Engine"',
)

if "predictions = build_predictions(" not in text:
    anchor = (
        "    optimized_portfolio = "
        "build_optimized_portfolio(\n"
    )

    start = text.find(anchor)

    if start == -1:
        raise SystemExit(
            "Portfolio optimizer anchor not found"
        )

    end = text.find("    )\n", start)

    if end == -1:
        raise SystemExit(
            "Portfolio optimizer end not found"
        )

    end += len("    )\n")

    addition = """
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
        limit=20,
    )
"""

    text = text[:end] + addition + text[end:]

context_anchor = (
    "        optimized_portfolio="
    "optimized_portfolio,\n"
)

context = """        optimized_portfolio=optimized_portfolio,
        risk_metrics=risk_metrics,
        regime=regime,
        sector_rotation=sector_rotation,
        predictions=predictions,
"""

if "risk_metrics=risk_metrics" not in text:
    if context_anchor not in text:
        raise SystemExit(
            "Dashboard context anchor not found"
        )

    text = text.replace(
        context_anchor,
        context,
        1,
    )

routes = '''

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


'''

if '@app.route("/api/v11.4/predictions")' not in text:
    marker = '\nif __name__ == "__main__":\n'

    if marker not in text:
        raise SystemExit(
            "Flask route insertion point not found"
        )

    text = text.replace(
        marker,
        routes + marker,
        1,
    )

text = text.replace(
    '"service": "Market Intelligence Platform V11.3"',
    '"service": "Market Intelligence Platform V11.4"',
)

text = text.replace(
    '"service": "NSE Signal Bot V11.2 Professional"',
    '"service": "Market Intelligence Platform V11.4"',
)

path.write_text(text, encoding="utf-8")
print("Updated app.py")
PY

echo "Step 6: Updating dashboard..."

python - <<'PY'
from pathlib import Path

path = Path("templates/dashboard.html")
text = path.read_text(encoding="utf-8")

for old in [
    "Market Intelligence Platform V11.3",
    "NSE Signal Bot V11.4",
    "NSE Signal Bot V11.3",
]:
    text = text.replace(
        old,
        "Market Intelligence Platform V11.4",
    )

panel = '''
<section class="dashboard-panel">
    <div class="panel-heading">
        <div>
            <p class="eyebrow">Market state intelligence</p>
            <h2>Market Regime Detection</h2>
        </div>

        <span class="risk-badge">
            {{ regime.market_risk_level }} RISK
        </span>
    </div>

    <div class="portfolio-metrics">
        <div>
            <span>Current regime</span>
            <strong>{{ regime.regime }}</strong>
        </div>

        <div>
            <span>Confidence</span>
            <strong>{{ regime.confidence_pct }}%</strong>
        </div>

        <div>
            <span>Breadth</span>
            <strong>{{ regime.breadth_score }}</strong>
        </div>

        <div>
            <span>Regime score</span>
            <strong>{{ regime.regime_score }}/100</strong>
        </div>
    </div>
</section>

<section class="dashboard-panel">
    <div class="panel-heading">
        <div>
            <p class="eyebrow">Forward-looking intelligence</p>
            <h2>Predictive AI Opportunities</h2>
        </div>
    </div>

    <div class="table-wrapper">
        <table class="dashboard-table compact-table">
            <thead>
                <tr>
                    <th>Symbol</th>
                    <th>Signal</th>
                    <th>Expected Return</th>
                    <th>Success Probability</th>
                    <th>Holding Period</th>
                    <th>Target</th>
                    <th>Expected Drawdown</th>
                </tr>
            </thead>

            <tbody>
                {% for item in predictions[:10] %}
                <tr>
                    <td>{{ item.symbol }}</td>
                    <td>{{ item.signal }}</td>

                    <td class="{% if item.expected_return_pct >= 0 %}positive{% else %}negative{% endif %}">
                        {{ item.expected_return_pct }}%
                    </td>

                    <td>
                        {{ item.probability_success_pct }}%
                    </td>

                    <td>
                        {{ item.holding_period_days }} days
                    </td>

                    <td>
                        KSh {{ item.target_price }}
                    </td>

                    <td class="negative">
                        {{ item.maximum_expected_drawdown_pct }}%
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <p class="section-description">
        Forecasts are heuristic estimates and are not
        guaranteed investment outcomes.
    </p>
</section>

<section class="two-column-grid">
    <article class="dashboard-panel">
        <div class="panel-heading">
            <div>
                <p class="eyebrow">
                    Institutional risk analytics
                </p>
                <h2>Risk Engine</h2>
            </div>
        </div>

        <div class="portfolio-metrics">
            <div>
                <span>Market risk</span>
                <strong>
                    {{ risk_metrics.market_risk_level }}
                </strong>
            </div>

            <div>
                <span>Volatility</span>
                <strong>
                    {{ risk_metrics.average_volatility_pct }}%
                </strong>
            </div>

            <div>
                <span>Sharpe ratio</span>
                <strong>
                    {{ risk_metrics.average_sharpe_ratio }}
                </strong>
            </div>

            <div>
                <span>Sortino ratio</span>
                <strong>
                    {{ risk_metrics.average_sortino_ratio }}
                </strong>
            </div>

            <div>
                <span>Worst drawdown</span>
                <strong class="negative">
                    {{ risk_metrics.worst_drawdown_pct }}%
                </strong>
            </div>

            <div>
                <span>VaR 95%</span>
                <strong class="negative">
                    {{ risk_metrics.average_var_95_pct }}%
                </strong>
            </div>
        </div>
    </article>

    <article class="dashboard-panel">
        <div class="panel-heading">
            <div>
                <p class="eyebrow">
                    Capital flow intelligence
                </p>
                <h2>Sector Rotation AI</h2>
            </div>
        </div>

        {% if sector_rotation.strongest_sector %}
        <p class="recommendation-box">
            <strong>Strongest sector:</strong>
            {{ sector_rotation.strongest_sector.sector }}
            ·
            {{ sector_rotation.strongest_sector.average_change_pct }}%
        </p>
        {% endif %}

        <div class="table-wrapper">
            <table class="dashboard-table compact-table">
                <thead>
                    <tr>
                        <th>Sector</th>
                        <th>Change</th>
                        <th>Breadth</th>
                        <th>Volume</th>
                        <th>Score</th>
                    </tr>
                </thead>

                <tbody>
                    {% for item in sector_rotation.sectors[:8] %}
                    <tr>
                        <td>{{ item.sector }}</td>

                        <td>
                            {{ item.average_change_pct }}%
                        </td>

                        <td>
                            {{ item.positive_breadth_pct }}%
                        </td>

                        <td>{{ item.total_volume }}</td>
                        <td>{{ item.rotation_score }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </article>
</section>

'''

if "Predictive AI Opportunities" not in text:
    marker = (
        '<section class="dashboard-panel '
        'cash-summary-panel">'
    )

    if marker not in text:
        raise SystemExit(
            "Dashboard insertion point not found"
        )

    text = text.replace(
        marker,
        panel + marker,
        1,
    )

path.write_text(text, encoding="utf-8")
print("Updated dashboard.html")
PY

echo "Step 7: Creating V11.4 tests..."

cat > test_v11_4.py <<'PY'
from services.market_data import get_market_snapshot
from services.predictive_engine import build_predictions
from services.quant_intelligence import (
    analyze_sector_rotation,
    detect_market_regime,
)
from services.risk_engine import build_market_risk
from services.technical_analysis import analyze_market


market = get_market_snapshot()
stocks = market.get("stocks", [])

assert stocks, "No market stocks returned"

technicals = analyze_market(stocks)
predictions = build_predictions(
    stocks,
    technicals,
    20,
)

risk = build_market_risk(stocks)

regime = detect_market_regime(
    market,
    technicals,
    risk,
)

sectors = analyze_sector_rotation(stocks)

assert predictions
assert regime.get("regime")
assert risk.get("market_risk_level")
assert sectors.get("sectors")

print("V11.4 TEST PASSED")
print("Market stocks:", len(stocks))
print("Technicals:", len(technicals))
print("Predictions:", len(predictions))
print("Regime:", regime["regime"])
print("Risk:", risk["market_risk_level"])
print("Sectors:", len(sectors["sectors"]))
PY

echo "Step 8: Running syntax checks..."

"$PROJECT/venv/bin/python" -m py_compile \
    app.py \
    run_daily_scan.py \
    test_v11_4.py \
    services/*.py

echo "Syntax checks passed."

echo "Step 9: Running V11.4 tests..."

"$PROJECT/venv/bin/python" test_v11_4.py

echo "Step 10: Restarting application..."

"$PROJECT/restart.sh"

echo "Step 11: Checking health endpoint..."

HEALTH="$(curl -fsS http://127.0.0.1:5000/health)"

echo "$HEALTH"

echo "$HEALTH" | grep -q '"status":"online"'

trap - ERR

echo
echo "=========================================="
echo "V11.4 upgrade completed successfully."
echo "Backup: $BACKUP"
echo "Log: $LOG"
echo "=========================================="
