#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT="/root/nse_signal_bot_v10_3"
STAMP="$(date +%Y-%m-%d_%H-%M-%S)"
BACKUP="$PROJECT/backups/v11_5A_$STAMP"
LOG="$PROJECT/logs/upgrade_v11_5A_$STAMP.log"
CREDENTIALS_FILE="$PROJECT/.mip_admin_credentials"

cd "$PROJECT"
mkdir -p "$BACKUP/templates" "$BACKUP/static/css" "$PROJECT/logs"

exec > >(tee -a "$LOG") 2>&1

rollback() {
    echo
    echo "Upgrade failed. Restoring the previous version..."

    [ -f "$BACKUP/app.py" ] &&
        cp "$BACKUP/app.py" "$PROJECT/app.py"

    [ -f "$BACKUP/templates/dashboard.html" ] &&
        cp "$BACKUP/templates/dashboard.html" \
           "$PROJECT/templates/dashboard.html"

    [ -f "$BACKUP/templates/screener.html" ] &&
        cp "$BACKUP/templates/screener.html" \
           "$PROJECT/templates/screener.html"

    [ -f "$BACKUP/static/css/style.css" ] &&
        cp "$BACKUP/static/css/style.css" \
           "$PROJECT/static/css/style.css"

    rm -f "$PROJECT/templates/login.html"
    rm -f "$PROJECT/templates/about.html"

    "$PROJECT/restart.sh" || true

    echo "Rollback completed."
    exit 1
}

trap rollback ERR

echo "=================================================="
echo "MIP PRO V11.5A"
echo "Branding and Security Installer"
echo "=================================================="

echo
echo "[1/9] Creating backups..."

cp app.py "$BACKUP/app.py"
cp templates/dashboard.html "$BACKUP/templates/dashboard.html"

if [ -f templates/screener.html ]; then
    cp templates/screener.html "$BACKUP/templates/screener.html"
fi

if [ -f static/css/style.css ]; then
    cp static/css/style.css "$BACKUP/static/css/style.css"
fi

echo "Backup created: $BACKUP"

echo
echo "[2/9] Creating administrator credentials..."

ADMIN_USERNAME="admin"
ADMIN_PASSWORD="$(
    "$PROJECT/venv/bin/python" - <<'PY'
import secrets
print(secrets.token_urlsafe(12))
PY
)"

PASSWORD_HASH="$(
    ADMIN_PASSWORD="$ADMIN_PASSWORD" \
    "$PROJECT/venv/bin/python" - <<'PY'
import os
from werkzeug.security import generate_password_hash

print(
    generate_password_hash(
        os.environ["ADMIN_PASSWORD"],
        method="scrypt",
    )
)
PY
)"

touch .env
chmod 600 .env

sed -i '/^MIP_ADMIN_USERNAME=/d' .env
sed -i '/^MIP_ADMIN_PASSWORD_HASH=/d' .env
sed -i '/^MIP_SECRET_KEY=/d' .env

SECRET_KEY="$(
    "$PROJECT/venv/bin/python" - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)"

cat >> .env <<EOF

MIP_ADMIN_USERNAME=$ADMIN_USERNAME
MIP_ADMIN_PASSWORD_HASH=$PASSWORD_HASH
MIP_SECRET_KEY=$SECRET_KEY
EOF

cat > "$CREDENTIALS_FILE" <<EOF
MIP PRO V11.5 Administrator

Username: $ADMIN_USERNAME
Password: $ADMIN_PASSWORD

Created: $(date)
EOF

chmod 600 "$CREDENTIALS_FILE"

echo "Secure credentials created."

echo
echo "[3/9] Updating Flask authentication and branding..."

python - <<'PY'
from pathlib import Path

path = Path("app.py")
text = path.read_text(encoding="utf-8")

old_import = (
    "from flask import Flask, render_template, jsonify, "
    "request, redirect, send_file"
)

new_import = (
    "from flask import Flask, render_template, jsonify, "
    "request, redirect, send_file, session, url_for"
)

if old_import in text:
    text = text.replace(old_import, new_import, 1)
elif "session" not in text.splitlines()[0]:
    text = text.replace(
        "from flask import Flask, render_template, jsonify, request, redirect",
        (
            "from flask import Flask, render_template, jsonify, "
            "request, redirect, session, url_for"
        ),
        1,
    )

security_imports = """import os
from functools import wraps

from dotenv import load_dotenv
from werkzeug.security import check_password_hash
"""

if "from werkzeug.security import check_password_hash" not in text:
    text = security_imports + "\n" + text

app_anchor = "app = Flask(__name__)\n"

security_setup = '''load_dotenv("/root/nse_signal_bot_v10_3/.env")

app = Flask(__name__)
app.secret_key = os.getenv("MIP_SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("MIP_SECRET_KEY is missing from .env")

PUBLIC_ENDPOINTS = {
    "login",
    "health",
    "static",
}


@app.before_request
def require_authentication():
    endpoint = request.endpoint

    if endpoint is None:
        return None

    if endpoint in PUBLIC_ENDPOINTS:
        return None

    if session.get("authenticated"):
        return None

    if request.path.startswith("/api/"):
        return jsonify({
            "error": "authentication_required",
            "message": "Please sign in to MIP PRO.",
        }), 401

    return redirect(url_for("login", next=request.path))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("authenticated"):
        return redirect(url_for("dashboard"))

    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        expected_username = os.getenv(
            "MIP_ADMIN_USERNAME",
            "admin",
        )

        password_hash = os.getenv(
            "MIP_ADMIN_PASSWORD_HASH",
            "",
        )

        if (
            username == expected_username
            and password_hash
            and check_password_hash(password_hash, password)
        ):
            session.clear()
            session["authenticated"] = True
            session["username"] = username
            session.permanent = True

            destination = request.args.get("next")

            if (
                not destination
                or not destination.startswith("/")
                or destination.startswith("//")
            ):
                destination = url_for("dashboard")

            return redirect(destination)

        error = "Incorrect username or password."

    return render_template(
        "login.html",
        error=error,
        version="11.5",
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/about")
def about():
    return render_template(
        "about.html",
        version="11.5",
    )
'''

if "def require_authentication():" not in text:
    if app_anchor not in text:
        raise SystemExit("Unable to find Flask app creation line.")

    text = text.replace(
        app_anchor,
        security_setup + "\n",
        1,
    )

text = text.replace(
    'VERSION = "11.4 Institutional Quant Engine"',
    'VERSION = "11.5 Professional Intelligence Suite"',
)

text = text.replace(
    '"service": "Market Intelligence Platform V11.4"',
    '"service": "MIP PRO"',
)

text = text.replace(
    '"service": "Market Intelligence Platform V11.3"',
    '"service": "MIP PRO"',
)

text = text.replace(
    '"service": "NSE Signal Bot V11.2 Professional"',
    '"service": "MIP PRO"',
)

path.write_text(text, encoding="utf-8")
print("Updated app.py")
PY

echo
echo "[4/9] Creating professional login page..."

cat > templates/login.html <<'HTML'
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1">

    <title>MIP PRO | Sign In</title>

    <link
        rel="stylesheet"
        href="{{ url_for('static', filename='css/style.css') }}">
</head>

<body class="login-page">

<main class="login-shell">
    <section class="login-card">

        <div class="login-brand-mark">
            <span class="mip-word">MIP</span>
            <span class="pro-word">PRO</span>
        </div>

        <p class="login-platform-name">
            Market Intelligence Platform
        </p>

        <h1>Professional Intelligence Suite</h1>

        <p class="login-tagline">
            AI-Powered Investment Intelligence for Africa
        </p>

        {% if error %}
        <div class="login-error">
            {{ error }}
        </div>
        {% endif %}

        <form method="post" class="login-form">

            <label>
                Username
                <input
                    type="text"
                    name="username"
                    autocomplete="username"
                    required
                    autofocus>
            </label>

            <label>
                Password
                <input
                    type="password"
                    name="password"
                    autocomplete="current-password"
                    required>
            </label>

            <button type="submit" class="login-button">
                Sign In
            </button>
        </form>

        <div class="login-features">
            <span>Live NSE Data</span>
            <span>Predictive AI</span>
            <span>Institutional Analytics</span>
        </div>

        <footer class="login-footer">
            <strong>MIP PRO</strong> · Version {{ version }}<br>
            Built in Kenya · Designed for African Markets
        </footer>

    </section>
</main>

</body>
</html>
HTML

echo
echo "[5/9] Creating About page..."

cat > templates/about.html <<'HTML'
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1">

    <title>About MIP PRO</title>

    <link
        rel="stylesheet"
        href="{{ url_for('static', filename='css/style.css') }}">
</head>

<body>

<main class="about-shell">
    <section class="about-card">

        <div class="login-brand-mark">
            <span class="mip-word">MIP</span>
            <span class="pro-word">PRO</span>
        </div>

        <h1>Market Intelligence Platform</h1>
        <h2>Professional Intelligence Suite</h2>

        <div class="about-grid">
            <div>
                <span>Version</span>
                <strong>{{ version }}</strong>
            </div>

            <div>
                <span>Market coverage</span>
                <strong>Nairobi Securities Exchange</strong>
            </div>

            <div>
                <span>Data provider</span>
                <strong>MyStocks Africa</strong>
            </div>

            <div>
                <span>Technology</span>
                <strong>Python · Flask · SQLite</strong>
            </div>
        </div>

        <p>
            MIP PRO combines live market data, predictive analytics,
            portfolio intelligence, institutional risk analysis,
            sector rotation and automated reporting.
        </p>

        <p class="recommendation-box">
            This platform is intended for analytical and educational
            purposes. It does not provide guaranteed investment outcomes.
        </p>

        <div class="about-actions">
            <a class="button" href="/">Dashboard</a>
            <a class="button secondary-button" href="/logout">Logout</a>
        </div>

    </section>
</main>

</body>
</html>
HTML

echo
echo "[6/9] Applying MIP PRO branding..."

python - <<'PY'
from pathlib import Path

files = [
    Path("templates/dashboard.html"),
    Path("templates/screener.html"),
    Path("services/reports.py"),
    Path("services/institutional_brief.py"),
    Path("services/scheduler_engine.py"),
]

replacements = {
    "Market Intelligence Platform V11.4": "MIP PRO",
    "Market Intelligence Platform V11.3": "MIP PRO",
    "NSE Signal Bot V11.4": "MIP PRO",
    "NSE Signal Bot V11.3": "MIP PRO",
    "NSE Signal Bot V11.2": "MIP PRO",
    "NSE Signal Bot V10.5": "MIP PRO",
    "NSE Signal Bot": "MIP PRO",
}

for path in files:
    if not path.exists():
        continue

    text = path.read_text(encoding="utf-8")

    for old, new in replacements.items():
        text = text.replace(old, new)

    path.write_text(text, encoding="utf-8")
    print("Branded:", path)

dashboard = Path("templates/dashboard.html")
text = dashboard.read_text(encoding="utf-8")

text = text.replace(
    "<title>MIP PRO</title>",
    "<title>MIP PRO | Professional Intelligence Suite</title>",
)

old_heading = "<h1>MIP PRO</h1>"

new_heading = """<div class="dashboard-brand">
            <div class="dashboard-brand-mark">
                <span class="mip-word">MIP</span>
                <span class="pro-word">PRO</span>
            </div>

            <div>
                <h1>Market Intelligence Platform</h1>
                <p class="subtitle">
                    Professional Intelligence Suite
                </p>
            </div>
        </div>"""

if old_heading in text:
    text = text.replace(old_heading, new_heading, 1)

text = text.replace(
    "MIP PRO · Professional Market Intelligence Platform",
    (
        "MIP PRO Professional Intelligence Suite · "
        "Version 11.5 · Built in Kenya"
    ),
)

if 'href="/about"' not in text:
    text = text.replace(
        '<a class="button secondary-button" href="/screener">',
        (
            '<a class="text-link" href="/about">About</a>\n'
            '        <a class="text-link" href="/logout">Logout</a>\n'
            '        <a class="button secondary-button" href="/screener">'
        ),
        1,
    )

dashboard.write_text(text, encoding="utf-8")
print("Dashboard header updated.")
PY

echo
echo "[7/9] Adding authentication and branding styles..."

cat >> static/css/style.css <<'CSS'

/* ==================================================
   MIP PRO V11.5 Branding and Authentication
   ================================================== */

.mip-word {
    color: #111111;
    font-weight: 900;
}

.pro-word {
    color: #c8102e;
    font-weight: 900;
    margin-left: 0.16em;
}

.dashboard-brand {
    display: flex;
    align-items: center;
    gap: 18px;
}

.dashboard-brand-mark,
.login-brand-mark {
    font-size: clamp(28px, 4vw, 46px);
    line-height: 1;
    letter-spacing: -2px;
    white-space: nowrap;
}

.dashboard-brand h1 {
    margin: 0;
}

.login-page {
    min-height: 100vh;
    margin: 0;
    background:
        radial-gradient(
            circle at top left,
            rgba(187, 146, 42, 0.18),
            transparent 35%
        ),
        linear-gradient(135deg, #071510, #10251c 55%, #08110e);
    color: #17231d;
}

.login-shell {
    min-height: 100vh;
    display: grid;
    place-items: center;
    padding: 24px;
}

.login-card {
    width: min(460px, 100%);
    box-sizing: border-box;
    padding: 42px;
    border-radius: 24px;
    background: rgba(255, 255, 255, 0.97);
    box-shadow: 0 28px 80px rgba(0, 0, 0, 0.34);
    text-align: center;
}

.login-platform-name {
    margin: 14px 0 4px;
    color: #a47b18;
    font-size: 14px;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

.login-card h1 {
    margin: 0;
    font-size: 25px;
    color: #17231d;
}

.login-tagline {
    margin: 12px 0 28px;
    color: #65716b;
    line-height: 1.5;
}

.login-form {
    display: grid;
    gap: 18px;
    text-align: left;
}

.login-form label {
    display: grid;
    gap: 7px;
    color: #33433b;
    font-size: 14px;
    font-weight: 700;
}

.login-form input {
    width: 100%;
    box-sizing: border-box;
    padding: 13px 14px;
    border: 1px solid #ccd4cf;
    border-radius: 10px;
    background: #ffffff;
    color: #17231d;
    font: inherit;
}

.login-form input:focus {
    outline: 3px solid rgba(187, 146, 42, 0.18);
    border-color: #a47b18;
}

.login-button {
    min-height: 48px;
    border: 0;
    border-radius: 10px;
    background: linear-gradient(135deg, #0b6b3a, #084b2b);
    color: #ffffff;
    font-size: 15px;
    font-weight: 800;
    cursor: pointer;
}

.login-button:hover {
    filter: brightness(1.08);
}

.login-error {
    margin: 0 0 18px;
    padding: 11px 13px;
    border: 1px solid rgba(200, 16, 46, 0.25);
    border-radius: 9px;
    background: rgba(200, 16, 46, 0.08);
    color: #a20d27;
    font-size: 14px;
}

.login-features {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 8px;
    margin: 24px 0;
}

.login-features span {
    padding: 6px 9px;
    border-radius: 999px;
    background: #edf5f0;
    color: #25533b;
    font-size: 11px;
    font-weight: 700;
}

.login-footer {
    color: #7a8580;
    font-size: 12px;
    line-height: 1.6;
}

.about-shell {
    min-height: 100vh;
    display: grid;
    place-items: center;
    padding: 30px;
    background: #f3f6f4;
}

.about-card {
    width: min(850px, 100%);
    box-sizing: border-box;
    padding: 40px;
    border-radius: 20px;
    background: #ffffff;
    box-shadow: 0 18px 55px rgba(20, 45, 32, 0.12);
}

.about-card h1 {
    margin-bottom: 4px;
}

.about-card h2 {
    margin-top: 0;
    color: #68746e;
    font-size: 18px;
}

.about-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
    margin: 28px 0;
}

.about-grid div {
    padding: 16px;
    border-radius: 12px;
    background: #f3f6f4;
}

.about-grid span,
.about-grid strong {
    display: block;
}

.about-grid span {
    margin-bottom: 5px;
    color: #68746e;
    font-size: 12px;
    text-transform: uppercase;
}

.about-actions {
    display: flex;
    gap: 12px;
    margin-top: 25px;
}

@media (max-width: 680px) {
    .dashboard-brand {
        align-items: flex-start;
        flex-direction: column;
    }

    .login-card {
        padding: 30px 22px;
    }

    .about-grid {
        grid-template-columns: 1fr;
    }
}
CSS

echo
echo "[8/9] Running validation..."

"$PROJECT/venv/bin/python" -m py_compile \
    app.py \
    services/*.py

echo "Python syntax checks passed."

echo
echo "[9/9] Restarting and testing..."

"$PROJECT/restart.sh"

HEALTH="$(
    curl -fsS http://127.0.0.1:5000/health
)"

echo "Health response:"
echo "$HEALTH"

echo "$HEALTH" | grep -q '"status":"online"'

LOGIN_STATUS="$(
    curl -s -o /dev/null -w "%{http_code}" \
    http://127.0.0.1:5000/login
)"

if [ "$LOGIN_STATUS" != "200" ]; then
    echo "Login page test failed: HTTP $LOGIN_STATUS"
    exit 1
fi

DASHBOARD_STATUS="$(
    curl -s -o /dev/null -w "%{http_code}" \
    http://127.0.0.1:5000/
)"

if [ "$DASHBOARD_STATUS" != "302" ]; then
    echo "Dashboard protection test failed: HTTP $DASHBOARD_STATUS"
    exit 1
fi

trap - ERR

echo
echo "=================================================="
echo "MIP PRO V11.5A installed successfully"
echo "=================================================="
echo
echo "Administrator credentials:"
cat "$CREDENTIALS_FILE"
echo
echo "Credentials file:"
echo "$CREDENTIALS_FILE"
echo
echo "Backup:"
echo "$BACKUP"
echo
echo "Log:"
echo "$LOG"
echo
echo "Open in your browser:"
echo "http://164.92.133.0/login"
echo "=================================================="
