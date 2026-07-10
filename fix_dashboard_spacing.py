from pathlib import Path
import re
import shutil
from datetime import datetime

HTML_FILE = Path("templates/dashboard.html")

if not HTML_FILE.exists():
    raise SystemExit(f"File not found: {HTML_FILE}")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_file = HTML_FILE.with_name(f"dashboard.html.backup_{timestamp}")
shutil.copy2(HTML_FILE, backup_file)

html = HTML_FILE.read_text(encoding="utf-8")

# ---------------------------------------------------------
# 1. Remove the accidentally inserted empty placeholder block
# ---------------------------------------------------------
placeholder_pattern = re.compile(
    r"""
    <section[^>]*class=["'][^"']*top-opportunities-section[^"']*["'][^>]*>
    .*?
    <table[^>]*class=["'][^"']*nse-market-table[^"']*["'][^>]*>
    \s*
    (?:<!--.*?-->)?
    \s*
    </table>
    .*?
    </section>
    """,
    re.IGNORECASE | re.DOTALL | re.VERBOSE,
)

html, removed_blocks = placeholder_pattern.subn("", html)

# ---------------------------------------------------------
# 2. Remove directly repeated opportunity headings
# ---------------------------------------------------------
duplicate_heading_pattern = re.compile(
    r"""
    (<h2[^>]*>\s*Top\s+Autonomous\s+Opportunities\s*</h2>)
    (?:\s|<br\s*/?>|</?div[^>]*>|</?section[^>]*>)*
    (<h2[^>]*>\s*Top\s+Autonomous\s+Opportunities\s*</h2>)
    """,
    re.IGNORECASE | re.DOTALL | re.VERBOSE,
)

html, duplicate_headings = duplicate_heading_pattern.subn(r"\1", html)

# ---------------------------------------------------------
# 3. Add a dashboard table class to plain tables
# ---------------------------------------------------------
html = re.sub(
    r"<table(?![^>]*class=)",
    '<table class="dashboard-table">',
    html,
    flags=re.IGNORECASE,
)

# Add dashboard-table without removing existing classes
def update_table_class(match):
    quote = match.group(1)
    classes = match.group(2).split()

    if "dashboard-table" not in classes:
        classes.append("dashboard-table")

    return f'class={quote}{" ".join(classes)}{quote}'

html = re.sub(
    r'class=(["\'])(.*?)\1',
    update_table_class,
    html,
    flags=re.IGNORECASE,
)

HTML_FILE.write_text(html, encoding="utf-8")

# ---------------------------------------------------------
# 4. Locate the CSS file
# ---------------------------------------------------------
possible_css_files = [
    Path("static/style.css"),
    Path("static/styles.css"),
    Path("static/css/style.css"),
    Path("static/css/styles.css"),
]

css_file = next((path for path in possible_css_files if path.exists()), None)

if css_file is None:
    css_file = Path("static/style.css")
    css_file.parent.mkdir(parents=True, exist_ok=True)
    css_file.touch()

css_backup = css_file.with_name(f"{css_file.name}.backup_{timestamp}")
shutil.copy2(css_file, css_backup)

css = css_file.read_text(encoding="utf-8")

START_MARKER = "/* DASHBOARD SPACING FIX START */"
END_MARKER = "/* DASHBOARD SPACING FIX END */"

spacing_css = """
/* DASHBOARD SPACING FIX START */

/* Keep the main dashboard content aligned and compact */
.dashboard-container,
main,
.content,
.container {
    width: 100%;
    box-sizing: border-box;
}

/* Consistent spacing for dashboard panels */
.panel,
.card,
.dashboard-section,
.top-opportunities-section {
    box-sizing: border-box;
    width: 100%;
    height: auto;
    min-height: 0;
    margin: 0 0 22px 0;
    padding: 20px;
}

/* Prevent large unexplained vertical spaces */
.top-opportunities-section,
.nse-market-table-wrapper {
    min-height: 0 !important;
    height: auto !important;
    margin-top: 0;
    margin-bottom: 0;
    padding-bottom: 0;
}

/* Headings */
.panel h2,
.card h2,
.dashboard-section h2,
.top-opportunities-section h2 {
    margin: 0 0 18px 0;
    padding: 0;
    line-height: 1.25;
}

/* Responsive table container */
.nse-market-table-wrapper,
.table-wrapper {
    display: block;
    width: 100%;
    overflow-x: auto;
    overflow-y: hidden;
    margin: 0;
    padding: 0;
}

/* Tables should use all available width */
.dashboard-table,
.nse-market-table {
    width: 100%;
    max-width: 100%;
    border-collapse: collapse;
    border-spacing: 0;
    table-layout: auto;
    margin: 0;
}

/* Proper spacing and alignment */
.dashboard-table th,
.dashboard-table td,
.nse-market-table th,
.nse-market-table td {
    padding: 10px 12px;
    text-align: left;
    vertical-align: middle;
    white-space: nowrap;
    line-height: 1.35;
}

/* Keep sections separated without excessive blank space */
.panel + .panel,
.card + .card,
.dashboard-section + .dashboard-section {
    margin-top: 0;
}

/* Portfolio recommendation spacing */
.recommendation,
.portfolio-recommendation {
    margin-top: 16px;
    margin-bottom: 0;
}

/* Mobile layout */
@media (max-width: 768px) {
    .panel,
    .card,
    .dashboard-section,
    .top-opportunities-section {
        padding: 14px;
        margin-bottom: 14px;
    }

    .dashboard-table th,
    .dashboard-table td,
    .nse-market-table th,
    .nse-market-table td {
        padding: 8px 10px;
        font-size: 14px;
    }
}

/* DASHBOARD SPACING FIX END */
"""

# Replace an earlier copy of the fix instead of duplicating it
if START_MARKER in css and END_MARKER in css:
    css = re.sub(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        spacing_css.strip(),
        css,
        flags=re.DOTALL,
    )
else:
    css = css.rstrip() + "\n\n" + spacing_css.strip() + "\n"

css_file.write_text(css, encoding="utf-8")

print()
print("Dashboard repair completed.")
print(f"HTML backup: {backup_file}")
print(f"CSS file:    {css_file}")
print(f"CSS backup:  {css_backup}")
print(f"Empty placeholder sections removed: {removed_blocks}")
print(f"Duplicate headings removed:          {duplicate_headings}")
print()
print("Review the changes with:")
print(f"  diff -u {backup_file} {HTML_FILE}")
