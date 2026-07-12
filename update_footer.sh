#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT="/root/nse_signal_bot_v10_3"
STAMP="$(date +%Y-%m-%d_%H-%M-%S)"
TEMPLATE="$PROJECT/templates/dashboard_v115.html"
BACKUP="$PROJECT/templates/dashboard_v115.html.before_footer_$STAMP"

cd "$PROJECT"

echo "Backing up current dashboard template..."
cp "$TEMPLATE" "$BACKUP"

echo "Updating footer..."

venv/bin/python - <<'PY'
from pathlib import Path
import re

path = Path("templates/dashboard_v115.html")
text = path.read_text(encoding="utf-8")

pattern = re.compile(
    r'<footer class="app-footer">.*?</footer>',
    re.DOTALL,
)

replacement = '''<footer class="app-footer">
    <strong>MIP PRO</strong>
    <span>Professional Intelligence Suite</span>
    <span>Version 11.5</span>
    <span>Powered by MIP Inc.</span>
    <span>AI Investment Intelligence for Africa</span>
</footer>'''

if not pattern.search(text):
    raise SystemExit("Footer block was not found.")

text = pattern.sub(replacement, text, count=1)

path.write_text(text, encoding="utf-8")

print("Footer updated successfully.")
PY

echo "Restarting application..."
./restart.sh

echo
echo "Verifying footer..."
grep -n -A6 -B1 '<footer class="app-footer">' \
    templates/dashboard_v115.html

echo
echo "Backup created:"
echo "$BACKUP"
