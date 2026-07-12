#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT="/root/nse_signal_bot_v10_3"
STAMP="$(date +%Y-%m-%d_%H-%M-%S)"
BACKUP="$PROJECT/backups/v11_5B_$STAMP"
LOG="$PROJECT/logs/upgrade_v11_5B_$STAMP.log"

cd "$PROJECT"

mkdir -p \
    "$BACKUP/templates" \
    "$BACKUP/static/css" \
    "$PROJECT/static/images" \
    "$PROJECT/logs"

exec > >(tee -a "$LOG") 2>&1

rollback() {
    echo
    echo "V11.5B failed. Restoring previous files..."

    [ -f "$BACKUP/app.py" ] &&
        cp "$BACKUP/app.py" "$PROJECT/app.py"

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
echo "MIP PRO V11.5B"
echo "Executive Dashboard Installer"
echo "=================================================="

echo
echo "[1/7] Creating backups..."

cp app.py "$BACKUP/app.py"
cp templates/dashboard.html \
   "$BACKUP/templates/dashboard.html"
cp static/css/style.css \
   "$BACKUP/static/css/style.css"

echo "Backup: $BACKUP"

echo
echo "[2/7] Adding optional logo support..."

python - <<'PY'
from pathlib import Path

path = Path("app.py")
text = path.read_text(encoding="utf-8")

if "from pathlib import Path" not in text:
    text = "from pathlib import Path\n" + text

anchor = '''    return render_template(
        "dashboard.html",
'''

if "logo_available=logo_available" not in text:
    calculation_anchor = "    cash_summary = get_cash_summary()\n"

    if calculation_anchor not in text:
        raise SystemExit(
            "Unable to find dashboard calculation anchor."
        )

    text = text.replace(
        calculation_anchor,
        calculation_anchor
        + '''
    logo_available = Path(
        "static/images/mip_pro_logo.png"
    ).exists()
''',
        1,
    )

    context_anchor = "        cash_summary=cash_summary,\n"

    if context_anchor not in text:
        raise SystemExit(
            "Unable to find dashboard template context."
        )

    text = text.replace(
        context_anchor,
        context_anchor
        + "        logo_available=logo_available,\n",
        1,
    )

path.write_text(text, encoding="utf-8")
print("Optional logo support added to app.py")
PY

echo
echo "[3/7] Updating executive dashboard header..."

python - <<'PY'
from pathlib import Path

path = Path("templates/dashboard.html")
text = path.read_text(encoding="utf-8")

start = text.find('<header class="topbar">')
end = text.find('</header>', start)

if start == -1 or end == -1:
    raise SystemExit("Dashboard header was not found.")

end += len('</header>')

new_header = '''<header class="topbar mip-executive-header">
    <div class="mip-header-brand">

        {% if logo_available %}
        <img
            class="mip-header-logo"
            src="{{ url_for('static', filename='images/mip_pro_logo.png') }}"
            alt="MIP PRO">
        {% else %}
        <div class="dashboard-brand-mark">
            <span class="mip-word">MIP</span>
            <span class="pro-word">PRO</span>
        </div>
        {% endif %}

        <div class="mip-header-copy">
            <p class="eyebrow">
                Market Intelligence Platform
            </p>

            <h1>MIP PRO</h1>

            <p class="subtitle">
                Professional Intelligence Suite
            </p>
        </div>
    </div>

    <nav class="mip-header-actions">
        <span class="system-online-badge">
            <span class="status-dot"></span>
            System Online
        </span>

        <a class="text-link" href="/about">
            About
        </a>

        <a class="text-link" href="/logout">
            Logout
        </a>

        <a class="button secondary-button" href="/screener">
            Full Screener
        </a>
    </nav>
</header>

<section class="mip-live-banner">
    <article>
        <span>Market Status</span>
        <strong>{{ market.market_status }}</strong>
    </article>

    <article>
        <span>Market Regime</span>
        <strong>
            {{ regime.regime|default('Collecting data') }}
        </strong>
    </article>

    <article>
        <span>AI Confidence</span>
        <strong>
            {{ committee.confidence|default(0) }}%
        </strong>
    </article>

    <article>
        <span>Data Provider</span>
        <strong>
            {{ market.provider|default('MyStocks Africa') }}
        </strong>
    </article>

    <article>
        <span>Securities</span>
        <strong>
            {{ market.security_count|default(market.stocks|length) }}
        </strong>
    </article>

    <article>
        <span>Last Update</span>
        <strong>
            {{ market.generated_at|default(now) }}
        </strong>
    </article>
</section>'''

text = text[:start] + new_header + text[end:]

text = text.replace(
    "<title>MIP PRO | Professional Intelligence Suite</title>",
    "<title>MIP PRO — Professional Intelligence Suite</title>",
)

text = text.replace(
    "MIP PRO Professional Intelligence Suite · Version 11.5 · Built in Kenya",
    (
        "MIP PRO Professional Intelligence Suite · "
        "Version 11.5 · Built in Kenya · "
        "AI-Powered Investment Intelligence for Africa"
    ),
)

path.write_text(text, encoding="utf-8")
print("Executive dashboard header installed.")
PY

echo
echo "[4/7] Adding executive dashboard styles..."

cat >> static/css/style.css <<'CSS'

/* ==================================================
   MIP PRO V11.5B Executive Dashboard
   ================================================== */

.mip-executive-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 30px;
    padding: 24px 32px;
    background:
        linear-gradient(
            115deg,
            rgba(255, 255, 255, 0.98),
            rgba(244, 248, 245, 0.98)
        );
    border-bottom: 1px solid rgba(20, 56, 37, 0.11);
    box-shadow: 0 8px 30px rgba(20, 45, 32, 0.07);
}

.mip-header-brand {
    display: flex;
    align-items: center;
    gap: 20px;
    min-width: 0;
}

.mip-header-logo {
    display: block;
    width: 145px;
    max-height: 92px;
    object-fit: contain;
    object-position: left center;
}

.mip-header-copy {
    min-width: 0;
}

.mip-header-copy .eyebrow {
    margin: 0 0 4px;
    color: #9a7318;
}

.mip-header-copy h1 {
    margin: 0;
    color: #121a16;
    font-size: clamp(30px, 4vw, 46px);
    letter-spacing: -1.5px;
}

.mip-header-copy .subtitle {
    margin: 3px 0 0;
    color: #5d6b64;
}

.mip-header-actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: 15px;
}

.system-online-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 9px 13px;
    border: 1px solid rgba(15, 114, 62, 0.18);
    border-radius: 999px;
    background: rgba(15, 114, 62, 0.08);
    color: #0c6537;
    font-size: 13px;
    font-weight: 800;
}

.mip-live-banner {
    display: grid;
    grid-template-columns:
        repeat(6, minmax(150px, 1fr));
    gap: 1px;
    margin: 0;
    background: #dfe7e2;
    border-bottom: 1px solid #dfe7e2;
}

.mip-live-banner article {
    min-width: 0;
    padding: 15px 18px;
    background: #ffffff;
}

.mip-live-banner span,
.mip-live-banner strong {
    display: block;
}

.mip-live-banner span {
    margin-bottom: 5px;
    color: #748078;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}

.mip-live-banner strong {
    overflow: hidden;
    color: #1c2a22;
    font-size: 14px;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.dashboard-container {
    max-width: 1600px;
}

.dashboard-panel {
    border: 1px solid rgba(20, 56, 37, 0.08);
    box-shadow: 0 14px 40px rgba(20, 45, 32, 0.07);
}

.summary-card {
    border: 1px solid rgba(20, 56, 37, 0.08);
    box-shadow: 0 10px 25px rgba(20, 45, 32, 0.06);
}

.dashboard-footer {
    padding: 24px;
    color: #617067;
    text-align: center;
    line-height: 1.7;
}

@media (max-width: 1200px) {
    .mip-live-banner {
        grid-template-columns:
            repeat(3, minmax(150px, 1fr));
    }
}

@media (max-width: 850px) {
    .mip-executive-header {
        align-items: flex-start;
        flex-direction: column;
        padding: 22px;
    }

    .mip-header-actions {
        justify-content: flex-start;
    }

    .mip-live-banner {
        grid-template-columns:
            repeat(2, minmax(130px, 1fr));
    }
}

@media (max-width: 520px) {
    .mip-header-brand {
        align-items: flex-start;
        flex-direction: column;
    }

    .mip-header-logo {
        width: 125px;
    }

    .mip-live-banner {
        grid-template-columns: 1fr;
    }
}
CSS

echo
echo "[5/7] Checking branding..."

grep -n -E \
    "MIP PRO|mip-live-banner|logo_available" \
    app.py templates/dashboard.html \
    | head -30

echo
echo "[6/7] Running syntax validation..."

"$PROJECT/venv/bin/python" -m py_compile \
    app.py \
    services/*.py

echo "Syntax validation passed."

echo
echo "[7/7] Restarting and verifying..."

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
    echo "Login test failed: HTTP $LOGIN_CODE"
    exit 1
fi

trap - ERR

echo
echo "=================================================="
echo "MIP PRO V11.5B installed successfully"
echo "=================================================="

if [ -f static/images/mip_pro_logo.png ]; then
    echo "Logo status: Installed"
else
    echo "Logo status: Text fallback active"
    echo "Add the logo later at:"
    echo "$PROJECT/static/images/mip_pro_logo.png"
fi

echo
echo "Backup:"
echo "$BACKUP"

echo
echo "Log:"
echo "$LOG"

echo
echo "Refresh the dashboard with Ctrl + F5."
echo "=================================================="
