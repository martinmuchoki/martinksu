#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_DIR="/root/nse_signal_bot_v10_3"
TIMESTAMP="$(date +%Y-%m-%d_%H-%M-%S)"
BACKUP_DIR="$PROJECT_DIR/backups/v11_3_$TIMESTAMP"
LOG_FILE="$PROJECT_DIR/logs/upgrade_v11_3_$TIMESTAMP.log"

cd "$PROJECT_DIR"

mkdir -p "$BACKUP_DIR"
mkdir -p "$PROJECT_DIR/logs"

exec > >(tee -a "$LOG_FILE") 2>&1

echo "=================================================="
echo "NSE Signal Bot V11.3 Upgrade"
echo "Started: $(date)"
echo "Backup: $BACKUP_DIR"
echo "=================================================="

FILES_TO_BACKUP=(
    "app.py"
    "run_daily_scan.py"
    "templates/dashboard.html"
)

NEW_FILES=(
    "services/performance_engine.py"
    "services/portfolio_optimizer.py"
    "services/institutional_brief.py"
    "test_v11_3.py"
)

rollback() {
    echo
    echo "Upgrade failed. Starting rollback..."

    for file in "${FILES_TO_BACKUP[@]}"; do
        if [ -f "$BACKUP_DIR/$file" ]; then
            mkdir -p "$(dirname "$PROJECT_DIR/$file")"
            cp "$BACKUP_DIR/$file" "$PROJECT_DIR/$file"
            echo "Restored: $file"
        fi
    done

    for file in "${NEW_FILES[@]}"; do
        rm -f "$PROJECT_DIR/$file"
    done

    if [ -x "$PROJECT_DIR/restart.sh" ]; then
        "$PROJECT_DIR/restart.sh" || true
    fi

    echo "Rollback completed."
    exit 1
}

trap rollback ERR

echo
echo "Step 1: Creating backups..."

for file in "${FILES_TO_BACKUP[@]}"; do
    if [ ! -f "$PROJECT_DIR/$file" ]; then
        echo "Required file missing: $file"
        exit 1
    fi

    mkdir -p "$BACKUP_DIR/$(dirname "$file")"
    cp "$PROJECT_DIR/$file" "$BACKUP_DIR/$file"
    echo "Backed up: $file"
done

echo
echo "Step 2: Installing AI performance engine..."

cat > services/performance_engine.py <<'PY'
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.database import get_conn, init_db
from services.recommendation_tracker import ensure_recommendation_table


HORIZONS = (1, 5, 20, 60)


def ensure_performance_table() -> None:
    init_db()
    ensure_recommendation_table()

    conn = get_conn()

    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_recommendation_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recommendation_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                recommendation_date TEXT NOT NULL,
                horizon_days INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                evaluation_date TEXT NOT NULL,
                evaluation_price REAL NOT NULL,
                return_pct REAL NOT NULL,
                decision TEXT NOT NULL,
                successful INTEGER NOT NULL,
                evaluated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(recommendation_id, horizon_days)
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_ai_performance_symbol
            ON ai_recommendation_performance(symbol)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_ai_performance_horizon
            ON ai_recommendation_performance(horizon_days)
            """
        )

        conn.commit()

    finally:
        conn.close()


def _is_successful(decision: str, return_pct: float) -> bool:
    normalized = decision.upper().strip()

    if normalized in {"BUY", "STRONG BUY", "ACCUMULATE"}:
        return return_pct > 0

    if normalized in {"SELL", "STRONG SELL"}:
        return return_pct < 0

    if normalized in {"HOLD", "WATCH"}:
        return abs(return_pct) <= 3

    return return_pct >= 0


def _future_price(
    conn,
    symbol: str,
    recommendation_date: str,
    horizon: int,
) -> Optional[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT trade_date, close
        FROM price_history
        WHERE symbol = ?
          AND trade_date > ?
        ORDER BY trade_date ASC
        LIMIT ?
        """,
        (symbol, recommendation_date, horizon),
    ).fetchall()

    if len(rows) < horizon:
        return None

    row = rows[horizon - 1]

    return {
        "trade_date": row["trade_date"],
        "close": float(row["close"]),
    }


def evaluate_recommendations() -> Dict[str, Any]:
    ensure_performance_table()

    conn = get_conn()
    evaluated = 0
    pending = 0

    try:
        recommendations = conn.execute(
            """
            SELECT *
            FROM ai_recommendations
            ORDER BY recommendation_date ASC, id ASC
            """
        ).fetchall()

        for recommendation in recommendations:
            entry_price = float(recommendation["price"] or 0)

            if entry_price <= 0:
                continue

            for horizon in HORIZONS:
                existing = conn.execute(
                    """
                    SELECT id
                    FROM ai_recommendation_performance
                    WHERE recommendation_id = ?
                      AND horizon_days = ?
                    """,
                    (recommendation["id"], horizon),
                ).fetchone()

                if existing:
                    continue

                future = _future_price(
                    conn,
                    recommendation["symbol"],
                    recommendation["recommendation_date"],
                    horizon,
                )

                if not future:
                    pending += 1
                    continue

                return_pct = round(
                    (
                        (future["close"] - entry_price)
                        / entry_price
                    )
                    * 100,
                    4,
                )

                successful = int(
                    _is_successful(
                        recommendation["decision"],
                        return_pct,
                    )
                )

                conn.execute(
                    """
                    INSERT OR IGNORE INTO ai_recommendation_performance (
                        recommendation_id,
                        symbol,
                        recommendation_date,
                        horizon_days,
                        entry_price,
                        evaluation_date,
                        evaluation_price,
                        return_pct,
                        decision,
                        successful
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        recommendation["id"],
                        recommendation["symbol"],
                        recommendation["recommendation_date"],
                        horizon,
                        entry_price,
                        future["trade_date"],
                        future["close"],
                        return_pct,
                        recommendation["decision"],
                        successful,
                    ),
                )

                evaluated += 1

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return {
        "success": True,
        "evaluated": evaluated,
        "pending": pending,
    }


def get_performance_summary() -> Dict[str, Any]:
    ensure_performance_table()

    conn = get_conn()

    try:
        totals = conn.execute(
            """
            SELECT
                COUNT(*) AS evaluations,
                SUM(successful) AS successful,
                AVG(return_pct) AS average_return,
                MAX(return_pct) AS best_return,
                MIN(return_pct) AS worst_return
            FROM ai_recommendation_performance
            """
        ).fetchone()

        recommendation_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM ai_recommendations
            """
        ).fetchone()[0]

        best = conn.execute(
            """
            SELECT
                symbol,
                decision,
                horizon_days,
                entry_price,
                evaluation_price,
                return_pct
            FROM ai_recommendation_performance
            ORDER BY return_pct DESC
            LIMIT 1
            """
        ).fetchone()

        horizon_rows = conn.execute(
            """
            SELECT
                horizon_days,
                COUNT(*) AS evaluations,
                SUM(successful) AS successful,
                AVG(return_pct) AS average_return
            FROM ai_recommendation_performance
            GROUP BY horizon_days
            ORDER BY horizon_days
            """
        ).fetchall()

        decision_rows = conn.execute(
            """
            SELECT
                decision,
                COUNT(*) AS evaluations,
                SUM(successful) AS successful,
                AVG(return_pct) AS average_return
            FROM ai_recommendation_performance
            GROUP BY decision
            ORDER BY evaluations DESC
            """
        ).fetchall()

        evaluations = int(totals["evaluations"] or 0)
        successful = int(totals["successful"] or 0)

        accuracy = (
            round((successful / evaluations) * 100, 2)
            if evaluations
            else 0.0
        )

        return {
            "recommendations": int(recommendation_count or 0),
            "evaluations": evaluations,
            "successful": successful,
            "accuracy": accuracy,
            "average_return": round(
                float(totals["average_return"] or 0),
                2,
            ),
            "best_return": round(
                float(totals["best_return"] or 0),
                2,
            ),
            "worst_return": round(
                float(totals["worst_return"] or 0),
                2,
            ),
            "best_performer": dict(best) if best else None,
            "by_horizon": [dict(row) for row in horizon_rows],
            "by_decision": [dict(row) for row in decision_rows],
            "status": (
                "ACTIVE"
                if evaluations
                else "COLLECTING DATA"
            ),
        }

    finally:
        conn.close()


def get_recent_performance(
    limit: int = 50,
) -> List[Dict[str, Any]]:
    ensure_performance_table()

    conn = get_conn()

    try:
        rows = conn.execute(
            """
            SELECT *
            FROM ai_recommendation_performance
            ORDER BY evaluation_date DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()
PY

echo
echo "Step 3: Installing portfolio optimizer..."

cat > services/portfolio_optimizer.py <<'PY'
from __future__ import annotations

from typing import Any, Dict, List


RISK_MULTIPLIERS = {
    "LOW RISK": 1.0,
    "MODERATE RISK": 0.7,
    "HIGH RISK": 0.3,
}


def build_optimized_portfolio(
    screener_results: List[Dict[str, Any]],
    capital: float = 100_000,
    invested_percentage: float = 75,
    maximum_positions: int = 7,
) -> Dict[str, Any]:
    capital = max(0.0, float(capital or 0))
    investable_amount = capital * (invested_percentage / 100)
    cash_reserve = capital - investable_amount

    eligible = []

    for item in screener_results:
        confidence = int(item.get("confidence") or 0)
        price = float(item.get("price") or 0)
        decision = str(item.get("decision") or "").upper()
        risk = str(item.get("risk") or "MODERATE RISK")

        if price <= 0:
            continue

        if confidence < 60:
            continue

        if decision not in {"BUY", "STRONG BUY"}:
            continue

        multiplier = RISK_MULTIPLIERS.get(risk, 0.6)
        score = confidence * multiplier

        eligible.append(
            {
                **item,
                "optimizer_score": score,
            }
        )

    eligible.sort(
        key=lambda item: (
            item["optimizer_score"],
            item.get("volume", 0),
        ),
        reverse=True,
    )

    selected = eligible[:maximum_positions]

    if not selected:
        return {
            "capital": round(capital, 2),
            "investable_amount": 0.0,
            "cash_reserve": round(capital, 2),
            "invested_percentage": 0.0,
            "cash_percentage": 100.0,
            "positions": [],
            "position_count": 0,
            "risk_level": "CAPITAL PRESERVATION",
            "message": "No qualifying BUY opportunities are currently available.",
        }

    sector_usage: Dict[str, float] = {}
    raw_total = sum(
        item["optimizer_score"]
        for item in selected
    )

    positions = []

    for item in selected:
        raw_weight = (
            item["optimizer_score"] / raw_total
            if raw_total
            else 0
        )

        weight_pct = raw_weight * invested_percentage
        weight_pct = min(weight_pct, 20.0)

        sector = item.get("sector") or "Unknown"
        current_sector_weight = sector_usage.get(sector, 0.0)

        if current_sector_weight + weight_pct > 35:
            weight_pct = max(
                0,
                35 - current_sector_weight,
            )

        if weight_pct <= 0:
            continue

        sector_usage[sector] = (
            current_sector_weight + weight_pct
        )

        allocation_amount = capital * (weight_pct / 100)
        price = float(item["price"])
        estimated_shares = int(allocation_amount // price)

        positions.append(
            {
                "symbol": item["symbol"],
                "name": item.get("name"),
                "sector": sector,
                "decision": item.get("decision"),
                "confidence": item.get("confidence"),
                "risk": item.get("risk"),
                "price": round(price, 2),
                "weight_pct": round(weight_pct, 2),
                "allocation_amount": round(
                    allocation_amount,
                    2,
                ),
                "estimated_shares": estimated_shares,
            }
        )

    actual_invested_pct = round(
        sum(position["weight_pct"] for position in positions),
        2,
    )

    actual_invested_amount = round(
        capital * actual_invested_pct / 100,
        2,
    )

    actual_cash = round(
        capital - actual_invested_amount,
        2,
    )

    average_confidence = (
        round(
            sum(
                float(position["confidence"] or 0)
                for position in positions
            )
            / len(positions),
            2,
        )
        if positions
        else 0
    )

    high_risk_count = sum(
        1
        for position in positions
        if position["risk"] == "HIGH RISK"
    )

    if high_risk_count:
        risk_level = "HIGH"
    elif any(
        position["risk"] == "MODERATE RISK"
        for position in positions
    ):
        risk_level = "MODERATE"
    else:
        risk_level = "LOW"

    return {
        "capital": round(capital, 2),
        "investable_amount": actual_invested_amount,
        "cash_reserve": actual_cash,
        "invested_percentage": actual_invested_pct,
        "cash_percentage": round(
            100 - actual_invested_pct,
            2,
        ),
        "positions": positions,
        "position_count": len(positions),
        "average_confidence": average_confidence,
        "risk_level": risk_level,
        "sector_exposure": sector_usage,
        "message": (
            "Allocation prioritizes high-confidence BUY signals, "
            "liquidity, risk control and sector diversification."
        ),
    }
PY

echo
echo "Step 4: Installing institutional Telegram brief..."

cat > services/institutional_brief.py <<'PY'
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from services.telegram_bot import send_telegram_alert


NAIROBI_TZ = ZoneInfo("Africa/Nairobi")


def build_institutional_brief(
    market: Dict[str, Any],
    screener: List[Dict[str, Any]],
    performance: Dict[str, Any],
    optimizer: Dict[str, Any],
) -> str:
    now = datetime.now(NAIROBI_TZ)

    lines = [
        "NSE Signal Bot V11.3",
        "",
        f"Market: {market.get('market_status', 'Unknown')}",
        f"Average change: {market.get('average_change', 0)}%",
        f"Securities: {len(market.get('stocks', []))}",
        "",
        "Top Opportunities",
    ]

    for index, item in enumerate(screener[:5], start=1):
        lines.append(
            f"{index}. {item.get('symbol')} "
            f"{item.get('decision')} "
            f"{item.get('confidence')}% "
            f"@ KSh {item.get('price')}"
        )

    lines.extend(
        [
            "",
            "AI Performance",
            f"Recommendations: {performance.get('recommendations', 0)}",
            f"Accuracy: {performance.get('accuracy', 0)}%",
            f"Average return: {performance.get('average_return', 0)}%",
            "",
            "Portfolio Optimizer",
            f"Positions: {optimizer.get('position_count', 0)}",
            f"Invested: {optimizer.get('invested_percentage', 0)}%",
            f"Cash: {optimizer.get('cash_percentage', 100)}%",
            f"Risk: {optimizer.get('risk_level', 'Unknown')}",
            "",
            f"Generated: {now.strftime('%Y-%m-%d %H:%M EAT')}",
        ]
    )

    return "\n".join(lines)


def send_institutional_brief(
    market: Dict[str, Any],
    screener: List[Dict[str, Any]],
    performance: Dict[str, Any],
    optimizer: Dict[str, Any],
) -> Dict[str, Any]:
    message = build_institutional_brief(
        market,
        screener,
        performance,
        optimizer,
    )

    result = send_telegram_alert(message)

    return {
        **result,
        "message_preview": message[:500],
    }
PY

echo
echo "Step 5: Updating daily scan..."

cat > run_daily_scan.py <<'PY'
from __future__ import annotations

from pprint import pprint

from services.institutional_brief import send_institutional_brief
from services.market_data import get_market_snapshot
from services.performance_engine import (
    evaluate_recommendations,
    get_performance_summary,
)
from services.portfolio_optimizer import build_optimized_portfolio
from services.recommendation_tracker import save_recommendations
from services.scheduler_engine import run_daily_automation
from services.screener_engine import run_screener


def run_v113_daily_scan():
    automation = run_daily_automation()

    market = get_market_snapshot()
    screener = run_screener()

    tracking = save_recommendations(screener)
    evaluation = evaluate_recommendations()
    performance = get_performance_summary()

    optimizer = build_optimized_portfolio(
        screener,
        capital=100_000,
    )

    telegram = send_institutional_brief(
        market,
        screener,
        performance,
        optimizer,
    )

    return {
        "version": "11.3",
        "automation": automation,
        "market_status": market.get("market_status"),
        "ranked_results": len(screener),
        "tracking": tracking,
        "evaluation": evaluation,
        "performance": performance,
        "optimizer": optimizer,
        "telegram": telegram,
    }


if __name__ == "__main__":
    pprint(run_v113_daily_scan())
PY

echo
echo "Step 6: Updating Flask application..."

python - <<'PY'
from pathlib import Path

path = Path("app.py")
text = path.read_text(encoding="utf-8")

imports_anchor = (
    "from services.screener_engine import run_screener\n"
)

new_imports = """from services.screener_engine import run_screener
from services.performance_engine import (
    evaluate_recommendations,
    get_performance_summary,
    get_recent_performance,
)
from services.portfolio_optimizer import build_optimized_portfolio
"""

if "from services.performance_engine import" not in text:
    if imports_anchor not in text:
        raise SystemExit("Unable to find app import anchor.")

    text = text.replace(
        imports_anchor,
        new_imports,
        1,
    )

text = text.replace(
    'VERSION = "11.2 Professional Market Intelligence"',
    'VERSION = "11.3 Institutional AI"',
)

cash_anchor = "    cash_summary = get_cash_summary()\n"

dashboard_addition = """    cash_summary = get_cash_summary()

    evaluate_recommendations()
    performance = get_performance_summary()

    optimizer_capital = max(
        float(cash_summary.get("cash_balance", 0) or 0),
        100000,
    )

    optimized_portfolio = build_optimized_portfolio(
        screener,
        capital=optimizer_capital,
    )
"""

if "optimized_portfolio = build_optimized_portfolio" not in text:
    if cash_anchor not in text:
        raise SystemExit("Unable to find cash summary anchor.")

    text = text.replace(
        cash_anchor,
        dashboard_addition,
        1,
    )

context_anchor = "        cash_summary=cash_summary,\n"

context_addition = """        cash_summary=cash_summary,
        performance=performance,
        optimized_portfolio=optimized_portfolio,
"""

if "performance=performance" not in text:
    if context_anchor not in text:
        raise SystemExit("Unable to find dashboard context anchor.")

    text = text.replace(
        context_anchor,
        context_addition,
        1,
    )

routes = '''

@app.route("/api/v11.3/performance")
def v113_performance():
    evaluate_recommendations()

    return jsonify({
        "summary": get_performance_summary(),
        "recent": get_recent_performance(100),
    })


@app.route("/api/v11.3/optimizer")
def v113_optimizer():
    results = run_screener()
    capital = request.args.get("capital", default=100000, type=float)

    return jsonify(
        build_optimized_portfolio(
            results,
            capital=capital,
        )
    )


'''

if '@app.route("/api/v11.3/performance")' not in text:
    marker = '\nif __name__ == "__main__":\n'

    if marker not in text:
        raise SystemExit("Unable to find application route marker.")

    text = text.replace(
        marker,
        routes + marker,
        1,
    )

path.write_text(text, encoding="utf-8")
print("Updated app.py")
PY

echo
echo "Step 7: Updating dashboard template..."

python - <<'PY'
from pathlib import Path

path = Path("templates/dashboard.html")
text = path.read_text(encoding="utf-8")

text = text.replace(
    "<title>NSE Signal Bot V11.4</title>",
    "<title>NSE Signal Bot V11.3</title>",
)

text = text.replace(
    "<h1>NSE Signal Bot V11.4</h1>",
    "<h1>NSE Signal Bot V11.3</h1>",
)

panel = '''
<section class="dashboard-panel">
    <div class="panel-heading">
        <div>
            <p class="eyebrow">Self-evaluating intelligence</p>
            <h2>AI Performance Analytics</h2>
        </div>

        <span class="risk-badge">
            {{ performance.status }}
        </span>
    </div>

    <div class="portfolio-metrics">
        <div>
            <span>Recommendations</span>
            <strong>{{ performance.recommendations }}</strong>
        </div>

        <div>
            <span>Evaluations</span>
            <strong>{{ performance.evaluations }}</strong>
        </div>

        <div>
            <span>AI Accuracy</span>
            <strong>{{ performance.accuracy }}%</strong>
        </div>

        <div>
            <span>Average Return</span>
            <strong class="{% if performance.average_return >= 0 %}positive{% else %}negative{% endif %}">
                {{ performance.average_return }}%
            </strong>
        </div>
    </div>

    {% if performance.best_performer %}
    <p class="recommendation-box">
        <strong>Best performer:</strong>
        {{ performance.best_performer.symbol }}
        · {{ performance.best_performer.return_pct }}%
        after {{ performance.best_performer.horizon_days }} trading days
    </p>
    {% else %}
    <p class="recommendation-box">
        Performance evaluation will begin when future trading-day
        prices become available.
    </p>
    {% endif %}
</section>

<section class="dashboard-panel">
    <div class="panel-heading">
        <div>
            <p class="eyebrow">Capital allocation</p>
            <h2>Institutional Portfolio Optimizer</h2>
        </div>

        <span class="risk-badge">
            {{ optimized_portfolio.risk_level }} RISK
        </span>
    </div>

    <div class="portfolio-metrics">
        <div>
            <span>Recommended positions</span>
            <strong>{{ optimized_portfolio.position_count }}</strong>
        </div>

        <div>
            <span>Invested allocation</span>
            <strong>{{ optimized_portfolio.invested_percentage }}%</strong>
        </div>

        <div>
            <span>Cash reserve</span>
            <strong>{{ optimized_portfolio.cash_percentage }}%</strong>
        </div>

        <div>
            <span>Average confidence</span>
            <strong>{{ optimized_portfolio.average_confidence|default(0) }}%</strong>
        </div>
    </div>

    {% if optimized_portfolio.positions %}
    <div class="table-wrapper">
        <table class="dashboard-table compact-table">
            <thead>
                <tr>
                    <th>Symbol</th>
                    <th>Decision</th>
                    <th>Confidence</th>
                    <th>Risk</th>
                    <th>Allocation</th>
                    <th>Amount</th>
                    <th>Shares</th>
                </tr>
            </thead>

            <tbody>
                {% for item in optimized_portfolio.positions %}
                <tr>
                    <td>
                        <a class="symbol-link" href="/stocks/{{ item.symbol }}">
                            {{ item.symbol }}
                        </a>
                    </td>
                    <td>{{ item.decision }}</td>
                    <td>{{ item.confidence }}%</td>
                    <td>{{ item.risk }}</td>
                    <td>{{ item.weight_pct }}%</td>
                    <td>KSh {{ "{:,.2f}".format(item.allocation_amount) }}</td>
                    <td>{{ item.estimated_shares }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% else %}
    <p class="recommendation-box">
        {{ optimized_portfolio.message }}
    </p>
    {% endif %}
</section>

'''

if "AI Performance Analytics" not in text:
    marker = '<section class="dashboard-panel cash-summary-panel">'

    if marker not in text:
        raise SystemExit("Unable to find dashboard insertion point.")

    text = text.replace(
        marker,
        panel + marker,
        1,
    )

path.write_text(text, encoding="utf-8")
print("Updated templates/dashboard.html")
PY

echo
echo "Step 8: Creating V11.3 test suite..."

cat > test_v11_3.py <<'PY'
from services.market_data import get_market_snapshot
from services.performance_engine import (
    evaluate_recommendations,
    get_performance_summary,
)
from services.portfolio_optimizer import build_optimized_portfolio
from services.recommendation_tracker import save_recommendations
from services.screener_engine import run_screener


def main() -> None:
    market = get_market_snapshot()
    screener = run_screener()

    assert market.get("stocks"), "No market stocks returned"
    assert screener, "Screener returned no results"

    tracking = save_recommendations(screener)
    evaluation = evaluate_recommendations()
    performance = get_performance_summary()

    optimizer = build_optimized_portfolio(
        screener,
        capital=100_000,
    )

    assert tracking["saved"] > 0
    assert performance["recommendations"] > 0
    assert "positions" in optimizer

    print("V11.3 TEST PASSED")
    print("Market stocks:", len(market["stocks"]))
    print("Screener results:", len(screener))
    print("Recommendations:", performance["recommendations"])
    print("Evaluations:", performance["evaluations"])
    print("Optimizer positions:", optimizer["position_count"])
    print("Evaluation update:", evaluation)


if __name__ == "__main__":
    main()
PY

echo
echo "Step 9: Initializing V11.3 database tables..."

"$PROJECT_DIR/venv/bin/python" - <<'PY'
from services.performance_engine import (
    ensure_performance_table,
    evaluate_recommendations,
)
from services.recommendation_tracker import ensure_recommendation_table

ensure_recommendation_table()
ensure_performance_table()

print(evaluate_recommendations())
print("Database migration completed.")
PY

echo
echo "Step 10: Running syntax checks..."

"$PROJECT_DIR/venv/bin/python" -m py_compile \
    app.py \
    run_daily_scan.py \
    test_v11_3.py \
    services/*.py

echo "Syntax checks passed."

echo
echo "Step 11: Running V11.3 tests..."

"$PROJECT_DIR/venv/bin/python" test_v11_3.py

echo
echo "Step 12: Restarting NSE Signal Bot..."

"$PROJECT_DIR/restart.sh"

echo
echo "Step 13: Verifying health endpoint..."

HEALTH_RESPONSE="$(
    curl -fsS http://127.0.0.1:5000/health
)"

echo "$HEALTH_RESPONSE"

if ! echo "$HEALTH_RESPONSE" | grep -q "online"; then
    echo "Health check failed."
    exit 1
fi

trap - ERR

echo
echo "=================================================="
echo "NSE Signal Bot V11.3 upgrade completed."
echo "Backup directory: $BACKUP_DIR"
echo "Log file: $LOG_FILE"
echo "=================================================="
