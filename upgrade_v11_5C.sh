#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT="/root/nse_signal_bot_v10_3"
STAMP="$(date +%Y-%m-%d_%H-%M-%S)"
BACKUP="$PROJECT/backups/v11_5C_$STAMP"
LOG="$PROJECT/logs/upgrade_v11_5C_$STAMP.log"

cd "$PROJECT"

mkdir -p \
    "$BACKUP/templates" \
    "$BACKUP/static/css" \
    "$PROJECT/logs"

exec > >(tee -a "$LOG") 2>&1

rollback() {
    echo
    echo "V11.5C failed. Restoring previous files..."

    [ -f "$BACKUP/templates/dashboard.html" ] &&
        cp "$BACKUP/templates/dashboard.html" \
           "$PROJECT/templates/dashboard.html"

    [ -f "$BACKUP/static/css/style.css" ] &&
        cp "$BACKUP/static/css/style.css" \
           "$PROJECT/static/css/style.css"

    "$PROJECT/restart.sh" || true

    echo "Rollback completed."
    exit 1
}

trap rollback ERR

echo "=================================================="
echo "MIP PRO V11.5C"
echo "Executive KPI Dashboard Upgrade"
echo "=================================================="

echo
echo "[1/6] Creating backups..."

cp templates/dashboard.html \
   "$BACKUP/templates/dashboard.html"

cp static/css/style.css \
   "$BACKUP/static/css/style.css"

echo "Backup created: $BACKUP"

echo
echo "[2/6] Installing executive KPI cards..."

python - <<'PY'
from pathlib import Path
import re

path = Path("templates/dashboard.html")
text = path.read_text(encoding="utf-8")

new_summary = '''
<section class="executive-kpi-grid">

    <article class="executive-kpi-card market-kpi">
        <div class="kpi-icon">M</div>

        <div class="kpi-content">
            <span class="kpi-label">Market Status</span>

            <strong class="kpi-value">
                {{ market.market_status }}
            </strong>

            <small>
                Average movement:
                <span class="{% if market.average_change >= 0 %}positive{% else %}negative{% endif %}">
                    {{ market.average_change }}%
                </span>
            </small>
        </div>
    </article>

    <article class="executive-kpi-card confidence-kpi">
        <div class="kpi-icon">AI</div>

        <div class="kpi-content">
            <span class="kpi-label">AI Confidence</span>

            <strong class="kpi-value">
                {{ committee.confidence }}%
            </strong>

            <div class="executive-progress">
                <div
                    class="executive-progress-fill"
                    style="width: {{ committee.confidence }}%">
                </div>
            </div>

            <small>{{ committee.final_decision }}</small>
        </div>
    </article>

    <article class="executive-kpi-card regime-kpi">
        <div class="kpi-icon">R</div>

        <div class="kpi-content">
            <span class="kpi-label">Market Regime</span>

            <strong class="kpi-value compact-value">
                {{ regime.regime|default('Collecting Data') }}
            </strong>

            <small>
                Confidence:
                {{ regime.confidence_pct|default(0) }}%
            </small>
        </div>
    </article>

    <article class="executive-kpi-card portfolio-kpi">
        <div class="kpi-icon">KSh</div>

        <div class="kpi-content">
            <span class="kpi-label">Portfolio Value</span>

            <strong class="kpi-value">
                KSh {{ "{:,.2f}".format(portfolio.total_value) }}
            </strong>

            <small>
                Return:
                <span class="{% if portfolio.pnl_pct >= 0 %}positive{% else %}negative{% endif %}">
                    {{ portfolio.pnl_pct }}%
                </span>
            </small>
        </div>
    </article>

    <article class="executive-kpi-card opportunity-kpi">
        <div class="kpi-icon">★</div>

        <div class="kpi-content">
            <span class="kpi-label">Top Opportunity</span>

            {% if screener %}
            <strong class="kpi-value">
                {{ screener[0].symbol }}
            </strong>

            <small>
                {{ screener[0].decision }}
                · {{ screener[0].confidence }}%
                · KSh {{ screener[0].price }}
            </small>
            {% else %}
            <strong class="kpi-value compact-value">
                No Signal
            </strong>

            <small>Waiting for market analysis</small>
            {% endif %}
        </div>
    </article>

    <article class="executive-kpi-card risk-kpi">
        <div class="kpi-icon">!</div>

        <div class="kpi-content">
            <span class="kpi-label">Institutional Risk</span>

            <strong class="kpi-value compact-value">
                {{ risk_metrics.market_risk_level|default('Collecting Data') }}
            </strong>

            <small>
                VaR 95%:
                {{ risk_metrics.average_var_95_pct|default(0) }}%
            </small>
        </div>
    </article>

</section>
'''

pattern = re.compile(
    r'<section class="summary-grid">.*?</section>',
    re.DOTALL,
)

if pattern.search(text):
    text = pattern.sub(new_summary, text, count=1)
elif "executive-kpi-grid" not in text:
    marker = '<main class="dashboard-container">'

    if marker not in text:
        raise SystemExit(
            "Dashboard main container was not found."
        )

    text = text.replace(
        marker,
        marker + "\n" + new_summary,
        1,
    )

path.write_text(text, encoding="utf-8")
print("Executive KPI cards installed.")
PY

echo
echo "[3/6] Improving dashboard section hierarchy..."

python - <<'PY'
from pathlib import Path

path = Path("templates/dashboard.html")
text = path.read_text(encoding="utf-8")

text = text.replace(
    '<p class="eyebrow">AI rankings</p>',
    '<p class="eyebrow">Institutional opportunity ranking</p>',
)

text = text.replace(
    '<p class="eyebrow">AI strategy</p>',
    '<p class="eyebrow">Autonomous investment intelligence</p>',
)

text = text.replace(
    '<p class="eyebrow">Portfolio intelligence</p>',
    '<p class="eyebrow">Capital and allocation intelligence</p>',
)

text = text.replace(
    '<p class="eyebrow">Market overview</p>',
    '<p class="eyebrow">Live market intelligence</p>',
)

text = text.replace(
    '<p class="eyebrow">Multi-agent intelligence</p>',
    '<p class="eyebrow">Multi-agent investment intelligence</p>',
)

path.write_text(text, encoding="utf-8")
print("Dashboard hierarchy improved.")
PY

echo
echo "[4/6] Installing executive styles..."

cat >> static/css/style.css <<'CSS'

/* ==================================================
   MIP PRO V11.5C Executive KPI Dashboard
   ================================================== */

:root {
    --mip-black: #111111;
    --mip-red: #c8102e;
    --mip-green: #08783f;
    --mip-dark-green: #064b2b;
    --mip-gold: #b9922a;
    --mip-soft-gold: #f8f2df;
    --mip-surface: #ffffff;
    --mip-background: #f4f7f5;
    --mip-border: rgba(16, 56, 35, 0.10);
    --mip-muted: #68766f;
}

body {
    background: var(--mip-background);
}

.executive-kpi-grid {
    display: grid;
    grid-template-columns:
        repeat(6, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 22px;
}

.executive-kpi-card {
    position: relative;
    display: flex;
    align-items: flex-start;
    gap: 14px;
    min-width: 0;
    padding: 20px;
    overflow: hidden;
    border: 1px solid var(--mip-border);
    border-radius: 16px;
    background: var(--mip-surface);
    box-shadow:
        0 10px 26px rgba(20, 45, 32, 0.07);
    transition:
        transform 180ms ease,
        box-shadow 180ms ease;
}

.executive-kpi-card::before {
    position: absolute;
    top: 0;
    right: 0;
    left: 0;
    height: 4px;
    content: "";
    background: var(--mip-green);
}

.executive-kpi-card:hover {
    transform: translateY(-2px);
    box-shadow:
        0 15px 36px rgba(20, 45, 32, 0.11);
}

.market-kpi::before,
.confidence-kpi::before {
    background: var(--mip-green);
}

.regime-kpi::before,
.portfolio-kpi::before {
    background: var(--mip-gold);
}

.opportunity-kpi::before {
    background:
        linear-gradient(
            90deg,
            var(--mip-black),
            var(--mip-red),
            var(--mip-green)
        );
}

.risk-kpi::before {
    background: var(--mip-red);
}

.kpi-icon {
    display: grid;
    flex: 0 0 42px;
    width: 42px;
    height: 42px;
    place-items: center;
    border-radius: 12px;
    background: rgba(8, 120, 63, 0.09);
    color: var(--mip-green);
    font-size: 13px;
    font-weight: 900;
}

.regime-kpi .kpi-icon,
.portfolio-kpi .kpi-icon {
    background: var(--mip-soft-gold);
    color: #8b6816;
}

.risk-kpi .kpi-icon {
    background: rgba(200, 16, 46, 0.09);
    color: var(--mip-red);
}

.opportunity-kpi .kpi-icon {
    background: #151515;
    color: #ffffff;
}

.kpi-content {
    min-width: 0;
}

.kpi-label {
    display: block;
    margin-bottom: 8px;
    color: var(--mip-muted);
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.07em;
    text-transform: uppercase;
}

.kpi-value {
    display: block;
    overflow: hidden;
    margin-bottom: 6px;
    color: #17231d;
    font-size: clamp(20px, 2vw, 28px);
    font-weight: 850;
    letter-spacing: -0.5px;
    line-height: 1.08;
    text-overflow: ellipsis;
}

.compact-value {
    font-size: clamp(16px, 1.5vw, 21px);
    line-height: 1.2;
    white-space: normal;
}

.kpi-content small {
    display: block;
    overflow: hidden;
    color: var(--mip-muted);
    font-size: 12px;
    line-height: 1.4;
    text-overflow: ellipsis;
}

.executive-progress {
    height: 6px;
    margin: 8px 0;
    overflow: hidden;
    border-radius: 999px;
    background: #e7ece9;
}

.executive-progress-fill {
    height: 100%;
    border-radius: inherit;
    background:
        linear-gradient(
            90deg,
            var(--mip-green),
            #19a35d
        );
}

.mip-header-copy .subtitle {
    color: var(--mip-gold);
    font-weight: 700;
    letter-spacing: 0.02em;
}

.panel-heading h2 {
    color: #142219;
    letter-spacing: -0.3px;
}

.panel-heading .eyebrow {
    color: var(--mip-gold);
}

.button {
    background:
        linear-gradient(
            135deg,
            var(--mip-green),
            var(--mip-dark-green)
        );
}

.secondary-button {
    border-color: rgba(8, 120, 63, 0.24);
    background: #ffffff;
    color: var(--mip-green);
}

.text-link {
    color: var(--mip-green);
}

.symbol-link {
    color: var(--mip-dark-green);
    font-weight: 850;
}

.positive {
    color: var(--mip-green);
}

.negative {
    color: var(--mip-red);
}

.signal-buy,
.signal-strong-buy {
    background: rgba(8, 120, 63, 0.10);
    color: var(--mip-green);
}

.signal-sell,
.signal-strong-sell {
    background: rgba(200, 16, 46, 0.10);
    color: var(--mip-red);
}

.dashboard-footer {
    border-top: 1px solid var(--mip-border);
    background: #ffffff;
}

@media (max-width: 1500px) {
    .executive-kpi-grid {
        grid-template-columns:
            repeat(3, minmax(210px, 1fr));
    }
}

@media (max-width: 900px) {
    .executive-kpi-grid {
        grid-template-columns:
            repeat(2, minmax(180px, 1fr));
    }
}

@media (max-width: 560px) {
    .executive-kpi-grid {
        grid-template-columns: 1fr;
    }

    .executive-kpi-card {
        padding: 18px;
    }
}
CSS

echo
echo "[5/6] Validating dashboard..."

python - <<'PY'
from pathlib import Path

template = Path(
    "templates/dashboard.html"
).read_text(encoding="utf-8")

required = [
    "executive-kpi-grid",
    "Market Status",
    "AI Confidence",
    "Market Regime",
    "Portfolio Value",
    "Top Opportunity",
    "Institutional Risk",
]

missing = [
    item for item in required
    if item not in template
]

if missing:
    raise SystemExit(
        "Dashboard validation failed. Missing: "
        + ", ".join(missing)
    )

print("Dashboard validation passed.")
PY

"$PROJECT/venv/bin/python" -m py_compile \
    app.py \
    services/*.py

echo "Python syntax checks passed."

echo
echo "[6/6] Restarting and testing..."

"$PROJECT/restart.sh"

HEALTH="$(
    curl -fsS http://127.0.0.1:5000/health
)"

echo "Health response:"
echo "$HEALTH"

echo "$HEALTH" | grep -q '"status":"online"'

LOGIN_CODE="$(
    curl -s -o /dev/null -w "%{http_code}" \
    http://127.0.0.1:5000/login
)"

if [ "$LOGIN_CODE" != "200" ]; then
    echo "Login page failed: HTTP $LOGIN_CODE"
    exit 1
fi

trap - ERR

echo
echo "=================================================="
echo "MIP PRO V11.5C installed successfully"
echo "=================================================="
echo "Backup: $BACKUP"
echo "Log: $LOG"
echo
echo "Sign in and press Ctrl + F5."
echo "=================================================="
