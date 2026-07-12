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
    const mapping = {
        "breadth-advancers": breadth.advancers,
        "breadth-decliners": breadth.decliners,
        "breadth-unchanged": breadth.unchanged,
        "breadth-ratio": breadth.advance_decline_ratio,
    };

    Object.entries(mapping).forEach(([id, value]) => {
        const element = document.getElementById(id);

        if (element) {
            element.textContent = value ?? 0;
        }
    });

    const positiveBar = document.getElementById(
        "breadth-advance-bar"
    );

    const negativeBar = document.getElementById(
        "breadth-decline-bar"
    );

    if (positiveBar) {
        positiveBar.style.width =
            `${breadth.advancing_percentage || 0}%`;
    }

    if (negativeBar) {
        negativeBar.style.width =
            `${breadth.declining_percentage || 0}%`;
    }

    const leaderContainer = document.getElementById(
        "volume-leaders"
    );

    if (leaderContainer) {
        leaderContainer.innerHTML = "";

        (breadth.volume_leaders || [])
            .slice(0, 16)
            .forEach((stock, index) => {
                const row = document.createElement("div");

                row.className = "leader-row";

                row.innerHTML = `
                    <span>${index + 1}. ${stock.symbol}</span>
                    <strong>${Number(
                        stock.volume || 0
                    ).toLocaleString()}</strong>
                `;

                leaderContainer.appendChild(row);
            });
    }
}

async function loadDashboardCharts(symbol = "SCOM") {
    try {
        const response = await fetch(
            `/api/v11.5/dashboard-charts?symbol=${
                encodeURIComponent(symbol)
            }`
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
