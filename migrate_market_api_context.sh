#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="/root/nse_signal_bot_v10_3"
SERVICE_NAME="nse-v10-3.service"
PYTHON="$PROJECT_DIR/venv/bin/python"

APP_FILE="$PROJECT_DIR/app.py"
MARKET_CONTEXT_FILE="$PROJECT_DIR/services/application/market_context.py"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$PROJECT_DIR/backups/market_api_context_$TIMESTAMP"
BASELINE_FILE="$BACKUP_DIR/baseline.json"
AFTER_FILE="$BACKUP_DIR/after.json"

cd "$PROJECT_DIR"

mkdir -p "$BACKUP_DIR"

cp "$APP_FILE" "$BACKUP_DIR/app.py"
cp "$MARKET_CONTEXT_FILE" "$BACKUP_DIR/market_context.py"

rollback() {
    local code=$?

    echo
    echo "Migration failed. Restoring backup..."

    cp "$BACKUP_DIR/app.py" "$APP_FILE"
    cp "$BACKUP_DIR/market_context.py" "$MARKET_CONTEXT_FILE"

    "$PYTHON" -m py_compile \
        app.py \
        services/application/market_context.py || true

    sudo systemctl restart "$SERVICE_NAME" || true

    exit "$code"
}

trap rollback ERR

echo "======================================================"
echo "MIP Phase 2.3 Sprint 2"
echo "Market API Context Unification"
echo "======================================================"

echo
echo "Backup: $BACKUP_DIR"

echo
echo "1. Capturing current API responses..."

BASELINE_FILE="$BASELINE_FILE" "$PYTHON" - <<'PY'
import json
import os
import time

from app import app

routes = [
    "/market",
    "/technicals",
    "/api/v11.4/predictions",
    "/api/v11.4/predictions?limit=5",
    "/api/v11.4/risk",
    "/api/v11.4/regime",
    "/api/v11.4/sectors",
]

results = {}

app.config.update(
    TESTING=True,
    PROPAGATE_EXCEPTIONS=True,
)

with app.test_client() as client:
    with client.session_transaction() as session:
        session["authenticated"] = True
        session["username"] = "market-api-baseline"

    for route in routes:
        started = time.monotonic()
        response = client.get(route)
        elapsed = time.monotonic() - started

        print(
            route,
            "HTTP",
            response.status_code,
            "bytes",
            len(response.data),
            "time",
            f"{elapsed:.2f}s",
        )

        if response.status_code != 200:
            raise SystemExit(
                f"Baseline route failed: {route}"
            )

        results[route] = {
            "status": response.status_code,
            "json": response.get_json(),
        }

with open(
    os.environ["BASELINE_FILE"],
    "w",
    encoding="utf-8",
) as handle:
    json.dump(
        results,
        handle,
        indent=2,
        sort_keys=True,
        default=str,
    )

print("PASS: baseline responses captured")
PY

echo
echo "2. Adding lazy focused methods to MarketContextBuilder..."

"$PYTHON" - <<'PY'
from pathlib import Path
import re

path = Path(
    "/root/nse_signal_bot_v10_3/"
    "services/application/market_context.py"
)

source = path.read_text(encoding="utf-8")

if "def market_snapshot(" in source:
    print("Focused market methods already exist")
    raise SystemExit(0)

old_init = '''        self.logger = logger or logging.getLogger(__name__)
'''

new_init = '''        self.logger = logger or logging.getLogger(__name__)

        self._market_cache: Optional[Dict[str, Any]] = None
        self._technicals_cache: Optional[Any] = None
        self._risk_cache: Optional[Any] = None
        self._regime_cache: Optional[Any] = None
        self._sector_rotation_cache: Optional[Any] = None
'''

if old_init not in source:
    raise SystemExit(
        "Unable to locate MarketContextBuilder.__init__"
    )

source = source.replace(old_init, new_init, 1)

marker = re.compile(
    r'(\n    def build_decision_context\()'
)

methods = '''
    def _market(self) -> Dict[str, Any]:
        """Return one market snapshot for this builder instance."""

        if self._market_cache is None:
            self._market_cache = get_market_snapshot()

        return self._market_cache

    def _stocks(self) -> Any:
        """Return normalized stock records from the market snapshot."""

        return self._market().get("stocks", [])

    def _technicals(self) -> Any:
        """Return technical analysis, computed once per context."""

        if self._technicals_cache is None:
            try:
                self._technicals_cache = analyze_market(
                    self._stocks()
                )
            except Exception as exc:
                self.logger.exception(
                    "Technical analysis failed: %s",
                    exc,
                )
                self._technicals_cache = []

        return self._technicals_cache

    def _risk(self) -> Any:
        """Return market risk metrics, computed once per context."""

        if self._risk_cache is None:
            self._risk_cache = build_market_risk(
                self._stocks()
            )

        return self._risk_cache

    def _regime(self) -> Any:
        """Return market regime, computed once per context."""

        if self._regime_cache is None:
            self._regime_cache = detect_market_regime(
                self._market(),
                self._technicals(),
                self._risk(),
            )

        return self._regime_cache

    def _sector_rotation(self) -> Any:
        """Return sector rotation, computed once per context."""

        if self._sector_rotation_cache is None:
            self._sector_rotation_cache = (
                analyze_sector_rotation(
                    self._stocks()
                )
            )

        return self._sector_rotation_cache

    def market_snapshot(self) -> Dict[str, Any]:
        """Return the canonical live market snapshot."""

        return self._market()

    def technical_analysis(self) -> Any:
        """Return market-wide technical analysis."""

        return self._technicals()

    def predictions(self, *, limit: int = 20) -> Any:
        """Return predictions while preserving the route limit."""

        normalized_limit = max(int(limit or 0), 0)

        return build_predictions(
            self._stocks(),
            self._technicals(),
            limit=normalized_limit,
        )

    def market_risk(self) -> Any:
        """Return market-wide risk intelligence."""

        return self._risk()

    def market_regime(self) -> Any:
        """Return the detected market regime."""

        return self._regime()

    def sector_rotation(self) -> Any:
        """Return sector rotation intelligence."""

        return self._sector_rotation()

'''

source, count = marker.subn(
    "\n" + methods.rstrip() + r"\1",
    source,
    count=1,
)

if count != 1:
    raise SystemExit(
        "Unable to locate build_decision_context()"
    )

path.write_text(source, encoding="utf-8")

print("PASS: lazy focused methods added")
PY

echo
echo "3. Updating shared build methods to reuse lazy dependencies..."

"$PYTHON" - <<'PY'
from pathlib import Path

path = Path(
    "/root/nse_signal_bot_v10_3/"
    "services/application/market_context.py"
)

source = path.read_text(encoding="utf-8")

source = source.replace(
'''        market = get_market_snapshot()
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
''',
'''        market = self._market()
        technicals = self._technicals()
        risk_metrics = self._risk()
        regime = self._regime()
        sector_rotation = self._sector_rotation()
''',
1,
)

source = source.replace(
'''        screener = run_screener()
        market = get_market_snapshot()

        try:
            technicals = analyze_market(
                market.get("stocks", [])
            )
        except Exception as exc:
            self.logger.exception(
                "Technical analysis failed: %s",
                exc,
            )
            technicals = []

        stocks = market.get("stocks", [])

        risk_metrics = build_market_risk(stocks)

        regime = detect_market_regime(
            market,
            technicals,
            risk_metrics,
        )

        sector_rotation = analyze_sector_rotation(stocks)
''',
'''        screener = run_screener()
        market = self._market()
        stocks = self._stocks()
        technicals = self._technicals()
        risk_metrics = self._risk()
        regime = self._regime()
        sector_rotation = self._sector_rotation()
''',
1,
)

path.write_text(source, encoding="utf-8")

print("PASS: existing build methods now reuse lazy context")
PY

echo
echo "4. Migrating the six market API routes..."

"$PYTHON" - <<'PY'
from pathlib import Path
import re

path = Path("/root/nse_signal_bot_v10_3/app.py")
source = path.read_text(encoding="utf-8")

if (
    "from services.application.market_context import "
    "MarketContextBuilder"
) not in source:
    source = source.replace(
        "from services.dashboard_context_builder "
        "import DashboardContextBuilder\n",
        "from services.dashboard_context_builder "
        "import DashboardContextBuilder\n"
        "from services.application.market_context "
        "import MarketContextBuilder\n",
        1,
    )

replacements = [
    (
        re.compile(
            r'@app\.route\("/market"\)\n'
            r'def market\(\):\n'
            r'.*?'
            r'(?=\n@app\.route\("/technicals"\))',
            re.DOTALL,
        ),
        '''@app.route("/market")
def market():
    context = MarketContextBuilder(logger=app.logger)

    return jsonify(context.market_snapshot())

''',
    ),
    (
        re.compile(
            r'@app\.route\("/technicals"\)\n'
            r'def technicals\(\):\n'
            r'.*?'
            r'(?=\n@app\.route\("/committee"\))',
            re.DOTALL,
        ),
        '''@app.route("/technicals")
def technicals():
    context = MarketContextBuilder(logger=app.logger)

    return jsonify(context.technical_analysis())

''',
    ),
    (
        re.compile(
            r'@app\.route\("/api/v11\.4/predictions"\)\n'
            r'def v114_predictions\(\):\n'
            r'.*?'
            r'(?=\n@app\.route\("/api/v11\.4/risk"\))',
            re.DOTALL,
        ),
        '''@app.route("/api/v11.4/predictions")
def v114_predictions():
    context = MarketContextBuilder(logger=app.logger)

    return jsonify(
        context.predictions(
            limit=request.args.get(
                "limit",
                default=20,
                type=int,
            )
        )
    )

''',
    ),
    (
        re.compile(
            r'@app\.route\("/api/v11\.4/risk"\)\n'
            r'def v114_risk\(\):\n'
            r'.*?'
            r'(?=\n@app\.route\("/api/v11\.4/risk/<symbol>"\))',
            re.DOTALL,
        ),
        '''@app.route("/api/v11.4/risk")
def v114_risk():
    context = MarketContextBuilder(logger=app.logger)

    return jsonify(context.market_risk())

''',
    ),
    (
        re.compile(
            r'@app\.route\("/api/v11\.4/regime"\)\n'
            r'def v114_regime\(\):\n'
            r'.*?'
            r'(?=\n@app\.route\("/api/v11\.4/sectors"\))',
            re.DOTALL,
        ),
        '''@app.route("/api/v11.4/regime")
def v114_regime():
    context = MarketContextBuilder(logger=app.logger)

    return jsonify(context.market_regime())

''',
    ),
    (
        re.compile(
            r'@app\.route\("/api/v11\.4/sectors"\)\n'
            r'def v114_sectors\(\):\n'
            r'.*?'
            r'(?=\n\s*# BEGIN MIP PRO ZIIDI COPILOT ROUTES)',
            re.DOTALL,
        ),
        '''@app.route("/api/v11.4/sectors")
def v114_sectors():
    context = MarketContextBuilder(logger=app.logger)

    return jsonify(context.sector_rotation())

''',
    ),
]

for pattern, replacement in replacements:
    source, count = pattern.subn(
        replacement,
        source,
        count=1,
    )

    if count != 1:
        raise SystemExit(
            f"Failed to migrate pattern: {pattern.pattern[:80]}"
        )

path.write_text(source, encoding="utf-8")

print("PASS: six routes migrated")
PY

echo
echo "5. Running syntax and import checks..."

"$PYTHON" -m py_compile \
    app.py \
    services/application/market_context.py \
    services/application/decision_context.py \
    services/application/portfolio_context.py \
    services/dashboard_context_builder.py

"$PYTHON" - <<'PY'
from app import app
from services.application.market_context import (
    MarketContextBuilder,
)

required_methods = [
    "market_snapshot",
    "technical_analysis",
    "predictions",
    "market_risk",
    "market_regime",
    "sector_rotation",
]

for method in required_methods:
    if not hasattr(MarketContextBuilder, method):
        raise SystemExit(
            f"Missing MarketContextBuilder.{method}"
        )

routes = {
    rule.rule
    for rule in app.url_map.iter_rules()
}

required_routes = {
    "/market",
    "/technicals",
    "/api/v11.4/predictions",
    "/api/v11.4/risk",
    "/api/v11.4/regime",
    "/api/v11.4/sectors",
}

missing = required_routes - routes

if missing:
    raise SystemExit(
        f"Missing routes: {sorted(missing)}"
    )

print("PASS: imports and route registration")
PY

echo
echo "6. Testing migrated responses..."

AFTER_FILE="$AFTER_FILE" "$PYTHON" - <<'PY'
import json
import os
import time

from app import app

routes = [
    "/market",
    "/technicals",
    "/api/v11.4/predictions",
    "/api/v11.4/predictions?limit=5",
    "/api/v11.4/risk",
    "/api/v11.4/regime",
    "/api/v11.4/sectors",
]

results = {}

app.config.update(
    TESTING=True,
    PROPAGATE_EXCEPTIONS=True,
)

with app.test_client() as client:
    with client.session_transaction() as session:
        session["authenticated"] = True
        session["username"] = "market-api-after"

    for route in routes:
        started = time.monotonic()
        response = client.get(route)
        elapsed = time.monotonic() - started

        print(
            route,
            "HTTP",
            response.status_code,
            "bytes",
            len(response.data),
            "time",
            f"{elapsed:.2f}s",
        )

        if response.status_code != 200:
            print(
                response.data.decode(
                    "utf-8",
                    errors="replace",
                )[:2000]
            )
            raise SystemExit(
                f"Migrated route failed: {route}"
            )

        results[route] = {
            "status": response.status_code,
            "json": response.get_json(),
        }

with open(
    os.environ["AFTER_FILE"],
    "w",
    encoding="utf-8",
) as handle:
    json.dump(
        results,
        handle,
        indent=2,
        sort_keys=True,
        default=str,
    )

print("PASS: migrated responses captured")
PY

echo
echo "7. Comparing response schemas..."

BASELINE_FILE="$BASELINE_FILE" \
AFTER_FILE="$AFTER_FILE" \
"$PYTHON" - <<'PY'
import json
import os

with open(
    os.environ["BASELINE_FILE"],
    encoding="utf-8",
) as handle:
    before = json.load(handle)

with open(
    os.environ["AFTER_FILE"],
    encoding="utf-8",
) as handle:
    after = json.load(handle)


def shape(value):
    if isinstance(value, dict):
        return {
            key: shape(item)
            for key, item in sorted(value.items())
        }

    if isinstance(value, list):
        if not value:
            return ["dynamic"]

        return [shape(value[0])]

    if value is None:
        return "null"

    return type(value).__name__


for route in before:
    if route not in after:
        raise SystemExit(
            f"Missing migrated result for {route}"
        )

    before_json = before[route]["json"]
    after_json = after[route]["json"]

    before_type = type(before_json).__name__
    after_type = type(after_json).__name__

    if before_type != after_type:
        raise SystemExit(
            f"{route}: response type changed "
            f"{before_type} -> {after_type}"
        )

    if isinstance(before_json, dict):
        missing_keys = (
            set(before_json) - set(after_json)
        )

        if missing_keys:
            raise SystemExit(
                f"{route}: missing keys "
                f"{sorted(missing_keys)}"
            )

    print(
        "PASS:",
        route,
        "response type:",
        after_type,
    )

limited = after[
    "/api/v11.4/predictions?limit=5"
]["json"]

if isinstance(limited, list) and len(limited) > 5:
    raise SystemExit(
        "Predictions limit parameter was not preserved"
    )

print("PASS: response structures preserved")
print("PASS: prediction limit preserved")
PY

echo
echo "8. Confirming target routes contain no direct orchestration..."

"$PYTHON" - <<'PY'
from pathlib import Path
import re

source = Path(
    "/root/nse_signal_bot_v10_3/app.py"
).read_text(encoding="utf-8")

route_names = [
    "market",
    "technicals",
    "v114_predictions",
    "v114_risk",
    "v114_regime",
    "v114_sectors",
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
            f"Unable to inspect {route_name}"
        )

    body = match.group(1)

    forbidden = [
        "get_market_snapshot(",
        "analyze_market(",
        "build_predictions(",
        "build_market_risk(",
        "detect_market_regime(",
        "analyze_sector_rotation(",
    ]

    found = [
        item
        for item in forbidden
        if item in body
    ]

    if found:
        raise SystemExit(
            f"{route_name} still contains: {found}"
        )

print("PASS: target routes delegate to MarketContextBuilder")
PY

echo
echo "9. Running dashboard and decision API regression tests..."

"$PYTHON" - <<'PY'
from app import app

app.config.update(
    TESTING=True,
    PROPAGATE_EXCEPTIONS=True,
)

routes = [
    "/",
    "/?ui=v117",
    "/api/v11.7/decision",
]

with app.test_client() as client:
    with client.session_transaction() as session:
        session["authenticated"] = True
        session["username"] = "market-context-regression"

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

print("PASS: dashboard and decision regression tests")
PY

echo
echo "10. Restarting production service..."

sudo systemctl restart "$SERVICE_NAME"
sleep 3

sudo systemctl is-active --quiet "$SERVICE_NAME"

echo "PASS: service active"

echo
echo "11. Checking production health..."

curl \
    --fail \
    --silent \
    --show-error \
    --max-time 30 \
    http://127.0.0.1:5000/health

echo
echo

echo "12. Checking service warnings..."

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
echo "13. Recording migration in Git..."

git add \
    app.py \
    services/application/market_context.py \
    migrate_market_api_context.sh

if git diff --cached --quiet; then
    echo "No changes detected"
else
    git commit -m \
        "refactor: unify market APIs through shared context"
fi

CURRENT_BRANCH="$(git branch --show-current)"
git push origin "$CURRENT_BRANCH"

echo
echo "======================================================"
echo "Market API context migration completed successfully"
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
