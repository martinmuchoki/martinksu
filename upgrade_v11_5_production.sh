#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT="/root/nse_signal_bot_v10_3"
STAMP="$(date +%Y-%m-%d_%H-%M-%S)"
BACKUP="$PROJECT/backups/v11_5_production_$STAMP"
LOG="$PROJECT/logs/v11_5_production_$STAMP.log"

mkdir -p \
"$BACKUP" \
"$BACKUP/services" \
"$BACKUP/templates" \
"$BACKUP/static/css" \
"$BACKUP/static/js" \
"$PROJECT/logs"

exec > >(tee -a "$LOG") 2>&1

rollback() {

echo
echo "Rolling back..."

[ -f "$BACKUP/app.py" ] &&
cp "$BACKUP/app.py" "$PROJECT/app.py"

[ -f "$BACKUP/services/reports.py" ] &&
cp "$BACKUP/services/reports.py" \
"$PROJECT/services/reports.py"

[ -f "$BACKUP/templates/dashboard_v115.html" ] &&
cp "$BACKUP/templates/dashboard_v115.html" \
"$PROJECT/templates/dashboard_v115.html"

[ -f "$BACKUP/static/css/v115.css" ] &&
cp "$BACKUP/static/css/v115.css" \
"$PROJECT/static/css/v115.css"

[ -f "$BACKUP/static/js/v115_charts.js" ] &&
cp "$BACKUP/static/js/v115_charts.js" \
"$PROJECT/static/js/v115_charts.js"

./restart.sh || true

echo "Rollback complete."
exit 1
}

trap rollback ERR

echo
echo "========================================="
echo " MIP PRO V11.5 Production Installer"
echo "========================================="

echo
echo "[1/5] Creating backup..."

cp app.py "$BACKUP/"
cp services/reports.py "$BACKUP/services/"
cp templates/dashboard_v115.html "$BACKUP/templates/"
cp static/css/v115.css "$BACKUP/static/css/"
cp static/js/v115_charts.js "$BACKUP/static/js/"

echo "Backup completed."

echo
echo "[2/5] Upgrading executive PDF report..."

venv/bin/python - <<'PY'
from pathlib import Path
import re

path = Path("services/reports.py")
text = path.read_text(encoding="utf-8")

# Ensure ReportLab Image is imported.
import_block = re.search(
    r"from reportlab\.platypus import \((.*?)\)",
    text,
    flags=re.DOTALL,
)

if import_block and "Image," not in import_block.group(1):
    updated_block = import_block.group(0).replace(
        "    PageBreak,\n",
        "    Image,\n    PageBreak,\n",
        1,
    )

    text = text.replace(
        import_block.group(0),
        updated_block,
        1,
    )

# Use the V11.5 Production PDF filename.
text = re.sub(
    r'PDF_REPORT_FILE\s*=\s*REPORT_DIR\s*/\s*"[^"]+\.pdf"',
    'PDF_REPORT_FILE = REPORT_DIR / '
    '"MIP_PRO_Daily_Intelligence_Report_v11_5_Production.pdf"',
    text,
    count=1,
)

# Add the logo path.
logo_line = 'LOGO_FILE = Path("static/images/mip_pro_logo.png")'

if logo_line not in text:
    pdf_line = (
        'PDF_REPORT_FILE = REPORT_DIR / '
        '"MIP_PRO_Daily_Intelligence_Report_v11_5_Production.pdf"'
    )

    text = text.replace(
        pdf_line,
        pdf_line + "\n" + logo_line,
        1,
    )

# Add branded footer with page numbers.
footer_pattern = re.compile(
    r"def _add_page_number\(canvas, document\) -> None:.*?"
    r"(?=\n\ndef generate_daily_report)",
    re.DOTALL,
)

footer_code = '''def _add_page_number(canvas, document) -> None:
    canvas.saveState()

    canvas.setStrokeColor(colors.HexColor("#D9E3DC"))
    canvas.line(
        18 * mm,
        15 * mm,
        A4[0] - 18 * mm,
        15 * mm,
    )

    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#5E6A63"))

    canvas.drawString(
        18 * mm,
        10.5 * mm,
        "Powered by MIP Inc. | "
        "AI Investment Intelligence for Africa",
    )

    canvas.drawRightString(
        A4[0] - 18 * mm,
        10.5 * mm,
        f"MIP PRO V11.5 Production | Page {document.page}",
    )

    canvas.restoreState()
'''

if footer_pattern.search(text):
    text = footer_pattern.sub(
        footer_code,
        text,
        count=1,
    )

# Update PDF document metadata.
text = text.replace(
    'title="Daily Intelligence Report"',
    'title="MIP PRO Daily Intelligence Report"',
)

# Add branded title styles if missing.
if '"BrandName"' not in text:
    anchor = '''    subtitle_style = ParagraphStyle(
'''

    styles = '''    brand_style = ParagraphStyle(
        "BrandName",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#111111"),
        spaceAfter=4,
    )

    edition_style = ParagraphStyle(
        "BrandEdition",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#B48C25"),
        spaceAfter=10,
    )

'''

    text = text.replace(
        anchor,
        styles + anchor,
        1,
    )

# Replace the existing report title section.
story_pattern = re.compile(
    r"    story = \[.*?\]\n\n"
    r"    market_data =",
    re.DOTALL,
)

new_story = '''    story = []

    if LOGO_FILE.exists():
        logo = Image(
            str(LOGO_FILE),
            width=46 * mm,
            height=36.8 * mm,
        )
        logo.hAlign = "CENTER"
        story.append(logo)
        story.append(Spacer(1, 4))

    story.append(
        Paragraph(
            "MIP PRO",
            brand_style,
        )
    )

    story.append(
        Paragraph(
            "Professional Intelligence Suite",
            edition_style,
        )
    )

    story.append(
        Paragraph(
            (
                "Daily Market Intelligence Report<br/>"
                "Version 11.5 Production<br/>"
                f"Generated: {generated_at}<br/>"
                "Powered by MIP Inc.<br/>"
                "AI Investment Intelligence for Africa"
            ),
            subtitle_style,
        )
    )

    market_data ='''

if story_pattern.search(text):
    text = story_pattern.sub(
        new_story,
        text,
        count=1,
    )
else:
    if (
        "MIP PRO" in text
        and "LOGO_FILE" in text
        and "Daily Market Intelligence Report" in text
    ):
        print(
            "PDF title section is already branded; "
            "continuing with production updates."
        )
    else:
        raise SystemExit(
            "Unable to find or verify the report title section."
        )

# Increase PDF opportunities from 10 to 16.
text = text.replace(
    "for index, item in enumerate(opportunities[:10], start=1):",
    "for index, item in enumerate(opportunities[:16], start=1):",
)

# Apply MIP green to headings and table headers.
text = text.replace(
    'colors.HexColor("#16324F")',
    'colors.HexColor("#08783F")',
)

path.write_text(text, encoding="utf-8")

print("PDF branding and Top 16 opportunities installed.")
PY


echo
echo "[3/5] Updating production version and branding..."

venv/bin/python - <<'PY'
from pathlib import Path
import re

app = Path("app.py")
text = app.read_text(encoding="utf-8")

text = re.sub(
    r'VERSION\s*=\s*"11\.5 RC2"',
    'VERSION = "11.5 Production"',
    text,
    count=1,
)

text = text.replace(
    'download_name="MIP_PRO_Daily_Intelligence_Report_v11_5.pdf"',
    'download_name="MIP_PRO_Daily_Intelligence_Report_v11_5_Production.pdf"',
)

text = text.replace(
    'download_name="daily_intelligence_report_v11_4.pdf"',
    'download_name="MIP_PRO_Daily_Intelligence_Report_v11_5_Production.pdf"',
)

app.write_text(text, encoding="utf-8")
print("app.py updated.")

dashboard = Path("templates/dashboard_v115.html")
html = dashboard.read_text(encoding="utf-8")

footer_pattern = re.compile(
    r'<footer class="app-footer">.*?</footer>',
    re.DOTALL,
)

footer = '''<footer class="app-footer">
    <strong>MIP PRO</strong>
    <span>Professional Intelligence Suite</span>
    <span>Version 11.5</span>
    <span>Powered by MIP Inc.</span>
    <span>AI Investment Intelligence for Africa</span>
</footer>'''

if footer_pattern.search(html):
    html = footer_pattern.sub(
        footer,
        html,
        count=1,
    )
else:
    raise SystemExit("Dashboard footer was not found.")

html = html.replace(
    "Version 11.5 RC2",
    "Version 11.5",
)

dashboard.write_text(html, encoding="utf-8")
print("Dashboard production branding updated.")
PY

echo
echo "Production version and footer branding completed."


echo
echo "[4/5] Validating application and generating test PDF..."

venv/bin/python -m py_compile \
    app.py \
    services/reports.py \
    services/*.py

venv/bin/python - <<'PY'
from pathlib import Path

from services.market_data import get_market_snapshot
from services.technical_analysis import analyze_market
from services.portfolio import get_portfolio
from services.ai_committee import run_committee
from services.autonomous_assistant import autonomous_decision
from services.reports import generate_daily_report

market = get_market_snapshot()
technicals = analyze_market(market.get("stocks", []))
portfolio = get_portfolio()

committee = run_committee(
    market=market,
    technicals=technicals,
    portfolio=portfolio,
)

assistant = autonomous_decision(
    market,
    committee,
    portfolio,
    technicals,
)

report = generate_daily_report(
    market,
    committee,
    portfolio,
    assistant,
)

path = Path(report["path"])

if not path.exists():
    raise SystemExit("PDF was not generated.")

if path.stat().st_size < 5000:
    raise SystemExit(
        f"Generated PDF is too small: {path.stat().st_size} bytes"
    )

if path.read_bytes()[:4] != b"%PDF":
    raise SystemExit("Generated file is not a valid PDF.")

print(f"PDF test passed: {path}")
print(f"PDF size: {path.stat().st_size:,} bytes")
PY

echo
echo "Restarting application..."

./restart.sh
sleep 2

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
    echo "Login route failed: HTTP $LOGIN_CODE"
    exit 1
fi

echo "Validation and health checks passed."


echo
echo "[5/5] Creating release notes and production package..."

RELEASE_NOTES="$PROJECT/RELEASE_NOTES_V11_5.md"
PACKAGE="$PROJECT/backups/MIP_PRO_V11_5_PRODUCTION_$STAMP.tar.gz"

cat > "$RELEASE_NOTES" <<EOF
# MIP PRO V11.5 Production

Released: $(date '+%Y-%m-%d %H:%M:%S %Z')

## Product

- MIP PRO
- Professional Intelligence Suite
- Version 11.5 Production
- Powered by MIP Inc.
- AI Investment Intelligence for Africa

## Production features

- Secure administrator login
- Live NSE market data
- AI Investment Committee
- Top 16 NSE Predictions
- Top 16 AI Stock Screener
- Top 16 Volume Leaders
- Market Breadth
- Interactive charts
- Portfolio intelligence
- Institutional risk analytics
- Sector rotation
- Recommendation performance tracking
- Branded PDF report with logo
- Telegram daily intelligence report

## Backup

$BACKUP

## Upgrade log

$LOG

## Production package

$PACKAGE
EOF

tar \
    --exclude="./backups" \
    --exclude="./logs" \
    --exclude="./venv" \
    --exclude="./__pycache__" \
    --exclude="*/__pycache__" \
    -czf "$PACKAGE" .

test -s "$PACKAGE"

trap - ERR

echo
echo "========================================="
echo " MIP PRO V11.5 Production Completed"
echo "========================================="
echo
echo "Backup:"
echo "$BACKUP"
echo
echo "Production package:"
echo "$PACKAGE"
echo
echo "Release notes:"
echo "$RELEASE_NOTES"
echo
echo "Log:"
echo "$LOG"
echo
echo "Open the dashboard and download the PDF."
echo "Press Ctrl + Shift + R."
echo "========================================="

