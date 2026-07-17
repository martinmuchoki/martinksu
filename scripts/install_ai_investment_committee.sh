#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$HOME/nse_signal_bot_v10_3}"
cd "$PROJECT_DIR"

STAMP="$(date +%F_%H-%M-%S)"
mkdir -p backups/dev

echo "==> Backing up app.py"
cp app.py "backups/dev/app.py.before_committee_api_${STAMP}"

echo "==> Installing committee API route"

venv/bin/python - <<'PY'
from pathlib import Path

path = Path("app.py")
text = path.read_text(encoding="utf-8")

import_line = (
    "from services.ai_investment_committee "
    "import build_ai_investment_committee\n"
)

if import_line not in text:
    marker = (
        "from services.prediction_center import "
        "build_prediction_center\n"
    )

    if marker not in text:
        raise SystemExit(
            "Prediction Center import marker not found."
        )

    text = text.replace(
        marker,
        marker + import_line,
        1,
    )

route = '''

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


'''

if "def v117_investment_committee():" not in text:
    marker = '\nif __name__ == "__main__":\n'

    if marker not in text:
        raise SystemExit(
            "Application ending marker not found."
        )

    text = text.replace(
        marker,
        route + marker,
        1,
    )

path.write_text(text, encoding="utf-8")

print("Committee API route installed.")
PY

echo "==> Compiling"
venv/bin/python -m py_compile \
    services/ai_investment_committee.py \
    services/prediction_center.py \
    services/market_regime_engine.py \
    services/ai_conviction_engine.py \
    app.py

echo "==> Restarting"
./restart.sh

echo "==> Testing committee API"
venv/bin/python - <<'PY'
from app import app

app.testing = True

with app.test_client() as client:
    with client.session_transaction() as session:
        session["authenticated"] = True
        session["username"] = "admin"

    response = client.get(
        "/api/v11.7/investment-committee"
    )

    payload = response.get_json() or {}

    print("API STATUS:", response.status_code)
    print(
        "DECISIONS:",
        len(payload.get("decisions", [])),
    )
    print(
        "TOP:",
        payload.get("summary", {}).get(
            "top_symbol"
        ),
        payload.get("summary", {}).get(
            "top_score"
        ),
    )

    if response.status_code != 200:
        print(payload)
        raise SystemExit(
            "Committee API test failed."
        )
PY

echo "AI Investment Committee API installation complete."
