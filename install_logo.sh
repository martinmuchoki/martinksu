#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT="/root/nse_signal_bot_v10_3"
STAMP="$(date +%Y-%m-%d_%H-%M-%S)"
BACKUP="$PROJECT/backups/logo_install_$STAMP"
LOG="$PROJECT/logs/install_logo_$STAMP.log"

cd "$PROJECT"
mkdir -p "$BACKUP/templates" "$BACKUP/static/css" "$PROJECT/logs"

exec > >(tee -a "$LOG") 2>&1

rollback() {
    echo "Logo installation failed. Restoring files..."

    [ -f "$BACKUP/templates/dashboard_v115.html" ] &&
        cp "$BACKUP/templates/dashboard_v115.html" \
           "$PROJECT/templates/dashboard_v115.html"

    [ -f "$BACKUP/templates/login.html" ] &&
        cp "$BACKUP/templates/login.html" \
           "$PROJECT/templates/login.html"

    [ -f "$BACKUP/templates/about.html" ] &&
        cp "$BACKUP/templates/about.html" \
           "$PROJECT/templates/about.html"

    [ -f "$BACKUP/static/css/v115.css" ] &&
        cp "$BACKUP/static/css/v115.css" \
           "$PROJECT/static/css/v115.css"

    [ -f "$BACKUP/static/css/style.css" ] &&
        cp "$BACKUP/static/css/style.css" \
           "$PROJECT/static/css/style.css"

    "$PROJECT/restart.sh" || true
    exit 1
}

trap rollback ERR

LOGO="$PROJECT/static/images/mip_pro_logo.png"

if [ ! -f "$LOGO" ]; then
    echo "Logo not found:"
    echo "$LOGO"
    exit 1
fi

echo "Backing up current branding files..."

cp templates/dashboard_v115.html \
   "$BACKUP/templates/dashboard_v115.html"

cp templates/login.html \
   "$BACKUP/templates/login.html"

[ -f templates/about.html ] &&
    cp templates/about.html \
       "$BACKUP/templates/about.html"

cp static/css/v115.css \
   "$BACKUP/static/css/v115.css"

cp static/css/style.css \
   "$BACKUP/static/css/style.css"

echo "Updating login and About pages..."

python - <<'PY'
from pathlib import Path
import re

for filename, css_class, marker in (
    ("templates/login.html", "login-logo-image", '<section class="login-card">'),
    ("templates/about.html", "about-logo-image", '<section class="about-card">'),
):
    path = Path(filename)

    if not path.exists():
        continue

    text = path.read_text(encoding="utf-8")

    image = (
        '<img\n'
        f'            class="{css_class}"\n'
        '            src="{{ url_for(\'static\', filename=\'images/mip_pro_logo.png\') }}"\n'
        '            alt="MIP PRO">'
    )

    text = re.sub(
        r'<div class="login-brand-mark">.*?</div>',
        image,
        text,
        count=1,
        flags=re.DOTALL,
    )

    if css_class not in text:
        text = text.replace(
            marker,
            marker + "\n\n        " + image,
            1,
        )

    path.write_text(text, encoding="utf-8")
    print("Updated:", filename)
PY

cat >> static/css/style.css <<'CSS'

.login-logo-image {
    display: block;
    width: min(235px, 76%);
    height: auto;
    margin: 0 auto 18px;
    object-fit: contain;
}

.about-logo-image {
    display: block;
    width: min(255px, 72%);
    height: auto;
    margin: 0 0 22px;
    object-fit: contain;
}
CSS

cat >> static/css/v115.css <<'CSS'

.brand-logo {
    width: 150px;
    height: auto;
    max-height: 105px;
    object-fit: contain;
    object-position: left center;
}
CSS

echo "Validating and restarting..."

python -m py_compile app.py services/*.py
./restart.sh

curl -fsS http://127.0.0.1:5000/health

trap - ERR

echo
echo "Logo installed successfully."
echo "Backup: $BACKUP"
echo "Log: $LOG"
