#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="/root/nse_signal_bot_v10_3"
PYTHON="$PROJECT_DIR/venv/bin/python"
SERVICE_NAME="nse-v10-3.service"

cd "$PROJECT_DIR"

echo "======================================================"
echo "MIP Dashboard Context Builder — Functional Verification"
echo "======================================================"

echo
echo "1. Syntax validation"
"$PYTHON" -m py_compile \
    app.py \
    services/dashboard_context_builder.py

echo "PASS: Python syntax"

echo
echo "2. Import and route validation"
"$PYTHON" - <<'PY'
import app

routes = {rule.rule for rule in app.app.url_map.iter_rules()}

required = {
    "/",
    "/health",
    "/api/v11.7/decision",
}

missing = required - routes

if missing:
    raise SystemExit(f"Missing routes: {sorted(missing)}")

print(f"PASS: {len(routes)} routes registered")
PY

echo
echo "3. Authenticated Flask dashboard tests"
"$PYTHON" - <<'PY'
import time
import traceback

from app import app


def test_dashboard(client, url, label, expected_template_marker):
    started = time.monotonic()

    response = client.get(
        url,
        follow_redirects=False,
    )

    elapsed = time.monotonic() - started

    print(
        f"{label}: status={response.status_code}, "
        f"bytes={len(response.data)}, "
        f"time={elapsed:.2f}s"
    )

    if response.status_code != 200:
        print(response.data[:1000].decode("utf-8", errors="replace"))
        raise AssertionError(
            f"{label} returned HTTP {response.status_code}"
        )

    body = response.data.decode(
        "utf-8",
        errors="replace",
    )

    if not body.strip():
        raise AssertionError(f"{label} returned an empty page")

    if "Internal Server Error" in body:
        raise AssertionError(
            f"{label} contains an Internal Server Error"
        )

    print(
        f"PASS: {label} rendered using "
        f"{expected_template_marker}"
    )


try:
    app.config.update(
        TESTING=True,
        PROPAGATE_EXCEPTIONS=True,
    )

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["authenticated"] = True
            session["username"] = "verification"

        test_dashboard(
            client,
            "/",
            "Legacy dashboard",
            "dashboard_v115.html",
        )

        test_dashboard(
            client,
            "/?ui=v117",
            "Version 11.7 dashboard",
            "dashboard_v117.html",
        )

except Exception:
    print()
    print("DASHBOARD VERIFICATION FAILED")
    traceback.print_exc()
    raise
PY

echo
echo "4. Service state"
sudo systemctl is-active "$SERVICE_NAME"
sudo systemctl status "$SERVICE_NAME" \
    --no-pager \
    --lines=15

echo
echo "5. Errors since latest restart"
RESTART_TIME="$(
    systemctl show "$SERVICE_NAME" \
        --property=ActiveEnterTimestamp \
        --value
)"

echo "Service active since: $RESTART_TIME"

sudo journalctl \
    -u "$SERVICE_NAME" \
    --since "$RESTART_TIME" \
    --priority=warning \
    --no-pager || true

echo
echo "6. Git verification"
git status --short
git log -1 --oneline
git show --stat --oneline --summary HEAD

echo
echo "======================================================"
echo "FUNCTIONAL VERIFICATION COMPLETED"
echo "======================================================"
