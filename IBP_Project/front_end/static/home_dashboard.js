document.addEventListener("DOMContentLoaded", () => {
  let salesPerformanceChart = null;

  function formatCurrency(value) {
    return new Intl.NumberFormat("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(value || 0);
  }

  function formatInteger(value) {
    return new Intl.NumberFormat("en-US", {
      maximumFractionDigits: 0
    }).format(value || 0);
  }

  function formatPercent(value) {
    return `${Number(value || 0).toFixed(2)}`;
  }

  async function fetchJson(url) {
    const res = await fetch(url);
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || "Failed request.");
    }

    return data;
  }

  async function loadSalesPerformanceChart() {
    const data = await fetchJson("/api/home/quarterly-sales-profit");

    const labels = data.map(item => `Qtr ${item.quarter}`);
    const salesData = data.map(item => item.sales);
    const profitData = data.map(item => item.profit);

    const yearLabels = data.map(item => item.year);

    const ctx = document.getElementById("salesPerformanceChart").getContext("2d");

    if (salesPerformanceChart) {
      salesPerformanceChart.destroy();
    }

    salesPerformanceChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: data.map(item => `Qtr ${item.quarter} ${item.year}`),
        datasets: [
          {
            label: "Sales",
            data: salesData,
            tension: 0.2,
            fill: false,
            borderWidth: 3
          },
          {
            label: "Profit",
            data: profitData,
            tension: 0.2,
            fill: false,
            borderWidth: 3
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "top",
            align: "end"
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              callback: function(value) {
                if (value >= 1000000) {
                  return (value / 1000000) + "M";
                }
                if (value >= 1000) {
                  return (value / 1000) + "K";
                }
                return value;
              }
            },
            title: {
              display: true,
              text: "Sales and Profit"
            }
          },
          x: {
            title: {
              display: true,
              text: "Quarter"
            }
          }
        }
      }
    });
  }

  async function loadYearlySummaryTables() {
    const data = await fetchJson("/api/home/yearly-summary");

    const revenueBody = document.getElementById("revenueTableBody");
    const profitBody = document.getElementById("profitTableBody");
    const marginBody = document.getElementById("marginTableBody");

    revenueBody.innerHTML = "";
    profitBody.innerHTML = "";
    marginBody.innerHTML = "";

    data.rows.forEach((row) => {
      revenueBody.innerHTML += `
        <tr>
          <td>${row.year}</td>
          <td class="text-end">${formatCurrency(row.revenue)}</td>
        </tr>
      `;

      profitBody.innerHTML += `
        <tr>
          <td>${row.year}</td>
          <td class="text-end">${formatCurrency(row.profit)}</td>
        </tr>
      `;

      marginBody.innerHTML += `
        <tr>
          <td>${row.year}</td>
          <td class="text-end">${formatPercent(row.margin)}</td>
        </tr>
      `;
    });

    document.getElementById("revenueTotal").textContent = formatCurrency(data.total_revenue);
    document.getElementById("profitTotal").textContent = formatCurrency(data.total_profit);
    document.getElementById("marginTotal").textContent = `${formatPercent(data.total_margin)}`;
  }

  async function loadTopProfitTable() {
    const data = await fetchJson("/api/home/top-profit-products");
    const tbody = document.getElementById("topProfitBody");
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

  async function loadTopBestSellersTable() {
    const data = await fetchJson("/api/home/top-best-sellers");
    const tbody = document.getElementById("topBestSellersBody");
    tbody.innerHTML = "";

    data.forEach((row) => {
      tbody.innerHTML += `
        <tr>
          <td>${row.product}</td>
          <td class="text-end">${formatInteger(row.transactions)}</td>
        </tr>
      `;
    });
  }

  async function loadTopCustomersTable() {
    const data = await fetchJson("/api/home/top-customers");
    const tbody = document.getElementById("topCustomersBody");
    tbody.innerHTML = "";

    data.forEach((row) => {
      tbody.innerHTML += `
        <tr>
          <td>${row.customer}</td>
          <td class="text-end">${formatInteger(row.transactions)}</td>
        </tr>
      `;
    });
  }

  async function initHomeDashboard() {
    await Promise.all([
      loadSalesPerformanceChart(),
      loadYearlySummaryTables(),
      loadTopProfitTable(),
      loadTopBestSellersTable(),
      loadTopCustomersTable()
    ]);
  }

  initHomeDashboard().catch((err) => {
    console.error(err);
    alert("Failed to load home dashboard.");
  });
});