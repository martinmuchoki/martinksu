#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT="/root/nse_signal_bot_v10_3"
STAMP="$(date +%Y-%m-%d_%H-%M-%S)"
BACKUP="$PROJECT/backups/v11_5_rc2_$STAMP"
LOG="$PROJECT/logs/v11_5_rc2_$STAMP.log"

cd "$PROJECT"

mkdir -p \
    "$BACKUP/templates" \
    "$BACKUP/static/css" \
    "$BACKUP/static/js" \
    "$BACKUP/services" \
    "$PROJECT/static/js" \
    "$PROJECT/logs"

exec > >(tee -a "$LOG") 2>&1

rollback() {
    echo
    echo "RC2 installation failed. Rolling back..."

    [ -f "$BACKUP/app.py" ] &&
        cp "$BACKUP/app.py" "$PROJECT/app.py"

    [ -f "$BACKUP/templates/dashboard_v115.html" ] &&
        cp "$BACKUP/templates/dashboard_v115.html" \
           "$PROJECT/templates/dashboard_v115.html"

    [ -f "$BACKUP/static/css/v115.css" ] &&
        cp "$BACKUP/static/css/v115.css" \
           "$PROJECT/static/css/v115.css"

    [ -f "$BACKUP/static/js/v115_charts.js" ] &&
        cp "$BACKUP/static/js/v115_charts.js" \
           "$PROJECT/static/js/v115_charts.js"

    rm -f "$PROJECT/services/dashboard_charts.py"

    "$PROJECT/restart.sh" || true

    echo "Rollback completed."
    exit 1
}

trap rollback ERR

echo "=================================================="
echo "MIP PRO V11.5 RC2"
echo "Interactive Intelligence Dashboard"
echo "=================================================="

echo
echo "[1/9] Creating backups..."

cp app.py "$BACKUP/app.py"

cp templates/dashboard_v115.html \
   "$BACKUP/templates/dashboard_v115.html"

cp static/css/v115.css \
   "$BACKUP/static/css/v115.css"

if [ -f static/js/v115_charts.js ]; then
    cp static/js/v115_charts.js \
       "$BACKUP/static/js/v115_charts.js"
fi

echo "Backup created:"
echo "$BACKUP"

echo
echo "[2/9] Installing dashboard chart service..."

cat > services/dashboard_charts.py <<'PY'
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List

from services.database import get_conn, init_db
from services.market_data import get_market_snapshot
from services.performance_engine import get_performance_summary


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def get_market_breadth() -> Dict[str, Any]:
    market = get_market_snapshot()
    stocks = market.get("stocks", [])

    advancers = [
        stock
        for stock in stocks
        if _safe_float(stock.get("change_pct")) > 0
    ]

    decliners = [
        stock
        for stock in stocks
        if _safe_float(stock.get("change_pct")) < 0
    ]

    unchanged = [
        stock
        for stock in stocks
        if _safe_float(stock.get("change_pct")) == 0
    ]

    volume_leaders = sorted(
        stocks,
        key=lambda item: _safe_int(item.get("volume")),
        reverse=True,
    )[:10]

    gainers = sorted(
        stocks,
        key=lambda item: _safe_float(item.get("change_pct")),
        reverse=True,
    )[:10]

    losers = sorted(
        stocks,
        key=lambda item: _safe_float(item.get("change_pct")),
    )[:10]

    total = len(stocks)

    return {
        "advancers": len(advancers),
        "decliners": len(decliners),
        "unchanged": len(unchanged),
        "total": total,
        "advance_decline_ratio": round(
            len(advancers) / len(decliners),
            2,
        ) if decliners else float(len(advancers)),
        "advancing_percentage": round(
            len(advancers) / total * 100,
            2,
        ) if total else 0,
        "declining_percentage": round(
            len(decliners) / total * 100,
            2,
        ) if total else 0,
        "volume_leaders": volume_leaders,
        "top_gainers": gainers,
        "top_losers": losers,
        "generated_at": datetime.now().isoformat(),
    }


def get_market_history_chart(
    symbol: str = "SCOM",
    limit: int = 60,
) -> Dict[str, Any]:
    init_db()

    conn = get_conn()

    try:
        rows = conn.execute(
            """
            SELECT trade_date, close, volume
            FROM price_history
            WHERE symbol = ?
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            (symbol.upper(), limit),
        ).fetchall()

    finally:
        conn.close()

    rows = list(reversed(rows))

    return {
        "symbol": symbol.upper(),
        "labels": [
            row["trade_date"]
            for row in rows
        ],
        "prices": [
            round(_safe_float(row["close"]), 2)
            for row in rows
        ],
        "volumes": [
            _safe_int(row["volume"])
            for row in rows
        ],
    }


def get_portfolio_history_chart(
    limit: int = 60,
) -> Dict[str, Any]:
    init_db()
    conn = get_conn()

    try:
        holdings = conn.execute(
            """
            SELECT symbol, shares
            FROM portfolio
            WHERE shares > 0
            """
        ).fetchall()

        values_by_date: Dict[str, float] = defaultdict(float)

        for holding in holdings:
            rows = conn.execute(
                """
                SELECT trade_date, close
                FROM price_history
                WHERE symbol = ?
                ORDER BY trade_date DESC
                LIMIT ?
                """,
                (holding["symbol"], limit),
            ).fetchall()

            for row in rows:
                values_by_date[row["trade_date"]] += (
                    _safe_float(row["close"])
                    * _safe_float(holding["shares"])
                )

    finally:
        conn.close()

    labels = sorted(values_by_date.keys())[-limit:]

    return {
        "labels": labels,
        "values": [
            round(values_by_date[label], 2)
            for label in labels
        ],
    }


def get_ai_confidence_history(
    limit: int = 60,
) -> Dict[str, Any]:
    init_db()

    conn = get_conn()

    try:
        rows = conn.execute(
            """
            SELECT
                recommendation_date,
                AVG(confidence) AS average_confidence,
                COUNT(*) AS recommendation_count
            FROM ai_recommendations
            GROUP BY recommendation_date
            ORDER BY recommendation_date DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    except Exception:
        rows = []

    finally:
        conn.close()

    rows = list(reversed(rows))

    return {
        "labels": [
            row["recommendation_date"]
            for row in rows
        ],
        "confidence": [
            round(
                _safe_float(row["average_confidence"]),
                2,
            )
            for row in rows
        ],
        "recommendations": [
            _safe_int(row["recommendation_count"])
            for row in rows
        ],
    }


def get_sector_chart() -> Dict[str, Any]:
    market = get_market_snapshot()
    grouped: Dict[str, List[float]] = defaultdict(list)

    for stock in market.get("stocks", []):
        sector = stock.get("sector") or "Unknown"

        grouped[sector].append(
            _safe_float(stock.get("change_pct"))
        )

    rows = []

    for sector, changes in grouped.items():
        average_change = (
            sum(changes) / len(changes)
            if changes
            else 0
        )

        rows.append({
            "sector": sector,
            "average_change": round(
                average_change,
                2,
            ),
        })

    rows.sort(
        key=lambda item: item["average_change"],
        reverse=True,
    )

    rows = rows[:12]

    return {
        "labels": [
            item["sector"]
            for item in rows
        ],
        "values": [
            item["average_change"]
            for item in rows
        ],
    }


def get_dashboard_chart_data(
    symbol: str = "SCOM",
) -> Dict[str, Any]:
    return {
        "market_history": get_market_history_chart(symbol),
        "portfolio_history": get_portfolio_history_chart(),
        "ai_confidence": get_ai_confidence_history(),
        "sector_rotation": get_sector_chart(),
        "breadth": get_market_breadth(),
        "performance": get_performance_summary(),
        "generated_at": datetime.now().isoformat(),
    }
PY

echo
echo "[3/9] Adding RC2 API endpoints..."

python - <<'PY'
from pathlib import Path

path = Path("app.py")
text = path.read_text(encoding="utf-8")

import_anchor = (
    "from services.screener_engine import run_screener\n"
)

chart_import = """from services.dashboard_charts import (
    get_dashboard_chart_data,
    get_market_breadth,
)
"""

if "from services.dashboard_charts import" not in text:
    if import_anchor not in text:
        raise SystemExit(
            "Unable to find screener import in app.py"
        )

    text = text.replace(
        import_anchor,
        import_anchor + chart_import,
        1,
    )

routes = '''

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


'''

if '@app.route("/api/v11.5/dashboard-charts")' not in text:
    marker = '\nif __name__ == "__main__":\n'

    if marker not in text:
        raise SystemExit(
            "Unable to find Flask route insertion point."
        )

    text = text.replace(
        marker,
        routes + marker,
        1,
    )

text = text.replace(
    'VERSION = "11.5 RC1"',
    'VERSION = "11.5 RC2"',
)

path.write_text(text, encoding="utf-8")
print("RC2 API endpoints installed.")
PY

echo
echo "[4/9] Adding interactive dashboard panels..."

python - <<'PY'
from pathlib import Path

path = Path("templates/dashboard_v115.html")
text = path.read_text(encoding="utf-8")

chart_script = '''
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
'''

if "chart.umd.min.js" not in text:
    text = text.replace(
        "</head>",
        chart_script + "</head>",
        1,
    )

charts_panel = '''
<section class="panel rc2-chart-section">

    <div class="panel-heading">
        <div>
            <span class="section-label">
                Interactive Market Intelligence
            </span>

            <h2>Market and Portfolio Charts</h2>
        </div>

        <div class="chart-symbol-control">
            <label for="chart-symbol">
                Stock
            </label>

            <select id="chart-symbol">
                {% for stock in market.stocks %}
                <option
                    value="{{ stock.symbol }}"
                    {% if stock.symbol == 'SCOM' %}selected{% endif %}>
                    {{ stock.symbol }}
                </option>
                {% endfor %}
            </select>
        </div>
    </div>

    <div class="charts-grid">

        <article class="chart-card">
            <div class="chart-card-heading">
                <h3 id="market-chart-title">
                    SCOM Price History
                </h3>

                <span>Historical close</span>
            </div>

            <div class="chart-container">
                <canvas id="market-history-chart"></canvas>
            </div>
        </article>

        <article class="chart-card">
            <div class="chart-card-heading">
                <h3>Portfolio Value</h3>
                <span>Historical valuation</span>
            </div>

            <div class="chart-container">
                <canvas id="portfolio-history-chart"></canvas>
            </div>
        </article>

        <article class="chart-card">
            <div class="chart-card-heading">
                <h3>AI Confidence</h3>
                <span>Recommendation confidence trend</span>
            </div>

            <div class="chart-container">
                <canvas id="ai-confidence-chart"></canvas>
            </div>
        </article>

        <article class="chart-card">
            <div class="chart-card-heading">
                <h3>Sector Rotation</h3>
                <span>Average sector movement</span>
            </div>

            <div class="chart-container">
                <canvas id="sector-rotation-chart"></canvas>
            </div>
        </article>

    </div>

</section>

<section class="content-grid two-columns rc2-breadth-section">

    <article class="panel">
        <div class="panel-heading">
            <div>
                <span class="section-label">
                    Market Breadth
                </span>

                <h2>Advancers and Decliners</h2>
            </div>
        </div>

        <div class="breadth-grid">

            <div class="breadth-card breadth-positive">
                <span>Advancers</span>
                <strong id="breadth-advancers">0</strong>
            </div>

            <div class="breadth-card breadth-negative">
                <span>Decliners</span>
                <strong id="breadth-decliners">0</strong>
            </div>

            <div class="breadth-card breadth-neutral">
                <span>Unchanged</span>
                <strong id="breadth-unchanged">0</strong>
            </div>

            <div class="breadth-card breadth-ratio">
                <span>Advance/Decline</span>
                <strong id="breadth-ratio">0</strong>
            </div>

        </div>

        <div class="breadth-bar">
            <div
                id="breadth-advance-bar"
                class="breadth-bar-positive">
            </div>

            <div
                id="breadth-decline-bar"
                class="breadth-bar-negative">
            </div>
        </div>
    </article>

    <article class="panel">
        <div class="panel-heading">
            <div>
                <span class="section-label">
                    Volume Intelligence
                </span>

                <h2>Volume Leaders</h2>
            </div>
        </div>

        <div
            id="volume-leaders"
            class="leader-list">
        </div>
    </article>

</section>
'''

if "Market and Portfolio Charts" not in text:
    marker = '<section class="content-grid two-columns">'

    if marker not in text:
        raise SystemExit(
            "Unable to find dashboard chart insertion point."
        )

    text = text.replace(
        marker,
        charts_panel + "\n" + marker,
        1,
    )

filter_panel = '''
<div class="screener-filter-bar">

    <label>
        Search
        <input
            id="screener-search"
            type="search"
            placeholder="Symbol or company">
    </label>

    <label>
        Decision
        <select id="screener-decision-filter">
            <option value="">All decisions</option>
            <option value="STRONG BUY">Strong Buy</option>
            <option value="BUY">Buy</option>
            <option value="HOLD">Hold</option>
            <option value="WATCH">Watch</option>
            <option value="SELL">Sell</option>
        </select>
    </label>

    <label>
        Risk
        <select id="screener-risk-filter">
            <option value="">All risk levels</option>
            <option value="LOW RISK">Low Risk</option>
            <option value="MODERATE RISK">Moderate Risk</option>
            <option value="HIGH RISK">High Risk</option>
        </select>
    </label>

    <label>
        Sector
        <select id="screener-sector-filter">
            <option value="">All sectors</option>

            {% set sectors = [] %}

            {% for stock in screener %}
                {% if stock.sector not in sectors %}
                    {% set _ = sectors.append(stock.sector) %}
                {% endif %}
            {% endfor %}

            {% for sector in sectors|sort %}
            <option value="{{ sector }}">
                {{ sector }}
            </option>
            {% endfor %}
        </select>
    </label>

    <label>
        Minimum confidence
        <input
            id="screener-confidence-filter"
            type="number"
            min="0"
            max="100"
            value="0">
    </label>

    <button
        id="screener-reset"
        type="button"
        class="filter-reset-button">
        Reset
    </button>

</div>

<p class="filter-result-count">
    Showing
    <strong id="screener-visible-count">
        {{ screener[:15]|length }}
    </strong>
    results
</p>
'''

if "screener-filter-bar" not in text:
    table_marker = '''
    <div class="table-wrapper">
        <table>
            <thead>
                <tr>
                    <th>Rank</th>
'''

    if table_marker not in text:
        raise SystemExit(
            "Unable to find screener table marker."
        )

    text = text.replace(
        table_marker,
        filter_panel + table_marker,
        1,
    )

text = text.replace(
    '<tbody>\n                {% for stock in screener[:15] %}',
    '''<tbody id="screener-table-body">
                {% for stock in screener %}''',
    1,
)

text = text.replace(
    '<tr>\n                    <td>{{ loop.index }}</td>',
    '''<tr
                    class="screener-row"
                    data-symbol="{{ stock.symbol|lower }}"
                    data-company="{{ stock.name|lower }}"
                    data-decision="{{ stock.decision }}"
                    data-risk="{{ stock.risk }}"
                    data-sector="{{ stock.sector }}"
                    data-confidence="{{ stock.confidence }}">
                    <td class="screener-rank">{{ loop.index }}</td>''',
    1,
)

javascript = '''
<script
    src="{{ url_for('static', filename='js/v115_charts.js') }}">
</script>
'''

if "js/v115_charts.js" not in text:
    text = text.replace(
        "</body>",
        javascript + "\n</body>",
        1,
    )

text = text.replace(
    "Version 11.5 RC1",
    "Version 11.5 RC2",
)

path.write_text(text, encoding="utf-8")
print("RC2 dashboard panels installed.")
PY

echo
echo "[5/9] Installing interactive JavaScript..."

cat > static/js/v115_charts.js <<'JS'
"use strict";

let marketHistoryChart = null;
let portfolioHistoryChart = null;
let confidenceChart = null;
let sectorChart = null;

const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
        intersect: false,
        mode: "index",
    },
    plugins: {
        legend: {
            display: false,
        },
    },
    scales: {
        x: {
            grid: {
                display: false,
            },
            ticks: {
                maxTicksLimit: 8,
            },
        },
        y: {
            beginAtZero: false,
            grid: {
                color: "rgba(20, 45, 32, 0.08)",
            },
        },
    },
};

function destroyChart(chart) {
    if (chart) {
        chart.destroy();
    }
}

function createLineChart(
    elementId,
    labels,
    values,
    datasetLabel
) {
    const canvas = document.getElementById(elementId);

    if (!canvas || typeof Chart === "undefined") {
        return null;
    }

    return new Chart(canvas, {
        type: "line",
        data: {
            labels,
            datasets: [
                {
                    label: datasetLabel,
                    data: values,
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true,
                    pointRadius: 1.5,
                    pointHoverRadius: 5,
                    borderColor: "#08783f",
                    backgroundColor: "rgba(8, 120, 63, 0.10)",
                },
            ],
        },
        options: chartDefaults,
    });
}

function createSectorChart(labels, values) {
    const canvas = document.getElementById(
        "sector-rotation-chart"
    );

    if (!canvas || typeof Chart === "undefined") {
        return null;
    }

    return new Chart(canvas, {
        type: "bar",
        data: {
            labels,
            datasets: [
                {
                    data: values,
                    borderWidth: 0,
                    borderRadius: 4,
                    backgroundColor: values.map(
                        value => (
                            value >= 0
                                ? "rgba(8, 120, 63, 0.78)"
                                : "rgba(200, 16, 46, 0.78)"
                        )
                    ),
                },
            ],
        },
        options: {
            ...chartDefaults,
            indexAxis: "y",
            scales: {
                x: {
                    grid: {
                        color: "rgba(20, 45, 32, 0.08)",
                    },
                },
                y: {
                    grid: {
                        display: false,
                    },
                },
            },
        },
    });
}

function updateBreadth(breadth) {
    const mapping = {
        "breadth-advancers": breadth.advancers,
        "breadth-decliners": breadth.decliners,
        "breadth-unchanged": breadth.unchanged,
        "breadth-ratio": breadth.advance_decline_ratio,
    };

    Object.entries(mapping).forEach(([id, value]) => {
        const element = document.getElementById(id);

        if (element) {
            element.textContent = value ?? 0;
        }
    });

    const positiveBar = document.getElementById(
        "breadth-advance-bar"
    );

    const negativeBar = document.getElementById(
        "breadth-decline-bar"
    );

    if (positiveBar) {
        positiveBar.style.width =
            `${breadth.advancing_percentage || 0}%`;
    }

    if (negativeBar) {
        negativeBar.style.width =
            `${breadth.declining_percentage || 0}%`;
    }

    const leaderContainer = document.getElementById(
        "volume-leaders"
    );

    if (leaderContainer) {
        leaderContainer.innerHTML = "";

        (breadth.volume_leaders || [])
            .slice(0, 8)
            .forEach((stock, index) => {
                const row = document.createElement("div");

                row.className = "leader-row";

                row.innerHTML = `
                    <span>${index + 1}. ${stock.symbol}</span>
                    <strong>${Number(
                        stock.volume || 0
                    ).toLocaleString()}</strong>
                `;

                leaderContainer.appendChild(row);
            });
    }
}

async function loadDashboardCharts(symbol = "SCOM") {
    try {
        const response = await fetch(
            `/api/v11.5/dashboard-charts?symbol=${
                encodeURIComponent(symbol)
            }`
        );

        if (!response.ok) {
            throw new Error(
                `Dashboard chart API returned ${response.status}`
            );
        }

        const data = await response.json();

        destroyChart(marketHistoryChart);
        destroyChart(portfolioHistoryChart);
        destroyChart(confidenceChart);
        destroyChart(sectorChart);

        marketHistoryChart = createLineChart(
            "market-history-chart",
            data.market_history.labels || [],
            data.market_history.prices || [],
            `${symbol} close`
        );

        portfolioHistoryChart = createLineChart(
            "portfolio-history-chart",
            data.portfolio_history.labels || [],
            data.portfolio_history.values || [],
            "Portfolio value"
        );

        confidenceChart = createLineChart(
            "ai-confidence-chart",
            data.ai_confidence.labels || [],
            data.ai_confidence.confidence || [],
            "AI confidence"
        );

        sectorChart = createSectorChart(
            data.sector_rotation.labels || [],
            data.sector_rotation.values || []
        );

        updateBreadth(data.breadth || {});

        const title = document.getElementById(
            "market-chart-title"
        );

        if (title) {
            title.textContent = `${symbol} Price History`;
        }

    } catch (error) {
        console.error(
            "Unable to load dashboard charts:",
            error
        );
    }
}

function applyScreenerFilters() {
    const search = (
        document.getElementById("screener-search")?.value
        || ""
    ).trim().toLowerCase();

    const decision = (
        document.getElementById(
            "screener-decision-filter"
        )?.value
        || ""
    );

    const risk = (
        document.getElementById(
            "screener-risk-filter"
        )?.value
        || ""
    );

    const sector = (
        document.getElementById(
            "screener-sector-filter"
        )?.value
        || ""
    );

    const minimumConfidence = Number(
        document.getElementById(
            "screener-confidence-filter"
        )?.value
        || 0
    );

    const rows = Array.from(
        document.querySelectorAll(".screener-row")
    );

    let visibleCount = 0;

    rows.forEach(row => {
        const matchesSearch = (
            !search
            || row.dataset.symbol.includes(search)
            || row.dataset.company.includes(search)
        );

        const matchesDecision = (
            !decision
            || row.dataset.decision === decision
        );

        const matchesRisk = (
            !risk
            || row.dataset.risk === risk
        );

        const matchesSector = (
            !sector
            || row.dataset.sector === sector
        );

        const matchesConfidence = (
            Number(row.dataset.confidence || 0)
            >= minimumConfidence
        );

        const visible = (
            matchesSearch
            && matchesDecision
            && matchesRisk
            && matchesSector
            && matchesConfidence
        );

        row.hidden = !visible;

        if (visible) {
            visibleCount += 1;

            const rank = row.querySelector(
                ".screener-rank"
            );

            if (rank) {
                rank.textContent = visibleCount;
            }
        }
    });

    const counter = document.getElementById(
        "screener-visible-count"
    );

    if (counter) {
        counter.textContent = visibleCount;
    }
}

function initializeScreenerFilters() {
    const filterIds = [
        "screener-search",
        "screener-decision-filter",
        "screener-risk-filter",
        "screener-sector-filter",
        "screener-confidence-filter",
    ];

    filterIds.forEach(id => {
        const element = document.getElementById(id);

        if (!element) {
            return;
        }

        element.addEventListener(
            element.tagName === "INPUT"
                ? "input"
                : "change",
            applyScreenerFilters
        );
    });

    const resetButton = document.getElementById(
        "screener-reset"
    );

    if (resetButton) {
        resetButton.addEventListener("click", () => {
            filterIds.forEach(id => {
                const element = document.getElementById(id);

                if (!element) {
                    return;
                }

                if (
                    id === "screener-confidence-filter"
                ) {
                    element.value = "0";
                } else {
                    element.value = "";
                }
            });

            applyScreenerFilters();
        });
    }

    applyScreenerFilters();
}

document.addEventListener("DOMContentLoaded", () => {
    const symbolSelect = document.getElementById(
        "chart-symbol"
    );

    const initialSymbol = symbolSelect?.value || "SCOM";

    loadDashboardCharts(initialSymbol);
    initializeScreenerFilters();

    if (symbolSelect) {
        symbolSelect.addEventListener(
            "change",
            event => {
                loadDashboardCharts(
                    event.target.value
                );
            }
        );
    }
});
JS

echo
echo "[6/9] Installing RC2 dashboard styles..."

cat >> static/css/v115.css <<'CSS'

/* ==================================================
   MIP PRO V11.5 RC2
   Interactive Charts, Breadth and Advanced Screener
   ================================================== */

.rc2-chart-section {
    overflow: hidden;
}

.chart-symbol-control {
    display: flex;
    align-items: center;
    gap: 9px;
}

.chart-symbol-control label {
    color: var(--muted);
    font-size: 13px;
    font-weight: 700;
}

.chart-symbol-control select {
    min-width: 110px;
    padding: 8px 10px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: #ffffff;
    color: var(--dark);
    font: inherit;
}

.charts-grid {
    display: grid;
    grid-template-columns:
        repeat(2, minmax(0, 1fr));
    gap: 16px;
}

.chart-card {
    min-width: 0;
    padding: 17px;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: #fbfdfc;
}

.chart-card-heading {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 14px;
    margin-bottom: 12px;
}

.chart-card-heading h3 {
    margin: 0;
    color: var(--black);
    font-size: 17px;
}

.chart-card-heading span {
    color: var(--muted);
    font-size: 12px;
}

.chart-container {
    position: relative;
    height: 285px;
}

.breadth-grid {
    display: grid;
    grid-template-columns:
        repeat(4, minmax(100px, 1fr));
    gap: 10px;
}

.breadth-card {
    padding: 15px;
    border-radius: 10px;
    background: #f2f6f3;
}

.breadth-card span,
.breadth-card strong {
    display: block;
}

.breadth-card span {
    margin-bottom: 7px;
    color: var(--muted);
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
}

.breadth-card strong {
    color: var(--black);
    font-size: 24px;
}

.breadth-positive {
    background: rgba(8, 120, 63, 0.09);
}

.breadth-positive strong {
    color: var(--green);
}

.breadth-negative {
    background: rgba(200, 16, 46, 0.09);
}

.breadth-negative strong {
    color: var(--red);
}

.breadth-neutral {
    background: rgba(109, 121, 114, 0.10);
}

.breadth-ratio {
    background: var(--gold-soft);
}

.breadth-bar {
    display: flex;
    width: 100%;
    height: 12px;
    margin-top: 18px;
    overflow: hidden;
    border-radius: 999px;
    background: #e8eeea;
}

.breadth-bar-positive {
    width: 0;
    background: var(--green);
    transition: width 350ms ease;
}

.breadth-bar-negative {
    width: 0;
    background: var(--red);
    transition: width 350ms ease;
}

.leader-list {
    display: grid;
    gap: 3px;
}

.leader-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    padding: 10px 0;
    border-bottom: 1px solid #edf1ee;
}

.leader-row span {
    color: var(--dark);
    font-weight: 750;
}

.leader-row strong {
    color: var(--green-dark);
    font-size: 13px;
}

.screener-filter-bar {
    display: grid;
    grid-template-columns:
        minmax(180px, 2fr)
        repeat(4, minmax(145px, 1fr))
        auto;
    gap: 11px;
    align-items: end;
    margin-bottom: 13px;
    padding: 15px;
    border: 1px solid var(--border);
    border-radius: 11px;
    background: #f7faf8;
}

.screener-filter-bar label {
    display: grid;
    gap: 6px;
    color: var(--muted);
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
}

.screener-filter-bar input,
.screener-filter-bar select {
    width: 100%;
    min-height: 40px;
    padding: 8px 10px;
    border: 1px solid #ced9d2;
    border-radius: 8px;
    background: #ffffff;
    color: var(--dark);
    font: inherit;
    font-size: 13px;
}

.screener-filter-bar input:focus,
.screener-filter-bar select:focus {
    outline: 3px solid rgba(8, 120, 63, 0.11);
    border-color: var(--green);
}

.filter-reset-button {
    min-height: 40px;
    padding: 8px 15px;
    border: 1px solid rgba(200, 16, 46, 0.24);
    border-radius: 8px;
    background: #ffffff;
    color: var(--red);
    font: inherit;
    font-size: 13px;
    font-weight: 800;
    cursor: pointer;
}

.filter-result-count {
    margin: 0 0 12px;
    color: var(--muted);
    font-size: 12px;
}

.screener-row[hidden] {
    display: none;
}

@media (max-width: 1300px) {
    .screener-filter-bar {
        grid-template-columns:
            repeat(3, minmax(160px, 1fr));
    }
}

@media (max-width: 900px) {
    .charts-grid {
        grid-template-columns: 1fr;
    }

    .breadth-grid {
        grid-template-columns:
            repeat(2, minmax(110px, 1fr));
    }

    .screener-filter-bar {
        grid-template-columns:
            repeat(2, minmax(150px, 1fr));
    }
}

@media (max-width: 560px) {
    .chart-card-heading {
        flex-direction: column;
    }

    .chart-container {
        height: 235px;
    }

    .breadth-grid,
    .screener-filter-bar {
        grid-template-columns: 1fr;
    }

    .chart-symbol-control {
        align-items: flex-start;
        flex-direction: column;
    }

    .chart-symbol-control select {
        width: 100%;
    }
}
CSS

echo
echo "[7/9] Validating RC2 source files..."

"$PROJECT/venv/bin/python" -m py_compile \
    app.py \
    services/*.py

"$PROJECT/venv/bin/python" - <<'PY'
from pathlib import Path

required_files = [
    Path("services/dashboard_charts.py"),
    Path("static/js/v115_charts.js"),
    Path("static/css/v115.css"),
    Path("templates/dashboard_v115.html"),
]

for path in required_files:
    if not path.exists():
        raise RuntimeError(
            f"Missing RC2 file: {path}"
        )

template = Path(
    "templates/dashboard_v115.html"
).read_text(encoding="utf-8")

required_template_content = [
    "Market and Portfolio Charts",
    "market-history-chart",
    "portfolio-history-chart",
    "ai-confidence-chart",
    "sector-rotation-chart",
    "Market Breadth",
    "screener-filter-bar",
    "js/v115_charts.js",
]

missing = [
    item
    for item in required_template_content
    if item not in template
]

if missing:
    raise RuntimeError(
        "RC2 template validation failed: "
        + ", ".join(missing)
    )

print("RC2 source validation passed.")
PY

echo
echo "[8/9] Restarting application..."

"$PROJECT/restart.sh"

echo
echo "[9/9] Running RC2 release checks..."

HEALTH="$(
    curl -fsS http://127.0.0.1:5000/health
)"

echo "Health:"
echo "$HEALTH"

echo "$HEALTH" | grep -q '"status":"online"'

LOGIN_CODE="$(
    curl -s -o /dev/null -w "%{http_code}" \
    http://127.0.0.1:5000/login
)"

if [ "$LOGIN_CODE" != "200" ]; then
    echo "Login route failed: HTTP $LOGIN_CODE"
    exit 1
fi

CHART_API_CODE="$(
    curl -s \
        -o /dev/null \
        -w "%{http_code}" \
        -c /tmp/mip_rc2_cookie.txt \
        http://127.0.0.1:5000/api/v11.5/dashboard-charts
)"

if [ "$CHART_API_CODE" != "401" ]; then
    echo
    echo "Warning:"
    echo "Expected protected chart API to return 401."
    echo "Received HTTP $CHART_API_CODE."
fi

trap - ERR

echo
echo "=================================================="
echo "MIP PRO V11.5 RC2 installed successfully"
echo "=================================================="
echo
echo "New capabilities:"
echo "- Interactive stock history chart"
echo "- Portfolio value chart"
echo "- AI confidence trend"
echo "- Sector rotation chart"
echo "- Market breadth analytics"
echo "- Volume leaders"
echo "- Advanced screener filters"
echo "- Improved mobile responsiveness"
echo
echo "Backup:"
echo "$BACKUP"
echo
echo "Log:"
echo "$LOG"
echo
echo "Sign in and press Ctrl + F5."
echo "=================================================="
