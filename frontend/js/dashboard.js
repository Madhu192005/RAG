"use strict";

document.addEventListener("DOMContentLoaded", () => {
  loadDashboardBackendData();
  const refresh = document.getElementById("refreshStatsBtn");
  if (refresh) refresh.addEventListener("click", async () => {
    refresh.disabled = true; refresh.textContent = "Updating…";
    await loadDashboardBackendData(); refresh.disabled = false; refresh.textContent = "🔄 Refresh Data";
  });
});

let categoryChartInstance = null;

async function loadDashboardBackendData() {
  const summaryResult = await Promise.allSettled([
    WW_API.getAnalyticsSummary(), WW_API.getAnalyticsCategories(),
    WW_API.get("/api/waste/reports?limit=5"), WW_API.get("/api/collections/requests?limit=5"),
    WW_API.get("/api/analytics/collection-operations")
  ]);
  const [summary, categories, reports, requests, operations] = summaryResult;
  if (summary.status === "fulfilled") {
    const data = summary.value;
    text("statTotalWaste", `${Number(data.total_waste_logged_kg).toLocaleString()} kg`);
    text("statRecycled", `${Number(data.total_recycled_kg).toLocaleString()} kg`);
    text("statPickups", String(data.pending_pickups_count));
    text("statCO2", `${Number(data.co2_avoided_kg).toLocaleString()} kg`);
  } else ["statTotalWaste", "statRecycled", "statPickups", "statCO2"].forEach(id => text(id, "Unavailable"));

  initCategoryDonutChart(categories.status === "fulfilled" ? categories.value.categories : []);
  renderReports(reports.status === "fulfilled" ? reports.value : []);
  renderRequests(requests.status === "fulfilled" ? requests.value : []);
  if (operations.status === "fulfilled") renderCollectionOperations(operations.value);
  else document.getElementById("collectionOperationsPanel").style.display = "none";
}

function initCategoryDonutChart(categories) {
  const canvas = document.getElementById("categoryDonutChart"); if (!canvas || !window.Chart) return;
  if (categoryChartInstance) categoryChartInstance.destroy();
  const labels = categories.map(item => item.category);
  const values = categories.map(item => Number(item.share_pct || 0));
  const colors = categories.map(item => item.color_code || "#2e7d32");
  categoryChartInstance = new Chart(canvas.getContext("2d"), {
    type: "doughnut", data: { labels, datasets: [{ data: values, backgroundColor: colors, borderWidth: 2, borderColor: "#fff" }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" } }, cutout: "68%" }
  });
  text("categoryChartNote", categories.length ? "Distribution of stored waste reports." : "No report distribution is available.");
}

function renderReports(rows) {
  const body = document.getElementById("recentReportsBody"); body.replaceChildren();
  if (!rows.length) return emptyRow(body, 6, "No waste reports are available.");
  rows.forEach(report => {
    const tr = document.createElement("tr");
    [`#W-${report.id}`, report.title, report.category, report.estimated_weight_kg || "—",
      new Date(report.created_at).toLocaleString(), report.status].forEach(value => {
      const td = document.createElement("td"); td.textContent = value; tr.appendChild(td);
    }); body.appendChild(tr);
  });
  text("reportsCount", `${rows.length} latest report(s)`);
}

function renderRequests(rows) {
  const body = document.getElementById("recentRequestsBody"); body.replaceChildren();
  if (!rows.length) return emptyRow(body, 5, "No collection requests are available to this account.");
  rows.forEach(request => {
    const tr = document.createElement("tr");
    [String(request.id), request.pickup_address, request.category, request.requested_date || request.preferred_date, request.status.replaceAll("_", " ")].forEach(value => {
      const td = document.createElement("td"); td.textContent = value; tr.appendChild(td);
    }); body.appendChild(tr);
  });
}

function renderCollectionOperations(data) {
  const panel = document.getElementById("collectionOperationsPanel"), grid = document.getElementById("collectionOperationsGrid");
  panel.style.display = "block"; grid.replaceChildren();
  const values = [...Object.entries(data.collection_requests || {}),
    ["Active recycling centers", data.active_recycling_centers],
    ["Unverified recycling centers", data.unverified_recycling_centers]];
  values.forEach(([label, count]) => {
    const item = document.createElement("div"); item.className = "collection-ops-item";
    const strong = document.createElement("strong"); strong.textContent = `${label.replaceAll("_", " ")}: ${Number(count || 0)}`;
    item.appendChild(strong); grid.appendChild(item);
  });
}

function emptyRow(parent, columns, message) {
  const row = document.createElement("tr"), cell = document.createElement("td");
  cell.colSpan = columns; cell.textContent = message; row.appendChild(cell); parent.appendChild(row);
}
function text(id, value) { const node = document.getElementById(id); if (node) node.textContent = value; }
