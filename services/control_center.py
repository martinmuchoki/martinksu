from __future__ import annotations

import os
import platform
import shutil
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from services.database import DB_PATH, get_conn
from services.learning_engine import get_learning_summary
from services.enterprise_scheduler import get_scheduler_status


PROJECT_DIR = Path(__file__).resolve().parent.parent
REPORT_DIR = PROJECT_DIR / "reports"
BACKUP_DIR = PROJECT_DIR / "backups"
LOG_DIR = PROJECT_DIR / "logs"

PDF_REPORT = (
    REPORT_DIR
    / "MIP_PRO_Daily_Intelligence_Report_v11_5_Production.pdf"
)

BOOT_TIME_FILE = Path("/proc/uptime")


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _format_bytes(size: int) -> str:
    value = float(max(0, size))

    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.2f} {unit}"

        value /= 1024

    return f"{value:.2f} TB"


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))

    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []

    if days:
        parts.append(f"{days}d")

    if hours or days:
        parts.append(f"{hours}h")

    if minutes or hours or days:
        parts.append(f"{minutes}m")

    parts.append(f"{seconds}s")

    return " ".join(parts)


def _server_uptime_seconds() -> float:
    try:
        value = BOOT_TIME_FILE.read_text(
            encoding="utf-8"
        ).split()[0]

        return float(value)

    except (OSError, ValueError, IndexError):
        return 0.0


def _memory_status() -> Dict[str, Any]:
    total_kb = 0
    available_kb = 0

    try:
        values = {}

        for line in Path("/proc/meminfo").read_text(
            encoding="utf-8"
        ).splitlines():
            key, raw = line.split(":", 1)
            values[key] = int(raw.strip().split()[0])

        total_kb = values.get("MemTotal", 0)
        available_kb = values.get("MemAvailable", 0)

    except (OSError, ValueError, IndexError):
        pass

    used_kb = max(0, total_kb - available_kb)

    usage_pct = (
        round((used_kb / total_kb) * 100, 2)
        if total_kb
        else 0.0
    )

    return {
        "total_bytes": total_kb * 1024,
        "used_bytes": used_kb * 1024,
        "available_bytes": available_kb * 1024,
        "total": _format_bytes(total_kb * 1024),
        "used": _format_bytes(used_kb * 1024),
        "available": _format_bytes(
            available_kb * 1024
        ),
        "usage_pct": usage_pct,
    }


def _cpu_status() -> Dict[str, Any]:
    load_1 = 0.0
    load_5 = 0.0
    load_15 = 0.0

    try:
        load_1, load_5, load_15 = os.getloadavg()
    except (AttributeError, OSError):
        pass

    cpu_count = os.cpu_count() or 1

    estimated_usage = min(
        100.0,
        round((load_1 / cpu_count) * 100, 2),
    )

    return {
        "cores": cpu_count,
        "load_1": round(load_1, 2),
        "load_5": round(load_5, 2),
        "load_15": round(load_15, 2),
        "estimated_usage_pct": estimated_usage,
    }


def _disk_status() -> Dict[str, Any]:
    usage = shutil.disk_usage(PROJECT_DIR)

    used = usage.total - usage.free

    usage_pct = (
        round((used / usage.total) * 100, 2)
        if usage.total
        else 0.0
    )

    return {
        "total_bytes": usage.total,
        "used_bytes": used,
        "free_bytes": usage.free,
        "total": _format_bytes(usage.total),
        "used": _format_bytes(used),
        "free": _format_bytes(usage.free),
        "usage_pct": usage_pct,
    }


def _latest_file(
    directory: Path,
    pattern: str = "*",
) -> Optional[Path]:
    if not directory.exists():
        return None

    files = [
        path
        for path in directory.glob(pattern)
        if path.is_file()
    ]

    if not files:
        return None

    return max(
        files,
        key=lambda path: path.stat().st_mtime,
    )


def _file_info(path: Optional[Path]) -> Dict[str, Any]:
    if not path or not path.exists():
        return {
            "available": False,
            "name": None,
            "path": None,
            "size": "0 B",
            "modified_at": None,
        }

    modified = datetime.fromtimestamp(
        path.stat().st_mtime
    ).strftime("%Y-%m-%d %H:%M:%S")

    return {
        "available": True,
        "name": path.name,
        "path": str(path),
        "size": _format_bytes(_safe_size(path)),
        "modified_at": modified,
    }


def _database_status() -> Dict[str, Any]:
    status = {
        "available": DB_PATH.exists(),
        "path": str(DB_PATH),
        "size": _format_bytes(_safe_size(DB_PATH)),
        "tables": 0,
        "stocks": 0,
        "price_history": 0,
        "recommendations": 0,
        "evaluations": 0,
        "portfolio_holdings": 0,
        "integrity": "UNKNOWN",
    }

    if not DB_PATH.exists():
        return status

    conn = get_conn()

    try:
        tables = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()

        status["tables"] = len(tables)

        table_names = {
            row["name"]
            for row in tables
        }

        count_map = {
            "stocks": "stocks",
            "price_history": "price_history",
            "recommendations": "ai_recommendations",
            "evaluations":
                "ai_recommendation_performance",
            "portfolio_holdings": "portfolio",
        }

        for key, table in count_map.items():
            if table not in table_names:
                continue

            status[key] = conn.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0]

        integrity = conn.execute(
            "PRAGMA quick_check"
        ).fetchone()[0]

        status["integrity"] = str(
            integrity
        ).upper()

    except sqlite3.Error as exc:
        status["integrity"] = f"ERROR: {exc}"

    finally:
        conn.close()

    return status


def _telegram_status() -> Dict[str, Any]:
    token = (
        os.getenv("TELEGRAM_BOT_TOKEN")
        or os.getenv("BOT_TOKEN")
    )

    chat_id = (
        os.getenv("TELEGRAM_CHAT_ID")
        or os.getenv("CHAT_ID")
    )

    configured = bool(token and chat_id)

    return {
        "configured": configured,
        "token_present": bool(token),
        "chat_id_present": bool(chat_id),
        "status": (
            "CONFIGURED"
            if configured
            else "CHECK CONFIGURATION"
        ),
    }


def get_control_center_status() -> Dict[str, Any]:
    learning = get_learning_summary(
        evaluate_first=False
    )

    latest_backup = _latest_file(
        BACKUP_DIR,
        "*.tar.gz",
    )

    if latest_backup is None:
        latest_backup = _latest_file(BACKUP_DIR)

    latest_log = _latest_file(LOG_DIR, "*.log")

    report = (
        PDF_REPORT
        if PDF_REPORT.exists()
        else _latest_file(REPORT_DIR, "*.pdf")
    )

    uptime_seconds = _server_uptime_seconds()

    return {
        "generated_at": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "application": {
            "service": "MIP PRO",
            "version":
                "11.6.2 Enterprise Scheduler",
            "status": "ONLINE",
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "process_id": os.getpid(),
        },
        "server": {
            "hostname": platform.node(),
            "uptime_seconds": uptime_seconds,
            "uptime": _format_duration(
                uptime_seconds
            ),
            "cpu": _cpu_status(),
            "memory": _memory_status(),
            "disk": _disk_status(),
        },
        "database": _database_status(),
        "learning": learning,
        "scheduler": get_scheduler_status(),
        "telegram": _telegram_status(),
        "pdf": _file_info(report),
        "backup": _file_info(latest_backup),
        "latest_log": _file_info(latest_log),
    }
