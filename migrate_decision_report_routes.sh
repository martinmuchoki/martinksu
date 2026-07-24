#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="/root/nse_signal_bot_v10_3"
SERVICE_NAME="nse-v10-3.service"
PYTHON="$PROJECT_DIR/venv/bin/python"
APP_FILE="$PROJECT_DIR/app.py"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$PROJECT_DIR/backups/decision_report_routes_$TIMESTAMP"

cd "$PROJECT_DIR"

mkdir -p "$BACKUP_DIR"
cp "$APP_FILE" "$BACKUP_DIR/app.py"

rollback() {
    local code=$?

    echo
    echo "Migration failed. Restoring app.py..."

    cp "$BACKUP_DIR/app.py" "$APP_FILE"

    "$PYTHON" -m py_compile app.py || true
    sudo systemctl restart "$SERVICE_NAME" || true

    exit "$code"
}

trap rollback ERR

echo "======================================================"
echo "MIP Phase 2.3 Sprint 3"
echo "Decision and Report Route Unification"
echo "======================================================"

echo
echo "Backup: $BACKUP_DIR"

echo
echo "1. Capturing current route response types..."

"$PYTHON" - <<'PY'
from app import app

app.config.update(
    TESTING=True,
    PROPAGATE_EXCEPTIONS=True,
)

routes = [
    "/committee",
    "/assistant",
    "/api/v11.4/daily-report",
]

with app.test_client() as client:
    with client.session_transaction() as session:
        session["authenticated"] = True
        session["username"] = "sprint3-baseline"

    for route in routes:
        response = client.get(route)

        print(
            route,
            "HTTP",
            response.status_code,
            "type",
            type(response.get_json()).__name__,
            "bytes",
            len(response.data),
        )

        if response.status_code != 200:
            raise SystemExit(
                f"Baseline route failed: {route}"
            )

print("PASS: baseline route types captured")
PY

echo
echo "2. Refactoring app.py..."

"$PYTHON" - <<'PY'
from pathlib import Path
import re

path = Path("/root/nse_signal_bot_v10_3/app.py")
source = path.read_text(encoding="utf-8")

# --------------------------------------------------
# Ensure canonical application-context imports exist
# --------------------------------------------------

required_imports = [
    (
        "from services.application.market_context "
        "import MarketContextBuilder\n"
    ),
    (
        "from services.application.portfolio_context "
        "import PortfolioContextBuilder\n"
    ),
    (
        "from services.application.decision_context "
        "import DecisionContextBuilder\n"
    ),
]

anchor = (
    "from services.dashboard_context_builder "
    "import DashboardContextBuilder\n"
)

if anchor not in source:
    raise SystemExit(
        "DashboardContextBuilder import anchor not found"
    )

missing_imports = [
    item
    for item in required_imports
    if item not in source
]

if missing_imports:
    source = source.replace(
        anchor,
        anchor + "".join(missing_imports),
        1,
    )

# --------------------------------------------------
# Add one shared composition helper
# --------------------------------------------------

helper_name = "_build_decision_route_context"

if f"def {helper_name}(" not in source:
    route_anchor = '@app.route("/market")'

    if route_anchor not in source:
        raise SystemExit(
            "Unable to locate /market route anchor"
        )

    helper = '''
def _build_decision_route_context():
    """
    Compose canonical market, portfolio and decision contexts.

    HTTP routes consume this shared application composition instead
    of directly orchestrating business services.
    """

    market_context = MarketContextBuilder(
        logger=app.logger,
    ).build_decision_context()

    portfolio_context = PortfolioContextBuilder(
        logger=app.logger,
    ).build()

    decision_context = DecisionContextBuilder(
        logger=app.logger,
    ).build(
        market_context=market_context,
        portfolio_context=portfolio_context,
    )

    return {
        "market_context": market_context,
        "portfolio_context": portfolio_context,
        "decision_context": decision_context,
    }


'''

    source = source.replace(
        route_anchor,
        helper + route_anchor,
        1,
    )

# --------------------------------------------------
# Refactor /committee
# --------------------------------------------------

committee_pattern = re.compile(
    r'@app\.route\("/committee"\)\n'
    r'def committee\(\):\n'
    r'.*?'
    r'(?=\n@app\.route\("/portfolio"\))',
    re.DOTALL,
)

committee_replacement = '''@app.route("/committee")
def committee():
    context = _build_decision_route_context()

    return jsonify(
        context["decision_context"]["committee"]
    )

'''

source, count = committee_pattern.subn(
    committee_replacement,
    source,
    count=1,
)

if count != 1:
    raise SystemExit(
        "Failed to refactor /committee"
    )

# --------------------------------------------------
# Refactor /assistant
# --------------------------------------------------

assistant_pattern = re.compile(
    r'@app\.route\("/assistant"\)\n'
    r'def assistant\(\):\n'
    r'.*?'
    r'(?=\n@app\.route\("/telegram/test"\))',
    re.DOTALL,
)

assistant_replacement = '''@app.route("/assistant")
def assistant():
    context = _build_decision_route_context()

    return jsonify(
        context["decision_context"]["assistant"]
    )

'''

source, count = assistant_pattern.subn(
    assistant_replacement,
    source,
    count=1,
)

if count != 1:
    raise SystemExit(
        "Failed to refactor /assistant"
    )

# --------------------------------------------------
# Refactor /download_report
# --------------------------------------------------

download_pattern = re.compile(
    r'@app\.route\("/download_report"\)\n'
    r'def download_report\(\):\n'
    r'.*?'
    r'(?=\n@app\.route\("/api/v11\.4/daily-report"\))',
    re.DOTALL,
)

download_replacement = '''@app.route("/download_report")
def download_report():
    context = _build_decision_route_context()

    market = context["market_context"]["market"]
    portfolio = context["portfolio_context"]["portfolio"]
    committee = context["decision_context"]["committee"]
    assistant = context["decision_context"]["assistant"]

    report = generate_daily_report(
        market,
        committee,
        portfolio,
        assistant,
    )

    return send_file(
        report["path"],
        as_attachment=True,
        download_name=(
            "MIP_PRO_Daily_Intelligence_"
            "Report_v11_5_Production.pdf"
        ),
        mimetype="application/pdf",
    )

'''

source, count = download_pattern.subn(
    download_replacement,
    source,
    count=1,
)

if count != 1:
    raise SystemExit(
        "Failed to refactor /download_report"
    )

# --------------------------------------------------
# Refactor /api/v11.4/daily-report
# --------------------------------------------------

daily_report_pattern = re.compile(
    r'@app\.route\("/api/v11\.4/daily-report"\)\n'
    r'def v114_daily_report\(\):\n'
    r'.*?'
    r'(?=\n@app\.route\("/api/v11\.5/dashboard-charts"\))',
    re.DOTALL,
)

daily_report_replacement = '''@app.route("/api/v11.4/daily-report")
def v114_daily_report():
    context = _build_decision_route_context()

    market = context["market_context"]["market"]
    portfolio = context["portfolio_context"]["portfolio"]
    committee = context["decision_context"]["committee"]
    assistant = context["decision_context"]["assistant"]

    return jsonify(
        generate_daily_report(
            market,
            committee,
            portfolio,
            assistant,
        )
    )


'''

source, count = daily_report_pattern.subn(
    daily_report_replacement,
    source,
    count=1,
)

if count != 1:
    raise SystemExit(
        "Failed to refactor daily-report route"
    )

path.write_text(source, encoding="utf-8")

print("PASS: four routes refactored")
PY

echo
echo "3. Running syntax and import checks..."

"$PYTHON" -m py_compile \
    app.py \
    services/application/market_context.py \
    services/application/portfolio_context.py \
    services/application/decision_context.py \
    services/ai_committee.py \
    services/autonomous_assistant.py \
    services/reports.py

"$PYTHON" - <<'PY'
from app import app
from services.application.market_context import (
    MarketContextBuilder,
)
from services.application.portfolio_context import (
    PortfolioContextBuilder,
)
from services.application.decision_context import (
    DecisionContextBuilder,
)

routes = {
    rule.rule
    for rule in app.url_map.iter_rules()
}

required = {
    "/committee",
    "/assistant",
    "/download_report",
    "/api/v11.4/daily-report",
}

missing = required - routes

if missing:
    raise SystemExit(
        f"Missing routes: {sorted(missing)}"
    )

print("PASS: application imports")
print("PASS: target routes registered")
PY

echo
echo "4. Testing canonical context composition..."

"$PYTHON" - <<'PY'
import logging

from services.application.market_context import (
    MarketContextBuilder,
)
from services.application.portfolio_context import (
    PortfolioContextBuilder,
)
from services.application.decision_context import (
    DecisionContextBuilder,
)

logger = logging.getLogger("sprint3-test")

market_context = MarketContextBuilder(
    logger=logger,
).build_decision_context()

portfolio_context = PortfolioContextBuilder(
    logger=logger,
).build()

decision_context = DecisionContextBuilder(
    logger=logger,
).build(
    market_context=market_context,
    portfolio_context=portfolio_context,
)

required_market = {
    "market",
    "technicals",
    "risk_metrics",
    "regime",
    "sector_rotation",
}

required_portfolio = {
    "portfolio",
}

required_decision = {
    "committee",
    "assistant",
    "persisted_signals",
    "persisted_signal_summary",
    "decision",
}

missing_market = (
    required_market - set(market_context)
)

missing_portfolio = (
    required_portfolio - set(portfolio_context)
)

missing_decision = (
    required_decision - set(decision_context)
)

if missing_market:
    raise SystemExit(
        f"Missing market context keys: {missing_market}"
    )

if missing_portfolio:
    raise SystemExit(
        f"Missing portfolio context keys: {missing_portfolio}"
    )

if missing_decision:
    raise SystemExit(
        f"Missing decision context keys: {missing_decision}"
    )

committee = decision_context["committee"]
assistant = decision_context["assistant"]

if not isinstance(committee, dict):
    raise SystemExit(
        "Committee result is not a dictionary"
    )

if not isinstance(assistant, dict):
    raise SystemExit(
        "Assistant result is not a dictionary"
    )

print(
    "Committee:",
    committee.get("final_decision"),
    committee.get("confidence"),
)

print(
    "Assistant:",
    assistant.get("action"),
    assistant.get("confidence"),
)

print("PASS: canonical context composition")
PY

echo
echo "5. Testing refactored routes..."

"$PYTHON" - <<'PY'
from app import app

app.config.update(
    TESTING=True,
    PROPAGATE_EXCEPTIONS=True,
)

json_routes = [
    "/committee",
    "/assistant",
    "/api/v11.4/daily-report",
]

with app.test_client() as client:
    with client.session_transaction() as session:
        session["authenticated"] = True
        session["username"] = "sprint3-after"

    for route in json_routes:
        response = client.get(route)

        print(
            route,
            "HTTP",
            response.status_code,
            "bytes",
            len(response.data),
        )

        if response.status_code != 200:
            print(
                response.data.decode(
                    "utf-8",
                    errors="replace",
                )[:2000]
            )

            raise SystemExit(
                f"Route failed: {route}"
            )

        result = response.get_json()

        if not isinstance(result, dict):
            raise SystemExit(
                f"{route} did not return a JSON object"
            )

    report_response = client.get(
        "/download_report"
    )

    print(
        "/download_report",
        "HTTP",
        report_response.status_code,
        "mimetype",
        report_response.mimetype,
        "bytes",
        len(report_response.data),
    )

    if report_response.status_code != 200:
        raise SystemExit(
            "/download_report failed"
        )

    if report_response.mimetype != "application/pdf":
        raise SystemExit(
            "Download report did not return a PDF"
        )

    if not report_response.data.startswith(b"%PDF"):
        raise SystemExit(
            "Downloaded report is not a valid PDF"
        )

print("PASS: all four target routes")
PY

echo
echo "6. Confirming route-level orchestration was removed..."

"$PYTHON" - <<'PY'
from pathlib import Path
import re

source = Path(
    "/root/nse_signal_bot_v10_3/app.py"
).read_text(encoding="utf-8")

route_names = [
    "committee",
    "assistant",
    "download_report",
    "v114_daily_report",
]

for route_name in route_names:
    pattern = re.compile(
        rf"def {route_name}\(.*?\):\n"
        rf"(.*?)(?=\n@app\.route|\Z)",
        re.DOTALL,
    )

    match = pattern.search(source)

    if not match:
        raise SystemExit(
            f"Unable to inspect route {route_name}"
        )

    body = match.group(1)

    forbidden = [
        "get_market_snapshot(",
        "analyze_market(",
        "run_committee(",
        "get_portfolio(",
        "autonomous_decision(",
    ]

    found = [
        call
        for call in forbidden
        if call in body
    ]

    if found:
        raise SystemExit(
            f"{route_name} still directly calls {found}"
        )

print(
    "PASS: target routes contain no direct "
    "business orchestration"
)
PY

echo
echo "7. Running broader regression tests..."

"$PYTHON" - <<'PY'
from app import app

app.config.update(
    TESTING=True,
    PROPAGATE_EXCEPTIONS=True,
)

routes = [
    "/",
    "/?ui=v117",
    "/market",
    "/technicals",
    "/portfolio",
    "/api/v11.4/predictions?limit=5",
    "/api/v11.4/risk",
    "/api/v11.4/regime",
    "/api/v11.4/sectors",
    "/api/v11.7/decision",
]

with app.test_client() as client:
    with client.session_transaction() as session:
        session["authenticated"] = True
        session["username"] = "sprint3-regression"

    for route in routes:
        response = client.get(route)

        print(
            route,
            "HTTP",
            response.status_code,
            "bytes",
            len(response.data),
        )

        if response.status_code != 200:
            raise SystemExit(
                f"Regression detected: {route}"
            )

print("PASS: broader route regression tests")
PY

echo
echo "8. Restarting production service..."

sudo systemctl restart "$SERVICE_NAME"
sleep 3

sudo systemctl is-active --quiet "$SERVICE_NAME"

echo "PASS: service active"

echo
echo "9. Checking production health..."

curl \
    --fail \
    --silent \
    --show-error \
    --max-time 30 \
    http://127.0.0.1:5000/health

echo
echo

echo "10. Checking warnings since restart..."

ACTIVE_TIME="$(
    systemctl show "$SERVICE_NAME" \
        --property=ActiveEnterTimestamp \
        --value
)"

sudo journalctl \
    -u "$SERVICE_NAME" \
    --since "$ACTIVE_TIME" \
    --priority=warning \
    --no-pager || true

echo
echo "11. Checking remaining direct orchestration references..."

grep -n -E \
'run_committee|get_market_snapshot|analyze_market|autonomous_decision|generate_daily_report' \
app.py || true

echo
echo "12. Recording migration in Git..."

git add \
    app.py \
    migrate_decision_report_routes.sh

if git diff --cached --quiet; then
    echo "No changes detected"
else
    git commit -m \
        "refactor: unify committee assistant and report routes"
fi

CURRENT_BRANCH="$(git branch --show-current)"
git push origin "$CURRENT_BRANCH"

echo
echo "======================================================"
echo "Sprint 3 migration completed successfully"
echo "======================================================"

echo
echo "Commit:"
git log -1 --oneline

echo
echo "Backup:"
echo "$BACKUP_DIR"

echo
echo "Git status:"
git status --short
