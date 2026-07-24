#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$HOME/nse_signal_bot_v10_3}"
SERVICE_NAME="${SERVICE_NAME:-nse-v10-3.service}"
TEMPLATE="templates/dashboard_v115.html"

cd "$PROJECT_DIR"

STAMP="$(date +%F_%H-%M-%S)"
BACKUP_DIR="backups/intelligence_analytics_stage3/$STAMP"
REPORT_FILE="reports/intelligence_analytics_stage3.txt"

mkdir -p \
    "$BACKUP_DIR" \
    scripts \
    reports

echo "======================================================"
echo "MIP PRO Intelligence Analytics — Stage 3"
echo "Dashboard Integration"
echo "======================================================"

if [[ ! -f "$TEMPLATE" ]]; then
    echo "ERROR: $TEMPLATE was not found."
    exit 1
fi

if [[ ! -f services/intelligence_analytics.py ]]; then
    echo "ERROR: Intelligence analytics service is missing."
    exit 1
fi

if ! grep -q '/api/v11.7/intelligence/summary' app.py; then
    echo "ERROR: Stage 2 summary API route is missing."
    exit 1
fi

echo
echo "==> Creating template backup"

cp "$TEMPLATE" "$BACKUP_DIR/dashboard_v115.html"

echo "Backup created:"
echo "$BACKUP_DIR/dashboard_v115.html"

echo
echo "==> Patching dashboard template"

venv/bin/python - <<'PY'
from pathlib import Path

template_path = Path("templates/dashboard_v115.html")
text = template_path.read_text(encoding="utf-8")

STYLE_MARKER = "BEGIN MIP PRO INTELLIGENCE ANALYTICS STYLES"
HTML_MARKER = "BEGIN MIP PRO INTELLIGENCE ANALYTICS PANEL"
SCRIPT_MARKER = "BEGIN MIP PRO INTELLIGENCE ANALYTICS SCRIPT"

styles = r'''
<!-- BEGIN MIP PRO INTELLIGENCE ANALYTICS STYLES -->
<style>
    .mip-intelligence-analytics {
        margin-top: 24px;
        margin-bottom: 24px;
    }

    .mip-intelligence-header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 16px;
        margin-bottom: 16px;
        flex-wrap: wrap;
    }

    .mip-intelligence-header h2 {
        margin: 0;
    }

    .mip-intelligence-subtitle {
        margin: 5px 0 0;
        opacity: 0.72;
        font-size: 0.9rem;
    }

    .mip-intelligence-status {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        padding: 7px 12px;
        border-radius: 999px;
        font-size: 0.82rem;
        font-weight: 700;
        background: rgba(148, 163, 184, 0.16);
    }

    .mip-intelligence-status::before {
        content: "";
        width: 9px;
        height: 9px;
        border-radius: 50%;
        background: #94a3b8;
    }

    .mip-intelligence-status.is-healthy::before {
        background: #22c55e;
        box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.14);
    }

    .mip-intelligence-status.is-degraded::before,
    .mip-intelligence-status.is-error::before {
        background: #ef4444;
        box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.14);
    }

    .mip-analytics-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 14px;
    }

    .mip-analytics-card {
        min-width: 0;
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 14px;
        padding: 16px;
        background: rgba(15, 23, 42, 0.2);
    }

    .mip-analytics-label {
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.045em;
        opacity: 0.7;
        margin-bottom: 8px;
    }

    .mip-analytics-value {
        font-size: 1.45rem;
        font-weight: 800;
        line-height: 1.15;
        word-break: break-word;
    }

    .mip-analytics-detail {
        margin-top: 7px;
        font-size: 0.78rem;
        opacity: 0.68;
    }

    .mip-analytics-lower-grid {
        display: grid;
        grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
        gap: 14px;
        margin-top: 14px;
    }

    .mip-analytics-table-wrapper {
        width: 100%;
        overflow-x: auto;
    }

    .mip-analytics-table {
        width: 100%;
        border-collapse: collapse;
        min-width: 520px;
    }

    .mip-analytics-table th,
    .mip-analytics-table td {
        padding: 10px 9px;
        text-align: left;
        border-bottom: 1px solid rgba(148, 163, 184, 0.16);
        white-space: nowrap;
    }

    .mip-analytics-table th {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        opacity: 0.68;
    }

    .mip-analytics-table td {
        font-size: 0.88rem;
    }

    .mip-analytics-empty {
        padding: 22px 8px;
        text-align: center;
        opacity: 0.68;
    }

    .mip-regime-badge {
        display: inline-flex;
        padding: 5px 9px;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 800;
        background: rgba(148, 163, 184, 0.15);
    }

    .mip-regime-badge.regime-bull,
    .mip-regime-badge.regime-bullish {
        background: rgba(34, 197, 94, 0.16);
        color: #4ade80;
    }

    .mip-regime-badge.regime-bear,
    .mip-regime-badge.regime-bearish {
        background: rgba(239, 68, 68, 0.16);
        color: #f87171;
    }

    .mip-regime-badge.regime-sideways,
    .mip-regime-badge.regime-neutral {
        background: rgba(245, 158, 11, 0.16);
        color: #fbbf24;
    }

    @media (max-width: 1100px) {
        .mip-analytics-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
    }

    @media (max-width: 760px) {
        .mip-analytics-grid,
        .mip-analytics-lower-grid {
            grid-template-columns: 1fr;
        }

        .mip-analytics-value {
            font-size: 1.25rem;
        }
    }
</style>
<!-- END MIP PRO INTELLIGENCE ANALYTICS STYLES -->
'''

panel = r'''
<!-- BEGIN MIP PRO INTELLIGENCE ANALYTICS PANEL -->
<section
    id="mip-intelligence-analytics"
    class="panel mip-intelligence-analytics"
>
    <div class="mip-intelligence-header">
        <div>
            <h2>Intelligence Analytics</h2>
            <p class="mip-intelligence-subtitle">
                Historical AI decisions, engine performance and repository health
            </p>
        </div>

        <div
            id="mip-analytics-status"
            class="mip-intelligence-status"
        >
            Loading
        </div>
    </div>

    <div class="mip-analytics-grid">
        <article class="mip-analytics-card">
            <div class="mip-analytics-label">Total Intelligence Runs</div>
            <div id="mip-total-runs" class="mip-analytics-value">—</div>
            <div id="mip-run-activity" class="mip-analytics-detail">
                Loading activity
            </div>
        </article>

        <article class="mip-analytics-card">
            <div class="mip-analytics-label">Current Market Regime</div>
            <div id="mip-current-regime" class="mip-analytics-value">—</div>
            <div id="mip-regime-detail" class="mip-analytics-detail">
                Loading regime
            </div>
        </article>

        <article class="mip-analytics-card">
            <div class="mip-analytics-label">Average Engine Time</div>
            <div id="mip-average-runtime" class="mip-analytics-value">—</div>
            <div id="mip-engine-detail" class="mip-analytics-detail">
                Loading performance
            </div>
        </article>

        <article class="mip-analytics-card">
            <div class="mip-analytics-label">Most Recommended Stock</div>
            <div id="mip-top-stock" class="mip-analytics-value">—</div>
            <div id="mip-top-stock-detail" class="mip-analytics-detail">
                Loading recommendations
            </div>
        </article>

        <article class="mip-analytics-card">
            <div class="mip-analytics-label">AI Confidence</div>
            <div id="mip-average-confidence" class="mip-analytics-value">—</div>
            <div class="mip-analytics-detail">
                Historical committee average
            </div>
        </article>

        <article class="mip-analytics-card">
            <div class="mip-analytics-label">Success Rate</div>
            <div id="mip-success-rate" class="mip-analytics-value">—</div>
            <div id="mip-success-detail" class="mip-analytics-detail">
                Loading repository activity
            </div>
        </article>

        <article class="mip-analytics-card">
            <div class="mip-analytics-label">Repository Integrity</div>
            <div id="mip-repository-integrity" class="mip-analytics-value">—</div>
            <div id="mip-repository-detail" class="mip-analytics-detail">
                Loading repository health
            </div>
        </article>

        <article class="mip-analytics-card">
            <div class="mip-analytics-label">Latest Intelligence Run</div>
            <div id="mip-latest-run" class="mip-analytics-value">—</div>
            <div id="mip-latest-run-detail" class="mip-analytics-detail">
                Loading latest run
            </div>
        </article>
    </div>

    <div class="mip-analytics-lower-grid">
        <article class="mip-analytics-card">
            <h3>Top AI Recommendations</h3>

            <div class="mip-analytics-table-wrapper">
                <table class="mip-analytics-table">
                    <thead>
                        <tr>
                            <th>Symbol</th>
                            <th>Count</th>
                            <th>Confidence</th>
                            <th>Expected Return</th>
                        </tr>
                    </thead>
                    <tbody id="mip-top-recommendations">
                        <tr>
                            <td colspan="4" class="mip-analytics-empty">
                                Loading recommendations…
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </article>

        <article class="mip-analytics-card">
            <h3>Market Regime History</h3>

            <div class="mip-analytics-table-wrapper">
                <table class="mip-analytics-table">
                    <thead>
                        <tr>
                            <th>Regime</th>
                            <th>Occurrences</th>
                            <th>Share</th>
                            <th>Confidence</th>
                        </tr>
                    </thead>
                    <tbody id="mip-regime-distribution">
                        <tr>
                            <td colspan="4" class="mip-analytics-empty">
                                Loading regimes…
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </article>
    </div>
</section>
<!-- END MIP PRO INTELLIGENCE ANALYTICS PANEL -->
'''

script = r'''
<!-- BEGIN MIP PRO INTELLIGENCE ANALYTICS SCRIPT -->
<script>
(function () {
    "use strict";

    const SUMMARY_URL = "/api/v11.7/intelligence/summary";
    const REFRESH_INTERVAL_MS = 120000;

    function byId(id) {
        return document.getElementById(id);
    }

    function setText(id, value) {
        const element = byId(id);

        if (element) {
            element.textContent = value;
        }
    }

    function numberValue(value, fallback = 0) {
        const parsed = Number(value);

        return Number.isFinite(parsed) ? parsed : fallback;
    }

    function formatNumber(value, digits = 0) {
        return numberValue(value).toLocaleString(undefined, {
            minimumFractionDigits: digits,
            maximumFractionDigits: digits
        });
    }

    function formatPercent(value, digits = 1) {
        return formatNumber(value, digits) + "%";
    }

    function formatSeconds(value) {
        return formatNumber(value, 2) + " s";
    }

    function formatDate(value) {
        if (!value) {
            return "No completed run";
        }

        const date = new Date(value);

        if (Number.isNaN(date.getTime())) {
            return String(value);
        }

        return date.toLocaleString();
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }

    function regimeClass(value) {
        return String(value || "unknown")
            .trim()
            .toLowerCase()
            .replaceAll(" ", "-");
    }

    function setStatus(status, label) {
        const element = byId("mip-analytics-status");

        if (!element) {
            return;
        }

        element.classList.remove(
            "is-healthy",
            "is-degraded",
            "is-error"
        );

        element.classList.add(
            status === "healthy"
                ? "is-healthy"
                : status === "degraded"
                    ? "is-degraded"
                    : "is-error"
        );

        element.textContent = label;
    }

    function renderTopRecommendations(rows) {
        const body = byId("mip-top-recommendations");

        if (!body) {
            return;
        }

        if (!Array.isArray(rows) || rows.length === 0) {
            body.innerHTML = `
                <tr>
                    <td colspan="4" class="mip-analytics-empty">
                        No recommendation history available
                    </td>
                </tr>
            `;
            return;
        }

        body.innerHTML = rows.slice(0, 8).map((row) => `
            <tr>
                <td><strong>${escapeHtml(row.symbol || "—")}</strong></td>
                <td>${formatNumber(row.recommendation_count)}</td>
                <td>${formatPercent(row.average_confidence)}</td>
                <td>${formatPercent(row.average_expected_return)}</td>
            </tr>
        `).join("");
    }

    function renderRegimeDistribution(rows) {
        const body = byId("mip-regime-distribution");

        if (!body) {
            return;
        }

        if (!Array.isArray(rows) || rows.length === 0) {
            body.innerHTML = `
                <tr>
                    <td colspan="4" class="mip-analytics-empty">
                        No regime history available
                    </td>
                </tr>
            `;
            return;
        }

        body.innerHTML = rows.map((row) => {
            const regime = row.regime || "UNKNOWN";

            return `
                <tr>
                    <td>
                        <span class="mip-regime-badge regime-${regimeClass(regime)}">
                            ${escapeHtml(regime)}
                        </span>
                    </td>
                    <td>${formatNumber(row.count)}</td>
                    <td>${formatPercent(row.percentage)}</td>
                    <td>${formatPercent(row.average_confidence)}</td>
                </tr>
            `;
        }).join("");
    }

    function renderSummary(payload) {
        const activity = payload.activity || {};
        const engine = payload.engine || {};
        const market = payload.market || {};
        const recommendations = payload.recommendations || {};
        const repository = payload.repository || {};
        const latestRun = repository.latest_run || {};
        const regimes = payload.regimes || {};

        setStatus(
            payload.status || repository.status || "unknown",
            (payload.status || repository.status || "unknown").toUpperCase()
        );

        setText(
            "mip-total-runs",
            formatNumber(activity.total_runs)
        );

        setText(
            "mip-run-activity",
            `${formatNumber(activity.today_runs)} today · ` +
            `${formatNumber(activity.week_runs)} this week`
        );

        const currentRegime = market.current_regime || "UNKNOWN";

        byId("mip-current-regime").innerHTML = `
            <span class="mip-regime-badge regime-${regimeClass(currentRegime)}">
                ${escapeHtml(currentRegime)}
            </span>
        `;

        setText(
            "mip-regime-detail",
            `${formatPercent(market.regime_confidence)} confidence · ` +
            `${market.risk_level || "UNKNOWN"} risk`
        );

        setText(
            "mip-average-runtime",
            formatSeconds(engine.average_total_seconds)
        );

        setText(
            "mip-engine-detail",
            `Prediction ${formatSeconds(engine.average_prediction_center_seconds)} · ` +
            `Committee ${formatSeconds(engine.average_committee_seconds)}`
        );

        setText(
            "mip-top-stock",
            recommendations.most_recommended_stock || "—"
        );

        setText(
            "mip-top-stock-detail",
            `${formatPercent(recommendations.average_expected_return)} ` +
            `average expected return`
        );

        setText(
            "mip-average-confidence",
            formatPercent(recommendations.average_confidence)
        );

        setText(
            "mip-success-rate",
            formatPercent(activity.success_rate)
        );

        setText(
            "mip-success-detail",
            `${formatNumber(activity.completed_runs)} completed · ` +
            `${formatNumber(activity.failed_runs)} failed`
        );

        setText(
            "mip-repository-integrity",
            String(repository.integrity || "unknown").toUpperCase()
        );

        setText(
            "mip-repository-detail",
            `Repository ${repository.status || "unknown"}`
        );

        setText(
            "mip-latest-run",
            latestRun.market_regime || "—"
        );

        setText(
            "mip-latest-run-detail",
            `${formatDate(latestRun.generated_at)} · ` +
            `${formatSeconds(latestRun.total_seconds)}`
        );

        renderTopRecommendations(
            recommendations.top_symbols || []
        );

        renderRegimeDistribution(
            regimes.distribution || []
        );
    }

    function renderError(error) {
        console.error(
            "Intelligence analytics dashboard error:",
            error
        );

        setStatus("error", "UNAVAILABLE");

        setText("mip-total-runs", "—");
        setText("mip-run-activity", "Unable to load analytics");
        setText("mip-repository-detail", "API request failed");
    }

    async function loadIntelligenceAnalytics() {
        try {
            const response = await fetch(SUMMARY_URL, {
                method: "GET",
                credentials: "same-origin",
                headers: {
                    "Accept": "application/json"
                },
                cache: "no-store"
            });

            if (!response.ok) {
                throw new Error(
                    `Analytics API returned HTTP ${response.status}`
                );
            }

            const payload = await response.json();

            renderSummary(payload);
        } catch (error) {
            renderError(error);
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            loadIntelligenceAnalytics
        );
    } else {
        loadIntelligenceAnalytics();
    }

    window.setInterval(
        loadIntelligenceAnalytics,
        REFRESH_INTERVAL_MS
    );
})();
</script>
<!-- END MIP PRO INTELLIGENCE ANALYTICS SCRIPT -->
'''

changed = False

if STYLE_MARKER not in text:
    if "</head>" in text:
        text = text.replace(
            "</head>",
            styles + "\n</head>",
            1,
        )
    else:
        text = styles + "\n" + text

    changed = True
    print("Analytics styles added.")
else:
    print("Analytics styles already present.")

if HTML_MARKER not in text:
    insertion_candidates = [
        "</main>",
        "</body>",
    ]

    inserted = False

    for marker in insertion_candidates:
        if marker in text:
            text = text.replace(
                marker,
                panel + "\n" + marker,
                1,
            )
            inserted = True
            break

    if not inserted:
        text += "\n" + panel

    changed = True
    print("Analytics panel added.")
else:
    print("Analytics panel already present.")

if SCRIPT_MARKER not in text:
    if "</body>" in text:
        text = text.replace(
            "</body>",
            script + "\n</body>",
            1,
        )
    else:
        text += "\n" + script

    changed = True
    print("Analytics JavaScript added.")
else:
    print("Analytics JavaScript already present.")

if changed:
    template_path.write_text(
        text,
        encoding="utf-8",
    )
    print("Dashboard template updated successfully.")
else:
    print("No dashboard changes were required.")
PY

echo
echo "==> Verifying dashboard markers"

for marker in \
    "BEGIN MIP PRO INTELLIGENCE ANALYTICS STYLES" \
    "BEGIN MIP PRO INTELLIGENCE ANALYTICS PANEL" \
    "BEGIN MIP PRO INTELLIGENCE ANALYTICS SCRIPT"
do
    if grep -q "$marker" "$TEMPLATE"; then
        echo "PASS: $marker"
    else
        echo "ERROR: Missing marker: $marker"
        cp "$BACKUP_DIR/dashboard_v115.html" "$TEMPLATE"
        exit 1
    fi
done

echo
echo "==> Checking for duplicate installations"

venv/bin/python - <<'PY'
from pathlib import Path

text = Path(
    "templates/dashboard_v115.html"
).read_text(encoding="utf-8")

checks = {
    "style marker":
        text.count(
            "BEGIN MIP PRO INTELLIGENCE ANALYTICS STYLES"
        ),
    "panel marker":
        text.count(
            "BEGIN MIP PRO INTELLIGENCE ANALYTICS PANEL"
        ),
    "script marker":
        text.count(
            "BEGIN MIP PRO INTELLIGENCE ANALYTICS SCRIPT"
        ),
    "analytics section ID":
        text.count(
            'id="mip-intelligence-analytics"'
        ),
}

for name, count in checks.items():
    print(f"{name}: {count}")

    if count != 1:
        raise SystemExit(
            f"ERROR: Expected one {name}, found {count}"
        )

print("DUPLICATE INSTALLATION TEST: PASS")
PY

echo
echo "==> Validating Flask template rendering"

venv/bin/python - <<'PY'
from app import app

with app.test_request_context("/"):
    template = app.jinja_env.get_template(
        "dashboard_v115.html"
    )

    rendered = template.render()

required_content = (
    "Intelligence Analytics",
    "mip-intelligence-analytics",
    "/api/v11.7/intelligence/summary",
    "mip-top-recommendations",
    "mip-regime-distribution",
)

for item in required_content:
    assert item in rendered, item
    print("PASS:", item)

print("JINJA TEMPLATE RENDER TEST: PASS")
PY

echo
echo "==> Compiling Python application"

venv/bin/python -m py_compile \
    app.py \
    services/intelligence_analytics.py

echo "PYTHON COMPILATION: PASS"

echo
echo "==> Verifying SQLite integrity"

venv/bin/python - <<'PY'
import sqlite3

from services.database import DB_PATH

with sqlite3.connect(DB_PATH) as connection:
    result = connection.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]

print("SQLITE INTEGRITY:", result)

assert result == "ok"
PY

echo
echo "==> Restarting production service"

sudo systemctl restart "$SERVICE_NAME"

sleep 3

if ! sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "ERROR: Service failed to start."
    echo "Restoring dashboard backup."

    cp \
        "$BACKUP_DIR/dashboard_v115.html" \
        "$TEMPLATE"

    sudo systemctl restart "$SERVICE_NAME"

    exit 1
fi

echo "SERVICE STATUS: active"

echo
echo "==> Checking service logs"

if sudo journalctl \
    -u "$SERVICE_NAME" \
    --since "2 minutes ago" \
    --no-pager \
    | grep -Ei \
        'traceback|syntaxerror|jinja2.*error|templatenotfound|worker failed to boot'
then
    echo
    echo "ERROR: Serious application error detected."
    echo "Restoring dashboard backup."

    cp \
        "$BACKUP_DIR/dashboard_v115.html" \
        "$TEMPLATE"

    sudo systemctl restart "$SERVICE_NAME"

    exit 1
else
    echo "SERVICE LOG CHECK: PASS"
fi

echo
echo "==> Testing application availability"

ROOT_STATUS="$(
    curl \
        --silent \
        --output /dev/null \
        --write-out '%{http_code}' \
        http://127.0.0.1:5000/ \
    || true
)"

SUMMARY_STATUS="$(
    curl \
        --silent \
        --output /dev/null \
        --write-out '%{http_code}' \
        http://127.0.0.1:5000/api/v11.7/intelligence/summary \
    || true
)"

echo "Application root -> HTTP $ROOT_STATUS"
echo "Analytics summary -> HTTP $SUMMARY_STATUS"

case "$ROOT_STATUS" in
    200|302|401|403)
        ;;
    *)
        echo "ERROR: Unexpected application root status."
        exit 1
        ;;
esac

case "$SUMMARY_STATUS" in
    200|302|401|403)
        ;;
    *)
        echo "ERROR: Unexpected analytics API status."
        exit 1
        ;;
esac

echo "HTTP AVAILABILITY TEST: PASS"

echo
echo "==> Creating installation report"

cat > "$REPORT_FILE" <<EOF
MIP PRO Intelligence Analytics — Stage 3

Installed at:
$STAMP

Modified:
$TEMPLATE

Dashboard components:
- Intelligence Analytics summary panel
- Total intelligence runs
- Current market regime
- Average engine runtime
- Most recommended stock
- AI confidence
- Success rate
- Repository integrity
- Latest intelligence run
- Top AI recommendations table
- Market regime distribution table
- Two-minute automatic refresh

API source:
GET /api/v11.7/intelligence/summary

Validation:
- Template markers passed
- Duplicate installation test passed
- Jinja rendering passed
- Python compilation passed
- SQLite integrity passed
- Production service restarted
- Service logs passed
- HTTP availability passed

Backup:
$BACKUP_DIR/dashboard_v115.html
EOF

echo "Report created: $REPORT_FILE"

echo
echo "==> Creating Git checkpoint"

git add \
    "$TEMPLATE" \
    scripts/install_intelligence_analytics_stage3.sh

if git diff --cached --quiet; then
    echo "No Git changes to commit."
else
    git commit -m \
        "add intelligence analytics dashboard"
fi

echo
echo "======================================================"
echo "Intelligence Analytics Stage 3: COMPLETE"
echo "======================================================"
echo
echo "Dashboard template:"
echo "  $TEMPLATE"
echo
echo "Backup:"
echo "  $BACKUP_DIR/dashboard_v115.html"
echo
echo "Refresh the dashboard in your browser."
echo "Use Ctrl+F5 for a full refresh."
