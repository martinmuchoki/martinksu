#!/usr/bin/env python3
"""
NSE Signal Bot — Unused Code Analyzer

Report-only tool. It does not delete or modify project files.

Checks:
- Potentially unused Python modules
- Potentially unused functions and classes
- Unreferenced templates
- Unreferenced static assets
- Duplicate files
- Backup/legacy files
- Empty Python files
- Large files
- __pycache__ and compiled files

Important:
Results are candidates for review, not automatic deletion decisions.
Dynamic imports, decorators, Flask routes, schedulers and reflection can create
false positives.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]

EXCLUDED_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    "venv",
    ".venv",
    "env",
    "node_modules",
    "__pycache__",
    "reports",
    "backups",
}

PYTHON_ENTRYPOINT_NAMES = {
    "app.py",
    "wsgi.py",
    "manage.py",
    "run.py",
    "worker.py",
    "scheduler.py",
    "gunicorn.conf.py",
}

COMMON_MAGIC_METHODS = {
    "__init__",
    "__str__",
    "__repr__",
    "__enter__",
    "__exit__",
    "__iter__",
    "__next__",
    "__len__",
    "__getitem__",
    "__setitem__",
    "__call__",
    "__post_init__",
}

DECORATOR_MARKERS = {
    "route",
    "before_request",
    "after_request",
    "errorhandler",
    "context_processor",
    "template_filter",
    "template_global",
    "command",
    "task",
    "job",
    "scheduled_job",
    "receiver",
    "register",
    "property",
    "staticmethod",
    "classmethod",
}

BACKUP_PATTERNS = (
    ".bak",
    ".backup",
    ".old",
    ".orig",
    ".save",
    "~",
    "_backup",
    "backup_",
    "_legacy",
    "_deprecated",
)

TEXT_EXTENSIONS = {
    ".py",
    ".html",
    ".jinja",
    ".jinja2",
    ".js",
    ".css",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".service",
    ".sh",
    ".md",
    ".txt",
}


@dataclass
class Finding:
    category: str
    path: str
    name: str = ""
    line: int | None = None
    reason: str = ""
    confidence: str = "medium"


def is_excluded(path: Path) -> bool:
    try:
        relative = path.relative_to(PROJECT_ROOT)
    except ValueError:
        return True

    return any(part in EXCLUDED_DIRS for part in relative.parts)


def iter_files(extensions: set[str] | None = None) -> Iterable[Path]:
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file() or is_excluded(path):
            continue

        if extensions is None or path.suffix.lower() in extensions:
            yield path


def relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def module_name(path: Path) -> str:
    rel = path.relative_to(PROJECT_ROOT).with_suffix("")
    parts = list(rel.parts)

    if parts and parts[-1] == "__init__":
        parts = parts[:-1]

    return ".".join(parts)


def decorator_names(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> set[str]:
    names: set[str] = set()

    for decorator in node.decorator_list:
        try:
            text = ast.unparse(decorator)
        except Exception:
            text = ""

        for marker in DECORATOR_MARKERS:
            if re.search(rf"\b{re.escape(marker)}\b", text):
                names.add(marker)

    return names


class PythonVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.imports: set[str] = set()
        self.names_used: set[str] = set()
        self.string_values: set[str] = set()
        self.definitions: list[dict] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self.imports.add(node.module)

        for alias in node.names:
            self.names_used.add(alias.name)

        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self.names_used.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self.names_used.add(node.attr)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str):
            self.string_values.add(node.value)
        self.generic_visit(node)

    def record_definition(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
        kind: str,
    ) -> None:
        self.definitions.append(
            {
                "name": node.name,
                "kind": kind,
                "line": node.lineno,
                "decorators": sorted(decorator_names(node)),
            }
        )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.record_definition(node, "function")
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.record_definition(node, "async function")
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.record_definition(node, "class")
        self.generic_visit(node)


def parse_python_files() -> tuple[dict[Path, PythonVisitor], list[Finding]]:
    parsed: dict[Path, PythonVisitor] = {}
    findings: list[Finding] = []

    for path in iter_files({".py"}):
        text = safe_read(path)

        if not text.strip():
            findings.append(
                Finding(
                    category="Empty Python files",
                    path=relative(path),
                    reason="File contains no executable source code.",
                    confidence="high",
                )
            )
            continue

        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            findings.append(
                Finding(
                    category="Python parse errors",
                    path=relative(path),
                    line=exc.lineno,
                    reason=str(exc),
                    confidence="high",
                )
            )
            continue

        visitor = PythonVisitor(path)
        visitor.visit(tree)
        parsed[path] = visitor

    return parsed, findings


def analyze_python(parsed: dict[Path, PythonVisitor]) -> list[Finding]:
    findings: list[Finding] = []

    all_imports: set[str] = set()
    all_used_names: set[str] = set()
    all_strings: set[str] = set()
    all_source = ""

    for path, visitor in parsed.items():
        all_imports.update(visitor.imports)
        all_used_names.update(visitor.names_used)
        all_strings.update(visitor.string_values)
        all_source += "\n" + safe_read(path)

    project_modules = {
        module_name(path): path
        for path in parsed
        if path.name != "__init__.py"
    }

    for module, path in sorted(project_modules.items()):
        if path.name in PYTHON_ENTRYPOINT_NAMES:
            continue

        if path.parent == PROJECT_ROOT:
            continue

        short_name = module.split(".")[-1]

        imported = any(
            imported_module == module
            or imported_module.startswith(module + ".")
            or module.startswith(imported_module + ".")
            for imported_module in all_imports
        )

        string_referenced = any(
            module in value or short_name in value
            for value in all_strings
        )

        source_referenced = bool(
            re.search(
                rf"\b{re.escape(short_name)}\b",
                all_source.replace(safe_read(path), "", 1),
            )
        )

        if not imported and not string_referenced and not source_referenced:
            findings.append(
                Finding(
                    category="Potentially unused Python modules",
                    path=relative(path),
                    name=module,
                    reason="No static import or obvious textual reference found.",
                    confidence="medium",
                )
            )

    definition_occurrences: defaultdict[str, list[tuple[Path, dict]]] = defaultdict(list)

    for path, visitor in parsed.items():
        for definition in visitor.definitions:
            definition_occurrences[definition["name"]].append((path, definition))

    for name, definitions in sorted(definition_occurrences.items()):
        if name.startswith("__") and name.endswith("__"):
            continue

        if name in COMMON_MAGIC_METHODS:
            continue

        for path, definition in definitions:
            if definition["decorators"]:
                continue

            text_without_definition = "\n".join(
                safe_read(other_path)
                for other_path in parsed
                if other_path != path
            )

            same_file_lines = safe_read(path).splitlines()
            same_file_text = "\n".join(
                line
                for index, line in enumerate(same_file_lines, start=1)
                if index != definition["line"]
            )

            total_matches = len(
                re.findall(
                    rf"\b{re.escape(name)}\b",
                    text_without_definition + "\n" + same_file_text,
                )
            )

            if total_matches == 0:
                findings.append(
                    Finding(
                        category=f"Potentially unused {definition['kind']}s",
                        path=relative(path),
                        name=name,
                        line=definition["line"],
                        reason="Definition name has no other static reference.",
                        confidence="low",
                    )
                )

    return findings


def collect_template_references() -> set[str]:
    references: set[str] = set()

    patterns = [
        r"""render_template\(\s*["']([^"']+)["']""",
        r"""{%\s*(?:include|extends|import|from)\s+["']([^"']+)["']""",
    ]

    for path in iter_files({".py", ".html", ".jinja", ".jinja2"}):
        text = safe_read(path)
        for pattern in patterns:
            references.update(re.findall(pattern, text))

    return references


def analyze_templates() -> list[Finding]:
    findings: list[Finding] = []
    templates_dir = PROJECT_ROOT / "templates"

    if not templates_dir.exists():
        return findings

    references = collect_template_references()

    for path in templates_dir.rglob("*"):
        if not path.is_file():
            continue

        rel_template = path.relative_to(templates_dir).as_posix()

        if rel_template in references:
            continue

        if path.name.startswith("_"):
            confidence = "low"
            reason = "Partial template has no detected static include."
        else:
            confidence = "medium"
            reason = "No render_template, include or extends reference found."

        findings.append(
            Finding(
                category="Potentially unused templates",
                path=relative(path),
                name=rel_template,
                reason=reason,
                confidence=confidence,
            )
        )

    return findings


def collect_static_references() -> tuple[set[str], str]:
    references: set[str] = set()
    combined = ""

    patterns = [
        r"""url_for\(\s*["']static["']\s*,\s*filename\s*=\s*["']([^"']+)["']""",
        r"""(?:src|href)\s*=\s*["']/static/([^"'?#]+)""",
        r"""url\(\s*["']?/?static/([^"')?#]+)""",
    ]

    for path in iter_files(TEXT_EXTENSIONS):
        text = safe_read(path)
        combined += "\n" + text

        for pattern in patterns:
            references.update(re.findall(pattern, text))

    return references, combined


def analyze_static_assets() -> list[Finding]:
    findings: list[Finding] = []
    static_dir = PROJECT_ROOT / "static"

    if not static_dir.exists():
        return findings

    references, combined = collect_static_references()

    for path in static_dir.rglob("*"):
        if not path.is_file():
            continue

        rel_static = path.relative_to(static_dir).as_posix()

        referenced = (
            rel_static in references
            or path.name in combined
        )

        if not referenced:
            findings.append(
                Finding(
                    category="Potentially unused static assets",
                    path=relative(path),
                    name=rel_static,
                    reason="No template, CSS, JavaScript or Python reference found.",
                    confidence="medium",
                )
            )

    return findings


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def analyze_duplicates() -> list[Finding]:
    findings: list[Finding] = []
    hashes: defaultdict[tuple[int, str], list[Path]] = defaultdict(list)

    for path in iter_files():
        try:
            size = path.stat().st_size
        except OSError:
            continue

        if size == 0:
            continue

        try:
            digest = file_hash(path)
        except OSError:
            continue

        hashes[(size, digest)].append(path)

    for (_, _), paths in hashes.items():
        if len(paths) < 2:
            continue

        names = ", ".join(relative(path) for path in paths)

        for path in paths:
            findings.append(
                Finding(
                    category="Duplicate files",
                    path=relative(path),
                    reason=f"Identical content shared by: {names}",
                    confidence="high",
                )
            )

    return findings


def analyze_backup_files() -> list[Finding]:
    findings: list[Finding] = []

    for path in iter_files():
        lower_name = path.name.lower()

        if any(pattern in lower_name for pattern in BACKUP_PATTERNS):
            findings.append(
                Finding(
                    category="Backup or legacy files",
                    path=relative(path),
                    reason="Filename appears to indicate backup, old or legacy content.",
                    confidence="high",
                )
            )

    backups_dir = PROJECT_ROOT / "backups"
    if backups_dir.exists():
        try:
            size = sum(
                file.stat().st_size
                for file in backups_dir.rglob("*")
                if file.is_file()
            )
        except OSError:
            size = 0

        findings.append(
            Finding(
                category="Backup directories",
                path="backups/",
                reason=f"Backup directory uses approximately {format_size(size)}.",
                confidence="high",
            )
        )

    return findings


def analyze_cache_files() -> list[Finding]:
    findings: list[Finding] = []

    for path in PROJECT_ROOT.rglob("__pycache__"):
        if path.is_dir():
            findings.append(
                Finding(
                    category="Generated cache directories",
                    path=relative(path),
                    reason="Python bytecode cache; safe to regenerate.",
                    confidence="high",
                )
            )

    for suffix in ("*.pyc", "*.pyo"):
        for path in PROJECT_ROOT.rglob(suffix):
            if path.is_file():
                findings.append(
                    Finding(
                        category="Generated compiled files",
                        path=relative(path),
                        reason="Compiled Python file; safe to regenerate.",
                        confidence="high",
                    )
                )

    return findings


def analyze_large_files(limit_mb: int = 5) -> list[Finding]:
    findings: list[Finding] = []
    limit_bytes = limit_mb * 1024 * 1024

    for path in iter_files():
        try:
            size = path.stat().st_size
        except OSError:
            continue

        if size >= limit_bytes:
            findings.append(
                Finding(
                    category="Large files",
                    path=relative(path),
                    reason=f"File size is {format_size(size)}.",
                    confidence="high",
                )
            )

    return findings


def format_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(size)

    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024

    return f"{value:.1f} GB"


def confidence_rank(value: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(value, 3)


def create_markdown_report(findings: list[Finding], generated_at: str) -> str:
    grouped: defaultdict[str, list[Finding]] = defaultdict(list)

    for finding in findings:
        grouped[finding.category].append(finding)

    lines = [
        "# NSE Signal Bot — Unused Code Analysis",
        "",
        f"Generated: `{generated_at}`",
        f"Project: `{PROJECT_ROOT}`",
        "",
        "## Important",
        "",
        "This is a report-only static analysis. Nothing was deleted.",
        "",
        "Potential false positives may come from dynamic imports, Flask decorators,",
        "scheduled jobs, reflection, Jinja-generated paths and configuration-driven code.",
        "",
        "## Summary",
        "",
        "| Category | Findings |",
        "|---|---:|",
    ]

    for category in sorted(grouped):
        lines.append(f"| {category} | {len(grouped[category])} |")

    lines.extend(
        [
            "",
            f"**Total findings:** {len(findings)}",
            "",
        ]
    )

    if not findings:
        lines.append("No cleanup candidates were detected.")
        return "\n".join(lines)

    for category in sorted(grouped):
        lines.extend([f"## {category}", ""])

        category_items = sorted(
            grouped[category],
            key=lambda item: (
                confidence_rank(item.confidence),
                item.path,
                item.line or 0,
                item.name,
            ),
        )

        for item in category_items:
            location = item.path
            if item.line:
                location += f":{item.line}"

            name = f" — `{item.name}`" if item.name else ""

            lines.append(
                f"- **[{item.confidence.upper()}]** `{location}`{name}"
            )
            lines.append(f"  - {item.reason}")

        lines.append("")

    lines.extend(
        [
            "## Recommended review order",
            "",
            "1. High-confidence backup, cache and duplicate-file findings.",
            "2. Unreferenced templates and static assets.",
            "3. Unused Python modules.",
            "4. Functions and classes marked low-confidence.",
            "",
            "Do not delete Python functions or modules solely from this report.",
            "Confirm Flask routes, scheduled jobs and dynamic imports first.",
        ]
    )

    return "\n".join(lines)


def main() -> int:
    print("=" * 64)
    print("NSE SIGNAL BOT — UNUSED CODE ANALYZER")
    print("=" * 64)
    print("Mode: REPORT ONLY — no files will be deleted")
    print()

    findings: list[Finding] = []

    print("[1/8] Parsing Python source...")
    parsed, parse_findings = parse_python_files()
    findings.extend(parse_findings)

    print("[2/8] Analyzing Python modules, functions and classes...")
    findings.extend(analyze_python(parsed))

    print("[3/8] Analyzing templates...")
    findings.extend(analyze_templates())

    print("[4/8] Analyzing static assets...")
    findings.extend(analyze_static_assets())

    print("[5/8] Detecting duplicate files...")
    findings.extend(analyze_duplicates())

    print("[6/8] Detecting backup and legacy files...")
    findings.extend(analyze_backup_files())

    print("[7/8] Detecting generated cache and large files...")
    findings.extend(analyze_cache_files())
    findings.extend(analyze_large_files())

    print("[8/8] Writing reports...")

    findings.sort(
        key=lambda item: (
            item.category,
            confidence_rank(item.confidence),
            item.path,
            item.line or 0,
        )
    )

    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    generated_at = now.isoformat(timespec="seconds")

    reports_dir = PROJECT_ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)

    markdown_path = reports_dir / f"unused_code_report_{timestamp}.md"
    json_path = reports_dir / f"unused_code_report_{timestamp}.json"

    markdown_path.write_text(
        create_markdown_report(findings, generated_at),
        encoding="utf-8",
    )

    json_path.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "project_root": str(PROJECT_ROOT),
                "report_only": True,
                "total_findings": len(findings),
                "findings": [asdict(item) for item in findings],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    categories: defaultdict[str, int] = defaultdict(int)
    for finding in findings:
        categories[finding.category] += 1

    print()
    print("=" * 64)
    print("ANALYSIS COMPLETE")
    print("=" * 64)

    for category in sorted(categories):
        print(f"{category}: {categories[category]}")

    print()
    print(f"Total findings: {len(findings)}")
    print(f"Markdown report: {relative(markdown_path)}")
    print(f"JSON report:     {relative(json_path)}")
    print()
    print("No project files were modified or deleted.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
