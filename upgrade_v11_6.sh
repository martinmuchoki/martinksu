#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT="/root/nse_signal_bot_v10_3"
STAMP="$(date +%Y-%m-%d_%H-%M-%S)"
BACKUP="$PROJECT/backups/v11_6_enterprise_$STAMP"
LOG="$PROJECT/logs/v11_6_enterprise_$STAMP.log"

cd "$PROJECT"

mkdir -p \
    "$BACKUP/services" \
    "$BACKUP/templates" \
    "$BACKUP/static/css" \
    "$PROJECT/logs"

exec > >(tee -a "$LOG") 2>&1

rollback() {
    echo
    echo "V11.6 installation failed. Restoring V11.5 Production..."

    [ -f "$BACKUP/app.py" ] &&
        cp "$BACKUP/app.py" "$PROJECT/app.py"

    [ -f "$BACKUP/templates/dashboard_v115.html" ] &&
        cp "$BACKUP/templates/dashboard_v115.html" \
           "$PROJECT/templates/dashboard_v115.html"

    [ -f "$BACKUP/static/css/v115.css" ] &&
        cp "$BACKUP/static/css/v115.css" \
           "$PROJECT/static/css/v115.css"

    if [ -f "$BACKUP/services/learning_engine.py" ]; then
        cp "$BACKUP/services/learning_engine.py" \
           "$PROJECT/services/learning_engine.py"
    else
        rm -f "$PROJECT/services/learning_engine.py"
    fi

    ./restart.sh || true
    echo "Rollback complete."
    exit 1
}

trap rollback ERR

echo "=============================================="
echo " MIP PRO V11.6 Enterprise Intelligence"
echo "=============================================="

echo
echo "[1/6] Creating backup..."

cp app.py "$BACKUP/app.py"

cp templates/dashboard_v115.html \
   "$BACKUP/templates/dashboard_v115.html"

cp static/css/v115.css \
   "$BACKUP/static/css/v115.css"

[ -f services/learning_engine.py ] &&
    cp services/learning_engine.py \
       "$BACKUP/services/learning_engine.py"

echo "Backup completed:"
echo "$BACKUP"

echo
echo "[2/6] Installing AI Learning Engine..."

cat > services/learning_engine.py <<'PY'
from __future__ import annotations

from math import log10
from typing import Any, Dict, List

from services.database import get_conn
from services.performance_engine import (
    ensure_performance_table,
    evaluate_recommendations,
    get_performance_summary,
)

MIN_SAMPLE_FOR_ACTIVE = 20


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _accuracy(successful: Any, evaluations: Any) -> float:
    evaluations = _safe_int(evaluations)

    if evaluations <= 0:
        return 0.0

    return round(
        (_safe_int(successful) / evaluations) * 100,
        2,
    )


def _confidence_adjustment(
    accuracy: float,
    evaluations: int,
) -> float:
    if evaluations <= 0:
        return 0.0

    sample_strength = min(
        1.0,
        log10(evaluations + 1) / log10(101),
    )

    raw_adjustment = (accuracy - 50.0) * 0.20
    adjusted = raw_adjustment * sample_strength

    return round(
        max(-8.0, min(8.0, adjusted)),
        2,
    )


def apply_adaptive_confidence(
    confidence: Any,
    learning_summary: Dict[str, Any] | None = None,
) -> int:
    summary = learning_summary or get_learning_summary(
        evaluate_first=False
    )

    updated = round(
        _safe_float(confidence)
        + _safe_float(summary.get("confidence_adjustment"))
    )

    return max(0, min(100, updated))


def _group_rows(
    query: str,
    parameters: tuple = (),
) -> List[Dict[str, Any]]:
    conn = get_conn()

    try:
        rows = conn.execute(
            query,
            parameters,
        ).fetchall()

        result = []

        for row in rows:
            item = dict(row)

            evaluations = _safe_int(
                item.get("evaluations")
            )

            successful = _safe_int(
                item.get("successful")
            )

            item["evaluations"] = evaluations
            item["successful"] = successful
            item["accuracy"] = _accuracy(
                successful,
                evaluations,
            )

            item["average_return"] = round(
                _safe_float(item.get("average_return")),
                2,
            )

            result.append(item)

        return result

    finally:
        conn.close()


def get_learning_by_horizon() -> List[Dict[str, Any]]:
    ensure_performance_table()

    return _group_rows(
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
    )


def get_learning_by_decision() -> List[Dict[str, Any]]:
    ensure_performance_table()

    return _group_rows(
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
    )


def get_learning_by_sector() -> List[Dict[str, Any]]:
    ensure_performance_table()

    return _group_rows(
        """
        SELECT
            COALESCE(s.sector, 'Unknown') AS sector,
            COUNT(*) AS evaluations,
            SUM(p.successful) AS successful,
            AVG(p.return_pct) AS average_return
        FROM ai_recommendation_performance AS p
        LEFT JOIN stocks AS s
            ON s.symbol = p.symbol
        GROUP BY COALESCE(s.sector, 'Unknown')
        ORDER BY average_return DESC, evaluations DESC
        """
    )


def get_learning_summary(
    evaluate_first: bool = True,
) -> Dict[str, Any]:
    ensure_performance_table()

    if evaluate_first:
        evaluation_update = evaluate_recommendations()
    else:
        evaluation_update = {
            "success": True,
            "evaluated": 0,
            "pending": 0,
        }

    performance = get_performance_summary()

    evaluations = _safe_int(
        performance.get("evaluations")
    )

    accuracy = _safe_float(
        performance.get("accuracy")
    )

    average_return = _safe_float(
        performance.get("average_return")
    )

    by_horizon = get_learning_by_horizon()
    by_decision = get_learning_by_decision()
    by_sector = get_learning_by_sector()

    best_horizon = max(
        by_horizon,
        key=lambda item: (
            item.get("accuracy", 0),
            item.get("average_return", 0),
        ),
        default=None,
    )

    best_decision = max(
        by_decision,
        key=lambda item: (
            item.get("accuracy", 0),
            item.get("average_return", 0),
        ),
        default=None,
    )

    best_sector = max(
        by_sector,
        key=lambda item: (
            item.get("accuracy", 0),
            item.get("average_return", 0),
        ),
        default=None,
    )

    confidence_adjustment = _confidence_adjustment(
        accuracy,
        evaluations,
    )

    sample_progress = min(
        100.0,
        round(
            (evaluations / MIN_SAMPLE_FOR_ACTIVE) * 100,
            2,
        ),
    )

    if evaluations <= 0:
        learning_score = 0.0
        status = "COLLECTING DATA"
    else:
        return_component = max(
            0.0,
            min(
                100.0,
                50.0 + average_return * 2.5,
            ),
        )

        sample_component = min(
            100.0,
            evaluations
            / MIN_SAMPLE_FOR_ACTIVE
            * 100,
        )

        learning_score = round(
            accuracy * 0.60
            + return_component * 0.25
            + sample_component * 0.15,
            2,
        )

        status = (
            "ACTIVE"
            if evaluations >= MIN_SAMPLE_FOR_ACTIVE
            else "EARLY LEARNING"
        )

    return {
        "version": "11.6 Enterprise Intelligence",
        "status": status,
        "learning_score": learning_score,
        "recommendations": _safe_int(
            performance.get("recommendations")
        ),
        "evaluations": evaluations,
        "successful": _safe_int(
            performance.get("successful")
        ),
        "accuracy": round(accuracy, 2),
        "average_return": round(
            average_return,
            2,
        ),
        "best_return": round(
            _safe_float(
                performance.get("best_return")
            ),
            2,
        ),
        "worst_return": round(
            _safe_float(
                performance.get("worst_return")
            ),
            2,
        ),
        "confidence_adjustment":
            confidence_adjustment,
        "sample_progress_pct":
            sample_progress,
        "minimum_active_sample":
            MIN_SAMPLE_FOR_ACTIVE,
        "best_horizon": best_horizon,
        "best_decision": best_decision,
        "best_sector": best_sector,
        "by_horizon": by_horizon,
        "by_decision": by_decision,
        "by_sector": by_sector,
        "evaluation_update": evaluation_update,
    }
PY

echo "AI Learning Engine installed."


echo
echo "[2/6] Installing AI Learning Engine..."

cat > services/learning_engine.py <<'PY'
from __future__ import annotations

from math import log10
from typing import Any, Dict, List

from services.database import get_conn
from services.performance_engine import (
    ensure_performance_table,
    evaluate_recommendations,
    get_performance_summary,
)

MIN_SAMPLE_FOR_ACTIVE = 20


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _accuracy(successful: Any, evaluations: Any) -> float:
    evaluations = _safe_int(evaluations)

    if evaluations <= 0:
        return 0.0

    return round(
        (_safe_int(successful) / evaluations) * 100,
        2,
    )


def _confidence_adjustment(
    accuracy: float,
    evaluations: int,
) -> float:
    if evaluations <= 0:
        return 0.0

    sample_strength = min(
        1.0,
        log10(evaluations + 1) / log10(101),
    )

    raw_adjustment = (accuracy - 50.0) * 0.20
    adjusted = raw_adjustment * sample_strength

    return round(
        max(-8.0, min(8.0, adjusted)),
        2,
    )


def apply_adaptive_confidence(
    confidence: Any,
    learning_summary: Dict[str, Any] | None = None,
) -> int:
    summary = learning_summary or get_learning_summary(
        evaluate_first=False
    )

    updated = round(
        _safe_float(confidence)
        + _safe_float(summary.get("confidence_adjustment"))
    )

    return max(0, min(100, updated))


def _group_rows(
    query: str,
    parameters: tuple = (),
) -> List[Dict[str, Any]]:
    conn = get_conn()

    try:
        rows = conn.execute(
            query,
            parameters,
        ).fetchall()

        result = []

        for row in rows:
            item = dict(row)

            evaluations = _safe_int(
                item.get("evaluations")
            )

            successful = _safe_int(
                item.get("successful")
            )

            item["evaluations"] = evaluations
            item["successful"] = successful
            item["accuracy"] = _accuracy(
                successful,
                evaluations,
            )

            item["average_return"] = round(
                _safe_float(item.get("average_return")),
                2,
            )

            result.append(item)

        return result

    finally:
        conn.close()


def get_learning_by_horizon() -> List[Dict[str, Any]]:
    ensure_performance_table()

    return _group_rows(
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
    )


def get_learning_by_decision() -> List[Dict[str, Any]]:
    ensure_performance_table()

    return _group_rows(
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
    )


def get_learning_by_sector() -> List[Dict[str, Any]]:
    ensure_performance_table()

    return _group_rows(
        """
        SELECT
            COALESCE(s.sector, 'Unknown') AS sector,
            COUNT(*) AS evaluations,
            SUM(p.successful) AS successful,
            AVG(p.return_pct) AS average_return
        FROM ai_recommendation_performance AS p
        LEFT JOIN stocks AS s
            ON s.symbol = p.symbol
        GROUP BY COALESCE(s.sector, 'Unknown')
        ORDER BY average_return DESC, evaluations DESC
        """
    )


def get_learning_summary(
    evaluate_first: bool = True,
) -> Dict[str, Any]:
    ensure_performance_table()

    if evaluate_first:
        evaluation_update = evaluate_recommendations()
    else:
        evaluation_update = {
            "success": True,
            "evaluated": 0,
            "pending": 0,
        }

    performance = get_performance_summary()

    evaluations = _safe_int(
        performance.get("evaluations")
    )

    accuracy = _safe_float(
        performance.get("accuracy")
    )

    average_return = _safe_float(
        performance.get("average_return")
    )

    by_horizon = get_learning_by_horizon()
    by_decision = get_learning_by_decision()
    by_sector = get_learning_by_sector()

    best_horizon = max(
        by_horizon,
        key=lambda item: (
            item.get("accuracy", 0),
            item.get("average_return", 0),
        ),
        default=None,
    )

    best_decision = max(
        by_decision,
        key=lambda item: (
            item.get("accuracy", 0),
            item.get("average_return", 0),
        ),
        default=None,
    )

    best_sector = max(
        by_sector,
        key=lambda item: (
            item.get("accuracy", 0),
            item.get("average_return", 0),
        ),
        default=None,
    )

    confidence_adjustment = _confidence_adjustment(
        accuracy,
        evaluations,
    )

    sample_progress = min(
        100.0,
        round(
            (evaluations / MIN_SAMPLE_FOR_ACTIVE) * 100,
            2,
        ),
    )

    if evaluations <= 0:
        learning_score = 0.0
        status = "COLLECTING DATA"
    else:
        return_component = max(
            0.0,
            min(
                100.0,
                50.0 + average_return * 2.5,
            ),
        )

        sample_component = min(
            100.0,
            evaluations
            / MIN_SAMPLE_FOR_ACTIVE
            * 100,
        )

        learning_score = round(
            accuracy * 0.60
            + return_component * 0.25
            + sample_component * 0.15,
            2,
        )

        status = (
            "ACTIVE"
            if evaluations >= MIN_SAMPLE_FOR_ACTIVE
            else "EARLY LEARNING"
        )

    return {
        "version": "11.6 Enterprise Intelligence",
        "status": status,
        "learning_score": learning_score,
        "recommendations": _safe_int(
            performance.get("recommendations")
        ),
        "evaluations": evaluations,
        "successful": _safe_int(
            performance.get("successful")
        ),
        "accuracy": round(accuracy, 2),
        "average_return": round(
            average_return,
            2,
        ),
        "best_return": round(
            _safe_float(
                performance.get("best_return")
            ),
            2,
        ),
        "worst_return": round(
            _safe_float(
                performance.get("worst_return")
            ),
            2,
        ),
        "confidence_adjustment":
            confidence_adjustment,
        "sample_progress_pct":
            sample_progress,
        "minimum_active_sample":
            MIN_SAMPLE_FOR_ACTIVE,
        "best_horizon": best_horizon,
        "best_decision": best_decision,
        "best_sector": best_sector,
        "by_horizon": by_horizon,
        "by_decision": by_decision,
        "by_sector": by_sector,
        "evaluation_update": evaluation_update,
    }
PY

echo "AI Learning Engine installed."


echo
echo "[3/6] Connecting Learning Engine to Flask..."

venv/bin/python - <<'PY'
from pathlib import Path
import re

path = Path("app.py")
text = path.read_text(encoding="utf-8")

learning_import = '''from services.learning_engine import (
    apply_adaptive_confidence,
    get_learning_summary,
)
'''

# Add the import safely before the first Flask route.
if "from services.learning_engine import" not in text:
    route_position = text.find('@app.route(')

    if route_position == -1:
        raise SystemExit(
            "Unable to find the first Flask route."
        )

    text = (
        text[:route_position]
        + learning_import
        + "\n"
        + text[route_position:]
    )

# Connect learning data to the main dashboard route.
if "learning = get_learning_summary(" not in text:
    anchor = "performance = get_performance_summary()"

    if anchor not in text:
        raise SystemExit(
            "Dashboard performance assignment was not found."
        )

    text = text.replace(
        anchor,
        '''performance = get_performance_summary()

    learning = get_learning_summary(
        evaluate_first=False
    )''',
        1,
    )

# Pass learning into the dashboard template.
if "learning=learning," not in text:
    anchor = "performance=performance,"

    if anchor not in text:
        raise SystemExit(
            "Dashboard template context was not found."
        )

    text = text.replace(
        anchor,
        '''performance=performance,
        learning=learning,''',
        1,
    )

# Add V11.6 API routes.
routes = '''

@app.route("/api/v11.6/learning")
def v116_learning():
    return jsonify(
        get_learning_summary()
    )


@app.route(
    "/api/v11.6/adaptive-confidence/<int:confidence>"
)
def v116_adaptive_confidence(confidence):
    learning = get_learning_summary(
        evaluate_first=False
    )

    return jsonify({
        "original_confidence": confidence,
        "adaptive_confidence":
            apply_adaptive_confidence(
                confidence,
                learning,
            ),
        "adjustment":
            learning["confidence_adjustment"],
        "learning_status":
            learning["status"],
        "evaluations":
            learning["evaluations"],
    })


'''

if '@app.route("/api/v11.6/learning")' not in text:
    marker = '\nif __name__ == "__main__":\n'

    if marker not in text:
        raise SystemExit(
            "Flask route insertion point was not found."
        )

    text = text.replace(
        marker,
        routes + marker,
        1,
    )

# Upgrade the displayed version.
text = re.sub(
    r'VERSION\s*=\s*"11\.5 Production"',
    'VERSION = "11.6 Enterprise Intelligence"',
    text,
    count=1,
)

path.write_text(text, encoding="utf-8")

print("Learning Engine connected to Flask.")
PY

echo "Flask integration completed."


echo
echo "[4/6] Installing AI Learning dashboard panel..."

venv/bin/python - <<'PY'
from pathlib import Path

path = Path("templates/dashboard_v115.html")
text = path.read_text(encoding="utf-8")

panel = '''
<section class="panel enterprise-learning-panel">

    <div class="panel-heading">
        <div>
            <span class="section-label">
                Enterprise Intelligence
            </span>

            <h2>AI Learning Engine</h2>
        </div>

        <span class="learning-status-badge">
            {{ learning.status|default('COLLECTING DATA') }}
        </span>
    </div>

    <div class="learning-metric-grid">

        <article>
            <span>Learning Score</span>

            <strong>
                {{ learning.learning_score|default(0) }}%
            </strong>

            <small>
                Adaptive intelligence readiness
            </small>
        </article>

        <article>
            <span>Historical Accuracy</span>

            <strong>
                {{ learning.accuracy|default(0) }}%
            </strong>

            <small>
                {{ learning.successful|default(0) }}
                successful of
                {{ learning.evaluations|default(0) }}
                evaluations
            </small>
        </article>

        <article>
            <span>Average Return</span>

            <strong class="{% if learning.average_return|default(0) >= 0 %}positive{% else %}negative{% endif %}">
                {{ learning.average_return|default(0) }}%
            </strong>

            <small>
                Across evaluated recommendations
            </small>
        </article>

        <article>
            <span>Confidence Adjustment</span>

            <strong class="{% if learning.confidence_adjustment|default(0) >= 0 %}positive{% else %}negative{% endif %}">
                {{ learning.confidence_adjustment|default(0) }}
            </strong>

            <small>
                Conservative adaptive points
            </small>
        </article>

    </div>

    <div class="learning-progress-row">

        <div>
            <span>Learning history progress</span>

            <strong>
                {{ learning.evaluations|default(0) }}
                /
                {{ learning.minimum_active_sample|default(20) }}
            </strong>
        </div>

        <div class="learning-progress">
            <div
                class="learning-progress-fill"
                style="width: {{ learning.sample_progress_pct|default(0) }}%">
            </div>
        </div>

    </div>

    <div class="learning-insight-grid">

        <div>
            <span>Best Decision</span>

            <strong>
                {% if learning.best_decision %}
                    {{ learning.best_decision.decision }}
                {% else %}
                    Collecting data
                {% endif %}
            </strong>
        </div>

        <div>
            <span>Best Horizon</span>

            <strong>
                {% if learning.best_horizon %}
                    {{ learning.best_horizon.horizon_days }}
                    trading days
                {% else %}
                    Collecting data
                {% endif %}
            </strong>
        </div>

        <div>
            <span>Best Sector</span>

            <strong>
                {% if learning.best_sector %}
                    {{ learning.best_sector.sector }}
                {% else %}
                    Collecting data
                {% endif %}
            </strong>
        </div>

    </div>

</section>
'''

if "enterprise-learning-panel" not in text:
    marker = '<section class="content-grid two-columns">'

    if marker not in text:
        raise SystemExit(
            "Dashboard insertion point was not found."
        )

    text = text.replace(
        marker,
        panel + "\n\n" + marker,
        1,
    )

text = text.replace(
    "Version 11.5",
    "Version 11.6",
)

path.write_text(text, encoding="utf-8")

print("AI Learning dashboard panel installed.")
PY

cat >> static/css/v115.css <<'CSS'

/* ==================================================
   MIP PRO V11.6 Enterprise Intelligence
   AI Learning Engine
   ================================================== */

.enterprise-learning-panel {
    width: 100%;
    margin-bottom: 20px;
    border-top: 4px solid var(--gold);
}

.learning-status-badge {
    padding: 8px 12px;
    border-radius: 999px;
    background: var(--gold-soft);
    color: #7d611c;
    font-size: 12px;
    font-weight: 900;
}

.learning-metric-grid {
    display: grid;
    grid-template-columns:
        repeat(4, minmax(160px, 1fr));
    gap: 14px;
}

.learning-metric-grid article {
    padding: 18px;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: #f8fbf9;
}

.learning-metric-grid span,
.learning-metric-grid strong,
.learning-metric-grid small {
    display: block;
}

.learning-metric-grid span {
    margin-bottom: 8px;
    color: var(--muted);
    font-size: 11px;
    font-weight: 850;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}

.learning-metric-grid strong {
    margin-bottom: 7px;
    color: var(--black);
    font-size: 26px;
}

.learning-metric-grid small {
    color: var(--muted);
    line-height: 1.4;
}

.learning-progress-row {
    margin-top: 18px;
    padding: 16px 18px;
    border-radius: 12px;
    background: #f4f7f5;
}

.learning-progress-row > div:first-child {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 10px;
}

.learning-progress {
    height: 10px;
    overflow: hidden;
    border-radius: 999px;
    background: #dde6e0;
}

.learning-progress-fill {
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(
        90deg,
        var(--green),
        var(--gold)
    );
    transition: width 300ms ease;
}

.learning-insight-grid {
    display: grid;
    grid-template-columns:
        repeat(3, minmax(160px, 1fr));
    gap: 14px;
    margin-top: 16px;
}

.learning-insight-grid > div {
    padding: 14px 16px;
    border-left: 4px solid var(--green);
    border-radius: 8px;
    background: #fbfdfc;
}

.learning-insight-grid span,
.learning-insight-grid strong {
    display: block;
}

.learning-insight-grid span {
    margin-bottom: 5px;
    color: var(--muted);
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
}

@media (max-width: 1100px) {
    .learning-metric-grid {
        grid-template-columns:
            repeat(2, minmax(160px, 1fr));
    }
}

@media (max-width: 700px) {
    .learning-metric-grid,
    .learning-insight-grid {
        grid-template-columns: 1fr;
    }
}
CSS

echo "AI Learning dashboard panel completed."


echo
echo "[5/6] Validating V11.6 Enterprise Intelligence..."

venv/bin/python -m py_compile \
    app.py \
    services/learning_engine.py \
    services/*.py

venv/bin/python - <<'PY'
from services.learning_engine import (
    apply_adaptive_confidence,
    get_learning_summary,
)

summary = get_learning_summary()

required = {
    "status",
    "learning_score",
    "accuracy",
    "evaluations",
    "confidence_adjustment",
    "by_horizon",
    "by_decision",
    "by_sector",
}

missing = required - set(summary)

if missing:
    raise SystemExit(
        "Learning summary is missing: "
        + ", ".join(sorted(missing))
    )

adaptive = apply_adaptive_confidence(
    75,
    summary,
)

if not 0 <= adaptive <= 100:
    raise SystemExit(
        "Adaptive confidence is outside 0–100."
    )

print("Learning status:", summary["status"])
print("Learning score:", summary["learning_score"])
print("Recommendations:", summary["recommendations"])
print("Evaluations:", summary["evaluations"])
print("Accuracy:", summary["accuracy"])
print(
    "Confidence adjustment:",
    summary["confidence_adjustment"],
)
print("Adaptive confidence test:", adaptive)
print("Learning Engine validation passed.")
PY

echo
echo "Restarting MIP PRO..."

./restart.sh
sleep 2

HEALTH="$(
    curl -fsS \
    http://127.0.0.1:5000/health
)"

echo "Health response:"
echo "$HEALTH"

echo "$HEALTH" |
    grep -q '"status":"online"'

echo "$HEALTH" |
    grep -q '11.6 Enterprise Intelligence'

LOGIN_CODE="$(
    curl -s \
    -o /dev/null \
    -w "%{http_code}" \
    http://127.0.0.1:5000/login
)"

if [ "$LOGIN_CODE" != "200" ]; then
    echo "Login route failed: HTTP $LOGIN_CODE"
    exit 1
fi

echo
echo "Testing V11.6 Learning API..."

venv/bin/python - <<'PY'
from app import app

app.testing = True

with app.test_client() as client:
    with client.session_transaction() as session:
        session["authenticated"] = True
        session["username"] = "admin"

    response = client.get(
        "/api/v11.6/learning"
    )

    print(
        "Learning API status:",
        response.status_code,
    )

    if response.status_code != 200:
        raise SystemExit(
            "Learning API test failed."
        )

    payload = response.get_json()

    if "status" not in payload:
        raise SystemExit(
            "Learning API response is invalid."
        )

    print(
        "Learning API state:",
        payload["status"],
    )

    dashboard = client.get("/")

    print(
        "Dashboard status:",
        dashboard.status_code,
    )

    if dashboard.status_code != 200:
        raise SystemExit(
            "Dashboard test failed."
        )

print("V11.6 smoke tests passed.")
PY

echo "Validation, restart and smoke tests completed."


echo
echo "[6/6] Creating V11.6 release notes..."

RELEASE_NOTES="$PROJECT/RELEASE_NOTES_V11_6.md"

cat > "$RELEASE_NOTES" <<EOF
# MIP PRO V11.6 Enterprise Intelligence

Installed: $(date '+%Y-%m-%d %H:%M:%S %Z')

## Added

- AI Learning Engine
- Historical recommendation accuracy
- Learning score
- Accuracy by decision
- Accuracy by time horizon
- Accuracy by sector
- Conservative adaptive-confidence adjustment
- Enterprise Learning dashboard panel
- V11.6 Learning API
- V11.6 Adaptive Confidence API
- Automatic backup
- Validation and smoke tests
- Automatic rollback protection

## Learning status

The system may initially show COLLECTING DATA until enough
1-, 5-, 20-, and 60-trading-day recommendation outcomes are available.

## Backup

$BACKUP

## Upgrade log

$LOG
EOF

trap - ERR

echo
echo "=============================================="
echo " MIP PRO V11.6 Enterprise Installed"
echo "=============================================="
echo
echo "Backup:"
echo "$BACKUP"
echo
echo "Release notes:"
echo "$RELEASE_NOTES"
echo
echo "Log:"
echo "$LOG"
echo
echo "Open the dashboard and press Ctrl + Shift + R."
echo "=============================================="

