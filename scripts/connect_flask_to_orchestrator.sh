#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$HOME/nse_signal_bot_v10_3}"
SERVICE_NAME="${SERVICE_NAME:-nse-v10-3.service}"

cd "$PROJECT_DIR"

STAMP="$(date +%F_%H-%M-%S)"
BACKUP_DIR="backups/orchestrator_flask/$STAMP"

mkdir -p "$BACKUP_DIR"

echo "================================================"
echo "MIP PRO — Connect Flask to Intelligence Orchestrator"
echo "================================================"

echo
echo "==> Backing up app.py"

cp app.py "$BACKUP_DIR/app.py"
echo "Backup saved: $BACKUP_DIR/app.py"

echo
echo "==> Updating imports and route calls"

venv/bin/python - <<'PY'
from pathlib import Path

path = Path("app.py")
text = path.read_text(encoding="utf-8")

old_prediction_import = (
    "from services.prediction_center import build_prediction_center"
)
old_committee_import = (
    "from services.ai_investment_committee "
    "import build_ai_investment_committee"
)

new_import = (
    "from services.intelligence_orchestrator import (\n"
    "    get_prediction_center,\n"
    "    get_investment_committee,\n"
    ")"
)

changes = []

if old_prediction_import in text:
    text = text.replace(old_prediction_import, new_import, 1)
    changes.append("Replaced Prediction Center import")
elif new_import in text:
    changes.append("Orchestrator import already installed")
else:
    raise SystemExit(
        "ERROR: Prediction Center import was not found."
    )

if old_committee_import in text:
    text = text.replace(old_committee_import + "\n", "", 1)
    changes.append("Removed direct Committee import")
elif "build_ai_investment_committee" not in text:
    changes.append("Direct Committee import already removed")
else:
    raise SystemExit(
        "ERROR: Committee import exists in an unexpected format."
    )

prediction_calls = text.count("build_prediction_center()")
committee_calls = text.count("build_ai_investment_committee()")

if prediction_calls != 1:
    raise SystemExit(
        "ERROR: Expected exactly one build_prediction_center() "
        f"call in app.py; found {prediction_calls}."
    )

if committee_calls != 1:
    raise SystemExit(
        "ERROR: Expected exactly one "
        "build_ai_investment_committee() call in app.py; "
        f"found {committee_calls}."
    )

text = text.replace(
    "build_prediction_center()",
    "get_prediction_center()",
    1,
)
changes.append("Prediction API now uses orchestrator")

text = text.replace(
    "build_ai_investment_committee()",
    "get_investment_committee()",
    1,
)
changes.append("Committee API now uses orchestrator")

path.write_text(text, encoding="utf-8")

for change in changes:
    print("OK:", change)
PY

echo
echo "==> Confirming route integration"

grep -nE \
'intelligence_orchestrator|get_prediction_center|get_investment_committee|build_prediction_center|build_ai_investment_committee' \
app.py

echo
echo "==> Compiling Python files"

venv/bin/python -m py_compile \
    app.py \
    services/intelligence_orchestrator.py \
    services/prediction_center.py \
    services/ai_investment_committee.py

echo "Compilation successful."

echo
echo "==> Running direct Flask route tests"

venv/bin/python - <<'PY'
from time import perf_counter

from app import app
from services.intelligence_orchestrator import (
    clear_intelligence_cache,
)

clear_intelligence_cache()

client = app.test_client()

started = perf_counter()
prediction_response = client.get(
    "/api/v11.6.4/prediction-center"
)
prediction_time = perf_counter() - started

started = perf_counter()
committee_response = client.get(
    "/api/v11.7/investment-committee"
)
committee_time = perf_counter() - started

print()
print(
    "Prediction status:",
    prediction_response.status_code,
)
print(
    "Prediction request time:",
    round(prediction_time, 4),
    "seconds",
)
print(
    "Committee status:",
    committee_response.status_code,
)
print(
    "Committee request time:",
    round(committee_time, 4),
    "seconds",
)

assert prediction_response.status_code == 200
assert committee_response.status_code == 200

prediction_payload = prediction_response.get_json()
committee_payload = committee_response.get_json()

assert isinstance(prediction_payload, dict)
assert isinstance(committee_payload, dict)

print(
    "Prediction payload keys:",
    sorted(prediction_payload.keys()),
)
print(
    "Committee payload keys:",
    sorted(committee_payload.keys()),
)

print()
print("FLASK ORCHESTRATOR TEST: PASS")
PY

echo
echo "==> Restarting production service"

sudo systemctl restart "$SERVICE_NAME"
sleep 4

sudo systemctl is-active --quiet "$SERVICE_NAME"

echo "Service status: ACTIVE"

echo
echo "==> Testing production API endpoints"

PREDICTION_OUTPUT="$(mktemp)"
COMMITTEE_OUTPUT="$(mktemp)"

PREDICTION_HTTP="$(
    curl \
        --silent \
        --show-error \
        --output "$PREDICTION_OUTPUT" \
        --write-out '%{http_code}' \
        http://127.0.0.1:5000/api/v11.6.4/prediction-center
)"

COMMITTEE_HTTP="$(
    curl \
        --silent \
        --show-error \
        --output "$COMMITTEE_OUTPUT" \
        --write-out '%{http_code}' \
        http://127.0.0.1:5000/api/v11.7/investment-committee
)"

echo "Prediction API HTTP: $PREDICTION_HTTP"
echo "Committee API HTTP:  $COMMITTEE_HTTP"

if [[ "$PREDICTION_HTTP" != "200" ]]; then
    echo
    echo "Prediction API response:"
    cat "$PREDICTION_OUTPUT"
    echo
    exit 1
fi

if [[ "$COMMITTEE_HTTP" != "200" ]]; then
    echo
    echo "Committee API response:"
    cat "$COMMITTEE_OUTPUT"
    echo
    exit 1
fi

venv/bin/python - "$PREDICTION_OUTPUT" "$COMMITTEE_OUTPUT" <<'PY'
import json
import sys
from pathlib import Path

prediction = json.loads(
    Path(sys.argv[1]).read_text(encoding="utf-8")
)
committee = json.loads(
    Path(sys.argv[2]).read_text(encoding="utf-8")
)

prediction_data = prediction.get("data", prediction)
committee_data = committee.get("data", committee)

predictions = prediction_data.get("predictions", [])
decisions = committee_data.get("decisions", [])

regime = (
    prediction_data.get("market_regime", {})
    or committee_data.get("market_regime", {})
    or {}
)

summary = committee_data.get("summary", {}) or {}

print()
print("Production predictions:", len(predictions))
print("Production decisions:", len(decisions))
print("Market regime:", regime.get("regime"))
print("Top committee stock:", summary.get("top_symbol"))

assert predictions, "Prediction response contains no predictions"
assert decisions, "Committee response contains no decisions"

print()
print("PRODUCTION API TEST: PASS")
PY

rm -f "$PREDICTION_OUTPUT" "$COMMITTEE_OUTPUT"

echo
echo "==> Creating Git checkpoint"

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git add \
        app.py \
        scripts/connect_flask_to_orchestrator.sh

    if git diff --cached --quiet; then
        echo "No new changes to commit."
    else
        git commit -m \
            "route prediction and committee APIs through orchestrator"
    fi
fi

echo
echo "================================================"
echo "Flask Orchestrator Integration: COMPLETE"
echo "================================================"
echo
echo "Backup:"
echo "$BACKUP_DIR/app.py"
