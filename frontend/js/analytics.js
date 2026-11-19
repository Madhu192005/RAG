/**
 * WasteWise AI – analytics.js (Step 2)
 * --------------------------------------
 * Multi-chart dashboard using Chart.js.
 * Implements:
 *   1. Monthly collection bar chart
 *   2. Stream composition doughnut chart
 *   3. Diversion efficiency curve (line chart)
 *   4. Top diverted streams horizontal bar chart
 * All datasets are clearly documented as illustrative demo metrics.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Chart.js global typography styling
  if (typeof Chart !== "undefined") {
    Chart.defaults.font.family = "'Segoe UI', system-ui, -apple-system, sans-serif";
    Chart.defaults.color = "#5a6b5b";
  }

  initMonthlyCollectionChart();
  initMaterialCategoryChart();
  initDiversionTrendChart();
  initTopStreamsChart();
  initExportAction();
});

/**
 * 1. Monthly Collection vs Diversion Bar Chart
 */
function initMonthlyCollectionChart() {
  const canvas = document.getElementById("monthlyCollectionChart");
  if (!canvas) return;

  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const totalCollected = [1200, 1340, 1420, 1550, 1610, 1750, 1820, 1900, 1740, 1880, 1940, 1850];
  const totalDiverted  = [ 780,  890,  980, 1090, 1180, 1290, 1360, 1420, 1310, 1430, 1490, 1420];

  new Chart(canvas.getContext("2d"), {
    type: "bar",
    data: {
      labels: months,
      datasets: [
        {
          label: "Gross Waste Collected (kg)",
          data: totalCollected,
          backgroundColor: "rgba(141, 110, 99, 0.4)",
          borderColor: "#8d6e63",
          borderWidth: 1,
          borderRadius: 4
        },
        {
          label: "Diverted & Recycled (kg)",
          data: totalDiverted,
          backgroundColor: "rgba(46, 125, 50, 0.8)",
          borderColor: "#2e7d32",
          borderWidth: 1,
          borderRadius: 4
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: true,
          title: { display: true, text: "Kilograms (kg)", font: { size: 11 } },
          grid: { color: "rgba(0,0,0,0.05)" }
        },
        x: {
          grid: { display: false }
        }
      },
      plugins: {
        legend: { position: "top", labels: { boxWidth: 12, font: { size: 11 } } }
      }
    }
  });
}

/**
 * 2. Cumulative Material Stream Composition Doughnut
 */
function initMaterialCategoryChart() {
  const canvas = document.getElementById("materialCategoryChart");
  if (!canvas) return;

  new Chart(canvas.getContext("2d"), {
    type: "doughnut",
    data: {
      labels: [
        "Cardboard & Paper",
        "Rigid & Film Plastics",
        "Organics & Greenwaste",
        "Glass & Minerals",
        "E-Waste & Batteries",
        "Residual Landfill"
      ],
      datasets: [{
        data: [32, 24, 22, 10, 4, 8],
        backgroundColor: [
          "#0288d1", // Blue
          "#2e7d32", // Green
          "#81c784", // Light green
          "#26a69a", // Teal
          "#7b1fa2", // Purple
          "#9e9e9e"  // Grey
        ],
        borderWidth: 2,
        borderColor: "#ffffff",
        hoverOffset: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "bottom",
          labels: { boxWidth: 10, font: { size: 11 }, padding: 8 }
        }
      },
      cutout: "64%"
    }
  });
}

/**
 * 3. Monthly Diversion Efficiency Trend Line
 */
function initDiversionTrendChart() {
  const canvas = document.getElementById("diversionTrendChart");
  if (!canvas) return;

  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const efficiency = [65.0, 66.4, 69.0, 70.3, 73.2, 73.7, 74.7, 74.7, 75.2, 76.0, 76.8, 76.7];

  new Chart(canvas.getContext("2d"), {
    type: "line",
    data: {
      labels: months,
      datasets: [{
        label: "Facility Diversion Rate (%)",
        data: efficiency,
        borderColor: "#2e7d32",
        backgroundColor: "rgba(46, 125, 50, 0.12)",
        fill: true,
        tension: 0.35,
        pointBackgroundColor: "#2e7d32",
        pointBorderColor: "#ffffff",
        pointBorderWidth: 2,
        pointRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          min: 60,
          max: 85,
          title: { display: true, text: "Diversion %", font: { size: 11 } },
          grid: { color: "rgba(0,0,0,0.05)" }
        },
        x: { grid: { display: false } }
      },
      plugins: {
        legend: { display: false }
      }
    }
  });
}

/**
 * 4. Primary Diverted Streams Horizontal Bar
 */
function initTopStreamsChart() {
  const canvas = document.getElementById("topStreamsChart");
  if (!canvas) return;

  new Chart(canvas.getContext("2d"), {
    type: "bar",
    data: {
      labels: ["OCC Cardboard", "PET Plastic #1", "Food Scraps", "Aluminum Cans", "Li-ion Cells"],
      datasets: [{
        label: "Diverted Weight (kg)",
        data: [5800, 3940, 3450, 1620, 720],
        backgroundColor: [
          "#0288d1",
          "#2e7d32",
          "#81c784",
          "#f57c00",
          "#7b1fa2"
        ],
        borderRadius: 4
      }]
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          beginAtZero: true,
          title: { display: true, text: "Tonnage / Kilograms", font: { size: 11 } },
          grid: { color: "rgba(0,0,0,0.05)" }
        },
        y: { grid: { display: false } }
      },
      plugins: {
        legend: { display: false }
      }
    }
  });
}

/**
 * Audit log export interaction
 */
function initExportAction() {
  const btn = document.getElementById("exportDataBtn");
  if (!btn) return;

  btn.addEventListener("click", () => {
    alert(
      "📥 Generating CSV Audit Report:\n\n" +
      "File: WasteWise_ESG_Audit_Trailing12M.csv\n" +
      "Status: Formatted with verified simulation fixtures.\n" +
      "(Live server-side streaming will connect to FastAPI in Step 4)."
    );
  });
}
