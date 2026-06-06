document.addEventListener("DOMContentLoaded", () => {
  let activeTab = "daily";

  let dailyOrdersChart = null;
  let dailySalesChart = null;
  let dailyProfitChart = null;
  let monthlyRevenueProfitChart = null;
  let comparisonSalesChart = null;
  let comparisonProfitChart = null;

  const tabDailyBtn = document.getElementById("tabDailyBtn");
  const tabMonthlyBtn = document.getElementById("tabMonthlyBtn");
  const tabComparisonBtn = document.getElementById("tabComparisonBtn");

  const dailyTabContent = document.getElementById("dailyTabContent");
  const monthlyTabContent = document.getElementById("monthlyTabContent");
  const comparisonTabContent = document.getElementById("comparisonTabContent");

  const salesNativeLayout = document.getElementById("salesNativeLayout");
  const salesFilterPanel = document.getElementById("salesFilterPanel");

  const salesYearFilters = document.getElementById("salesYearFilters");
  const salesMonthFilters = document.getElementById("salesMonthFilters");
  const salesDayFilters = document.getElementById("salesDayFilters");
  const salesDayFilterGroup = document.getElementById("salesDayFilterGroup");
  const salesApplyBtn = document.getElementById("salesApplyBtn");
  const salesResetBtn = document.getElementById("salesResetBtn");

  const compareMode = document.getElementById("compareMode");
  const compareYear1 = document.getElementById("compareYear1");
  const compareMonth1 = document.getElementById("compareMonth1");
  const compareYear2 = document.getElementById("compareYear2");
  const compareMonth2 = document.getElementById("compareMonth2");
  const salesComparisonApplyBtn = document.getElementById("salesComparisonApplyBtn");
  const salesComparisonResetBtn = document.getElementById("salesComparisonResetBtn");
  const comparisonSalesTitle = document.getElementById("comparisonSalesTitle");
  const comparisonProfitTitle = document.getElementById("comparisonProfitTitle");

  let defaultFilters = {
    year: [],
    month: [],
    day: []
  };

  let comparisonDefaults = null;

  const CATEGORY_COLORS = [
    "#2F80ED",
    "#F2994A",
    "#27AE60",
    "#9B51E0",
    "#EB5757",
    "#56CCF2",
    "#F2C94C",
    "#6FCF97",
    "#BB6BD9",
    "#2D9CDB",
    "#219653",
    "#F66D44"
  ];

  const SERIES_COLORS = [
    "#2F80ED",
    "#EB5757",
    "#27AE60",
    "#F2994A",
    "#9B51E0",
    "#56CCF2"
  ];

  function formatCurrency(value) {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 2
    }).format(Number(value || 0));
  }

  function formatCompactCurrency(value) {
    const num = Number(value || 0);
    if (num >= 1000000) return `$${(num / 1000000).toFixed(2)}M`;
    if (num >= 1000) return `$${(num / 1000).toFixed(2)}K`;
    return formatCurrency(num);
  }

  function formatNumber(value) {
    return new Intl.NumberFormat("en-US", {
      maximumFractionDigits: 0
    }).format(Number(value || 0));
  }

  async function fetchJson(url, fallbackValue = null) {
    try {
      const res = await fetch(url);
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || `Request failed: ${url}`);
      }
      return data;
    } catch (err) {
      console.error("Fetch error:", url, err);
      if (fallbackValue !== null) return fallbackValue;
      throw err;
    }
  }

  function getCategoryColorMap(labels) {
    const map = {};
    labels.forEach((label, index) => {
      map[label] = CATEGORY_COLORS[index % CATEGORY_COLORS.length];
    });
    return map;
  }

  function renderCheckboxList(container, items, filterName, selectedValues, labelFn = (v) => v) {
    if (!container) return;

    container.innerHTML = "";

    items.forEach((item) => {
      const value = typeof item === "object" ? item.value : item;
      const label = typeof item === "object" ? item.label : labelFn(item);

      const wrapper = document.createElement("label");
      wrapper.className = "sales-check-item";

      wrapper.innerHTML = `
        <input type="checkbox" data-filter="${filterName}" value="${value}">
        <span>${label}</span>
      `;

      const input = wrapper.querySelector("input");
      if (
        selectedValues.includes(Number(value)) ||
        selectedValues.includes(String(value))
      ) {
        input.checked = true;
      }

      container.appendChild(wrapper);
    });
  }

  function renderDayGrid(container, days, selectedValues) {
    if (!container) return;

    container.innerHTML = "";

    days.forEach((day) => {
      const isSelected =
        selectedValues.includes(Number(day)) ||
        selectedValues.includes(String(day));

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = `sales-day-btn ${isSelected ? "active" : ""}`;
      btn.dataset.filter = "day";
      btn.dataset.value = day;
      btn.textContent = day;

      btn.addEventListener("click", () => {
        btn.classList.toggle("active");
      });

      container.appendChild(btn);
    });
  }

  function getCheckedValues(filterName) {
    if (filterName === "day") {
      return Array.from(document.querySelectorAll(".sales-day-btn.active"))
        .map((el) => Number(el.dataset.value))
        .sort((a, b) => a - b);
    }

    return Array.from(
      document.querySelectorAll(`input[data-filter="${filterName}"]:checked`)
    )
      .map((el) => Number(el.value))
      .sort((a, b) => a - b);
  }

  function buildFilterQuery(includeDays = true) {
    const params = new URLSearchParams();

    getCheckedValues("year").forEach((value) => params.append("year", value));
    getCheckedValues("month").forEach((value) => params.append("month", value));

    if (includeDays) {
      getCheckedValues("day").forEach((value) => params.append("day", value));
    }

    return params.toString();
  }

  async function loadFilterOptions(preserveCurrent = false) {
    const yearValues = preserveCurrent ? getCheckedValues("year") : [];
    const monthValues = preserveCurrent ? getCheckedValues("month") : [];

    const params = new URLSearchParams();
    yearValues.forEach((v) => params.append("year", v));
    monthValues.forEach((v) => params.append("month", v));

    const url = params.toString()
      ? `/api/sales/filter-options?${params.toString()}`
      : `/api/sales/filter-options`;

    const data = await fetchJson(url, {
      years: [],
      months: [],
      days: [],
      defaults: { year: null, month: null, day: null }
    });

    if (!preserveCurrent) {
      defaultFilters = {
        year: data.defaults.year ? [data.defaults.year] : [],
        month: data.defaults.month ? [data.defaults.month] : [],
        day: data.defaults.day ? [data.defaults.day] : []
      };
    }

    const selectedYears = preserveCurrent ? yearValues : defaultFilters.year;
    const selectedMonths = preserveCurrent ? monthValues : defaultFilters.month;

    let selectedDays = preserveCurrent ? getCheckedValues("day") : defaultFilters.day;
    selectedDays = selectedDays.filter((d) => data.days.includes(d));

    if (!preserveCurrent && selectedDays.length === 0 && data.defaults.day) {
      selectedDays = [data.defaults.day];
    }

    renderCheckboxList(salesYearFilters, data.years, "year", selectedYears);
    renderCheckboxList(salesMonthFilters, data.months, "month", selectedMonths);
    renderDayGrid(salesDayFilters, data.days, selectedDays);
  }

  function setActiveTab(tabName) {
    activeTab = tabName;

    if (tabDailyBtn) tabDailyBtn.classList.toggle("active", tabName === "daily");
    if (tabMonthlyBtn) tabMonthlyBtn.classList.toggle("active", tabName === "monthly");
    if (tabComparisonBtn) tabComparisonBtn.classList.toggle("active", tabName === "comparison");

    if (dailyTabContent) dailyTabContent.classList.toggle("active", tabName === "daily");
    if (monthlyTabContent) monthlyTabContent.classList.toggle("active", tabName === "monthly");
    if (comparisonTabContent) comparisonTabContent.classList.toggle("active", tabName === "comparison");

    const isComparison = tabName === "comparison";

    if (salesNativeLayout) {
      salesNativeLayout.classList.toggle("comparison-mode", isComparison);
    }

    if (salesFilterPanel) {
      salesFilterPanel.style.display = isComparison ? "none" : "";
    }

    if (salesDayFilterGroup) {
      salesDayFilterGroup.style.display = tabName === "daily" ? "block" : "none";
    }

    if (tabName !== "daily") {
      document
        .querySelectorAll(".sales-day-btn.active")
        .forEach((btn) => btn.classList.remove("active"));
    }

    toggleComparisonMonthFields();
  }

  function buildHtmlLegend(containerId, labels, colorMap) {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = "";

    labels.forEach((label) => {
      const item = document.createElement("div");
      item.className = "sales-chart-legend-item";

      item.innerHTML = `
        <span class="sales-chart-legend-swatch" style="background:${colorMap[label]}"></span>
        <span class="sales-chart-legend-label">${label}</span>
      `;

      container.appendChild(item);
    });
  }

  const piePercentLabelsPlugin = {
    id: "piePercentLabelsPlugin",
    afterDatasetsDraw(chart) {
      const { ctx } = chart;
      const dataset = chart.data.datasets[0];
      const meta = chart.getDatasetMeta(0);

      if (!dataset || !meta || !meta.data || !meta.data.length) {
        return;
      }

      const values = dataset.data.map((v) => Number(v || 0));
      const total = values.reduce((sum, v) => sum + v, 0);

      if (!total) return;

      ctx.save();
      ctx.font = "700 12px Arial";
      ctx.fillStyle = "#ffffff";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";

      meta.data.forEach((arc, index) => {
        const value = values[index];
        const percent = (value / total) * 100;

        if (percent < 4) return;

        const position = arc.tooltipPosition();
        ctx.fillText(`${percent.toFixed(1)}%`, position.x, position.y);
      });

      ctx.restore();
    }
  };

  function createPieChart({
    canvasId,
    legendContainerId,
    chartType = "pie",
    labels,
    values,
    tooltipValueFormatter
  }) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;

    const colorMap = getCategoryColorMap(labels);
    const colors = labels.map((label) => colorMap[label]);
    const total = values.reduce((sum, val) => sum + Number(val || 0), 0);

    buildHtmlLegend(legendContainerId, labels, colorMap);

    return new Chart(canvas.getContext("2d"), {
      type: chartType,
      data: {
        labels,
        datasets: [
          {
            data: values,
            backgroundColor: colors,
            borderColor: "#ffffff",
            borderWidth: 2,
            hoverOffset: 10
          }
        ]
      },
      plugins: [piePercentLabelsPlugin],
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: chartType === "doughnut" ? "60%" : undefined,
        layout: {
          padding: 12
        },
        plugins: {
          legend: {
            display: false
          },
          tooltip: {
            callbacks: {
              label: function (context) {
                const value = Number(context.raw || 0);
                const percent = total ? ((value / total) * 100).toFixed(1) : "0.0";
                return ` ${tooltipValueFormatter(value)} (${percent}%)`;
              }
            }
          }
        }
      }
    });
  }

  function createLineChart(canvasId, labels, series, valueFormatter = formatCurrency) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;

    return new Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        labels,
        datasets: series.map((item, index) => ({
          label: item.label,
          data: item.data,
          tension: 0.25,
          fill: false,
          borderWidth: 3,
          borderColor: item.color || SERIES_COLORS[index % SERIES_COLORS.length],
          backgroundColor: item.color || SERIES_COLORS[index % SERIES_COLORS.length],
          pointRadius: 3,
          pointHoverRadius: 5
        }))
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: "index",
          intersect: false
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              callback: (value) => valueFormatter(value)
            }
          }
        },
        plugins: {
          legend: {
            display: true,
            position: "top",
            align: "end"
          },
          tooltip: {
            callbacks: {
              label: function (context) {
                return `${context.dataset.label}: ${valueFormatter(context.raw)}`;
              }
            }
          }
        }
      }
    });
  }

  async function loadDailySummary() {
    const qs = buildFilterQuery(true);
    const data = await fetchJson(`/api/sales/daily/summary?${qs}`, {
      rows: [],
      total_sales: 0,
      total_profit: 0,
      total_transactions: 0
    });

    const tbody = document.getElementById("dailySummaryBody");
    if (!tbody) return;

    tbody.innerHTML = "";

    data.rows.forEach((row) => {
      tbody.innerHTML += `
        <tr>
          <td>${row.category}</td>
          <td class="text-end">${formatCurrency(row.sales)}</td>
          <td class="text-end">${formatCurrency(row.profit)}</td>
          <td class="text-end">${formatNumber(row.transactions)}</td>
        </tr>
      `;
    });

    document.getElementById("dailySummaryTotalSales").textContent = formatCurrency(data.total_sales);
    document.getElementById("dailySummaryTotalProfit").textContent = formatCurrency(data.total_profit);
    document.getElementById("dailySummaryTotalTransactions").textContent = formatNumber(data.total_transactions);
  }

  async function loadDailyAvgTransaction() {
    const qs = buildFilterQuery(true);
    const data = await fetchJson(`/api/sales/daily/avg-transaction?${qs}`, {
      avg_transaction_value: 0
    });

    const el = document.getElementById("dailyAvgTransactionValue");
    if (el) {
      el.textContent = formatCurrency(data.avg_transaction_value);
    }
  }

  async function loadDailyOrdersChart() {
    const qs = buildFilterQuery(true);
    const data = await fetchJson(`/api/sales/daily/orders-by-category?${qs}`, []);

    if (dailyOrdersChart) {
      dailyOrdersChart.destroy();
    }

    dailyOrdersChart = createPieChart({
      canvasId: "dailyOrdersByCategoryChart",
      legendContainerId: "dailyOrdersLegend",
      chartType: "pie",
      labels: data.map((x) => x.category),
      values: data.map((x) => Number(x.orders || 0)),
      tooltipValueFormatter: (value) => formatNumber(value)
    });
  }

  async function loadDailySalesChart() {
    const qs = buildFilterQuery(true);
    const data = await fetchJson(`/api/sales/daily/sales-by-category?${qs}`, []);

    if (dailySalesChart) {
      dailySalesChart.destroy();
    }

    dailySalesChart = createPieChart({
      canvasId: "dailySalesByCategoryChart",
      legendContainerId: "dailySalesLegend",
      chartType: "doughnut",
      labels: data.map((x) => x.category),
      values: data.map((x) => Number(x.sales || 0)),
      tooltipValueFormatter: (value) => formatCurrency(value)
    });
  }

  async function loadDailyProfitChart() {
    const qs = buildFilterQuery(true);
    const data = await fetchJson(`/api/sales/daily/profit-by-category?${qs}`, []);

    if (dailyProfitChart) {
      dailyProfitChart.destroy();
    }

    dailyProfitChart = createPieChart({
      canvasId: "dailyProfitByCategoryChart",
      legendContainerId: "dailyProfitLegend",
      chartType: "doughnut",
      labels: data.map((x) => x.category),
      values: data.map((x) => Number(x.profit || 0)),
      tooltipValueFormatter: (value) => formatCurrency(value)
    });
  }

  async function loadMonthlyTopProfit() {
    const qs = buildFilterQuery(false);
    const data = await fetchJson(`/api/sales/monthly/top-profit?${qs}`, []);

    const tbody = document.getElementById("monthlyTopProfitBody");
    if (!tbody) return;
    tbody.innerHTML = "";

    data.forEach((row) => {
      tbody.innerHTML += `
        <tr>
          <td>${row.product}</td>
          <td class="text-end">${formatCurrency(row.profit)}</td>
        </tr>
      `;
    });
  }

  async function loadMonthlyTopBestSellers() {
    const qs = buildFilterQuery(false);
    const data = await fetchJson(`/api/sales/monthly/top-best-sellers?${qs}`, []);

    const tbody = document.getElementById("monthlyTopBestSellersBody");
    if (!tbody) return;
    tbody.innerHTML = "";

    data.forEach((row) => {
      tbody.innerHTML += `
        <tr>
          <td>${row.product}</td>
          <td class="text-end">${formatNumber(row.transactions)}</td>
        </tr>
      `;
    });
  }

  async function loadMonthlyTopCustomers() {
    const qs = buildFilterQuery(false);
    const data = await fetchJson(`/api/sales/monthly/top-customers?${qs}`, []);

    const tbody = document.getElementById("monthlyTopCustomersBody");
    if (!tbody) return;
    tbody.innerHTML = "";

    data.forEach((row) => {
      tbody.innerHTML += `
        <tr>
          <td>${row.customer}</td>
          <td class="text-end">${formatNumber(row.transactions)}</td>
        </tr>
      `;
    });
  }

  async function loadMonthlyKpis() {
    const qs = buildFilterQuery(false);
    const data = await fetchJson(`/api/sales/monthly/kpis?${qs}`, {
      total_revenue: 0,
      total_profit: 0,
      profit_margin: 0,
      customer_visit: 0
    });

    document.getElementById("monthlyTotalRevenue").textContent = formatCompactCurrency(data.total_revenue);
    document.getElementById("monthlyTotalProfit").textContent = formatCompactCurrency(data.total_profit);
    document.getElementById("monthlyProfitMargin").textContent = Number(data.profit_margin || 0).toFixed(2);
    document.getElementById("monthlyCustomerVisit").textContent = formatNumber(data.customer_visit);
  }

  async function loadMonthlyRevenueProfitChart() {
    const qs = buildFilterQuery(false);
    const data = await fetchJson(`/api/sales/monthly/revenue-profit-by-day?${qs}`, []);

    const canvas = document.getElementById("monthlyRevenueProfitByDayChart");
    if (!canvas) return;

    if (monthlyRevenueProfitChart) {
      monthlyRevenueProfitChart.destroy();
    }

    monthlyRevenueProfitChart = new Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        labels: data.map((x) => x.day),
        datasets: [
          {
            label: "Sales",
            data: data.map((x) => x.sales),
            tension: 0.25,
            fill: false,
            borderWidth: 3,
            borderColor: SERIES_COLORS[0],
            backgroundColor: SERIES_COLORS[0]
          },
          {
            label: "Profit",
            data: data.map((x) => x.profit),
            tension: 0.25,
            fill: false,
            borderWidth: 3,
            borderColor: SERIES_COLORS[1],
            backgroundColor: SERIES_COLORS[1]
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: true,
            position: "top",
            align: "end"
          }
        }
      }
    });
  }

  async function loadDailyDashboard() {
    await loadDailySummary();
    await loadDailyAvgTransaction();
    await loadDailyOrdersChart();
    await loadDailySalesChart();
    await loadDailyProfitChart();
  }

  async function loadMonthlyDashboard() {
    await loadMonthlyTopProfit();
    await loadMonthlyTopBestSellers();
    await loadMonthlyTopCustomers();
    await loadMonthlyKpis();
    await loadMonthlyRevenueProfitChart();
  }

  function fillSelectOptions(selectEl, options, selectedValue = null, placeholder = null) {
    if (!selectEl) return;
    selectEl.innerHTML = "";

    if (placeholder) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = placeholder;
      selectEl.appendChild(opt);
    }

    options.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.value;
      option.textContent = item.label;
      if (String(item.value) === String(selectedValue)) {
        option.selected = true;
      }
      selectEl.appendChild(option);
    });
  }

  function getMonthOptionsForComparison(months) {
    return (months || []).map((m) => ({
      value: m.value,
      label: m.label
    }));
  }

  async function loadComparisonOptions(resetToDefault = false) {
    const data = await fetchJson(`/api/sales/comparison/options`, {
      years: [],
      months: [],
      defaults: {
        mode: "yoy",
        year1: null,
        year2: null,
        month1: null,
        month2: null
      }
    });

    if (!comparisonDefaults || resetToDefault) {
      comparisonDefaults = data.defaults;
    }

    const yearOptions = (data.years || []).map((year) => ({
      value: year,
      label: year
    }));

    const monthOptions = getMonthOptionsForComparison(data.months);

    const defaults = resetToDefault ? data.defaults : (comparisonDefaults || data.defaults);

    fillSelectOptions(compareYear1, yearOptions, defaults.year1);
    fillSelectOptions(compareYear2, yearOptions, defaults.year2);
    fillSelectOptions(compareMonth1, monthOptions, defaults.month1);
    fillSelectOptions(compareMonth2, monthOptions, defaults.month2);

    if (compareMode) {
      compareMode.value = defaults.mode || "yoy";
    }

    toggleComparisonMonthFields();
  }

  function toggleComparisonMonthFields() {
    const showMonths = compareMode && compareMode.value === "mom";
    document.querySelectorAll(".comparison-month-field").forEach((el) => {
      el.style.display = showMonths ? "block" : "none";
    });
  }

  function getComparisonQuery() {
    const params = new URLSearchParams();
    params.append("mode", compareMode.value);
    params.append("period1_year", compareYear1.value);
    params.append("period2_year", compareYear2.value);

    if (compareMode.value === "mom") {
      params.append("period1_month", compareMonth1.value);
      params.append("period2_month", compareMonth2.value);
    }

    return params.toString();
  }

  async function loadComparisonCharts() {
    const qs = getComparisonQuery();
    const data = await fetchJson(`/api/sales/comparison?${qs}`, {
      mode: "yoy",
      labels: [],
      sales_series: [],
      profit_series: [],
      title_suffix: ""
    });

    if (comparisonSalesChart) {
      comparisonSalesChart.destroy();
    }
    if (comparisonProfitChart) {
      comparisonProfitChart.destroy();
    }

    if (comparisonSalesTitle) {
      comparisonSalesTitle.textContent = `Comparative sales trends ${data.title_suffix || ""}`.trim();
    }
    if (comparisonProfitTitle) {
      comparisonProfitTitle.textContent = `Comparative profit trends ${data.title_suffix || ""}`.trim();
    }

    const salesSeries = (data.sales_series || []).map((item, index) => ({
      ...item,
      color: SERIES_COLORS[index % SERIES_COLORS.length]
    }));

    const profitSeries = (data.profit_series || []).map((item, index) => ({
      ...item,
      color: SERIES_COLORS[index % SERIES_COLORS.length]
    }));

    comparisonSalesChart = createLineChart(
      "comparisonSalesChart",
      data.labels || [],
      salesSeries,
      formatCurrency
    );

    comparisonProfitChart = createLineChart(
      "comparisonProfitChart",
      data.labels || [],
      profitSeries,
      formatCurrency
    );
  }

  async function loadComparisonDashboard() {
    await loadComparisonCharts();
  }

  async function loadActiveTab() {
    if (activeTab === "daily") {
      await loadDailyDashboard();
    } else if (activeTab === "monthly") {
      await loadMonthlyDashboard();
    } else {
      await loadComparisonDashboard();
    }
  }

  if (tabDailyBtn) {
    tabDailyBtn.addEventListener("click", async () => {
      setActiveTab("daily");
      await loadDailyDashboard();
    });
  }

  if (tabMonthlyBtn) {
    tabMonthlyBtn.addEventListener("click", async () => {
      setActiveTab("monthly");
      await loadMonthlyDashboard();
    });
  }

  if (tabComparisonBtn) {
    tabComparisonBtn.addEventListener("click", async () => {
      setActiveTab("comparison");
      await loadComparisonDashboard();
    });
  }

  if (compareMode) {
    compareMode.addEventListener("change", () => {
      toggleComparisonMonthFields();
    });
  }

  if (salesApplyBtn) {
    salesApplyBtn.addEventListener("click", async () => {
      try {
        await loadFilterOptions(true);
        if (activeTab !== "comparison") {
          await loadActiveTab();
        }
      } catch (err) {
        console.error(err);
      }
    });
  }

  if (salesResetBtn) {
    salesResetBtn.addEventListener("click", async () => {
      try {
        await loadFilterOptions(false);
        if (activeTab !== "comparison") {
          await loadActiveTab();
        }
      } catch (err) {
        console.error(err);
      }
    });
  }

  if (salesComparisonApplyBtn) {
    salesComparisonApplyBtn.addEventListener("click", async () => {
      try {
        await loadComparisonDashboard();
      } catch (err) {
        console.error(err);
      }
    });
  }

  if (salesComparisonResetBtn) {
    salesComparisonResetBtn.addEventListener("click", async () => {
      try {
        await loadComparisonOptions(true);
        await loadComparisonDashboard();
      } catch (err) {
        console.error(err);
      }
    });
  }

  async function init() {
    await loadFilterOptions(false);
    await loadComparisonOptions(true);
    setActiveTab("daily");
    await loadDailyDashboard();
  }

  init().catch((err) => {
    console.error(err);
  });
});