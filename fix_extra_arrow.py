from pathlib import Path
from datetime import datetime
import re
import shutil

file_path = Path("templates/dashboard.html")

if not file_path.exists():
    raise SystemExit(f"File not found: {file_path}")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = file_path.with_name(f"dashboard.html.before_arrow_fix_{timestamp}")

shutil.copy2(file_path, backup)

html = file_path.read_text(encoding="utf-8")

# Remove duplicated > after normal HTML opening tags, for example:
# <table ...>>
# <div ...>>
html = re.sub(
    r'(<(?:table|thead|tbody|tfoot|tr|th|td|div|section)[^>]*>)\s*>',
    r'\1',
    html,
    flags=re.IGNORECASE
)

# Remove a literal escaped arrow appearing by itself
html = re.sub(
    r'(?m)^[ \t]*(?:&gt;|>)[ \t]*$',
    '',
    html
)

# Remove dashboard-table from elements that are not tables
def clean_non_table_classes(match):
    tag = match.group(1)
    attributes = match.group(2)

    class_match = re.search(
        r'class=(["\'])(.*?)\1',
        attributes,
        flags=re.IGNORECASE
    )

    if not class_match:
        return match.group(0)

    classes = class_match.group(2).split()
    classes = [name for name in classes if name != "dashboard-table"]

    if classes:
        replacement = f'class={class_match.group(1)}{" ".join(classes)}{class_match.group(1)}'
        attributes = (
            attributes[:class_match.start()]
            + replacement
            + attributes[class_match.end():]
        )
    else:
        attributes = (
            attributes[:class_match.start()]
            + attributes[class_match.end():]
        )

    return f"<{tag}{attributes}>"

html = re.sub(
    r'<(?!table\b)([a-zA-Z][a-zA-Z0-9-]*)([^>]*)>',
    clean_non_table_classes,
    html
)

# Ensure each table has dashboard-table exactly once
def fix_table(match):
    attributes = match.group(1)

    class_match = re.search(
        r'class=(["\'])(.*?)\1',
        attributes,
        flags=re.IGNORECASE
    )

    if class_match:
        classes = class_match.group(2).split()

        # Remove duplicates while preserving order
        classes = list(dict.fromkeys(classes))

        if "dashboard-table" not in classes:
            classes.append("dashboard-table")

        replacement = f'class={class_match.group(1)}{" ".join(classes)}{class_match.group(1)}'

        attributes = (
            attributes[:class_match.start()]
            + replacement
            + attributes[class_match.end():]
        )
    else:
        attributes += ' class="dashboard-table"'

    return f"<table{attributes}>"

html = re.sub(
    r'<table([^>]*)>',
    fix_table,
    html,
    flags=re.IGNORECASE
)

file_path.write_text(html, encoding="utf-8")

print("Cleanup completed.")
print(f"Backup created: {backup}")
print()
print("Checking for remaining duplicated arrows:")
for number, line in enumerate(html.splitlines(), start=1):
    if ">>" in line or "&gt;" in line:
        print(f"{number}: {line}")
