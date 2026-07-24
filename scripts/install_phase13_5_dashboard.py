from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = PROJECT_ROOT / "templates" / "dashboard_v115.html"

PANEL_START = "<!-- BEGIN PHASE 13.5 INSTITUTIONAL SECTOR ROTATION -->"
PANEL_END = "<!-- END PHASE 13.5 INSTITUTIONAL SECTOR ROTATION -->"

STYLE_START = "<!-- BEGIN PHASE 13.5 STYLES -->"
STYLE_END = "<!-- END PHASE 13.5 STYLES -->"

SCRIPT_START = "<!-- BEGIN PHASE 13.5 SCRIPT -->"
SCRIPT_END = "<!-- END PHASE 13.5 SCRIPT -->"


PANEL_HTML = r'''
<!-- BEGIN PHASE 13.5 INSTITUTIONAL SECTOR ROTATION -->
<section
    id="institutional-sector-rotation"
    class="isr-panel"
    aria-labelledby="isr-title">

    <div class="isr-header">
        <div>
            <span class="section-label">
                Institutional Intelligence
            </span>
            <h2 id="isr-title">
                Institutional Sector Rotation
            </h2>
            <p>
                Confidence-adjusted capital rotation across NSE sectors.
            </p>
        </div>

        <span
            id="isr-status"
            class="isr-status">
            Loading…
        </span>
    </div>

    <div class="isr-kpi-grid">
        <article class="isr-kpi">
            <span>Rotation Strength</span>
            <strong id="isr-strength">--</strong>
            <small>out of 100</small>
        </article>

        <article class="isr-kpi">
            <span>Rotation Phase</span>
            <strong id="isr-phase">--</strong>
            <small>current market posture</small>
        </article>

        <article class="isr-kpi">
            <span>Stocks Analysed</span>
            <strong id="isr-stock-count">--</strong>
            <small>institutional profiles</small>
        </article>

        <article class="isr-kpi">
            <span>Sectors Analysed</span>
            <strong id="isr-sector-count">--</strong>
            <small>ranked sectors</small>
        </article>
    </div>

    <div class="isr-content-grid">
        <article class="isr-card">
            <div class="isr-card-heading">
                <h3>Leading Sectors</h3>
                <span>Top five</span>
            </div>

            <div
                id="isr-leaders"
                class="isr-sector-list">
                <p class="isr-empty">Loading sector rankings…</p>
            </div>
        </article>

        <article class="isr-card">
            <div class="isr-card-heading">
                <h3>Lagging Sectors</h3>
                <span>Bottom five</span>
            </div>

            <div
                id="isr-laggards"
                class="isr-sector-list">
                <p class="isr-empty">Loading sector rankings…</p>
            </div>
        </article>
    </div>

    <article class="isr-summary-card">
        <span>Rotation Summary</span>
        <p id="isr-summary">
            Institutional sector intelligence is loading.
        </p>
    </article>
</section>
<!-- END PHASE 13.5 INSTITUTIONAL SECTOR ROTATION -->
'''


STYLE_HTML = r'''
<!-- BEGIN PHASE 13.5 STYLES -->
<style>
.isr-panel {
    margin: 24px 0;
    padding: 24px;
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 18px;
    background: var(--panel-bg, rgba(15, 23, 42, 0.72));
    box-shadow: 0 16px 40px rgba(2, 6, 23, 0.18);
}

.isr-header,
.isr-card-heading,
.isr-sector-row,
.isr-sector-meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
}

.isr-header {
    align-items: flex-start;
    margin-bottom: 20px;
}

.isr-header h2 {
    margin: 4px 0 6px;
}

.isr-header p,
.isr-empty,
.isr-summary-card p {
    margin: 0;
    opacity: 0.78;
}

.isr-status,
.isr-confidence {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 999px;
    font-weight: 700;
    white-space: nowrap;
}

.isr-status {
    padding: 8px 12px;
    background: rgba(148, 163, 184, 0.16);
}

.isr-status.ready {
    background: rgba(34, 197, 94, 0.16);
}

.isr-status.error {
    background: rgba(239, 68, 68, 0.16);
}

.isr-kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 14px;
    margin-bottom: 18px;
}

.isr-kpi,
.isr-card,
.isr-summary-card {
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 14px;
    background: rgba(148, 163, 184, 0.07);
}

.isr-kpi {
    padding: 16px;
}

.isr-kpi span,
.isr-kpi small,
.isr-summary-card > span {
    display: block;
    opacity: 0.72;
}

.isr-kpi strong {
    display: block;
    margin: 8px 0 3px;
    font-size: 1.6rem;
}

.isr-content-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 16px;
}

.isr-card {
    padding: 18px;
}

.isr-card-heading {
    margin-bottom: 12px;
}

.isr-card-heading h3 {
    margin: 0;
}

.isr-card-heading span {
    opacity: 0.66;
    font-size: 0.86rem;
}

.isr-sector-list {
    display: grid;
    gap: 10px;
}

.isr-sector-row {
    padding: 11px 0;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
}

.isr-sector-row:last-child {
    border-bottom: 0;
}

.isr-sector-name {
    min-width: 0;
}

.isr-sector-name strong,
.isr-sector-name small {
    display: block;
}

.isr-sector-name small {
    margin-top: 3px;
    opacity: 0.68;
}

.isr-sector-meta {
    justify-content: flex-end;
}

.isr-score {
    font-weight: 800;
}

.isr-confidence {
    min-width: 54px;
    padding: 5px 8px;
    font-size: 0.78rem;
    background: rgba(59, 130, 246, 0.15);
}

.isr-summary-card {
    margin-top: 16px;
    padding: 18px;
}

.isr-summary-card p {
    margin-top: 7px;
    line-height: 1.6;
}

@media (max-width: 900px) {
    .isr-kpi-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .isr-content-grid {
        grid-template-columns: 1fr;
    }
}

@media (max-width: 560px) {
    .isr-panel {
        padding: 16px;
    }

    .isr-header {
        display: block;
    }

    .isr-status {
        margin-top: 12px;
    }

    .isr-kpi-grid {
        grid-template-columns: 1fr;
    }

    .isr-sector-row {
        align-items: flex-start;
    }
}
</style>
<!-- END PHASE 13.5 STYLES -->
'''


SCRIPT_HTML = r'''
<!-- BEGIN PHASE 13.5 SCRIPT -->
<script>
(function () {
    "use strict";

    const endpoint = "/api/v11.5/market-breadth";

    function byId(id) {
        return document.getElementById(id);
    }

    function numberValue(value, fallback = 0) {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : fallback;
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }

    function sectorRow(item) {
        const sector = escapeHtml(item.sector || "Unknown");
        const phase = escapeHtml(
            item.rotation_phase ||
            item.phase ||
            "Neutral"
        );

        const score = numberValue(
            item.adjusted_rotation_score ??
            item.rotation_score
        ).toFixed(2);

        const confidence = numberValue(
            item.confidence_score
        ).toFixed(0);

        const rank = escapeHtml(item.rank || "");

        return `
            <div class="isr-sector-row">
                <div class="isr-sector-name">
                    <strong>${rank}. ${sector}</strong>
                    <small>${phase}</small>
                </div>

                <div class="isr-sector-meta">
                    <span class="isr-score">${score}</span>
                    <span class="isr-confidence">
                        ${confidence}% confidence
                    </span>
                </div>
            </div>
        `;
    }

    function renderList(element, items) {
        if (!element) {
            return;
        }

        if (!Array.isArray(items) || items.length === 0) {
            element.innerHTML =
                '<p class="isr-empty">No sector data available.</p>';
            return;
        }

        element.innerHTML = items.map(sectorRow).join("");
    }

    function setStatus(message, className) {
        const status = byId("isr-status");

        if (!status) {
            return;
        }

        status.textContent = message;
        status.classList.remove("ready", "error");

        if (className) {
            status.classList.add(className);
        }
    }

    async function loadInstitutionalSectorRotation() {
        setStatus("Loading…", "");

        try {
            const response = await fetch(endpoint, {
                credentials: "same-origin",
                headers: {
                    "Accept": "application/json"
                }
            });

            if (!response.ok) {
                throw new Error(
                    `Market breadth request failed: ${response.status}`
                );
            }

            const breadth = await response.json();
            const rotation =
                breadth.institutional_sector_rotation || {};

            const rankings = Array.isArray(
                rotation.sector_rankings
            )
                ? rotation.sector_rankings
                : [];

            const leaders = Array.isArray(rotation.leaders)
                ? rotation.leaders.slice(0, 5)
                : rankings.slice(0, 5);

            const laggards = Array.isArray(rotation.laggards)
                ? rotation.laggards.slice(0, 5)
                : rankings.slice(-5).reverse();

            byId("isr-strength").textContent =
                numberValue(
                    rotation.market_rotation_strength
                ).toFixed(2);

            byId("isr-phase").textContent =
                rotation.rotation_phase || "Neutral";

            byId("isr-stock-count").textContent =
                numberValue(rotation.stock_count);

            byId("isr-sector-count").textContent =
                numberValue(rotation.sector_count);

            byId("isr-summary").textContent =
                rotation.summary ||
                "Institutional capital rotation is currently neutral.";

            renderList(byId("isr-leaders"), leaders);
            renderList(byId("isr-laggards"), laggards);

            setStatus("Live", "ready");
        } catch (error) {
            console.error(
                "Institutional sector rotation load failed:",
                error
            );

            setStatus("Unavailable", "error");

            const summary = byId("isr-summary");

            if (summary) {
                summary.textContent =
                    "Institutional sector rotation data could not be loaded.";
            }
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            loadInstitutionalSectorRotation
        );
    } else {
        loadInstitutionalSectorRotation();
    }
})();
</script>
<!-- END PHASE 13.5 SCRIPT -->
'''


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    if not TEMPLATE.exists():
        fail(f"Active template not found: {TEMPLATE}")

    text = TEMPLATE.read_text(encoding="utf-8")

    markers = (PANEL_START, STYLE_START, SCRIPT_START)
    installed = [marker for marker in markers if marker in text]

    if installed:
        print("Phase 13.5 is already installed.")
        print(f"Template: {TEMPLATE}")
        return

    if "</main>" not in text:
        fail("Closing </main> tag not found")

    if "</body>" not in text:
        fail("Closing </body> tag not found")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = TEMPLATE.with_name(
        f"{TEMPLATE.name}.backup_phase13_5_{timestamp}"
    )

    shutil.copy2(TEMPLATE, backup)

    text = text.replace(
        "</main>",
        PANEL_HTML + "\n</main>",
        1,
    )

    text = text.replace(
        "</body>",
        STYLE_HTML + "\n" + SCRIPT_HTML + "\n</body>",
        1,
    )

    TEMPLATE.write_text(text, encoding="utf-8")

    final_text = TEMPLATE.read_text(encoding="utf-8")

    required = (
        PANEL_START,
        PANEL_END,
        STYLE_START,
        STYLE_END,
        SCRIPT_START,
        SCRIPT_END,
        'id="institutional-sector-rotation"',
        "/api/v11.5/market-breadth",
    )

    missing = [item for item in required if item not in final_text]

    if missing:
        shutil.copy2(backup, TEMPLATE)
        fail(
            "Verification failed; backup restored. Missing: "
            + ", ".join(missing)
        )

    print("PHASE 13.5 INSTALLATION PASSED")
    print(f"Template: {TEMPLATE}")
    print(f"Backup:   {backup}")
    print("Panel:    Institutional Sector Rotation")
    print("Endpoint: /api/v11.5/market-breadth")


if __name__ == "__main__":
    main()
