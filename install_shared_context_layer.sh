#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="/root/nse_signal_bot_v10_3"
SERVICE_NAME="nse-v10-3.service"
PYTHON="$PROJECT_DIR/venv/bin/python"

APP_DIR="$PROJECT_DIR/services/application"
DASHBOARD_BUILDER="$PROJECT_DIR/services/dashboard_context_builder.py"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$PROJECT_DIR/backups/shared_context_layer_$TIMESTAMP"

cd "$PROJECT_DIR"

if [[ ! -x "$PYTHON" ]]; then
    echo "ERROR: Python executable not found: $PYTHON"
    exit 1
fi

mkdir -p "$BACKUP_DIR"
mkdir -p "$APP_DIR"

cp "$DASHBOARD_BUILDER" \
   "$BACKUP_DIR/dashboard_context_builder.py"

if [[ -d "$APP_DIR" ]]; then
    cp -a "$APP_DIR" "$BACKUP_DIR/application_existing"
fi

restore_files() {
    echo
    echo "Restoring previous context architecture..."

    cp "$BACKUP_DIR/dashboard_context_builder.py" \
       "$DASHBOARD_BUILDER"

    rm -rf "$APP_DIR"

    if [[ -d "$BACKUP_DIR/application_existing" ]]; then
        cp -a "$BACKUP_DIR/application_existing" "$APP_DIR"
    fi
}

rollback() {
    local exit_code=$?

    echo
    echo "SHARED CONTEXT INSTALLATION FAILED."
    echo "Exit code: $exit_code"

    restore_files

    "$PYTHON" -m py_compile \
        app.py \
        services/dashboard_context_builder.py || true

    sudo systemctl restart "$SERVICE_NAME" || true
    sudo systemctl status \
        "$SERVICE_NAME" \
        --no-pager \
        -l || true

    exit "$exit_code"
}

trap rollback ERR

echo "======================================================"
echo "MIP Version 12.1 — Shared Context Layer"
echo "======================================================"
echo
echo "Backup directory:"
echo "$BACKUP_DIR"

cat > "$APP_DIR/__init__.py" <<'PY'
"""Application context builders for MIP Enterprise."""

from services.application.decision_context import (
    DecisionContextBuilder,
)
from services.application.market_context import (
    MarketContextBuilder,
)
from services.application.portfolio_context import (
    PortfolioContextBuilder,
)

__all__ = [
    "DecisionContextBuilder",
    "MarketContextBuilder",
    "PortfolioContextBuilder",
]
PY

cat > "$APP_DIR/market_context.py" <<'PY'
"""Reusable market intelligence application context."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from services.market_data import get_market_snapshot
from services.portfolio_optimizer import build_optimized_portfolio
from services.predictive_engine import build_predictions
from services.quant_intelligence import (
    analyze_sector_rotation,
    detect_market_regime,
)
from services.risk_engine import build_market_risk
from services.screener_engine import run_screener
from services.technical_analysis import analyze_market


class MarketContextBuilder:
    """Build canonical market intelligence for all consumers."""

    def __init__(
        self,
        *,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)

    def build(
        self,
        *,
        optimizer_capital: float = 100000,
    ) -> Dict[str, Any]:
        """Build market, technical, risk and prediction intelligence."""

        screener = run_screener()
        market = get_market_snapshot()

        try:
            technicals = analyze_market(
                market.get("stocks", [])
            )
        except Exception as exc:
            self.logger.exception(
                "Technical analysis failed: %s",
                exc,
            )
            technicals = []

        stocks = market.get("stocks", [])

        risk_metrics = build_market_risk(stocks)

        regime = detect_market_regime(
            market,
            technicals,
            risk_metrics,
        )

        sector_rotation = analyze_sector_rotation(stocks)

        predictions = build_predictions(
            stocks,
            technicals,
            limit=len(stocks),
        )

        optimized_portfolio = build_optimized_portfolio(
            screener,
            capital=max(float(optimizer_capital or 0), 100000),
        )

        return {
            "market": market,
            "technicals": technicals,
            "screener": screener,
            "risk_metrics": risk_metrics,
            "regime": regime,
            "sector_rotation": sector_rotation,
            "predictions": predictions,
            "optimized_portfolio": optimized_portfolio,
        }
PY

cat > "$APP_DIR/portfolio_context.py" <<'PY'
"""Reusable portfolio application context."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from services.learning_engine import get_learning_summary
from services.performance_engine import (
    evaluate_recommendations,
    get_performance_summary,
)
from services.portfolio import get_portfolio
from services.portfolio_transactions import (
    get_cash_summary,
    get_transactions,
)
from services.ziidi_copilot import (
    get_portfolio_summary as get_ziidi_portfolio_summary,
)


class PortfolioContextBuilder:
    """Build portfolio, capital and performance intelligence."""

    def __init__(
        self,
        *,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)

    def build(self) -> Dict[str, Any]:
        """Build the canonical portfolio context."""

        portfolio = get_portfolio()
        transactions = get_transactions(20)
        cash_summary = get_cash_summary()
        ziidi_summary = get_ziidi_portfolio_summary()

        invested_capital = float(
            ziidi_summary.get("invested_capital", 0) or 0
        )

        if isinstance(portfolio, dict):
            current_market_value = float(
                portfolio.get("total_value", 0) or 0
            )
        else:
            current_market_value = float(
                getattr(portfolio, "total_value", 0) or 0
            )

        cash_summary["portfolio_value"] = current_market_value
        cash_summary["invested_capital"] = invested_capital
        cash_summary["unrealized_gain"] = (
            current_market_value - invested_capital
        )

        portfolio_return = (
            (
                current_market_value - invested_capital
            )
            / invested_capital
            * 100
            if invested_capital > 0
            else 0.0
        )

        evaluate_recommendations()

        performance = get_performance_summary()

        learning = get_learning_summary(
            evaluate_first=False,
        )

        optimizer_capital = max(
            float(cash_summary.get("cash_balance", 0) or 0),
            100000,
        )

        return {
            "portfolio": portfolio,
            "transactions": transactions,
            "cash_summary": cash_summary,
            "portfolio_return": portfolio_return,
            "summary": ziidi_summary,
            "performance": performance,
            "learning": learning,
            "optimizer_capital": optimizer_capital,
        }
PY

cat > "$APP_DIR/decision_context.py" <<'PY'
"""Reusable investment decision application context."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from services.ai_committee import run_committee
from services.autonomous_assistant import autonomous_decision
from services.dashboard_charts import get_market_breadth
from services.decision_engine import get_ai_decision
from services.signal_service import get_signal_service


class DecisionContextBuilder:
    """Build committee, signal and AI decision intelligence."""

    def __init__(
        self,
        *,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)

    def build(
        self,
        *,
        market_context: Dict[str, Any],
        portfolio_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build investment decisions from canonical contexts."""

        market = market_context["market"]
        technicals = market_context["technicals"]
        portfolio = portfolio_context["portfolio"]

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

        (
            persisted_signals,
            persisted_signal_summary,
        ) = self._build_signal_context()

        persisted_top_signal = (
            persisted_signals[0]
            if persisted_signals
            else None
        )

        decision = self._build_ai_decision(
            persisted_signals=persisted_signals,
            persisted_signal_summary=persisted_signal_summary,
            regime=market_context["regime"],
            risk_metrics=market_context["risk_metrics"],
            sector_rotation=market_context["sector_rotation"],
        )

        return {
            "committee": committee,
            "assistant": assistant,
            "persisted_signals": persisted_signals,
            "persisted_top_signal": persisted_top_signal,
            "persisted_signal_summary": persisted_signal_summary,
            "decision": decision,
        }

    def _build_signal_context(
        self,
    ) -> tuple[list[Any], Dict[str, Any]]:
        """Read finalized committee decisions safely."""

        try:
            signal_service = get_signal_service()

            persisted_signals = signal_service.get_top_signals(
                limit=10,
            )

            persisted_signal_summary = (
                signal_service.get_dashboard_summary(limit=10)
            )

            return (
                persisted_signals,
                persisted_signal_summary,
            )

        except Exception:
            self.logger.exception(
                "SignalService context read failed"
            )

            return [], {
                "available": False,
                "signal_count": 0,
                "history_count": 0,
                "average_committee_score": 0,
                "average_confidence": 0,
                "decision_counts": {},
                "signals": [],
                "top_signal": None,
            }

    def _build_ai_decision(
        self,
        *,
        persisted_signals: list[Any],
        persisted_signal_summary: Dict[str, Any],
        regime: Any,
        risk_metrics: Any,
        sector_rotation: Any,
    ) -> Dict[str, Any]:
        """Build the authoritative dashboard decision object."""

        try:
            market_breadth = get_market_breadth()

            regime_label = (
                regime.get(
                    "label",
                    regime.get(
                        "regime",
                        regime.get(
                            "market_regime",
                            "Neutral / Selective",
                        ),
                    ),
                )
                if isinstance(regime, dict)
                else str(regime or "Neutral / Selective")
            )

            return get_ai_decision(
                signals=persisted_signals,
                market={
                    "status": regime_label,
                    "ai_confidence": (
                        persisted_signal_summary.get(
                            "average_confidence",
                            0,
                        )
                    ),
                },
                regime=(
                    regime
                    if isinstance(regime, dict)
                    else {
                        "label": str(
                            regime or "Neutral / Selective"
                        )
                    }
                ),
                risk_metrics=(
                    risk_metrics
                    if isinstance(risk_metrics, dict)
                    else {
                        "risk_level": str(
                            risk_metrics or "UNKNOWN"
                        )
                    }
                ),
                breadth=market_breadth,
                institutional=(
                    sector_rotation
                    if isinstance(sector_rotation, dict)
                    else {}
                ),
            )

        except Exception:
            self.logger.exception(
                "AI Decision Engine context failed"
            )

            return {
                "market_state": "Unavailable",
                "market_risk": "UNKNOWN",
                "decision": "WAIT",
                "decision_label": "WAIT",
                "decision_headline": (
                    "Decision intelligence is temporarily unavailable."
                ),
                "decision_reason": [
                    (
                        "The Decision Engine could not process "
                        "the current market data."
                    )
                ],
                "confidence": 0,
                "qualified_opportunities": [],
                "qualified_count": 0,
                "leading_signal": None,
                "breadth": {},
                "institutional": {},
                "thresholds": {},
            }
PY

cat > "$DASHBOARD_BUILDER" <<'PY'
"""Dashboard application-context composition.

The dashboard builder composes reusable market, portfolio and decision
contexts while preserving the established template contract.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from services.application.decision_context import (
    DecisionContextBuilder,
)
from services.application.market_context import (
    MarketContextBuilder,
)
from services.application.portfolio_context import (
    PortfolioContextBuilder,
)
from services.dashboard_engine import build_dashboard
from services.telegram_bot import telegram_status


class DashboardContextBuilder:
    """Compose all reusable contexts for dashboard rendering."""

    def __init__(
        self,
        *,
        version: str,
        logger: Optional[logging.Logger] = None,
        project_root: Optional[Path] = None,
    ) -> None:
        self.version = version
        self.logger = logger or logging.getLogger(__name__)
        self.project_root = (
            project_root
            or Path(__file__).resolve().parents[1]
        )

    def build(
        self,
        ui: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return the template and its complete rendering context."""

        dashboard_data = build_dashboard()

        portfolio_context = PortfolioContextBuilder(
            logger=self.logger,
        ).build()

        market_context = MarketContextBuilder(
            logger=self.logger,
        ).build(
            optimizer_capital=portfolio_context[
                "optimizer_capital"
            ],
        )

        decision_context = DecisionContextBuilder(
            logger=self.logger,
        ).build(
            market_context=market_context,
            portfolio_context=portfolio_context,
        )

        logo_available = (
            self.project_root
            / "static"
            / "images"
            / "mip_pro_logo.png"
        ).exists()

        template_name = (
            "dashboard_v117.html"
            if ui == "v117"
            else "dashboard_v115.html"
        )

        context = {
            "version": self.version,
            "dashboard": dashboard_data,
            "picks": dashboard_data["top_picks"],
            "market": market_context["market"],
            "technicals": market_context["technicals"],
            "committee": decision_context["committee"],
            "assistant": decision_context["assistant"],
            "portfolio": portfolio_context["portfolio"],
            "screener": market_context["screener"],
            "telegram_status": telegram_status(),
            "now": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "system_status": "Online",
            "transactions": portfolio_context["transactions"],
            "cash_summary": portfolio_context["cash_summary"],
            "portfolio_return": portfolio_context[
                "portfolio_return"
            ],
            "summary": portfolio_context["summary"],
            "logo_available": logo_available,
            "performance": portfolio_context["performance"],
            "learning": portfolio_context["learning"],
            "optimized_portfolio": market_context[
                "optimized_portfolio"
            ],
            "risk_metrics": market_context["risk_metrics"],
            "regime": market_context["regime"],
            "sector_rotation": market_context[
                "sector_rotation"
            ],
            "predictions": market_context["predictions"],
            "persisted_signals": decision_context[
                "persisted_signals"
            ],
            "persisted_top_signal": decision_context[
                "persisted_top_signal"
            ],
            "persisted_signal_summary": decision_context[
                "persisted_signal_summary"
            ],
            "decision": decision_context["decision"],
        }

        return {
            "template_name": template_name,
            "data": context,
        }
PY

echo
echo "Created shared context files:"
find "$APP_DIR" -maxdepth 1 -type f -print

echo
echo "1. Running syntax validation..."

"$PYTHON" -m py_compile \
    app.py \
    services/dashboard_context_builder.py \
    services/application/__init__.py \
    services/application/market_context.py \
    services/application/portfolio_context.py \
    services/application/decision_context.py

echo "PASS: Python syntax"

echo
echo "2. Running import validation..."

"$PYTHON" - <<'PY'
from services.application import (
    DecisionContextBuilder,
    MarketContextBuilder,
    PortfolioContextBuilder,
)
from services.dashboard_context_builder import (
    DashboardContextBuilder,
)

assert MarketContextBuilder
assert PortfolioContextBuilder
assert DecisionContextBuilder
assert DashboardContextBuilder

print("PASS: all context builders import correctly")
PY

echo
echo "3. Validating Flask routes..."

"$PYTHON" - <<'PY'
import app

routes = {
    rule.rule
    for rule in app.app.url_map.iter_rules()
}

required = {
    "/",
    "/health",
    "/api/v11.7/decision",
}

missing = required - routes

if missing:
    raise SystemExit(
        f"Missing required routes: {sorted(missing)}"
    )

print(f"PASS: {len(routes)} Flask routes registered")
PY

echo
echo "4. Running functional dashboard rendering tests..."

"$PYTHON" - <<'PY'
import time
import traceback

from app import app


def verify_dashboard(client, url, label):
    started = time.monotonic()

    response = client.get(
        url,
        follow_redirects=False,
    )

    elapsed = time.monotonic() - started
    size = len(response.data)

    print(
        f"{label}: status={response.status_code}, "
        f"bytes={size}, time={elapsed:.2f}s"
    )

    if response.status_code != 200:
        body = response.data.decode(
            "utf-8",
            errors="replace",
        )

        print(body[:2000])

        raise AssertionError(
            f"{label} returned HTTP "
            f"{response.status_code}"
        )

    if size < 10000:
        raise AssertionError(
            f"{label} response is unexpectedly small: {size}"
        )

    body = response.data.decode(
        "utf-8",
        errors="replace",
    )

    if "Internal Server Error" in body:
        raise AssertionError(
            f"{label} contains Internal Server Error"
        )

    print(f"PASS: {label}")


try:
    app.config.update(
        TESTING=True,
        PROPAGATE_EXCEPTIONS=True,
    )

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["authenticated"] = True
            session["username"] = "context-verification"

        verify_dashboard(
            client,
            "/",
            "Legacy dashboard",
        )

        verify_dashboard(
            client,
            "/?ui=v117",
            "Version 11.7 dashboard",
        )

except Exception:
    print()
    print("FUNCTIONAL DASHBOARD TEST FAILED")
    traceback.print_exc()
    raise
PY

echo
echo "5. Restarting production service..."

sudo systemctl restart "$SERVICE_NAME"
sleep 3

sudo systemctl is-active --quiet "$SERVICE_NAME"

echo "PASS: service is active"

echo
echo "6. Testing health endpoint..."

curl \
    --fail \
    --silent \
    --show-error \
    --max-time 30 \
    http://127.0.0.1:5000/health

echo
echo

echo "7. Checking warnings since restart..."

ACTIVE_TIME="$(
    systemctl show "$SERVICE_NAME" \
        --property=ActiveEnterTimestamp \
        --value
)"

sudo journalctl \
    -u "$SERVICE_NAME" \
    --since "$ACTIVE_TIME" \
    --priority=warning \
    --no-pager || true

echo
echo "8. Recording shared context layer in Git..."

git add \
    services/application \
    services/dashboard_context_builder.py \
    install_shared_context_layer.sh

if git diff --cached --quiet; then
    echo "No new changes to commit."
else
    git commit -m \
        "refactor: introduce shared application contexts"
fi

CURRENT_BRANCH="$(git branch --show-current)"
git push origin "$CURRENT_BRANCH"

echo
echo "======================================================"
echo "Shared Context Layer installed successfully"
echo "======================================================"
echo
echo "Commit:"
git log -1 --oneline

echo
echo "Context architecture:"
echo "  DashboardContextBuilder"
echo "      ├── MarketContextBuilder"
echo "      ├── PortfolioContextBuilder"
echo "      └── DecisionContextBuilder"

echo
echo "Backup retained at:"
echo "$BACKUP_DIR"

echo
echo "Git status:"
git status --short
