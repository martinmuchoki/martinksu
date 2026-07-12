#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT="/root/nse_signal_bot_v10_3"
STAMP=$(date +%Y-%m-%d_%H-%M-%S)

cd "$PROJECT"

echo "Creating backup..."
cp services/reports.py backups/reports_before_pdf_branding_$STAMP.py
cp app.py backups/app_before_pdf_branding_$STAMP.py

venv/bin/python - <<'PY'
from pathlib import Path

path = Path("services/reports.py")
text = path.read_text(encoding="utf-8")

# Import Image
if "Image," not in text:
    text = text.replace(
        "    Table,\n",
        "    Table,\n    Image,\n"
    )

# Add logo constant
if 'LOGO_FILE = Path("static/images/mip_pro_logo.png")' not in text:
    text = text.replace(
        'PDF_REPORT_FILE = REPORT_DIR / "daily_intelligence_report_v11_4.pdf"',
        '''PDF_REPORT_FILE = REPORT_DIR / "daily_intelligence_report_v11_5.pdf"
LOGO_FILE = Path("static/images/mip_pro_logo.png")'''
    )

old_story = '''    story = [
        Paragraph(
            "MARKET INTELLIGENCE PLATFORM V11.4",
            title_style,
        ),
        Paragraph(
            f"Daily Intelligence Report<br/>Generated: {generated_at}",
            subtitle_style,
        ),
    ]'''

new_story = '''    story = []

    if LOGO_FILE.exists():
        logo = Image(str(LOGO_FILE), width=42*mm, height=33.6*mm)
        logo.hAlign = "CENTER"
        story.append(logo)

    story.append(
        Paragraph(
            "MIP PRO",
            title_style,
        )
    )

    story.append(
        Paragraph(
            "Professional Intelligence Suite",
            subtitle_style,
        )
    )

    story.append(
        Paragraph(
            f"""
            Daily Market Intelligence Report<br/>
            Version 11.5 Production<br/>
            Generated: {generated_at}<br/>
            Powered by MIP Inc.<br/>
            AI Investment Intelligence for Africa
            """,
            subtitle_style,
        )
    )
'''

text = text.replace(old_story, new_story)

path.write_text(text, encoding="utf-8")
print("services/reports.py updated")
PY

venv/bin/python - <<'PY'
from pathlib import Path

path = Path("app.py")
text = path.read_text(encoding="utf-8")

text = text.replace(
    'download_name="daily_intelligence_report_v11_4.pdf"',
    'download_name="MIP_PRO_Daily_Intelligence_Report_v11_5.pdf"'
)

path.write_text(text, encoding="utf-8")
print("app.py updated")
PY

echo "Validating..."
venv/bin/python -m py_compile services/reports.py
venv/bin/python -m py_compile app.py

echo "Restarting..."
./restart.sh

echo
echo "PDF branding upgrade completed."
