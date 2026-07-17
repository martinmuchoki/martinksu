#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$HOME/nse_signal_bot_v10_3}"
SERVICE_NAME="${SERVICE_NAME:-nse-v10-3.service}"

cd "$PROJECT_DIR"

STAMP="$(date +%F_%H-%M-%S)"
BACKUP_DIR="backups/intelligence_analytics_stage2/$STAMP"
REPORT_FILE="reports/intelligence_analytics_stage2.txt"

mkdir -p \
    "$BACKUP_DIR" \
    scripts \
    reports

echo "======================================================"
echo "MIP PRO Intelligence Analytics — Stage 2"
echo "REST API Integration"
echo "======================================================"

if [[ ! -f app.py ]]; then
    echo "ERROR: app.py was not found."
    exit 1
fi

if [[ ! -f services/intelligence_analytics.py ]]; then
    echo "ERROR: services/intelligence_analytics.py was not found."
    echo "Stage 1 must be completed first."
    exit 1
fi

echo
echo "==> Backing up app.py"

cp app.py "$BACKUP_DIR/app.py"

echo "Backup created:"
echo "$BACKUP_DIR/app.py"

echo
echo "==> Patching app.py"

venv/bin/python - <<'PY'
from pathlib import Path

app_path = Path("app.py")
text = app_path.read_text(encoding="utf-8")

import_block = """from services.intelligence_analytics import (
    get_dashboard_summary,
    get_engine_statistics,
    get_market_regime_statistics,
    get_recommendation_statistics,
)
"""

route_block = r'''

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
'''

changed = False

if "from services.intelligence_analytics import (" not in text:
    app_marker = "app = Flask("

    if app_marker in text:
        text = text.replace(
            app_marker,
            import_block + "\n\n" + app_marker,
            1,
        )
    else:
        lines = text.splitlines()

        insert_at = 0

        for index, line in enumerate(lines):
            if line.startswith("from services.") or line.startswith(
                "import "
            ) or line.startswith("from "):
                insert_at = index + 1

        lines.insert(insert_at, import_block.rstrip())
        text = "\n".join(lines) + "\n"

    changed = True
    print("Analytics import added.")
else:
    print("Analytics import already present.")

begin_marker = "# BEGIN MIP PRO INTELLIGENCE ANALYTICS API"

if begin_marker not in text:
    main_marker = 'if __name__ == "__main__":'

    if main_marker not in text:
        raise SystemExit(
            "ERROR: Could not find the app.py main marker."
        )

    text = text.replace(
        main_marker,
        route_block + "\n\n" + main_marker,
        1,
    )

    changed = True
    print("Analytics API routes added.")
else:
    print("Analytics API routes already present.")

if changed:
    app_path.write_text(text, encoding="utf-8")
    print("app.py updated successfully.")
else:
    print("No changes were required.")
PY

echo
echo "==> Confirming inserted routes"

grep -nE \
'intelligence/summary|intelligence/performance|intelligence/recommendations|intelligence/regimes' \
app.py

echo
echo "==> Compiling modified modules"

venv/bin/python -m py_compile \
    services/intelligence_analytics.py \
    app.py

echo "Compilation: PASS"

echo
echo "==> Checking Flask URL registration"

venv/bin/python - <<'PY'
from app import app

required_routes = {
    "/api/v11.7/intelligence/summary",
    "/api/v11.7/intelligence/performance",
    "/api/v11.7/intelligence/recommendations",
    "/api/v11.7/intelligence/regimes",
}

registered_routes = {
    rule.rule
    for rule in app.url_map.iter_rules()
}

missing_routes = required_routes - registered_routes

print("REGISTERED ANALYTICS ROUTES:")

for route in sorted(required_routes):
    state = (
        "PASS"
        if route in registered_routes
        else "MISSING"
    )

    print(f"{state}: {route}")

if missing_routes:
    raise SystemExit(
        "Missing Flask routes: "
        + ", ".join(sorted(missing_routes))
    )

print()
print("FLASK ROUTE REGISTRATION TEST: PASS")
PY

echo
echo "==> Testing analytics view functions directly"

venv/bin/python - <<'PY'
from app import app

view_tests = {
    "v117_intelligence_summary": {
        "required_keys": {
            "status",
            "activity",
            "engine",
            "market",
            "recommendations",
            "repository",
        },
    },
    "v117_intelligence_performance": {
        "required_keys": {
            "run_count",
            "average_total_seconds",
            "history",
        },
    },
    "v117_intelligence_recommendations": {
        "required_keys": {
            "total_decisions",
            "top_symbols",
            "decision_distribution",
        },
    },
    "v117_intelligence_regimes": {
        "required_keys": {
            "current",
            "distribution",
            "history",
        },
    },
}

with app.app_context():
    for view_name, specification in view_tests.items():
        view_function = app.view_functions.get(view_name)

        if view_function is None:
            raise AssertionError(
                f"Missing view function: {view_name}"
            )

        result = view_function()

        if isinstance(result, tuple):
            response = result[0]
            status_code = result[1]
        else:
            response = result
            status_code = response.status_code

        payload = response.get_json()

        print()
        print("VIEW:", view_name)
        print("STATUS:", status_code)
        print("KEYS:", sorted(payload.keys()))

        assert status_code == 200, (
            view_name,
            status_code,
            payload,
        )

        missing_keys = (
            specification["required_keys"]
            - set(payload.keys())
        )

        assert not missing_keys, (
            view_name,
            missing_keys,
        )

print()
print("ANALYTICS VIEW FUNCTION TESTS: PASS")
PY

echo
echo "==> Verifying SQLite integrity"

venv/bin/python - <<'PY'
import sqlite3

from services.database import DB_PATH

with sqlite3.connect(DB_PATH) as connection:
    integrity = connection.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]

print("SQLITE INTEGRITY:", integrity)

assert integrity == "ok"

print("SQLITE INTEGRITY TEST: PASS")
PY

echo
echo "==> Restarting production service"

sudo systemctl restart "$SERVICE_NAME"

sleep 3

echo
echo "==> Checking service status"

sudo systemctl is-active --quiet "$SERVICE_NAME"

echo "SERVICE STATUS: active"

sudo systemctl status \
    "$SERVICE_NAME" \
    --no-pager \
    --lines=15

echo
echo "==> Checking recent service logs"

if sudo journalctl \
    -u "$SERVICE_NAME" \
    --since "2 minutes ago" \
    --no-pager \
    | grep -Ei \
        'traceback|syntaxerror|importerror|modulenotfounderror|worker failed to boot'
then
    echo
    echo "ERROR: A serious error was found in recent logs."
    echo "Restoring app.py backup."

    cp "$BACKUP_DIR/app.py" app.py

    sudo systemctl restart "$SERVICE_NAME"

    exit 1
else
    echo "SERVICE LOG CHECK: PASS"
fi

echo
echo "==> Testing local HTTP route availability"

for endpoint in \
    "/api/v11.7/intelligence/summary" \
    "/api/v11.7/intelligence/performance" \
    "/api/v11.7/intelligence/recommendations" \
    "/api/v11.7/intelligence/regimes"
do
    status_code="$(
        curl \
            --silent \
            --output /dev/null \
            --write-out '%{http_code}' \
            "http://127.0.0.1:5000${endpoint}" \
        || true
    )"

    echo "${endpoint} -> HTTP ${status_code}"

    case "$status_code" in
        200|302|401|403)
            ;;
        *)
            echo "ERROR: Unexpected HTTP status for ${endpoint}"
            exit 1
            ;;
    esac
done

echo
echo "HTTP ROUTE AVAILABILITY TEST: PASS"

echo
echo "==> Creating installation report"

cat > "$REPORT_FILE" <<EOF
MIP PRO Intelligence Analytics — Stage 2

Installed at:
$STAMP

Modified:
app.py

Added endpoints:
GET /api/v11.7/intelligence/summary
GET /api/v11.7/intelligence/performance
GET /api/v11.7/intelligence/recommendations
GET /api/v11.7/intelligence/regimes

Validation:
- Python compilation passed
- Flask route registration passed
- Analytics view function tests passed
- SQLite integrity passed
- Production service restarted
- Service log check passed
- HTTP route availability passed

Backup:
$BACKUP_DIR/app.py
EOF

echo "Report created: $REPORT_FILE"
echo "The reports directory remains excluded from Git."

echo
echo "==> Creating Git checkpoint"

git add \
    app.py \
    services/intelligence_analytics.py \
    scripts/install_intelligence_analytics_stage1.sh \
    scripts/install_intelligence_analytics_stage2.sh

if git diff --cached --quiet; then
    echo "No Git changes to commit."
else
    git commit -m \
        "add intelligence analytics REST API"
fi

echo
echo "======================================================"
echo "Intelligence Analytics Stage 2: COMPLETE"
echo "======================================================"
echo
echo "Installed endpoints:"
echo "  /api/v11.7/intelligence/summary"
echo "  /api/v11.7/intelligence/performance"
echo "  /api/v11.7/intelligence/recommendations"
echo "  /api/v11.7/intelligence/regimes"
echo
echo "Backup:"
echo "  $BACKUP_DIR/app.py"
