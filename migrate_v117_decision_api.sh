#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="/root/nse_signal_bot_v10_3"
SERVICE_NAME="nse-v10-3.service"
PYTHON="$PROJECT_DIR/venv/bin/python"

APP_FILE="$PROJECT_DIR/app.py"
MARKET_CONTEXT_FILE="$PROJECT_DIR/services/application/market_context.py"
DECISION_CONTEXT_FILE="$PROJECT_DIR/services/application/decision_context.py"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$PROJECT_DIR/backups/v117_decision_api_$TIMESTAMP"
BASELINE_JSON="$BACKUP_DIR/decision_before.json"
AFTER_JSON="$BACKUP_DIR/decision_after.json"

cd "$PROJECT_DIR"

if [[ ! -x "$PYTHON" ]]; then
    echo "ERROR: Python executable not found: $PYTHON"
    exit 1
fi

mkdir -p "$BACKUP_DIR"

cp "$APP_FILE" "$BACKUP_DIR/app.py"
cp "$MARKET_CONTEXT_FILE" "$BACKUP_DIR/market_context.py"
cp "$DECISION_CONTEXT_FILE" "$BACKUP_DIR/decision_context.py"

restore_files() {
    echo
    echo "Restoring previous files..."

    cp "$BACKUP_DIR/app.py" "$APP_FILE"
    cp "$BACKUP_DIR/market_context.py" "$MARKET_CONTEXT_FILE"
    cp "$BACKUP_DIR/decision_context.py" "$DECISION_CONTEXT_FILE"
}

rollback() {
    local exit_code=$?

    echo
    echo "DECISION API MIGRATION FAILED"
    echo "Exit code: $exit_code"

    restore_files

    "$PYTHON" -m py_compile \
        app.py \
        services/application/market_context.py \
        services/application/decision_context.py || true

    sudo systemctl restart "$SERVICE_NAME" || true
    sudo systemctl status \
        "$SERVICE_NAME" \
        --no-pager \
        -l || true

    exit "$exit_code"
}

trap rollback ERR

echo "======================================================"
echo "MIP Version 12.1 Phase 2.3"
echo "Decision API Context Unification"
echo "======================================================"

echo
echo "Backup directory:"
echo "$BACKUP_DIR"

echo
echo "1. Capturing existing decision API response..."

BASELINE_JSON="$BASELINE_JSON" "$PYTHON" - <<'PY'
import json
import os

from app import app

output_path = os.environ["BASELINE_JSON"]

app.config.update(
    TESTING=True,
    PROPAGATE_EXCEPTIONS=True,
)

with app.test_client() as client:
    with client.session_transaction() as session:
        session["authenticated"] = True
        session["username"] = "decision-api-baseline"

    response = client.get("/api/v11.7/decision")

    print(
        "Baseline response:",
        response.status_code,
        "bytes:",
        len(response.data),
    )

    if response.status_code != 200:
        print(
            response.data.decode(
                "utf-8",
                errors="replace",
            )[:3000]
        )
        raise SystemExit(
            "Existing decision API did not return HTTP 200"
        )

    payload = response.get_json()

    if not isinstance(payload, dict):
        raise SystemExit(
            "Existing decision response is not a JSON object"
        )

    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(
            payload,
            handle,
            indent=2,
            sort_keys=True,
            default=str,
        )

    print(
        "PASS: baseline captured with",
        len(payload),
        "top-level keys",
    )
PY

echo
echo "2. Adding focused shared-context methods..."

"$PYTHON" - <<'PY'
from pathlib import Path
import re

market_path = Path(
    "/root/nse_signal_bot_v10_3/"
    "services/application/market_context.py"
)

decision_path = Path(
    "/root/nse_signal_bot_v10_3/"
    "services/application/decision_context.py"
)

market_source = market_path.read_text(encoding="utf-8")
decision_source = decision_path.read_text(encoding="utf-8")

if "def build_decision_context(" not in market_source:
    market_marker = re.compile(
        r"(\n    def build\(\n"
        r"        self,\n"
        r"        \*,\n"
        r"        optimizer_capital: float = 100000,\n"
        r"    \) -> Dict\[str, Any\]:)"
    )

    market_method = '''
    def build_decision_context(self) -> Dict[str, Any]:
        """Build only the market intelligence required for decisions."""

        market = get_market_snapshot()
        stocks = market.get("stocks", [])

        try:
            technicals = analyze_market(stocks)
        except Exception as exc:
            self.logger.exception(
                "Decision technical analysis failed: %s",
                exc,
            )
            technicals = []

        risk_metrics = build_market_risk(stocks)

        regime = detect_market_regime(
            market,
            technicals,
            risk_metrics,
        )

        sector_rotation = analyze_sector_rotation(stocks)

        return {
            "market": market,
            "technicals": technicals,
            "risk_metrics": risk_metrics,
            "regime": regime,
            "sector_rotation": sector_rotation,
        }

'''

    market_source, replacements = market_marker.subn(
        "\\n" + market_method.rstrip() + r"\1",
        market_source,
        count=1,
    )

    if replacements != 1:
        raise SystemExit(
            "Unable to locate MarketContextBuilder.build()"
        )

if "def build_authoritative_decision(" not in decision_source:
    decision_marker = re.compile(
        r"(\n    def build\(\n"
        r"        self,\n"
        r"        \*,\n"
        r"        market_context: Dict\[str, Any\],\n"
        r"        portfolio_context: Dict\[str, Any\],\n"
        r"    \) -> Dict\[str, Any\]:)"
    )

    decision_method = '''
    def build_authoritative_decision(
        self,
        *,
        market_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build the authoritative decision without unrelated contexts."""

        (
            persisted_signals,
            persisted_signal_summary,
        ) = self._build_signal_context()

        decision = self._build_ai_decision(
            persisted_signals=persisted_signals,
            persisted_signal_summary=persisted_signal_summary,
            regime=market_context["regime"],
            risk_metrics=market_context["risk_metrics"],
            sector_rotation=market_context["sector_rotation"],
        )

        return {
            "persisted_signals": persisted_signals,
            "persisted_top_signal": (
                persisted_signals[0]
                if persisted_signals
                else None
            ),
            "persisted_signal_summary": persisted_signal_summary,
            "decision": decision,
        }

'''

    decision_source, replacements = decision_marker.subn(
        "\\n" + decision_method.rstrip() + r"\1",
        decision_source,
        count=1,
    )

    if replacements != 1:
        raise SystemExit(
            "Unable to locate DecisionContextBuilder.build()"
        )

market_path.write_text(market_source, encoding="utf-8")
decision_path.write_text(decision_source, encoding="utf-8")

print("PASS: focused context methods installed")
PY

echo
echo "3. Migrating /api/v11.7/decision..."

"$PYTHON" - <<'PY'
from pathlib import Path
import re

app_path = Path("/root/nse_signal_bot_v10_3/app.py")
source = app_path.read_text(encoding="utf-8")

route_pattern = re.compile(
    r'@app\.route\("/api/v11\.7/decision"\)\n'
    r'def v117_decision\(\):\n'
    r'.*?'
    r'(?=\n@app\.route\("/health"\))',
    flags=re.DOTALL,
)

replacement = '''@app.route("/api/v11.7/decision")
def v117_decision():
    """
    Return the authoritative Version 11.7 Decision Object.

    Market and decision orchestration are delegated to the
    shared application context layer.
    """
    from services.application.decision_context import (
        DecisionContextBuilder,
    )
    from services.application.market_context import (
        MarketContextBuilder,
    )

    market_context = MarketContextBuilder(
        logger=app.logger,
    ).build_decision_context()

    decision_context = DecisionContextBuilder(
        logger=app.logger,
    ).build_authoritative_decision(
        market_context=market_context,
    )

    return jsonify(decision_context["decision"])

'''

updated, replacements = route_pattern.subn(
    replacement,
    source,
    count=1,
)

if replacements != 1:
    raise SystemExit(
        "Unable to locate the existing v117_decision route"
    )

app_path.write_text(updated, encoding="utf-8")

print("PASS: decision API route migrated")
PY

echo
echo "4. Running syntax validation..."

"$PYTHON" -m py_compile \
    app.py \
    services/application/__init__.py \
    services/application/market_context.py \
    services/application/decision_context.py \
    services/application/portfolio_context.py \
    services/dashboard_context_builder.py

echo "PASS: Python syntax"

echo
echo "5. Running import and route validation..."

"$PYTHON" - <<'PY'
import app

from services.application.decision_context import (
    DecisionContextBuilder,
)
from services.application.market_context import (
    MarketContextBuilder,
)

assert hasattr(
    MarketContextBuilder,
    "build_decision_context",
)

assert hasattr(
    DecisionContextBuilder,
    "build_authoritative_decision",
)

routes = {
    rule.rule
    for rule in app.app.url_map.iter_rules()
}

required = {
    "/",
    "/health",
    "/api/v11.7/decision",
}

missing = required - routes

if missing:
    raise SystemExit(
        f"Missing required routes: {sorted(missing)}"
    )

print(f"PASS: {len(routes)} Flask routes registered")
print("PASS: focused context methods available")
PY

echo
echo "6. Testing migrated API and preserving schema..."

AFTER_JSON="$AFTER_JSON" "$PYTHON" - <<'PY'
import json
import os
import time

from app import app

output_path = os.environ["AFTER_JSON"]

app.config.update(
    TESTING=True,
    PROPAGATE_EXCEPTIONS=True,
)

started = time.monotonic()

with app.test_client() as client:
    with client.session_transaction() as session:
        session["authenticated"] = True
        session["username"] = "decision-api-verification"

    response = client.get("/api/v11.7/decision")

elapsed = time.monotonic() - started

print(
    "Migrated response:",
    response.status_code,
    "bytes:",
    len(response.data),
    "time:",
    f"{elapsed:.2f}s",
)

if response.status_code != 200:
    print(
        response.data.decode(
            "utf-8",
            errors="replace",
        )[:3000]
    )
    raise SystemExit(
        "Migrated decision API did not return HTTP 200"
    )

payload = response.get_json()

if not isinstance(payload, dict):
    raise SystemExit(
        "Migrated decision response is not a JSON object"
    )

with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(
        payload,
        handle,
        indent=2,
        sort_keys=True,
        default=str,
    )

print(
    "PASS: migrated decision API returned",
    len(payload),
    "top-level keys",
)
PY

BASELINE_JSON="$BASELINE_JSON" \
AFTER_JSON="$AFTER_JSON" \
"$PYTHON" - <<'PY'
import json
import os

before_path = os.environ["BASELINE_JSON"]
after_path = os.environ["AFTER_JSON"]

with open(before_path, encoding="utf-8") as handle:
    before = json.load(handle)

with open(after_path, encoding="utf-8") as handle:
    after = json.load(handle)


def schema(value):
    if isinstance(value, dict):
        return {
            key: schema(item)
            for key, item in sorted(value.items())
        }

    if isinstance(value, list):
        if not value:
            return ["empty_or_dynamic"]

        return [schema(value[0])]

    if value is None:
        return "null"

    return type(value).__name__


before_keys = set(before)
after_keys = set(after)

missing_keys = sorted(before_keys - after_keys)
new_keys = sorted(after_keys - before_keys)

if missing_keys:
    raise SystemExit(
        "Decision API lost top-level keys: "
        + ", ".join(missing_keys)
    )

if new_keys:
    print(
        "NOTICE: new top-level keys:",
        ", ".join(new_keys),
    )

before_schema = schema(before)
after_schema = schema(after)

type_changes = []

for key in sorted(before_keys & after_keys):
    before_type = type(before[key]).__name__
    after_type = type(after[key]).__name__

    if before_type != after_type:
        type_changes.append(
            f"{key}: {before_type} -> {after_type}"
        )

if type_changes:
    raise SystemExit(
        "Top-level response types changed: "
        + "; ".join(type_changes)
    )

print("PASS: all previous top-level keys preserved")
print("PASS: all previous top-level value types preserved")
print("Baseline keys:", len(before_keys))
print("Migrated keys:", len(after_keys))
PY

echo
echo "7. Verifying both dashboards..."

"$PYTHON" - <<'PY'
import time

from app import app

app.config.update(
    TESTING=True,
    PROPAGATE_EXCEPTIONS=True,
)

with app.test_client() as client:
    with client.session_transaction() as session:
        session["authenticated"] = True
        session["username"] = "dashboard-regression"

    for url, label in (
        ("/", "Legacy dashboard"),
        ("/?ui=v117", "Version 11.7 dashboard"),
    ):
        started = time.monotonic()
        response = client.get(url)
        elapsed = time.monotonic() - started

        print(
            f"{label}: HTTP {response.status_code}, "
            f"{len(response.data)} bytes, "
            f"{elapsed:.2f}s"
        )

        if response.status_code != 200:
            raise SystemExit(
                f"{label} regression detected"
            )

        if len(response.data) < 10000:
            raise SystemExit(
                f"{label} response unexpectedly small"
            )

print("PASS: dashboard regression tests")
PY

echo
echo "8. Restarting production service..."

sudo systemctl restart "$SERVICE_NAME"
sleep 3

sudo systemctl is-active --quiet "$SERVICE_NAME"

echo "PASS: service is active"

echo
echo "9. Testing production health endpoint..."

curl \
    --fail \
    --silent \
    --show-error \
    --max-time 30 \
    http://127.0.0.1:5000/health

echo
echo

echo "10. Testing production decision endpoint locally..."

HTTP_STATUS="$(
    curl \
        --silent \
        --output /tmp/mip_v117_decision_response.txt \
        --write-out "%{http_code}" \
        --max-time 60 \
        http://127.0.0.1:5000/api/v11.7/decision
)"

echo "Production decision endpoint HTTP status: $HTTP_STATUS"

if [[ "$HTTP_STATUS" != "200" && "$HTTP_STATUS" != "302" && "$HTTP_STATUS" != "401" ]]; then
    echo "Unexpected production response:"
    head -c 2000 /tmp/mip_v117_decision_response.txt || true
    echo
    exit 1
fi

echo "PASS: production endpoint is reachable"

echo
echo "11. Checking service warnings since restart..."

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
echo "12. Confirming duplicate decision orchestration was removed..."

if sed -n '/def v117_decision/,/@app.route("\/health")/p' app.py \
    | grep -E \
      'get_market_snapshot|analyze_market|build_market_risk|detect_market_regime|analyze_sector_rotation|get_signal_service|get_ai_decision'
then
    echo "ERROR: direct decision orchestration remains in route"
    exit 1
fi

echo "PASS: route delegates to shared contexts"

echo
echo "13. Recording migration in Git..."

git add \
    app.py \
    services/application/market_context.py \
    services/application/decision_context.py \
    migrate_v117_decision_api.sh

if git diff --cached --quiet; then
    echo "No changes to commit."
else
    git commit -m \
        "refactor: unify v11.7 decision API context"
fi

CURRENT_BRANCH="$(git branch --show-current)"
git push origin "$CURRENT_BRANCH"

echo
echo "======================================================"
echo "Decision API migration completed successfully"
echo "======================================================"

echo
echo "Commit:"
git log -1 --oneline

echo
echo "Backup retained at:"
echo "$BACKUP_DIR"

echo
echo "Git status:"
git status --short
