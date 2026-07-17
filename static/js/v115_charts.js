"use strict";

let marketHistoryChart = null;
let portfolioHistoryChart = null;
let confidenceChart = null;
let sectorChart = null;

const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
        intersect: false,
        mode: "index",
    },
    plugins: {
        legend: {
            display: false,
        },
    },
    scales: {
        x: {
            grid: {
                display: false,
            },
            ticks: {
                maxTicksLimit: 8,
            },
        },
        y: {
            beginAtZero: false,
            grid: {
                color: "rgba(20, 45, 32, 0.08)",
            },
        },
    },
};

function destroyChart(chart) {
    if (chart) {
        chart.destroy();
    }
}

function createLineChart(
    elementId,
    labels,
    values,
    datasetLabel
) {
    const canvas = document.getElementById(elementId);

    if (!canvas || typeof Chart === "undefined") {
        return null;
    }

    return new Chart(canvas, {
        type: "line",
        data: {
            labels,
            datasets: [
                {
                    label: datasetLabel,
                    data: values,
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true,
                    pointRadius: 1.5,
                    pointHoverRadius: 5,
                    borderColor: "#08783f",
                    backgroundColor: "rgba(8, 120, 63, 0.10)",
                },
            ],
        },
        options: chartDefaults,
    });
}

function createSectorChart(labels, values) {
    const canvas = document.getElementById(
        "sector-rotation-chart"
    );

    if (!canvas || typeof Chart === "undefined") {
        return null;
    }

    return new Chart(canvas, {
        type: "bar",
        data: {
            labels,
            datasets: [
                {
                    data: values,
                    borderWidth: 0,
                    borderRadius: 4,
                    backgroundColor: values.map(
                        value => (
                            value >= 0
                                ? "rgba(8, 120, 63, 0.78)"
                                : "rgba(200, 16, 46, 0.78)"
                        )
                    ),
                },
            ],
        },
        options: {
            ...chartDefaults,
            indexAxis: "y",
            scales: {
                x: {
                    grid: {
                        color: "rgba(20, 45, 32, 0.08)",
                    },
                },
                y: {
                    grid: {
                        display: false,
                    },
                },
            },
        },
    });
}

function updateBreadth(breadth) {
    const updateMetric = (
        id,
        value,
        secondary = ""
    ) => {
        const element = document.getElementById(id);

        if (!element) {
            return;
        }

        element.innerHTML = `
            ${value ?? 0}
            ${
                secondary
                    ? `<small>${secondary}</small>`
                    : ""
            }
        `;
    };

    updateMetric(
        "breadth-advancers",
        breadth.advancers,
        `${breadth.advancing_percentage ?? 0}%`
    );

    updateMetric(
        "breadth-decliners",
        breadth.decliners,
        `${breadth.declining_percentage ?? 0}%`
    );

    updateMetric(
        "breadth-unchanged",
        breadth.unchanged,
        `${breadth.unchanged_percentage ?? 0}%`
    );

    updateMetric(
        "breadth-ratio",
        breadth.advance_decline_ratio,
        breadth.breadth_signal || ""
    );

    const positiveBar = document.getElementById(
        "breadth-advance-bar"
    );

    const negativeBar = document.getElementById(
        "breadth-decline-bar"
    );

    if (positiveBar) {
        positiveBar.style.width =
            `${breadth.advancing_percentage ?? 0}%`;
    }

    if (negativeBar) {
        negativeBar.style.width =
            `${breadth.declining_percentage ?? 0}%`;
    }

    const marketPulse = document.getElementById(
        "market-pulse-text"
    );

    if (marketPulse) {
        marketPulse.textContent =
            breadth.market_pulse ||
            "Market interpretation is currently unavailable.";
    }

    const leaderContainer = document.getElementById(
        "volume-leaders"
    );

    if (leaderContainer) {
        leaderContainer.innerHTML = "";

        (breadth.volume_leaders || [])
            .slice(0, 16)
            .forEach((stock, index) => {
                const card = document.createElement("article");

                const signalClass =
                    stock.signal_class || "watchlist";

                const confidence = Math.max(
                    0,
                    Math.min(
                        100,
                        Number(
                            stock.institutional_confidence ?? 0
                        )
                    )
                );

                const reasons = (
                    stock.institutional_reasons || []
                )
                    .slice(0, 3)
                    .map(reason => `<li>${reason}</li>`)
                    .join("");

                card.className =
                    `institutional-volume-card signal-${signalClass}`;

                card.innerHTML = `
                    <div class="institutional-card-heading">
                        <div>
                            <span class="institutional-rank">
                                #${index + 1}
                            </span>

                            <h3>${stock.symbol || "-"}</h3>
                        </div>

                        <span class="institutional-badge">
                            ${stock.institutional_badge || "⚪"}
                        </span>
                    </div>

                    <div class="institutional-metrics">
                        <div>
                            <span>Volume</span>
                            <strong>
                                ${Number(
                                    stock.volume ?? 0
                                ).toLocaleString("en-KE")}
                            </strong>
                        </div>

                        <div>
                            <span>RVOL</span>
                            <strong>
                                ${Number(
                                    stock.relative_volume ?? 0
                                ).toFixed(2)}×
                            </strong>
                        </div>

                        <div>
                            <span>AI Score</span>
                            <strong>
                                ${Number(
                                    stock.score ?? 0
                                ).toFixed(0)}
                            </strong>
                        </div>

                        <div>
                            <span>Confidence</span>
                            <strong>
                                ${confidence.toFixed(0)}%
                            </strong>
                        </div>
                    </div>

                    <div class="institutional-confidence-bar">
                        <div style="width: ${confidence}%"></div>
                    </div>

                    <strong class="institutional-signal">
                        ${stock.institutional_badge || "⚪"}
                        ${stock.institutional_signal || "Watchlist"}
                    </strong>

                    <ul class="institutional-reasons">
                        ${reasons}
                    </ul>
                `;

                leaderContainer.appendChild(card);
            });
    }
}


function setChartLoading(isLoading) {
    const chartIds = [
        "market-history-chart",
        "portfolio-history-chart",
        "ai-confidence-chart",
        "sector-rotation-chart",
    ];

    chartIds.forEach(id => {
        const canvas = document.getElementById(id);

        if (!canvas || !canvas.parentElement) {
            return;
        }

        const parent = canvas.parentElement;
        parent.classList.add("chart-loading-container");

        let overlay = parent.querySelector(
            ".chart-loading-overlay"
        );

        if (!overlay) {
            overlay = document.createElement("div");
            overlay.className = "chart-loading-overlay";
            overlay.innerHTML = `
                <span class="chart-loading-spinner"></span>
                <strong>Loading intelligence chart...</strong>
            `;
            parent.appendChild(overlay);
        }

        overlay.hidden = !isLoading;
        canvas.style.opacity = isLoading ? "0.15" : "1";
    });
}

async function loadDashboardCharts(symbol = "SCOM") {
    try {
        setChartLoading(true);

        const response = await fetch(
            `/api/v11.5/dashboard-charts?symbol=${
                encodeURIComponent(symbol)
            }`,
            {
                cache: "no-store",
                headers: {
                    "Accept": "application/json"
                }
            }
        );

        if (!response.ok) {
            throw new Error(
                `Dashboard chart API returned ${response.status}`
            );
        }

        const data = await response.json();

        destroyChart(marketHistoryChart);
        destroyChart(portfolioHistoryChart);
        destroyChart(confidenceChart);
        destroyChart(sectorChart);

        marketHistoryChart = createLineChart(
            "market-history-chart",
            data.market_history.labels || [],
            data.market_history.prices || [],
            `${symbol} close`
        );

        portfolioHistoryChart = createLineChart(
            "portfolio-history-chart",
            data.portfolio_history.labels || [],
            data.portfolio_history.values || [],
            "Portfolio value"
        );

        confidenceChart = createLineChart(
            "ai-confidence-chart",
            data.ai_confidence.labels || [],
            data.ai_confidence.confidence || [],
            "AI confidence"
        );

        sectorChart = createSectorChart(
            data.sector_rotation.labels || [],
            data.sector_rotation.values || []
        );

        updateBreadth(data.breadth || {});

        const title = document.getElementById(
            "market-chart-title"
        );

        if (title) {
            title.textContent = `${symbol} Price History`;
        }

    } catch (error) {
        console.error(
            "Unable to load dashboard charts:",
            error
        );

        const pulse = document.getElementById(
            "market-pulse-text"
        );

        if (pulse) {
            pulse.textContent =
                "Dashboard intelligence could not be refreshed. " +
                "Please reload the page.";
        }
    } finally {
        setChartLoading(false);
    }
}

function applyScreenerFilters() {
    const search = (
        document.getElementById("screener-search")?.value
        || ""
    ).trim().toLowerCase();

    const decision = (
        document.getElementById(
            "screener-decision-filter"
        )?.value
        || ""
    );

    const risk = (
        document.getElementById(
            "screener-risk-filter"
        )?.value
        || ""
    );

    const sector = (
        document.getElementById(
            "screener-sector-filter"
        )?.value
        || ""
    );

    const minimumConfidence = Number(
        document.getElementById(
            "screener-confidence-filter"
        )?.value
        || 0
    );

    const rows = Array.from(
        document.querySelectorAll(".screener-row")
    );

    let visibleCount = 0;

    rows.forEach(row => {
        const matchesSearch = (
            !search
            || row.dataset.symbol.includes(search)
            || row.dataset.company.includes(search)
        );

        const matchesDecision = (
            !decision
            || row.dataset.decision === decision
        );

        const matchesRisk = (
            !risk
            || row.dataset.risk === risk
        );

        const matchesSector = (
            !sector
            || row.dataset.sector === sector
        );

        const matchesConfidence = (
            Number(row.dataset.confidence || 0)
            >= minimumConfidence
        );

        const visible = (
            matchesSearch
            && matchesDecision
            && matchesRisk
            && matchesSector
            && matchesConfidence
        );

        row.hidden = !visible;

        if (visible) {
            visibleCount += 1;

            const rank = row.querySelector(
                ".screener-rank"
            );

            if (rank) {
                rank.textContent = visibleCount;
            }
        }
    });

    const counter = document.getElementById(
        "screener-visible-count"
    );

    if (counter) {
        counter.textContent = visibleCount;
    }
}

function initializeScreenerFilters() {
    const filterIds = [
        "screener-search",
        "screener-decision-filter",
        "screener-risk-filter",
        "screener-sector-filter",
        "screener-confidence-filter",
    ];

    filterIds.forEach(id => {
        const element = document.getElementById(id);

        if (!element) {
            return;
        }

        element.addEventListener(
            element.tagName === "INPUT"
                ? "input"
                : "change",
            applyScreenerFilters
        );
    });

    const resetButton = document.getElementById(
        "screener-reset"
    );

    if (resetButton) {
        resetButton.addEventListener("click", () => {
            filterIds.forEach(id => {
                const element = document.getElementById(id);

                if (!element) {
                    return;
                }

                if (
                    id === "screener-confidence-filter"
                ) {
                    element.value = "0";
                } else {
                    element.value = "";
                }
            });

            applyScreenerFilters();
        });
    }

    applyScreenerFilters();
}

document.addEventListener("DOMContentLoaded", () => {
    const symbolSelect = document.getElementById(
        "chart-symbol"
    );

    const initialSymbol = symbolSelect?.value || "SCOM";

    loadDashboardCharts(initialSymbol);
    initializeScreenerFilters();

    if (symbolSelect) {
        symbolSelect.addEventListener(
            "change",
            event => {
                loadDashboardCharts(
                    event.target.value
                );
            }
        );
    }
});

/* MIP PRO intelligence table selector */
function initializeIntelligenceSelector() {
    const selector = document.getElementById(
        "intelligence-view-selector"
    );

    const predictions = document.getElementById(
        "predictions-view"
    );

    const screener = document.getElementById(
        "screener-view"
    );

    if (!selector || !predictions || !screener) {
        return;
    }

    function displaySelectedView() {
        const selected = selector.value;

        predictions.hidden = selected !== "predictions";
        screener.hidden = selected !== "screener";

        localStorage.setItem(
            "mip-intelligence-view",
            selected
        );
    }

    const savedView = localStorage.getItem(
        "mip-intelligence-view"
    );

    if (
        savedView === "predictions"
        || savedView === "screener"
    ) {
        selector.value = savedView;
    } else {
        selector.value = "predictions";
    }

    selector.addEventListener(
        "change",
        displaySelectedView
    );

    displaySelectedView();
}

document.addEventListener(
    "DOMContentLoaded",
    initializeIntelligenceSelector
);

/* ==================================================
   MIP PRO V11.6.4 RC3
   Prediction Center 2.0
   ================================================== */

let predictionCenterRows = [];

function predictionNumber(
    value,
    fallback = 0
) {
    const number = Number(value);

    return Number.isFinite(number)
        ? number
        : fallback;
}

function predictionSignalClass(signal) {
    return String(signal || "WATCH")
        .trim()
        .toLowerCase()
        .replace(/\s+/g, "-");
}

function predictionRiskClass(risk) {
    return String(risk || "INSUFFICIENT HISTORY")
        .trim()
        .toLowerCase()
        .replace(/\s+/g, "-");
}

function renderMarketRegime(payload) {
    const regime = payload.market_regime || {};
    const components = regime.components || {};

    const values = {
        "market-regime-score":
            `${predictionNumber(
                regime.regime_score
            ).toFixed(2)}`,

        "market-regime-confidence":
            `${predictionNumber(
                regime.confidence
            ).toFixed(0)}%`,

        "market-regime-risk":
            regime.market_risk_level || "UNKNOWN",

        "market-regime-equities":
            `${predictionNumber(
                regime.recommended_equities_pct
            ).toFixed(0)}%`,

        "market-regime-cash":
            `${predictionNumber(
                regime.recommended_cash_pct
            ).toFixed(0)}%`,

        "market-regime-multiplier":
            `${predictionNumber(
                regime.conviction_multiplier,
                1
            ).toFixed(2)}×`,

        "market-regime-breadth":
            predictionNumber(
                components.breadth_score
            ).toFixed(2),

        "market-regime-predictions":
            predictionNumber(
                components.prediction_score
            ).toFixed(2),

        "market-regime-institutional":
            predictionNumber(
                components.institutional_score
            ).toFixed(2),

        "market-regime-risk-score":
            predictionNumber(
                components.risk_score
            ).toFixed(2),

        "market-regime-learning":
            predictionNumber(
                components.learning_score
            ).toFixed(2),
    };

    Object.entries(values).forEach(
        ([id, value]) => {
            const element = document.getElementById(id);

            if (element) {
                element.textContent = value;
            }
        }
    );

    const badge = document.getElementById(
        "market-regime-badge"
    );

    if (badge) {
        badge.textContent = `${
            regime.badge || "⚪"
        } ${regime.regime || "UNKNOWN"}`;

        badge.dataset.regime = String(
            regime.regime || "UNKNOWN"
        ).toLowerCase();
    }

    const reasons = document.getElementById(
        "market-regime-reasons"
    );

    if (reasons) {
        reasons.innerHTML = (
            regime.reasons || []
        )
            .map(reason => `<li>${reason}</li>`)
            .join("");
    }
}

function renderPredictionSummary(payload) {
    const summary = payload.summary || {};

    const values = {
        "prediction-summary-count":
            summary.prediction_count ?? 0,

        "prediction-summary-conviction":
            `${predictionNumber(
                summary.average_conviction
            ).toFixed(1)}%`,

        "prediction-summary-return":
            `${predictionNumber(
                summary.average_expected_return
            ) >= 0 ? "+" : ""}${predictionNumber(
                summary.average_expected_return
            ).toFixed(2)}%`,

        "prediction-summary-leader":
            `${
                summary.highest_conviction_symbol || "—"
            } ${
                summary.highest_conviction_score ?? ""
            }`,

        "prediction-summary-institutional":
            summary.institutional_buying_count ?? 0,

        "prediction-summary-low-risk":
            summary.low_risk_count ?? 0,
    };

    Object.entries(values).forEach(
        ([id, value]) => {
            const element = document.getElementById(id);

            if (element) {
                element.textContent = value;
            }
        }
    );
}

function buildPredictionCard(stock, index) {
    const card = document.createElement("article");

    const signal = stock.signal || "WATCH";
    const risk = stock.risk_level || "INSUFFICIENT HISTORY";

    const conviction = Math.max(
        0,
        Math.min(
            100,
            predictionNumber(
                stock.conviction_score
            )
        )
    );

    const expectedReturn = predictionNumber(
        stock.expected_return
    );

    const reasons = (
        stock.reasons || []
    )
        .slice(0, 5)
        .map(reason => `<li>${reason}</li>`)
        .join("");

    card.className = [
        "prediction-card",
        `prediction-signal-${predictionSignalClass(signal)}`,
        `prediction-risk-${predictionRiskClass(risk)}`,
    ].join(" ");

    card.dataset.symbol = String(
        stock.symbol || ""
    ).toLowerCase();

    card.dataset.company = String(
        stock.name || ""
    ).toLowerCase();

    card.dataset.signal = signal;
    card.dataset.risk = risk;
    card.dataset.conviction = conviction;
    card.dataset.confidence = predictionNumber(
        stock.confidence
    );
    card.dataset.expectedReturn = expectedReturn;
    card.dataset.probability = predictionNumber(
        stock.prediction_probability_pct
    );
    card.dataset.target = predictionNumber(
        stock.target_price
    );
    card.dataset.rvol = predictionNumber(
        stock.relative_volume
    );

    card.innerHTML = `
        <div class="prediction-card-header">

            <div>
                <span class="prediction-rank">
                    #${index + 1}
                </span>

                <a
                    class="prediction-symbol"
                    href="/stocks/${encodeURIComponent(
                        stock.symbol || ""
                    )}">
                    ${stock.symbol || "—"}
                </a>

                <small>
                    ${stock.name || ""}
                </small>
            </div>

            <div class="prediction-rating">
                ${stock.rating || "☆☆☆☆☆"}
            </div>

        </div>

        <div class="prediction-signal-row">

            <span
                class="prediction-signal-badge
                signal-${predictionSignalClass(signal)}">
                ${signal}
            </span>

            <span
                class="prediction-risk-badge
                risk-${predictionRiskClass(risk)}">
                ${risk}
            </span>

        </div>

        <div class="prediction-conviction-heading">
            <span>AI Conviction</span>
            <strong>${conviction.toFixed(0)}%</strong>
        </div>

        <div class="prediction-conviction-bar">
            <div style="width: ${conviction}%"></div>
        </div>

        <div class="prediction-metric-grid">

            <div>
                <span>Confidence</span>
                <strong>
                    ${predictionNumber(
                        stock.confidence
                    ).toFixed(0)}%
                </strong>
            </div>

            <div>
                <span>Probability</span>
                <strong>
                    ${predictionNumber(
                        stock.prediction_probability_pct
                    ).toFixed(2)}%
                </strong>
            </div>

            <div>
                <span>Expected Return</span>
                <strong class="${
                    expectedReturn >= 0
                        ? "positive"
                        : "negative"
                }">
                    ${expectedReturn >= 0 ? "+" : ""}
                    ${expectedReturn.toFixed(2)}%
                </strong>
            </div>

            <div>
                <span>Target Price</span>
                <strong>
                    KSh ${predictionNumber(
                        stock.target_price
                    ).toLocaleString(
                        "en-KE",
                        {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                        }
                    )}
                </strong>
            </div>

            <div>
                <span>Horizon</span>
                <strong>
                    ${stock.horizon || "Monitor"}
                </strong>
            </div>

            <div>
                <span>RVOL</span>
                <strong>
                    ${predictionNumber(
                        stock.relative_volume
                    ).toFixed(2)}×
                </strong>
            </div>

            <div>
                <span>Volatility</span>
                <strong>
                    ${predictionNumber(
                        stock.volatility_pct
                    ).toFixed(2)}%
                </strong>
            </div>

            <div>
                <span>Sharpe</span>
                <strong>
                    ${predictionNumber(
                        stock.sharpe_ratio
                    ).toFixed(2)}
                </strong>
            </div>

        </div>

        <div class="prediction-institutional">
            <span>Institutional Intelligence</span>
            <strong>
                ${stock.institutional_signal ||
                  "No strong institutional signal"}
            </strong>
        </div>

        <details class="prediction-analysis">
            <summary>
                View AI Analysis
            </summary>

            <div class="prediction-analysis-content">

                <div>
                    <span>Trend</span>
                    <strong>
                        ${stock.trend || "Neutral"}
                    </strong>
                </div>

                <div>
                    <span>RSI</span>
                    <strong>
                        ${predictionNumber(
                            stock.rsi
                        ).toFixed(2)}
                    </strong>
                </div>

                <div>
                    <span>Maximum Drawdown</span>
                    <strong>
                        ${predictionNumber(
                            stock.maximum_drawdown_pct
                        ).toFixed(2)}%
                    </strong>
                </div>

                <div>
                    <span>Risk History</span>
                    <strong>
                        ${stock.risk_history_status ||
                          "INSUFFICIENT HISTORY"}
                    </strong>
                </div>

            </div>

            <ul class="prediction-reasons">
                ${reasons || `
                    <li>
                        Further confirmation is required.
                    </li>
                `}
            </ul>

        </details>
    `;

    return card;
}

function applyPredictionFilters() {
    const container = document.getElementById(
        "prediction-center-container"
    );

    if (!container) {
        return;
    }

    const search = (
        document.getElementById(
            "prediction-search"
        )?.value || ""
    ).trim().toLowerCase();

    const signal = (
        document.getElementById(
            "prediction-signal-filter"
        )?.value || ""
    );

    const risk = (
        document.getElementById(
            "prediction-risk-filter"
        )?.value || ""
    );

    const minimumConviction = predictionNumber(
        document.getElementById(
            "prediction-conviction-filter"
        )?.value
    );

    const sortMode = (
        document.getElementById(
            "prediction-sort"
        )?.value || "conviction"
    );

    const filtered = predictionCenterRows.filter(
        stock => {
            const matchesSearch = (
                !search
                || String(
                    stock.symbol || ""
                ).toLowerCase().includes(search)
                || String(
                    stock.name || ""
                ).toLowerCase().includes(search)
            );

            const matchesSignal = (
                !signal
                || stock.signal === signal
            );

            const matchesRisk = (
                !risk
                || stock.risk_level === risk
            );

            const matchesConviction = (
                predictionNumber(
                    stock.conviction_score
                ) >= minimumConviction
            );

            return (
                matchesSearch
                && matchesSignal
                && matchesRisk
                && matchesConviction
            );
        }
    );

    const sortKeys = {
        conviction: "conviction_score",
        confidence: "confidence",
        return: "expected_return",
        probability:
            "prediction_probability_pct",
        target: "target_price",
        rvol: "relative_volume",
    };

    const sortKey = (
        sortKeys[sortMode]
        || "conviction_score"
    );

    filtered.sort(
        (a, b) => (
            predictionNumber(b[sortKey])
            - predictionNumber(a[sortKey])
        )
    );

    container.innerHTML = "";

    filtered.forEach((stock, index) => {
        container.appendChild(
            buildPredictionCard(stock, index)
        );
    });

    if (!filtered.length) {
        container.innerHTML = `
            <div class="prediction-empty-state">
                No predictions match the selected filters.
            </div>
        `;
    }

    const count = document.getElementById(
        "prediction-visible-count"
    );

    if (count) {
        count.textContent = filtered.length;
    }
}

function initializePredictionFilters() {
    const ids = [
        "prediction-search",
        "prediction-signal-filter",
        "prediction-risk-filter",
        "prediction-conviction-filter",
        "prediction-sort",
    ];

    ids.forEach(id => {
        const element = document.getElementById(id);

        if (!element) {
            return;
        }

        element.addEventListener(
            element.tagName === "INPUT"
                ? "input"
                : "change",
            applyPredictionFilters
        );
    });

    const reset = document.getElementById(
        "prediction-reset"
    );

    if (reset) {
        reset.addEventListener("click", () => {
            ids.forEach(id => {
                const element = document.getElementById(id);

                if (!element) {
                    return;
                }

                if (
                    id === "prediction-conviction-filter"
                ) {
                    element.value = "0";
                } else if (
                    id === "prediction-sort"
                ) {
                    element.value = "conviction";
                } else {
                    element.value = "";
                }
            });

            applyPredictionFilters();
        });
    }
}

async function loadPredictionCenter() {
    const container = document.getElementById(
        "prediction-center-container"
    );

    if (!container) {
        return;
    }

    const status = document.getElementById(
        "prediction-center-status"
    );

    const errorBox = document.getElementById(
        "prediction-center-error"
    );

    try {
        if (status) {
            status.textContent = "Loading";
        }

        const response = await fetch(
            "/api/v11.6.4/prediction-center",
            {
                cache: "no-store",
                headers: {
                    "Accept": "application/json",
                },
            }
        );

        if (!response.ok) {
            throw new Error(
                `Prediction Center API returned ${
                    response.status
                }`
            );
        }

        const payload = await response.json();

        predictionCenterRows = (
            payload.predictions || []
        );

        renderMarketRegime(payload);
        renderPredictionSummary(payload);

        if (errorBox) {
            errorBox.hidden = true;
        }

        if (status) {
            status.textContent =
                `${predictionCenterRows.length} Live`;
        }

        applyPredictionFilters();

    } catch (error) {
        console.error(
            "Unable to load Prediction Center:",
            error
        );

        if (status) {
            status.textContent = "Unavailable";
        }

        if (errorBox) {
            errorBox.hidden = false;
            errorBox.textContent =
                "Prediction Center could not be loaded. " +
                "Please refresh the dashboard.";
        }

        container.innerHTML = `
            <div class="prediction-empty-state">
                Unified predictions are currently unavailable.
            </div>
        `;
    }
}

document.addEventListener(
    "DOMContentLoaded",
    () => {
        initializePredictionFilters();
        loadPredictionCenter();
    }
);
