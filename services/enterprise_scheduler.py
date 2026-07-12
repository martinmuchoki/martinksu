from __future__ import annotations

import json
import subprocess
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from services.database import get_conn, init_db


PROJECT_DIR = Path(__file__).resolve().parent.parent
NAIROBI_TZ = ZoneInfo("Africa/Nairobi")

SCHEDULE_HOUR = 8
SCHEDULE_MINUTE = 10
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 60


def kenya_now() -> datetime:
    return datetime.now(NAIROBI_TZ)


def ensure_scheduler_table() -> None:
    init_db()
    conn = get_conn()

    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS enterprise_scheduler_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                kenya_date TEXT NOT NULL,
                task TEXT NOT NULL,
                status TEXT NOT NULL,
                attempt INTEGER DEFAULT 1,
                duration_seconds REAL DEFAULT 0,
                message TEXT,
                details_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_scheduler_runs_date
            ON enterprise_scheduler_runs(kenya_date)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_scheduler_runs_status
            ON enterprise_scheduler_runs(status)
            """
        )

        conn.commit()

    finally:
        conn.close()


def _json_safe(value: Any) -> str:
    try:
        return json.dumps(
            value,
            default=str,
            ensure_ascii=False,
        )
    except Exception:
        return json.dumps(
            {"value": str(value)},
            ensure_ascii=False,
        )


def _create_run(
    task: str,
    attempt: int,
) -> int:
    ensure_scheduler_table()

    now = kenya_now()
    conn = get_conn()

    try:
        cursor = conn.execute(
            """
            INSERT INTO enterprise_scheduler_runs (
                started_at,
                kenya_date,
                task,
                status,
                attempt
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                now.isoformat(),
                now.date().isoformat(),
                task,
                "RUNNING",
                attempt,
            ),
        )

        conn.commit()
        return int(cursor.lastrowid)

    finally:
        conn.close()


def _finish_run(
    run_id: int,
    status: str,
    started_monotonic: float,
    message: str,
    details: Any = None,
) -> None:
    finished = kenya_now()
    duration = round(
        time.monotonic() - started_monotonic,
        2,
    )

    conn = get_conn()

    try:
        conn.execute(
            """
            UPDATE enterprise_scheduler_runs
            SET
                finished_at = ?,
                status = ?,
                duration_seconds = ?,
                message = ?,
                details_json = ?
            WHERE id = ?
            """,
            (
                finished.isoformat(),
                status,
                duration,
                message,
                _json_safe(details),
                run_id,
            ),
        )

        conn.commit()

    finally:
        conn.close()


def _run_command(
    command: List[str],
    timeout: int = 900,
) -> Dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )

    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout[-6000:],
        "stderr": result.stderr[-6000:],
        "success": result.returncode == 0,
    }


def run_market_update() -> Dict[str, Any]:
    script = PROJECT_DIR / "daily_update.sh"

    if not script.exists():
        return {
            "success": False,
            "error": "daily_update.sh was not found",
        }

    return _run_command(
        ["/usr/bin/env", "bash", str(script)],
        timeout=900,
    )


def run_ai_scan() -> Dict[str, Any]:
    python = PROJECT_DIR / "venv/bin/python"
    scan = PROJECT_DIR / "run_daily_scan.py"

    if not python.exists():
        return {
            "success": False,
            "error": "Virtual environment Python was not found",
        }

    if not scan.exists():
        return {
            "success": False,
            "error": "run_daily_scan.py was not found",
        }

    return _run_command(
        [str(python), str(scan)],
        timeout=1200,
    )


def run_pdf_generation() -> Dict[str, Any]:
    try:
        from services.ai_committee import run_committee
        from services.autonomous_assistant import autonomous_decision
        from services.market_data import get_market_snapshot
        from services.portfolio import get_portfolio
        from services.reports import generate_daily_report
        from services.technical_analysis import analyze_market

        market = get_market_snapshot()
        technicals = analyze_market(
            market.get("stocks", [])
        )
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

        return {
            "success": True,
            "report": report,
        }

    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }


def run_enterprise_cycle() -> Dict[str, Any]:
    steps = []
    overall_success = True

    market_update = run_market_update()
    steps.append({
        "task": "market_update",
        **market_update,
    })

    if not market_update.get("success"):
        overall_success = False

    ai_scan = run_ai_scan()
    steps.append({
        "task": "ai_scan",
        **ai_scan,
    })

    if not ai_scan.get("success"):
        overall_success = False

    pdf = run_pdf_generation()
    steps.append({
        "task": "pdf_generation",
        **pdf,
    })

    if not pdf.get("success"):
        overall_success = False

    return {
        "success": overall_success,
        "kenya_time": kenya_now().isoformat(),
        "steps": steps,
    }


def run_with_tracking(
    attempt: int = 1,
) -> Dict[str, Any]:
    started = time.monotonic()
    run_id = _create_run(
        task="enterprise_daily_cycle",
        attempt=attempt,
    )

    try:
        result = run_enterprise_cycle()

        status = (
            "SUCCESS"
            if result.get("success")
            else "FAILED"
        )

        _finish_run(
            run_id,
            status,
            started,
            (
                "Enterprise daily cycle completed"
                if status == "SUCCESS"
                else "One or more scheduler steps failed"
            ),
            result,
        )

        return {
            "run_id": run_id,
            "status": status,
            **result,
        }

    except Exception as exc:
        details = {
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }

        _finish_run(
            run_id,
            "FAILED",
            started,
            str(exc),
            details,
        )

        return {
            "run_id": run_id,
            "status": "FAILED",
            "success": False,
            **details,
        }


def run_with_retries() -> Dict[str, Any]:
    attempts = []

    for attempt in range(1, MAX_RETRIES + 2):
        result = run_with_tracking(attempt)
        attempts.append(result)

        if result.get("success"):
            return {
                "success": True,
                "attempts": attempts,
                "final": result,
            }

        if attempt <= MAX_RETRIES:
            time.sleep(RETRY_DELAY_SECONDS)

    return {
        "success": False,
        "attempts": attempts,
        "final": attempts[-1],
    }


def next_scheduled_run(
    from_time: datetime | None = None,
) -> datetime:
    now = from_time or kenya_now()

    candidate = now.replace(
        hour=SCHEDULE_HOUR,
        minute=SCHEDULE_MINUTE,
        second=0,
        microsecond=0,
    )

    if candidate <= now:
        candidate += timedelta(days=1)

    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)

    return candidate


def get_recent_scheduler_runs(
    limit: int = 20,
) -> List[Dict[str, Any]]:
    ensure_scheduler_table()
    conn = get_conn()

    try:
        rows = conn.execute(
            """
            SELECT *
            FROM enterprise_scheduler_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(int(limit), 100)),),
        ).fetchall()

        results = []

        for row in rows:
            item = dict(row)

            try:
                item["details"] = json.loads(
                    item.pop("details_json") or "{}"
                )
            except json.JSONDecodeError:
                item["details"] = {}
                item.pop("details_json", None)

            results.append(item)

        return results

    finally:
        conn.close()


def get_scheduler_status() -> Dict[str, Any]:
    ensure_scheduler_table()

    runs = get_recent_scheduler_runs(20)
    last_run = runs[0] if runs else None
    next_run = next_scheduled_run()

    today = kenya_now().date().isoformat()

    today_runs = [
        item
        for item in runs
        if item.get("kenya_date") == today
    ]

    successful_today = sum(
        1
        for item in today_runs
        if item.get("status") == "SUCCESS"
    )

    return {
        "version": "11.6.2 Enterprise Scheduler",
        "status": (
            "ACTIVE"
            if last_run
            else "READY"
        ),
        "timezone": "Africa/Nairobi",
        "current_kenya_time":
            kenya_now().isoformat(),
        "schedule": "08:10 Monday-Friday",
        "next_run": next_run.isoformat(),
        "last_run": last_run,
        "today_runs": len(today_runs),
        "successful_today": successful_today,
        "max_retries": MAX_RETRIES,
        "retry_delay_seconds":
            RETRY_DELAY_SECONDS,
        "recent_runs": runs,
    }
