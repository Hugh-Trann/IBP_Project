let reviewFiltersState = {
    year: null,
    month: [],
    categories: []
};

let reviewCharts = {
    summaryDirection: null,
    scoreMonthly: null,
    scoreCategory: null,
    sentimentMonthly: null,
    sentimentCategory: null,
    topicCount: null,
    topicSentiment: null
};

document.addEventListener("DOMContentLoaded", async () => {
    bindReviewTabs();
    bindReviewButtons();
    await initializeReviewFilters();
    await loadAllReviewDashboardData();
});

function bindReviewTabs() {
    const tabs = [
        { buttonId: "tabReviewSummaryBtn", contentId: "reviewSummaryTabContent" },
        { buttonId: "tabScoreReviewBtn", contentId: "scoreReviewTabContent" },
        { buttonId: "tabSentimentReviewBtn", contentId: "sentimentReviewTabContent" },
        { buttonId: "tabReviewTopicBtn", contentId: "reviewTopicTabContent" }
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

function bindReviewButtons() {
    const applyBtn = document.getElementById("reviewApplyBtn");
    const resetBtn = document.getElementById("reviewResetBtn");

    if (applyBtn) {
        applyBtn.addEventListener("click", async () => {
            reviewFiltersState.year = getSelectedReviewYear();
            reviewFiltersState.months = getSelectedReviewMonths();
            reviewFiltersState.categories = getSelectedReviewCategories();
            await loadAllReviewDashboardData();
        });
    }

    if (resetBtn) {
        resetBtn.addEventListener("click", async () => {
            resetReviewFilters();
            reviewFiltersState.year = getSelectedReviewYear();
            reviewFiltersState.months = [];
            reviewFiltersState.categories = [];
            await loadAllReviewDashboardData();
        });
    }
}

async function initializeReviewFilters() {
    const response = await fetch("/api/reviews/filters");
    if (!response.ok) {
        throw new Error(`Failed to load review filters: ${response.status}`);
    }

    const data = await response.json();

    renderReviewYearFilters(data.years || []);
    renderReviewMonthFilters(data.months_by_year || {});
    renderReviewCategoryFilters(data.categories || []);

    handleReviewYearChange();

    reviewFiltersState.year = getSelectedReviewYear();
    reviewFiltersState.months = getSelectedReviewMonths();
    reviewFiltersState.categories = getSelectedReviewCategories();
}

function renderReviewYearFilters(years) {
    const container = document.getElementById("reviewYearFilters");
    if (!container) return;

    container.innerHTML = "";

    if (!years.length) {
        container.innerHTML = `<div class="text-muted small">No years available</div>`;
        return;
    }

    years.forEach((year, index) => {
        const option = document.createElement("label");
        option.className = "review-filter-option";

        option.innerHTML = `
            <input type="radio" name="reviewYear" value="${year}" ${index === 0 ? "checked" : ""}>
            <span>${year}</span>
        `;

        container.appendChild(option);
    });

    container.querySelectorAll("input[name='reviewYear']").forEach(input => {
        input.addEventListener("change", handleReviewYearChange);
    });
}

function renderReviewMonthFilters(monthsByYear) {
    const container = document.getElementById("reviewMonthFilters");
    if (!container) return;

    container.dataset.monthsByYear = JSON.stringify(monthsByYear);
}

function renderReviewCategoryFilters(categories) {
    const container = document.getElementById("reviewCategoryFilters");
    if (!container) return;

    container.innerHTML = "";

    categories.forEach(category => {
        const option = document.createElement("label");
        option.className = "review-filter-option";

        option.innerHTML = `
            <input type="checkbox" name="reviewCategory" value="${escapeHtml(category)}">
            <span>${escapeHtml(category)}</span>
        `;

        container.appendChild(option);
    });
}

function handleReviewYearChange() {
    const selectedYear = getSelectedReviewYear();
    const monthContainer = document.getElementById("reviewMonthFilters");
    if (!monthContainer) return;

    const monthsByYear = JSON.parse(monthContainer.dataset.monthsByYear || "{}");
    const months = monthsByYear[String(selectedYear)] || [];

    monthContainer.innerHTML = "";

    if (!months.length) {
        monthContainer.innerHTML = `<div class="text-muted small">No months available</div>`;
        return;
    }

    months
        .slice()
        .sort((a, b) => Number(a.month_number) - Number(b.month_number))
        .forEach((month) => {
            const option = document.createElement("label");
            option.className = "review-filter-option";

            option.innerHTML = `
                <input type="checkbox" name="reviewMonth" value="${month.month_number}">
                <span>${month.month_name}</span>
            `;

            monthContainer.appendChild(option);
        });
}

function getSelectedReviewYear() {
    const selected = document.querySelector("input[name='reviewYear']:checked");
    return selected ? parseInt(selected.value, 10) : null;
}

function getSelectedReviewMonths() {
    return Array.from(
        document.querySelectorAll("input[name='reviewMonth']:checked")
    ).map(input => parseInt(input.value, 10));
}

function getSelectedReviewCategories() {
    return Array.from(
        document.querySelectorAll("input[name='reviewCategory']:checked")
    ).map(input => input.value);
}

function resetReviewFilters() {
    const yearInputs = document.querySelectorAll("input[name='reviewYear']");
    if (yearInputs.length > 0) {
        yearInputs.forEach((input, index) => {
            input.checked = index === 0;
        });
    }

    handleReviewYearChange();

    document.querySelectorAll("input[name='reviewCategory']").forEach(input => {
        input.checked = false;
    });
}

async function loadAllReviewDashboardData() {
    if (!reviewFiltersState.year) return;

    await Promise.all([
        loadReviewSummary(),
        loadReviewSummaryDirection(),
        loadScoreReview(),
        loadSentimentReview(),
        loadReviewTopic()
    ]);
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

function formatNumber(value) {
    return new Intl.NumberFormat("en-US").format(Number(value || 0));
}

function formatCurrency(value) {
    return new Intl.NumberFormat("en-US", {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(Number(value || 0));
}

function formatDecimal(value, digits = 2) {
    return Number(value || 0).toFixed(digits);
}

function escapeHtml(text) {
    return String(text ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function createOrReplaceChart(key, canvasId, config) {
    if (reviewCharts[key]) {
        reviewCharts[key].destroy();
    }

    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    reviewCharts[key] = new Chart(canvas, config);
}

function renderSimpleTable(bodyId, totalId, rows) {
    const body = document.getElementById(bodyId);
    const totalEl = document.getElementById(totalId);

    if (!body || !totalEl) return;

    body.innerHTML = "";

    let total = 0;

    rows.forEach(row => {
        const rowTotal = Number(row.Total || 0);
        total += rowTotal;

        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${escapeHtml(row.Category)}</td>
            <td class="text-end">${formatNumber(rowTotal)}</td>
        `;
        body.appendChild(tr);
    });

    totalEl.textContent = formatNumber(total);
}

function renderTopicCountTable(rows) {
    const body = document.getElementById("reviewTopicCountBody");
    const totalEl = document.getElementById("reviewTopicCountTotal");

    if (!body || !totalEl) return;

    body.innerHTML = "";

    let total = 0;

    rows.forEach(row => {
        const topic = row.Topic ?? "";
        const count = Number(row.TopicReviewCount || 0);
        total += count;

        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${escapeHtml(topic)}</td>
            <td class="text-end">${formatNumber(count)}</td>
        `;
        body.appendChild(tr);
    });

    totalEl.textContent = formatNumber(total);
}

function renderTopicSentimentTable(rows) {
    const body = document.getElementById("reviewTopicSentimentBody");
    const avgEl = document.getElementById("reviewTopicSentimentAvg");

    if (!body || !avgEl) return;

    body.innerHTML = "";

    let total = 0;
    let count = 0;

    rows.forEach(row => {
        const topic = row.Topic ?? "";
        const score = Number(row.AvgTopicSentimentScore || 0);

        total += score;
        count += 1;

        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${escapeHtml(topic)}</td>
            <td class="text-end">${formatDecimal(score)}</td>
        `;
        body.appendChild(tr);
    });

    avgEl.textContent = count ? formatDecimal(total / count) : "0.00";
}

async function loadReviewSummary() {
    const data = await fetchJson("/api/reviews/summary", {
        year: reviewFiltersState.year,
        month: reviewFiltersState.months,
        category: reviewFiltersState.categories
    });

    const cards = data.cards || {};
    const tables = data.tables || {};

    document.getElementById("reviewSummaryTotalReviews").textContent = formatNumber(cards.total_reviews);
    document.getElementById("reviewSummaryAvgScore").textContent = formatDecimal(cards.avg_review_score);
    document.getElementById("reviewSummaryPositiveReviews").textContent = formatNumber(cards.positive_reviews);
    document.getElementById("reviewSummaryNegativeReviews").textContent = formatNumber(cards.negative_reviews);

    renderSimpleTable("reviewPositiveBody", "reviewPositiveTotal", tables.positive || []);
    renderSimpleTable("reviewNeutralBody", "reviewNeutralTotal", tables.neutral || []);
    renderSimpleTable("reviewNegativeBody", "reviewNegativeTotal", tables.negative || []);
}

async function loadReviewSummaryDirection() {
    const data = await fetchJson("/api/reviews/summary-direction", {
        year: reviewFiltersState.year,
        category: reviewFiltersState.categories
    });

    const labels = data.map(row => row.MonthName);
    const positive = data.map(row => Number(row.PositiveReviews || 0));
    const neutral = data.map(row => Number(row.NeutralReviews || 0));
    const negative = data.map(row => Number(row.NegativeReviews || 0));

    createOrReplaceChart("summaryDirection", "reviewSummaryDirectionChart", {
        type: "bar",
        data: {
            labels,
            datasets: [
                {
                    label: "Positive",
                    data: positive,
                    backgroundColor: "#2388f2"
                },
                {
                    label: "Neutral",
                    data: neutral,
                    backgroundColor: "#1e3a8a"
                },
                {
                    label: "Negative",
                    data: negative,
                    backgroundColor: "#ea7a3c"
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: "index",
                intersect: false
            },
            plugins: {
                legend: {
                    position: "top",
                    align: "end"
                }
            },
            scales: {
                x: {
                    stacked: true
                },
                y: {
                    stacked: true,
                    beginAtZero: true
                }
            }
        }
    });
}

async function loadScoreReview() {
    const data = await fetchJson("/api/reviews/score", {
        year: reviewFiltersState.year,
        month: reviewFiltersState.months,
        category: reviewFiltersState.categories
    });

    const cards = data.cards || {};
    const monthlyChart = data.monthly_chart || [];
    const categoryChart = data.category_chart || [];

    document.getElementById("scoreReviewTotalSales").textContent = formatCurrency(cards.total_sales);
    document.getElementById("scoreReviewTotalTransactions").textContent = formatNumber(cards.total_transactions);
    document.getElementById("scoreReviewTotalReviews").textContent = formatNumber(cards.total_reviews);
    document.getElementById("scoreReviewAvgScore").textContent = formatDecimal(cards.avg_review_score);

    createOrReplaceChart("scoreMonthly", "scoreReviewMonthlyChart", {
        type: "bar",
        data: {
            labels: monthlyChart.map(row => row.MonthLabel),
            datasets: [
                {
                    type: "bar",
                    label: "Total Sales",
                    data: monthlyChart.map(row => Number(row.TotalSales || 0)),
                    backgroundColor: "#2388f2",
                    yAxisID: "y",
                    order: 1
                },
                {
                    type: "line",
                    label: "Avg Review Score",
                    data: monthlyChart.map(row => Number(row.AvgReviewScore || 0)),
                    borderColor: "#ea7a3c",
                    backgroundColor: "#ea7a3c",
                    tension: 0.25,
                    yAxisID: "y1",
                    order: 0,
                    pointRadius: 3,
                    pointHoverRadius: 4,
                    borderWidth: 3,
                    fill: false
                }
            ]
        },
        options: getDualAxisOptions("Total Sales", "Avg Review Score")
    });

    createOrReplaceChart("scoreCategory", "scoreReviewCategoryChart", {
        type: "bar",
        data: {
            labels: categoryChart.map(row => row.Category),
            datasets: [
                {
                    type: "bar",
                    label: "Total Sales",
                    data: categoryChart.map(row => Number(row.TotalSales || 0)),
                    backgroundColor: "#2388f2",
                    yAxisID: "y",
                    order: 1
                },
                {
                    type: "line",
                    label: "Avg Review Score",
                    data: categoryChart.map(row => Number(row.AvgReviewScore || 0)),
                    borderColor: "#ea7a3c",
                    backgroundColor: "#ea7a3c",
                    tension: 0.25,
                    yAxisID: "y1",
                    order: 0,
                    pointRadius: 3,
                    pointHoverRadius: 4,
                    borderWidth: 3,
                    fill: false
                }
            ]
        },
        options: getDualAxisOptions("Total Sales", "Avg Review Score")
    });
}

async function loadSentimentReview() {
    const data = await fetchJson("/api/reviews/sentiment", {
        year: reviewFiltersState.year,
        month: reviewFiltersState.months,
        category: reviewFiltersState.categories
    });

    const cards = data.cards || {};
    const monthlyChart = data.monthly_chart || [];
    const categoryChart = data.category_chart || [];

    document.getElementById("sentimentReviewTotalSales").textContent = formatCurrency(cards.total_sales);
    document.getElementById("sentimentReviewTotalTransactions").textContent = formatNumber(cards.total_transactions);
    document.getElementById("sentimentReviewTotalReviews").textContent = formatNumber(cards.total_reviews);
    document.getElementById("sentimentReviewAvgScore").textContent = formatDecimal(cards.avg_sentiment_score);

    createOrReplaceChart("sentimentMonthly", "sentimentReviewMonthlyChart", {
        type: "bar",
        data: {
            labels: monthlyChart.map(row => row.MonthLabel),
            datasets: [
                {
                    type: "bar",
                    label: "Total Sales",
                    data: monthlyChart.map(row => Number(row.TotalSales || 0)),
                    backgroundColor: "#2388f2",
                    yAxisID: "y",
                    order: 1
                },
                {
                    type: "line",
                    label: "Avg Sentiment Score",
                    data: monthlyChart.map(row => Number(row.AvgSentimentScore || 0)),
                    borderColor: "#ea7a3c",
                    backgroundColor: "#ea7a3c",
                    tension: 0.25,
                    yAxisID: "y1",
                    order: 0,
                    pointRadius: 3,
                    pointHoverRadius: 4,
                    borderWidth: 3,
                    fill: false
                }
            ]
        },
        options: getDualAxisOptions("Total Sales", "Avg Sentiment Score")
    });

    createOrReplaceChart("sentimentCategory", "sentimentReviewCategoryChart", {
        type: "bar",
        data: {
            labels: categoryChart.map(row => row.Category),
            datasets: [
                {
                    type: "bar",
                    label: "Total Sales",
                    data: categoryChart.map(row => Number(row.TotalSales || 0)),
                    backgroundColor: "#2388f2",
                    yAxisID: "y",
                    order: 1
                },
                {
                    type: "line",
                    label: "Avg Sentiment Score",
                    data: categoryChart.map(row => Number(row.AvgSentimentScore || 0)),
                    borderColor: "#ea7a3c",
                    backgroundColor: "#ea7a3c",
                    tension: 0.25,
                    yAxisID: "y1",
                    order: 0,
                    pointRadius: 3,
                    pointHoverRadius: 4,
                    borderWidth: 3,
                    fill: false
                }
            ]
        },
        options: getDualAxisOptions("Total Sales", "Avg Sentiment Score")
    });
}

async function loadReviewTopic() {
    const data = await fetchJson("/api/reviews/topic", {
        year: reviewFiltersState.year,
        month: reviewFiltersState.months,
        category: reviewFiltersState.categories
    });

    const topicCountChart = data.topic_count_chart || [];
    const topicSentimentChart = data.topic_sentiment_chart || [];

    renderTopicCountTable(topicCountChart);
    renderTopicSentimentTable(topicSentimentChart);

    createOrReplaceChart("topicCount", "reviewTopicCountChart", {
        type: "bar",
        data: {
            labels: topicCountChart.map(row => row.Topic),
            datasets: [
                {
                    label: "Reviews",
                    data: topicCountChart.map(row => Number(row.TopicReviewCount || 0)),
                    backgroundColor: "#2388f2"
                }
            ]
        },
        options: getSingleAxisBarOptions("Number of Reviews")
    });

    createOrReplaceChart("topicSentiment", "reviewTopicSentimentChart", {
        type: "bar",
        data: {
            labels: topicSentimentChart.map(row => row.Topic),
            datasets: [
                {
                    label: "Avg Sentiment Score",
                    data: topicSentimentChart.map(row => Number(row.AvgTopicSentimentScore || 0)),
                    backgroundColor: "#2388f2"
                }
            ]
        },
        options: getSingleAxisBarOptions("Avg Sentiment Score")
    });
}

function getDualAxisOptions(leftTitle, rightTitle) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
            mode: "index",
            intersect: false
        },
        plugins: {
            legend: {
                position: "top",
                align: "end"
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                title: {
                    display: true,
                    text: leftTitle
                }
            },
            y1: {
                beginAtZero: true,
                position: "right",
                grid: {
                    drawOnChartArea: false
                },
                title: {
                    display: true,
                    text: rightTitle
                }
            }
        }
    };
}

function getSingleAxisBarOptions(yTitle) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: true,
                position: "top",
                align: "end"
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                title: {
                    display: true,
                    text: yTitle
                }
            }
        }
    };
}