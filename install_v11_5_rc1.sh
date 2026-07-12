#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT="/root/nse_signal_bot_v10_3"
STAMP="$(date +%Y-%m-%d_%H-%M-%S)"
BACKUP="$PROJECT/backups/v11_5_rc1_$STAMP"
LOG="$PROJECT/logs/v11_5_rc1_$STAMP.log"

cd "$PROJECT"

mkdir -p \
    "$BACKUP/templates" \
    "$BACKUP/static/css" \
    "$PROJECT/static/css" \
    "$PROJECT/static/images" \
    "$PROJECT/logs"

exec > >(tee -a "$LOG") 2>&1

rollback() {
    echo
    echo "RC1 installation failed. Rolling back..."

    if [ -f "$BACKUP/app.py" ]; then
        cp "$BACKUP/app.py" "$PROJECT/app.py"
    fi

    rm -f "$PROJECT/templates/dashboard_v115.html"
    rm -f "$PROJECT/static/css/v115.css"

    "$PROJECT/restart.sh" || true

    echo "Rollback completed."
    exit 1
}

trap rollback ERR

echo "=================================================="
echo "MIP PRO V11.5 RC1"
echo "Executive Dashboard Release Candidate"
echo "=================================================="

echo
echo "[1/7] Backing up current application..."

cp app.py "$BACKUP/app.py"

if [ -f templates/dashboard.html ]; then
    cp templates/dashboard.html \
       "$BACKUP/templates/dashboard.html"
fi

if [ -f static/css/style.css ]; then
    cp static/css/style.css \
       "$BACKUP/static/css/style.css"
fi

echo "Backup created: $BACKUP"

echo
echo "[2/7] Creating clean V11.5 dashboard..."

cat > templates/dashboard_v115.html <<'HTML'
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1">

    <title>MIP PRO — Market Intelligence Platform</title>

    <link
        rel="stylesheet"
        href="{{ url_for('static', filename='css/v115.css') }}">
</head>

<body>

<header class="app-header">
    <div class="brand-area">

        {% if logo_available %}
        <img
            class="brand-logo"
            src="{{ url_for('static', filename='images/mip_pro_logo.png') }}"
            alt="MIP PRO">
        {% else %}
        <div class="text-logo">
            <span class="mip">MIP</span>
            <span class="pro">PRO</span>
        </div>
        {% endif %}

        <div class="brand-copy">
            <h1>Market Intelligence Platform</h1>
            <p>Intelligence. Insights. Impact.</p>
        </div>
    </div>

    <nav class="header-nav">
        <a href="/">Dashboard</a>
        <a href="/screener">Screener</a>
        <a href="/download_report">Reports</a>
        <a href="/about">About</a>
        <a href="/logout">Logout</a>
    </nav>
</header>

<section class="status-strip">

    <div>
        <span>System</span>
        <strong class="status-live">● Online</strong>
    </div>

    <div>
        <span>Market</span>
        <strong>{{ market.market_status }}</strong>
    </div>

    <div>
        <span>Provider</span>
        <strong>{{ market.provider|default('MyStocks Africa') }}</strong>
    </div>

    <div>
        <span>Regime</span>
        <strong>{{ regime.regime|default('Collecting Data') }}</strong>
    </div>

    <div>
        <span>Updated</span>
        <strong>{{ market.generated_at|default(now) }}</strong>
    </div>

</section>

<main class="page-shell">

<section class="kpi-grid">

    <article class="kpi-card green">
        <span class="kpi-label">Market Status</span>
        <strong>{{ market.market_status }}</strong>
        <small>
            Average change:
            <span class="{% if market.average_change >= 0 %}positive{% else %}negative{% endif %}">
                {{ market.average_change }}%
            </span>
        </small>
    </article>

    <article class="kpi-card gold">
        <span class="kpi-label">AI Confidence</span>
        <strong>{{ committee.confidence }}%</strong>
        <small>{{ committee.final_decision }}</small>
    </article>

    <article class="kpi-card black">
        <span class="kpi-label">Market Regime</span>
        <strong class="compact">
            {{ regime.regime|default('Collecting Data') }}
        </strong>
        <small>
            Confidence:
            {{ regime.confidence_pct|default(0) }}%
        </small>
    </article>

    <article class="kpi-card green">
        <span class="kpi-label">Portfolio Value</span>
        <strong>
            KSh {{ "{:,.2f}".format(portfolio.total_value) }}
        </strong>
        <small>
            Return:
            <span class="{% if portfolio.pnl_pct >= 0 %}positive{% else %}negative{% endif %}">
                {{ portfolio.pnl_pct }}%
            </span>
        </small>
    </article>

    <article class="kpi-card gold">
        <span class="kpi-label">Top Opportunity</span>

        {% if screener %}
        <strong>{{ screener[0].symbol }}</strong>
        <small>
            {{ screener[0].decision }}
            · {{ screener[0].confidence }}%
        </small>
        {% else %}
        <strong>No Signal</strong>
        <small>Waiting for analysis</small>
        {% endif %}
    </article>

    <article class="kpi-card red">
        <span class="kpi-label">Institutional Risk</span>
        <strong class="compact">
            {{ risk_metrics.market_risk_level|default('Collecting Data') }}
        </strong>
        <small>
            VaR 95%:
            {{ risk_metrics.average_var_95_pct|default(0) }}%
        </small>
    </article>

</section>

<section class="content-grid two-columns">

    <article class="panel">
        <div class="panel-heading">
            <div>
                <span class="section-label">AI Intelligence</span>
                <h2>Investment Committee</h2>
            </div>

            <span class="decision-badge">
                {{ committee.final_decision }}
                · {{ committee.confidence }}%
            </span>
        </div>

        <p class="panel-summary">
            {{ committee.summary }}
        </p>

        <div class="agent-grid">
            {% for agent in committee.agents[:6] %}
            <div class="agent-card">
                <span>{{ agent.role }}</span>
                <strong>{{ agent.name }}</strong>
                <b>{{ agent.decision }}</b>
                <small>{{ agent.confidence }}% confidence</small>
            </div>
            {% endfor %}
        </div>
    </article>

    <article class="panel">
        <div class="panel-heading">
            <div>
                <span class="section-label">Forward Intelligence</span>
                <h2>Top Predictions</h2>
            </div>
        </div>

        <div class="table-wrapper">
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Expected Return</th>
                        <th>Probability</th>
                        <th>Target</th>
                    </tr>
                </thead>

                <tbody>
                    {% for item in predictions[:8] %}
                    <tr>
                        <td>
                            <a href="/stocks/{{ item.symbol }}">
                                {{ item.symbol }}
                            </a>
                        </td>

                        <td class="{% if item.expected_return_pct >= 0 %}positive{% else %}negative{% endif %}">
                            {{ item.expected_return_pct }}%
                        </td>

                        <td>
                            {{ item.probability_success_pct }}%
                        </td>

                        <td>
                            KSh {{ item.target_price }}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </article>

</section>

<section class="panel">
    <div class="panel-heading">
        <div>
            <span class="section-label">Opportunity Ranking</span>
            <h2>AI Stock Screener</h2>
        </div>

        <a class="panel-link" href="/screener">
            View full screener
        </a>
    </div>

    <div class="table-wrapper">
        <table>
            <thead>
                <tr>
                    <th>Rank</th>
                    <th>Symbol</th>
                    <th>Company</th>
                    <th>Price</th>
                    <th>Decision</th>
                    <th>Confidence</th>
                    <th>Risk</th>
                    <th>Position</th>
                </tr>
            </thead>

            <tbody>
                {% for stock in screener[:15] %}
                <tr>
                    <td>{{ loop.index }}</td>

                    <td>
                        <a href="/stocks/{{ stock.symbol }}">
                            {{ stock.symbol }}
                        </a>
                    </td>

                    <td>{{ stock.name }}</td>

                    <td>
                        KSh {{ "{:,.2f}".format(stock.price) }}
                    </td>

                    <td>
                        <span class="signal signal-{{ stock.decision|lower|replace(' ', '-') }}">
                            {{ stock.decision }}
                        </span>
                    </td>

                    <td>{{ stock.confidence }}%</td>
                    <td>{{ stock.risk }}</td>
                    <td>{{ stock.position }}%</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</section>

<section class="content-grid three-columns">

    <article class="panel">
        <div class="panel-heading">
            <div>
                <span class="section-label">Capital Allocation</span>
                <h2>Portfolio Optimizer</h2>
            </div>
        </div>

        <div class="metric-list">
            <div>
                <span>Recommended positions</span>
                <strong>{{ optimized_portfolio.position_count }}</strong>
            </div>

            <div>
                <span>Invested allocation</span>
                <strong>
                    {{ optimized_portfolio.invested_percentage }}%
                </strong>
            </div>

            <div>
                <span>Cash reserve</span>
                <strong>
                    {{ optimized_portfolio.cash_percentage }}%
                </strong>
            </div>

            <div>
                <span>Risk</span>
                <strong>{{ optimized_portfolio.risk_level }}</strong>
            </div>
        </div>
    </article>

    <article class="panel">
        <div class="panel-heading">
            <div>
                <span class="section-label">Risk Analytics</span>
                <h2>Institutional Risk</h2>
            </div>
        </div>

        <div class="metric-list">
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
        </div>
    </article>

    <article class="panel">
        <div class="panel-heading">
            <div>
                <span class="section-label">Sector Intelligence</span>
                <h2>Sector Rotation</h2>
            </div>
        </div>

        {% if sector_rotation.strongest_sector %}
        <div class="sector-highlight">
            <span>Strongest sector</span>
            <strong>
                {{ sector_rotation.strongest_sector.sector }}
            </strong>
            <small>
                {{ sector_rotation.strongest_sector.average_change_pct }}%
            </small>
        </div>
        {% endif %}

        <div class="sector-list">
            {% for item in sector_rotation.sectors[:5] %}
            <div>
                <span>{{ item.sector }}</span>

                <strong class="{% if item.average_change_pct >= 0 %}positive{% else %}negative{% endif %}">
                    {{ item.average_change_pct }}%
                </strong>
            </div>
            {% endfor %}
        </div>
    </article>

</section>

<section class="content-grid two-columns">

    <article class="panel">
        <div class="panel-heading">
            <div>
                <span class="section-label">Performance</span>
                <h2>AI Performance Analytics</h2>
            </div>
        </div>

        <div class="metric-list">
            <div>
                <span>Recommendations</span>
                <strong>{{ performance.recommendations }}</strong>
            </div>

            <div>
                <span>Evaluations</span>
                <strong>{{ performance.evaluations }}</strong>
            </div>

            <div>
                <span>Accuracy</span>
                <strong>{{ performance.accuracy }}%</strong>
            </div>

            <div>
                <span>Average return</span>
                <strong class="{% if performance.average_return >= 0 %}positive{% else %}negative{% endif %}">
                    {{ performance.average_return }}%
                </strong>
            </div>
        </div>
    </article>

    <article class="panel report-card">
        <div>
            <span class="section-label">Reporting</span>
            <h2>Daily Intelligence Report</h2>

            <p>
                Download the latest executive market intelligence
                report in PDF format.
            </p>
        </div>

        <a class="primary-button" href="/download_report">
            Download PDF Report
        </a>
    </article>

</section>

</main>

<footer class="app-footer">
    <strong>MIP PRO</strong>
    <span>Market Intelligence Platform</span>
    <span>Version 11.5 RC1</span>
    <span>Built in Kenya</span>
</footer>

</body>
</html>
HTML

echo
echo "[3/7] Creating clean V11.5 stylesheet..."

cat > static/css/v115.css <<'CSS'
:root {
    --black: #121814;
    --dark: #17221b;
    --green: #08783f;
    --green-dark: #055d30;
    --red: #c8102e;
    --gold: #b48c25;
    --gold-soft: #f6efd9;
    --background: #eef3ef;
    --surface: #ffffff;
    --border: #dce5df;
    --muted: #6d7972;
    --shadow: 0 14px 36px rgba(20, 45, 32, 0.08);
}

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background: var(--background);
    color: var(--dark);
    font-family:
        Inter,
        ui-sans-serif,
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
}

a {
    color: var(--green-dark);
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

.app-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 30px;
    padding: 20px 34px;
    background: #ffffff;
    border-bottom: 1px solid var(--border);
}

.brand-area {
    display: flex;
    align-items: center;
    gap: 20px;
}

.brand-logo {
    width: 135px;
    max-height: 80px;
    object-fit: contain;
}

.text-logo {
    font-size: 36px;
    font-weight: 900;
    letter-spacing: -2px;
    white-space: nowrap;
}

.text-logo .mip {
    color: #111111;
}

.text-logo .pro {
    margin-left: 5px;
    color: var(--red);
}

.brand-copy h1 {
    margin: 0;
    color: var(--black);
    font-size: 25px;
    letter-spacing: -0.5px;
}

.brand-copy p {
    margin: 3px 0 0;
    color: var(--gold);
    font-weight: 700;
}

.header-nav {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 18px;
}

.header-nav a {
    color: #48554e;
    font-size: 14px;
    font-weight: 700;
}

.status-strip {
    display: grid;
    grid-template-columns: repeat(5, minmax(150px, 1fr));
    background: #151b17;
    color: #ffffff;
}

.status-strip div {
    padding: 13px 20px;
    border-right: 1px solid rgba(255,255,255,0.09);
}

.status-strip span,
.status-strip strong {
    display: block;
}

.status-strip span {
    margin-bottom: 3px;
    color: #aab5ae;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

.status-strip strong {
    overflow: hidden;
    font-size: 13px;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.status-live {
    color: #42d17b;
}

.page-shell {
    width: min(1680px, calc(100% - 40px));
    margin: 24px auto;
}

.kpi-grid {
    display: grid;
    grid-template-columns: repeat(6, minmax(180px, 1fr));
    gap: 15px;
    margin-bottom: 20px;
}

.kpi-card {
    position: relative;
    min-height: 130px;
    padding: 20px;
    overflow: hidden;
    border: 1px solid var(--border);
    border-radius: 14px;
    background: var(--surface);
    box-shadow: var(--shadow);
}

.kpi-card::before {
    position: absolute;
    top: 0;
    right: 0;
    left: 0;
    height: 4px;
    content: "";
    background: var(--green);
}

.kpi-card.gold::before {
    background: var(--gold);
}

.kpi-card.red::before {
    background: var(--red);
}

.kpi-card.black::before {
    background: var(--black);
}

.kpi-label {
    display: block;
    margin-bottom: 11px;
    color: var(--muted);
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.07em;
    text-transform: uppercase;
}

.kpi-card strong {
    display: block;
    margin-bottom: 8px;
    color: var(--black);
    font-size: 24px;
    line-height: 1.1;
}

.kpi-card strong.compact {
    font-size: 18px;
}

.kpi-card small {
    color: var(--muted);
    font-size: 12px;
}

.content-grid {
    display: grid;
    gap: 18px;
    margin-bottom: 20px;
}

.two-columns {
    grid-template-columns: repeat(2, minmax(0, 1fr));
}

.three-columns {
    grid-template-columns: repeat(3, minmax(0, 1fr));
}

.panel {
    padding: 22px;
    border: 1px solid var(--border);
    border-radius: 16px;
    background: var(--surface);
    box-shadow: var(--shadow);
    margin-bottom: 20px;
}

.panel-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
    margin-bottom: 18px;
}

.panel-heading h2,
.report-card h2 {
    margin: 3px 0 0;
    color: var(--black);
    font-size: 20px;
}

.section-label {
    color: var(--gold);
    font-size: 10px;
    font-weight: 900;
    letter-spacing: 0.09em;
    text-transform: uppercase;
}

.panel-summary {
    color: var(--muted);
    line-height: 1.6;
}

.panel-link {
    font-size: 13px;
    font-weight: 800;
}

.decision-badge {
    padding: 8px 12px;
    border-radius: 999px;
    background: rgba(8, 120, 63, 0.10);
    color: var(--green);
    font-size: 12px;
    font-weight: 900;
}

.agent-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
}

.agent-card {
    padding: 14px;
    border-radius: 10px;
    background: #f4f7f5;
}

.agent-card span,
.agent-card strong,
.agent-card b,
.agent-card small {
    display: block;
}

.agent-card span {
    color: var(--muted);
    font-size: 10px;
}

.agent-card strong {
    margin: 5px 0;
    font-size: 13px;
}

.agent-card b {
    color: var(--green);
    font-size: 13px;
}

.agent-card small {
    margin-top: 4px;
    color: var(--muted);
}

.table-wrapper {
    overflow-x: auto;
}

table {
    width: 100%;
    border-collapse: collapse;
}

th {
    padding: 11px 12px;
    background: #f1f5f2;
    color: #4e5b54;
    font-size: 11px;
    text-align: left;
    text-transform: uppercase;
}

td {
    padding: 12px;
    border-bottom: 1px solid #e7ede9;
    font-size: 13px;
}

tbody tr:hover {
    background: #fafcfb;
}

.signal {
    display: inline-block;
    padding: 5px 8px;
    border-radius: 999px;
    font-size: 10px;
    font-weight: 900;
}

.signal-buy,
.signal-strong-buy {
    background: rgba(8, 120, 63, 0.11);
    color: var(--green);
}

.signal-sell,
.signal-strong-sell {
    background: rgba(200, 16, 46, 0.10);
    color: var(--red);
}

.signal-hold,
.signal-watch {
    background: var(--gold-soft);
    color: #846519;
}

.metric-list {
    display: grid;
    gap: 9px;
}

.metric-list div,
.sector-list div {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 15px;
    padding: 11px 0;
    border-bottom: 1px solid #edf1ee;
}

.metric-list span,
.sector-list span {
    color: var(--muted);
    font-size: 13px;
}

.metric-list strong,
.sector-list strong {
    font-size: 14px;
}

.sector-highlight {
    margin-bottom: 12px;
    padding: 17px;
    border-radius: 11px;
    background: var(--gold-soft);
}

.sector-highlight span,
.sector-highlight strong,
.sector-highlight small {
    display: block;
}

.sector-highlight span {
    color: #7f681f;
    font-size: 10px;
    font-weight: 800;
    text-transform: uppercase;
}

.sector-highlight strong {
    margin: 5px 0;
    font-size: 20px;
}

.report-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 30px;
}

.report-card p {
    color: var(--muted);
}

.primary-button {
    display: inline-block;
    padding: 12px 17px;
    border-radius: 9px;
    background: linear-gradient(135deg, var(--green), var(--green-dark));
    color: #ffffff;
    font-weight: 800;
    white-space: nowrap;
}

.positive {
    color: var(--green) !important;
}

.negative {
    color: var(--red) !important;
}

.app-footer {
    display: flex;
    justify-content: center;
    flex-wrap: wrap;
    gap: 18px;
    padding: 25px;
    border-top: 1px solid var(--border);
    background: #ffffff;
    color: var(--muted);
    font-size: 12px;
}

.app-footer strong {
    color: var(--black);
}

@media (max-width: 1450px) {
    .kpi-grid {
        grid-template-columns: repeat(3, minmax(180px, 1fr));
    }
}

@media (max-width: 1050px) {
    .app-header {
        align-items: flex-start;
        flex-direction: column;
    }

    .status-strip {
        grid-template-columns: repeat(3, minmax(140px, 1fr));
    }

    .two-columns,
    .three-columns {
        grid-template-columns: 1fr;
    }
}

@media (max-width: 700px) {
    .page-shell {
        width: min(100% - 20px, 1680px);
    }

    .brand-area {
        align-items: flex-start;
        flex-direction: column;
    }

    .kpi-grid {
        grid-template-columns: 1fr;
    }

    .status-strip {
        grid-template-columns: 1fr;
    }

    .agent-grid {
        grid-template-columns: 1fr;
    }

    .report-card {
        align-items: flex-start;
        flex-direction: column;
    }
}
CSS

echo
echo "[4/7] Switching Flask to the new dashboard..."

python - <<'PY'
from pathlib import Path

path = Path("app.py")
text = path.read_text(encoding="utf-8")

old = '''        "dashboard.html",'''
new = '''        "dashboard_v115.html",'''

if old not in text:
    raise SystemExit(
        'Unable to find render_template("dashboard.html") in app.py'
    )

text = text.replace(old, new, 1)

text = text.replace(
    'VERSION = "11.5 Professional Intelligence Suite"',
    'VERSION = "11.5 RC1"',
)

path.write_text(text, encoding="utf-8")
print("Flask now uses dashboard_v115.html")
PY

echo
echo "[5/7] Validating source files..."

"$PROJECT/venv/bin/python" -m py_compile \
    app.py \
    services/*.py

"$PROJECT/venv/bin/python" - <<'PY'
from pathlib import Path

template = Path("templates/dashboard_v115.html")
stylesheet = Path("static/css/v115.css")

assert template.exists(), "New dashboard template is missing"
assert stylesheet.exists(), "New dashboard stylesheet is missing"

required = [
    "Market Intelligence Platform",
    "AI Stock Screener",
    "Portfolio Optimizer",
    "Institutional Risk",
    "Daily Intelligence Report",
]

content = template.read_text(encoding="utf-8")

missing = [item for item in required if item not in content]

if missing:
    raise RuntimeError(
        "Template validation failed: " + ", ".join(missing)
    )

print("Source validation passed.")
PY

echo
echo "[6/7] Restarting application..."

"$PROJECT/restart.sh"

echo
echo "[7/7] Running release checks..."

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

DASHBOARD_CODE="$(
    curl -s -o /dev/null -w "%{http_code}" \
    http://127.0.0.1:5000/
)"

if [ "$DASHBOARD_CODE" != "302" ]; then
    echo "Authentication protection failed: HTTP $DASHBOARD_CODE"
    exit 1
fi

trap - ERR

echo
echo "=================================================="
echo "MIP PRO V11.5 RC1 installed successfully"
echo "=================================================="
echo "Backup: $BACKUP"
echo "Log: $LOG"
echo
echo "Open:"
echo "http://164.92.133.0/login"
echo
echo "Sign in and press Ctrl + F5."
echo "=================================================="
