let forecastFiltersState = {
    forecastYear: null,
    months: [],
    categories: []
};

let forecastCharts = {
    salesForecast: null,
    salesForecastCategoryPie: null,
    categoryForecast: null,
    categoryForecastPie: null
};

const FORECAST_COLORS = [
    "#2F80ED",
    "#F2994A",
    "#27AE60",
    "#9B51E0",
    "#EB5757",
    "#56CCF2",
    "#F2C94C",
    "#6FCF97",
    "#BB6BD9",
    "#2D9CDB"
];

const doughnutPercentLabelsPlugin = {
    id: "doughnutPercentLabelsPlugin",
    afterDatasetsDraw(chart) {
        if (chart.config.type !== "doughnut" && chart.config.type !== "pie") return;

        const { ctx } = chart;
        const dataset = chart.data.datasets?.[0];
        const meta = chart.getDatasetMeta(0);

        if (!dataset || !meta || !meta.data || !meta.data.length) return;

        const values = dataset.data.map(v => Number(v || 0));
        const total = values.reduce((sum, v) => sum + v, 0);

        if (!total) return;

        ctx.save();
        ctx.font = "600 12px Arial";
        ctx.fillStyle = "#ffffff";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";

        meta.data.forEach((arc, index) => {
            const value = values[index];
            if (!value) return;

            const percent = (value / total) * 100;
            if (percent < 4) return;

            const angle = (arc.startAngle + arc.endAngle) / 2;
            const radius = arc.innerRadius + (arc.outerRadius - arc.innerRadius) * 0.58;
            const x = arc.x + Math.cos(angle) * radius;
            const y = arc.y + Math.sin(angle) * radius;

            ctx.fillText(`${percent.toFixed(1)}%`, x, y);
        });

        ctx.restore();
    }
};

document.addEventListener("DOMContentLoaded", async () => {
    if (window.Chart && !Chart.registry.plugins.get("doughnutPercentLabelsPlugin")) {
        Chart.register(doughnutPercentLabelsPlugin);
    }

    bindForecastTabs();
    bindForecastButtons();
    await initializeForecastFilters();
    await loadAllForecastDashboardData();
});

function bindForecastTabs() {
    const tabs = [
        { buttonId: "tabSalesForecastBtn", contentId: "salesForecastTabContent" },
        { buttonId: "tabCategoryForecastBtn", contentId: "categoryForecastTabContent" }
    ];

    tabs.forEach(tab => {
        const button = document.getElementById(tab.buttonId);
        const content = document.getElementById(tab.contentId);

        if (!button || !content) return;

        button.addEventListener("click", () => {
            tabs.forEach(t => {
                const btn = document.getElementById(t.buttonId);
                const cnt = document.getElementById(t.contentId);
                if (btn) btn.classList.remove("active");
                if (cnt) cnt.classList.remove("active");
            });

            button.classList.add("active");
            content.classList.add("active");
        });
    });
}

function bindForecastButtons() {
    const applyBtn = document.getElementById("forecastApplyBtn");
    const resetBtn = document.getElementById("forecastResetBtn");

    if (applyBtn) {
        applyBtn.addEventListener("click", async () => {
            forecastFiltersState.months = getSelectedForecastMonths();
            forecastFiltersState.categories = getSelectedForecastCategories();
            await loadAllForecastDashboardData();
        });
    }

    if (resetBtn) {
        resetBtn.addEventListener("click", async () => {
            resetForecastFilters();
            forecastFiltersState.months = [];
            forecastFiltersState.categories = [];
            await loadAllForecastDashboardData();
        });
    }
}

async function initializeForecastFilters() {
    const response = await fetch("/api/forecast/filters");
    if (!response.ok) {
        throw new Error(`Failed to load forecast filters: ${response.status}`);
    }

    const data = await response.json();

    forecastFiltersState.forecastYear = data.forecast_year;
    renderForecastYearDisplay(data.forecast_year);
    renderForecastMonthFilters(data.months || []);
    renderForecastCategoryFilters(data.categories || []);

    forecastFiltersState.months = getSelectedForecastMonths();
    forecastFiltersState.categories = getSelectedForecastCategories();
}

function renderForecastYearDisplay(year) {
    const el = document.getElementById("forecastYearDisplay");
    if (!el) return;
    el.textContent = year ?? "-";
}

function renderForecastMonthFilters(months) {
    const container = document.getElementById("forecastMonthFilters");
    if (!container) return;

    container.innerHTML = "";

    if (!months.length) {
        container.innerHTML = `<div class="text-muted small">No months available</div>`;
        return;
    }

    months
        .slice()
        .sort((a, b) => Number(a.month_number) - Number(b.month_number))
        .forEach(month => {
            const option = document.createElement("label");
            option.className = "forecast-filter-option";

            option.innerHTML = `
                <input type="checkbox" name="forecastMonth" value="${month.month_number}">
                <span>${month.month_name}</span>
            `;

            container.appendChild(option);
        });
}

function renderForecastCategoryFilters(categories) {
    const container = document.getElementById("forecastCategoryFilters");
    if (!container) return;

    container.innerHTML = "";

    if (!categories.length) {
        container.innerHTML = `<div class="text-muted small">No categories available</div>`;
        return;
    }

    categories.forEach(category => {
        const option = document.createElement("label");
        option.className = "forecast-filter-option";

        option.innerHTML = `
            <input type="checkbox" name="forecastCategory" value="${category}">
            <span>${category}</span>
        `;

        container.appendChild(option);
    });
}

function getSelectedForecastMonths() {
    return Array.from(
        document.querySelectorAll("input[name='forecastMonth']:checked")
    ).map(input => parseInt(input.value, 10));
}

function getSelectedForecastCategories() {
    return Array.from(
        document.querySelectorAll("input[name='forecastCategory']:checked")
    ).map(input => input.value);
}

function resetForecastFilters() {
    document.querySelectorAll("input[name='forecastMonth']").forEach(input => {
        input.checked = false;
    });

    document.querySelectorAll("input[name='forecastCategory']").forEach(input => {
        input.checked = false;
    });
}

function buildQuery(params) {
    const search = new URLSearchParams();

    Object.entries(params).forEach(([key, value]) => {
        if (Array.isArray(value)) {
            value.forEach(v => search.append(key, v));
        } else if (value !== null && value !== undefined && value !== "") {
            search.append(key, value);
        }
    });

    return search.toString();
}

async function fetchJson(url, params = {}) {
    const query = buildQuery(params);
    const fullUrl = query ? `${url}?${query}` : url;

    const response = await fetch(fullUrl);
    if (!response.ok) {
        throw new Error(`Request failed: ${response.status} - ${fullUrl}`);
    }

    return await response.json();
}

function createOrReplaceChart(key, canvasId, config) {
    if (forecastCharts[key]) {
        forecastCharts[key].destroy();
    }

    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    forecastCharts[key] = new Chart(canvas, config);
}

function formatCurrency(value) {
    return new Intl.NumberFormat("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(Number(value || 0));
}

function formatNumber(value) {
    return new Intl.NumberFormat("en-US", {
        maximumFractionDigits: 0
    }).format(Number(value || 0));
}

function getColorMap(labels) {
    const map = {};
    labels.forEach((label, index) => {
        map[label] = FORECAST_COLORS[index % FORECAST_COLORS.length];
    });
    return map;
}

function buildHtmlLegend(containerId, labels, colorMap) {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = "";

    labels.forEach(label => {
        const item = document.createElement("div");
        item.className = "forecast-legend-item";

        item.innerHTML = `
            <span class="forecast-legend-swatch" style="background:${colorMap[label]}"></span>
            <span class="forecast-legend-label">${label}</span>
        `;

        container.appendChild(item);
    });
}

function createPieChart({ key, canvasId, legendContainerId, labels, values, chartType = "doughnut" }) {
    const colorMap = getColorMap(labels);
    const colors = labels.map(label => colorMap[label]);
    const total = values.reduce((sum, value) => sum + Number(value || 0), 0);

    buildHtmlLegend(legendContainerId, labels, colorMap);

    createOrReplaceChart(key, canvasId, {
        type: chartType,
        data: {
            labels,
            datasets: [
                {
                    data: values,
                    backgroundColor: colors,
                    borderColor: "#ffffff",
                    borderWidth: 2,
                    hoverOffset: 6
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: {
                padding: {
                    top: 4,
                    bottom: 4,
                    left: 4,
                    right: 4
                }
            },
            cutout: chartType === "doughnut" ? "56%" : undefined,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            const value = Number(context.raw || 0);
                            const percent = total ? ((value / total) * 100).toFixed(1) : "0.0";
                            return ` ${formatNumber(value)} (${percent}%)`;
                        }
                    }
                }
            }
        }
    });
}

function renderSalesForecastTable(rows) {
    const body = document.getElementById("salesForecastTableBody");
    const totalEl = document.getElementById("salesForecastTableTotal");

    if (!body || !totalEl) return;

    body.innerHTML = "";

    let total = 0;

    rows.forEach(row => {
        const sales = Number(row.Sales || 0);
        total += sales;

        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${row.Month}</td>
            <td class="text-end">${formatCurrency(sales)}</td>
        `;
        body.appendChild(tr);
    });

    totalEl.textContent = formatCurrency(total);
}

function renderCategoryForecastTable(rows) {
    const body = document.getElementById("categoryForecastTableBody");
    const totalEl = document.getElementById("categoryForecastTableTotal");

    if (!body || !totalEl) return;

    body.innerHTML = "";

    let total = 0;

    rows.forEach(row => {
        const transactions = Number(row.ForecastTransactions || 0);
        total += transactions;

        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${row.Category}</td>
            <td class="text-end">${formatNumber(transactions)}</td>
        `;
        body.appendChild(tr);
    });

    totalEl.textContent = formatNumber(total);
}

async function loadAllForecastDashboardData() {
    await Promise.all([
        loadSalesForecast(),
        loadCategoryForecast()
    ]);
}

async function loadSalesForecast() {
    const data = await fetchJson("/api/forecast/sales", {
        month: forecastFiltersState.months,
        category: forecastFiltersState.categories
    });

    const chartRows = data.chart || [];
    const tableRows = data.table || [];
    const pieRows = data.category_pie || [];

    renderSalesForecastTable(tableRows);

    createOrReplaceChart("salesForecast", "salesForecastChart", {
        type: "bar",
        data: {
            labels: chartRows.map(row => row.MonthLabel),
            datasets: [
                {
                    label: "Sales Forecast",
                    data: chartRows.map(row => Number(row.Sales || 0)),
                    borderColor: "#2388f2",
                    backgroundColor: "#2388f2",
                    borderWidth: 1,
                    borderRadius: 6,
                    borderSkipped: false,
                    barPercentage: 0.72,
                    categoryPercentage: 0.72
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: {
                padding: {
                    top: 4,
                    bottom: 0,
                    left: 6,
                    right: 6
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grace: 0,
                    ticks: {
                        padding: 6
                    },
                    title: {
                        display: true,
                        text: "Sales"
                    },
                    grid: {
                        drawBorder: false
                    }
                },
                x: {
                    offset: true,
                    ticks: {
                        padding: 4
                    },
                    title: {
                        display: false
                    },
                    grid: {
                        display: false,
                        drawBorder: false
                    }
                }
            }
        }
    });

    createPieChart({
        key: "salesForecastCategoryPie",
        canvasId: "salesForecastCategoryPieChart",
        legendContainerId: "salesForecastCategoryLegend",
        labels: pieRows.map(row => row.Category),
        values: pieRows.map(row => Number(row.Sales || 0)),
        chartType: "doughnut"
    });
}

async function loadCategoryForecast() {
    const data = await fetchJson("/api/forecast/category", {
        month: forecastFiltersState.months,
        category: forecastFiltersState.categories
    });

    const chartRows = data.chart || [];
    const tableRows = data.table || [];
    const pieRows = data.pie || [];

    renderCategoryForecastTable(tableRows);

    createOrReplaceChart("categoryForecast", "categoryForecastChart", {
        type: "bar",
        data: {
            labels: chartRows.map(row => row.Category),
            datasets: [
                {
                    label: "Forecast Transactions",
                    data: chartRows.map(row => Number(row.ForecastTransactions || 0)),
                    backgroundColor: "#2388f2",
                    borderColor: "#2388f2",
                    borderWidth: 1,
                    borderRadius: 6,
                    borderSkipped: false,
                    barPercentage: 0.72,
                    categoryPercentage: 0.72
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: {
                padding: {
                    top: 4,
                    bottom: 0,
                    left: 6,
                    right: 6
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grace: 0,
                    ticks: {
                        padding: 6
                    },
                    title: {
                        display: true,
                        text: "Transactions"
                    },
                    grid: {
                        drawBorder: false
                    }
                },
                x: {
                    offset: true,
                    ticks: {
                        padding: 4,
                        maxRotation: 0,
                        minRotation: 0
                    },
                    title: {
                        display: false
                    },
                    grid: {
                        display: false,
                        drawBorder: false
                    }
                }
            }
        }
    });

    createPieChart({
        key: "categoryForecastPie",
        canvasId: "categoryForecastPieChart",
        legendContainerId: "categoryForecastPieLegend",
        labels: pieRows.map(row => row.Category),
        values: pieRows.map(row => Number(row.ForecastTransactions || 0)),
        chartType: "doughnut"
    });
}