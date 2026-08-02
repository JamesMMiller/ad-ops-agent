/* Profit Admin SPA — talks only to same-origin /api/* */

const money = (n, digits = 2) =>
  n == null || Number.isNaN(n)
    ? "—"
    : `£${Number(n).toLocaleString("en-GB", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      })}`;

const pct = (n) => (n == null ? "—" : `${Math.round(n * 100)}%`);

let snapshot = null;
let chart = null;
let productChart = null;
let subsetChart = null;
let selectedProductKey = null;
let subsetResult = null;

const el = (id) => document.getElementById(id);

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { Accept: "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
}

function showWarnings(warnings) {
  const box = el("warnings");
  if (!warnings || !warnings.length) {
    box.hidden = true;
    box.innerHTML = "";
    return;
  }
  box.hidden = false;
  box.innerHTML = `<strong>Partial refresh</strong><ul>${warnings
    .map((w) => `<li>${escapeHtml(w)}</li>`)
    .join("")}</ul>`;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderStats(data) {
  const t = data.pnl?.totals || {};
  el("stat-rev").textContent = money(t.revenue, 0);
  el("stat-ads").textContent = money(t.meta_spend, 0);

  const mer = t.mer3d;
  const merEl = el("stat-mer");
  merEl.textContent = mer == null ? "—" : `${mer.toFixed(2)}x`;
  merEl.className = "stat-value";
  if (mer != null) {
    merEl.classList.add(mer >= 2 ? "success" : mer >= 1.5 ? "warning" : "danger");
  }

  const pnl = t.cum_pnl;
  const pnlEl = el("stat-pnl");
  pnlEl.textContent = money(pnl, 0);
  pnlEl.className = "stat-value " + (pnl >= 0 ? "success" : "danger");

  const shop = data.sources?.shopify?.shop?.name;
  if (shop) el("subtitle").textContent = `${shop} · local ops desk`;

  const when = data.refreshed_at
    ? new Date(data.refreshed_at).toLocaleString("en-GB")
    : "—";
  el("last-refreshed").textContent = `Last refreshed: ${when}`;
}

function renderDailyTable(days) {
  const tbody = el("daily-table").querySelector("tbody");
  tbody.innerHTML = (days || [])
    .map((d) => {
      const cls = d.day_pnl > 0 ? "pos" : d.day_pnl < 0 ? "neg" : "";
      return `<tr class="${cls}">
        <td>${d.label}</td>
        <td>${money(d.rev)}</td>
        <td>${money(d.ads)}</td>
        <td>${money(d.cogs)}</td>
        <td>${money(d.kie_gbp)}</td>
        <td>${money(d.day_pnl)}</td>
        <td>${money(d.cum_pnl)}</td>
        <td>${d.mer3d == null ? "—" : d.mer3d.toFixed(2) + "x"}</td>
      </tr>`;
    })
    .join("");
}

function renderUnitTable(rows) {
  const tbody = el("unit-table").querySelector("tbody");
  tbody.innerHTML = (rows || [])
    .map(
      (r) => `<tr>
        <td>${escapeHtml(r.product)}</td>
        <td>${money(r.sell)}</td>
        <td>${money(r.landed)}</td>
        <td>${money(r.contrib)}</td>
        <td>${pct(r.margin)}</td>
        <td>${r.min_roas == null ? "—" : r.min_roas.toFixed(2) + "x"}</td>
        <td>${money(r.max_cpa)}</td>
      </tr>`,
    )
    .join("");
}

function renderProductTable(rows) {
  const table = el("product-table");
  const heading = el("product-pnl-heading");
  if (!table) return;
  const tbody = table.querySelector("tbody");
  if (!tbody) return;

  if (heading) {
    heading.textContent = rows?.length
      ? `Product profitability · ${rows.length} product${rows.length === 1 ? "" : "s"}`
      : "Product profitability";
  }

  if (!rows || !rows.length) {
    tbody.innerHTML =
      '<tr><td colspan="9" class="muted">No paid orders in this snapshot yet. Hit Refresh.</td></tr>';
    const detail = el("product-detail");
    if (detail) {
      detail.innerHTML =
        '<p class="muted">Select a product row to dig into variants and orders.</p>';
    }
    destroyProductChart();
    return;
  }

  if (
    !selectedProductKey ||
    !rows.some((r) => r.key === selectedProductKey)
  ) {
    selectedProductKey = rows[0].key;
  }

  tbody.innerHTML = rows
    .map((r) => {
      const selected = r.key === selectedProductKey ? "selected" : "";
      const contribCls =
        r.contrib > 0 ? "contrib-pos" : r.contrib < 0 ? "contrib-neg" : "";
      return `<tr class="${selected}" data-key="${escapeHtml(r.key)}">
        <td>${escapeHtml(r.product)}</td>
        <td>${r.orders}</td>
        <td>${r.units}</td>
        <td>${money(r.revenue)}</td>
        <td>${money(r.cogs)}</td>
        <td>${money(r.fees)}</td>
        <td class="${contribCls}">${money(r.contrib)}</td>
        <td>${pct(r.margin)}</td>
        <td>${money(r.avg_unit)}</td>
      </tr>`;
    })
    .join("");

  tbody.querySelectorAll("tr[data-key]").forEach((tr) => {
    tr.addEventListener("click", () => {
      selectedProductKey = tr.getAttribute("data-key");
      renderProductTable(rows);
    });
  });

  const selected = rows.find((r) => r.key === selectedProductKey) || rows[0];
  try {
    renderProductDetail(selected);
  } catch (e) {
    console.error("product detail failed", e);
  }
  try {
    renderProductChart(rows);
  } catch (e) {
    console.error("product chart failed", e);
  }
}

function renderProductDetail(row) {
  const box = el("product-detail");
  if (!row) {
    box.innerHTML =
      '<p class="muted">Select a product row to dig into variants and orders.</p>';
    return;
  }

  const variants = (row.variants || [])
    .map(
      (v) => `<tr>
        <td>${escapeHtml(v.variant)}</td>
        <td>${escapeHtml(v.sku)}</td>
        <td>${v.units}</td>
        <td>${money(v.revenue)}</td>
        <td>${money(v.contrib)}</td>
        <td>${pct(v.margin)}</td>
      </tr>`,
    )
    .join("");

  const lines = (row.order_lines || [])
    .map(
      (l) => `<tr>
        <td>${escapeHtml(l.order || "")}</td>
        <td>${escapeHtml(l.date || "")}</td>
        <td>${escapeHtml(l.variant)}</td>
        <td>${l.qty}</td>
        <td>${money(l.unit)}</td>
        <td class="${l.contrib > 0 ? "contrib-pos" : l.contrib < 0 ? "contrib-neg" : ""}">${money(l.contrib)}</td>
      </tr>`,
    )
    .join("");

  box.innerHTML = `
    <h3>${escapeHtml(row.product)}</h3>
    <p class="muted detail-meta">
      ${row.orders} order${row.orders === 1 ? "" : "s"} · ${row.units} unit${row.units === 1 ? "" : "s"} ·
      avg sell ${money(row.avg_unit)} · contrib ${money(row.contrib)} (${pct(row.margin)})
    </p>
    <h4>By variant</h4>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Variant</th>
            <th>SKU</th>
            <th>Units</th>
            <th>Revenue</th>
            <th>Contrib</th>
            <th>Margin</th>
          </tr>
        </thead>
        <tbody>${variants || '<tr><td colspan="6" class="muted">No variants</td></tr>'}</tbody>
      </table>
    </div>
    <h4>Order lines</h4>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Order</th>
            <th>Date</th>
            <th>Variant</th>
            <th>Qty</th>
            <th>Unit £</th>
            <th>Contrib</th>
          </tr>
        </thead>
        <tbody>${lines || '<tr><td colspan="6" class="muted">No lines</td></tr>'}</tbody>
      </table>
    </div>`;
}

function destroyProductChart() {
  if (productChart) {
    productChart.destroy();
    productChart = null;
  }
}

function destroyChart() {
  if (chart) {
    chart.destroy();
    chart = null;
  }
}

const MAIN_CHART_VIEWS = ["cumPnl", "cumRevCost", "dailyStack", "mer"];
window.MAIN_CHART_VIEWS = MAIN_CHART_VIEWS;

function zeroLinePlugin() {
  return {
    id: "zeroLine",
    afterDraw(c) {
      const y = c.scales.y;
      const x = c.scales.x;
      if (!y || y.min > 0 || y.max < 0) return;
      const yp = y.getPixelForValue(0);
      const { ctx: g } = c;
      g.save();
      g.strokeStyle = "#067647";
      g.setLineDash([4, 4]);
      g.beginPath();
      g.moveTo(x.left, yp);
      g.lineTo(x.right, yp);
      g.stroke();
      g.restore();
    },
  };
}

function merGuidesPlugin() {
  return {
    id: "merGuides",
    afterDraw(c) {
      const y = c.scales.y;
      const x = c.scales.x;
      const { ctx: g } = c;
      const draw = (val, color) => {
        if (val < y.min || val > y.max) return;
        const yp = y.getPixelForValue(val);
        g.save();
        g.strokeStyle = color;
        g.setLineDash([4, 4]);
        g.beginPath();
        g.moveTo(x.left, yp);
        g.lineTo(x.right, yp);
        g.stroke();
        g.restore();
      };
      draw(2.0, "#067647");
      draw(1.5, "#b54708");
    },
  };
}

/** Build Chart.js config + labels for a main P&L chart view. */
function mainChartSpec(view, days) {
  const labels = days.map((d) => d.label);
  const common = {
    responsive: false,
    animation: false,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: true, position: "bottom" },
    },
    scales: {
      y: { beginAtZero: false },
    },
  };

  const C = (key, fallback) =>
    typeof window.paConcept === "function" ? window.paConcept(key, fallback) : fallback;

  if (view === "cumPnl") {
    return {
      title: "Cumulative estimated P&L",
      note: C(
        "CHART_CUM_PNL",
        "Running profit/loss: revenue − landed COGS − fees − Meta − KIE − Shopify slice. £0 = break-even.",
      ),
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Cumulative P&L (£)",
            data: days.map((d) => d.cum_pnl),
            borderColor: "#b42318",
            backgroundColor: "rgba(180, 35, 24, 0.12)",
            fill: true,
            tension: 0.2,
          },
        ],
      },
      options: {
        ...common,
        scales: {
          y: {
            beginAtZero: false,
            ticks: { callback: (v) => `£${v}` },
          },
        },
      },
      plugins: [zeroLinePlugin()],
    };
  }

  if (view === "cumRevCost") {
    return {
      title: "Cumulative revenue vs total costs",
      note: C(
        "CHART_REV_COST",
        "Green = cumulative revenue; red = cumulative costs. Profit when green stays above red.",
      ),
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Cumulative revenue (£)",
            data: days.map((d) => d.cum_rev),
            borderColor: "#067647",
            backgroundColor: "rgba(6, 118, 71, 0.1)",
            fill: true,
            tension: 0.2,
          },
          {
            label: "Cumulative costs (£)",
            data: days.map((d) => d.cum_costs),
            borderColor: "#b42318",
            backgroundColor: "rgba(180, 35, 24, 0.08)",
            fill: true,
            tension: 0.2,
          },
        ],
      },
      options: {
        ...common,
        scales: { y: { beginAtZero: true, ticks: { callback: (v) => `£${v}` } } },
      },
      plugins: [],
    };
  }

  if (view === "dailyStack") {
    return {
      title: "Daily cost stack",
      note: C(
        "CHART_DAILY_STACK",
        "Each bar is one day’s cost mix: landed COGS, Meta, KIE, and fees + Shopify.",
      ),
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "Landed COGS",
            data: days.map((d) => d.cogs),
            backgroundColor: "#b54708",
            stack: "c",
          },
          {
            label: "Meta ads",
            data: days.map((d) => d.ads),
            backgroundColor: "#b42318",
            stack: "c",
          },
          {
            label: "KIE credits",
            data: days.map((d) => d.kie_gbp),
            backgroundColor: "#1f4b99",
            stack: "c",
          },
          {
            label: "Fees + Shopify",
            data: days.map((d) => Math.round((d.fees + d.shopify) * 100) / 100),
            backgroundColor: "#6b6b6b",
            stack: "c",
          },
        ],
      },
      options: {
        ...common,
        scales: {
          x: { stacked: true },
          y: {
            stacked: true,
            beginAtZero: true,
            ticks: { callback: (v) => `£${v}` },
          },
        },
      },
      plugins: [],
    };
  }

  if (view === "mer") {
    return {
      title: "Trailing 3-day MER",
      note: C(
        "CHART_MER",
        "Store revenue ÷ Meta spend (3-day window). Not Meta ROAS. ~2.0× healthy after COGS.",
      ),
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "3-day MER",
            data: days.map((d) => d.mer3d ?? null),
            borderColor: "#1f4b99",
            backgroundColor: "rgba(31, 75, 153, 0.1)",
            fill: true,
            spanGaps: false,
            tension: 0.2,
          },
        ],
      },
      options: {
        ...common,
        scales: {
          y: {
            beginAtZero: true,
            ticks: { callback: (v) => `${v}x` },
          },
        },
      },
      plugins: [merGuidesPlugin()],
    };
  }

  return null;
}
window.mainChartSpec = mainChartSpec;

function productChartSpec(rows) {
  if (!rows || !rows.length) return null;
  const sorted = [...rows].sort((a, b) => b.contrib - a.contrib);
  return {
    title: "Contribution by product (pre ads / KIE)",
    note:
      typeof window.paConcept === "function"
        ? window.paConcept(
            "CHART_PRODUCT_CONTRIB",
            "Contribution before Meta and KIE — positive bars fund ads; not full P&L.",
          )
        : "Contribution before Meta and KIE — positive bars fund ads; not full P&L.",
    type: "bar",
    data: {
      labels: sorted.map((r) => r.product),
      datasets: [
        {
          label: "Contribution (£)",
          data: sorted.map((r) => r.contrib),
          backgroundColor: sorted.map((r) =>
            r.contrib >= 0 ? "rgba(6, 118, 71, 0.75)" : "rgba(180, 35, 24, 0.75)",
          ),
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: false,
      animation: false,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
      },
      scales: {
        x: {
          ticks: { callback: (v) => `£${v}` },
        },
      },
    },
    plugins: [],
  };
}

function renderChart(view, days) {
  destroyChart();
  const spec = mainChartSpec(view, days);
  if (!spec) return;
  const title = el("chart-title");
  const note = el("chart-note");
  if (title) title.textContent = spec.title;
  if (note) note.textContent = spec.note;
  const ctx = el("main-chart").getContext("2d");
  chart = new Chart(ctx, {
    type: spec.type,
    data: spec.data,
    options: {
      ...spec.options,
      responsive: true,
      maintainAspectRatio: true,
      animation: false,
    },
    plugins: spec.plugins,
  });
}

function renderProductChart(rows) {
  destroyProductChart();
  const canvas = el("product-chart");
  const spec = productChartSpec(rows);
  if (!spec || !canvas) return;
  productChart = new Chart(canvas.getContext("2d"), {
    type: spec.type,
    data: spec.data,
    options: {
      ...spec.options,
      responsive: true,
      maintainAspectRatio: true,
      animation: false,
      plugins: {
        legend: { display: false },
        title: {
          display: true,
          text: spec.title,
          align: "start",
          color: "#6b6b6b",
          font: { size: 12, weight: "500" },
        },
      },
    },
    plugins: spec.plugins,
  });
}

function setPnlExportEnabled(on) {
  const btn = el("btn-pnl-export");
  if (btn) btn.disabled = !on;
}

function canvasToWhitePng(canvas) {
  if (!canvas || typeof canvas.toDataURL !== "function") return null;
  try {
    const tmp = document.createElement("canvas");
    tmp.width = canvas.width;
    tmp.height = canvas.height;
    const ctx = tmp.getContext("2d");
    if (!ctx) return canvas.toDataURL("image/png");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, tmp.width, tmp.height);
    ctx.drawImage(canvas, 0, 0);
    return tmp.toDataURL("image/png");
  } catch (_) {
    return null;
  }
}

function renderSpecToPng(spec, width, height) {
  if (!spec) return null;
  const host = document.createElement("div");
  host.style.cssText =
    "position:fixed;left:-10000px;top:0;width:" +
    width +
    "px;height:" +
    height +
    "px;pointer-events:none;opacity:0;";
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  host.appendChild(canvas);
  document.body.appendChild(host);
  let instance = null;
  try {
    instance = new Chart(canvas.getContext("2d"), {
      type: spec.type,
      data: spec.data,
      options: {
        ...spec.options,
        responsive: false,
        animation: false,
        maintainAspectRatio: false,
      },
      plugins: spec.plugins || [],
    });
    return canvasToWhitePng(canvas);
  } catch (_) {
    return null;
  } finally {
    if (instance) instance.destroy();
    host.remove();
  }
}

function captureAllChartsForExport() {
  const days = snapshot?.pnl?.days || [];
  const charts = [];
  for (const view of MAIN_CHART_VIEWS) {
    const spec = mainChartSpec(view, days);
    if (!spec || !days.length) continue;
    const png = renderSpecToPng(spec, 1100, 420);
    if (!png) continue;
    charts.push({ title: spec.title, note: spec.note, png });
  }
  const productSpec = productChartSpec(snapshot?.product_pnl || []);
  if (productSpec) {
    const rows = productSpec.data.labels.length;
    const height = Math.max(320, 48 + rows * 28);
    const png = renderSpecToPng(productSpec, 1100, height);
    if (png) {
      charts.push({
        title: productSpec.title,
        note: productSpec.note,
        png,
      });
    }
  }
  const subDays = subsetResult?.days || [];
  if (subDays.length) {
    const label = subsetResult.label || "Subset";
    const from = subsetResult.start_date || "";
    for (const view of MAIN_CHART_VIEWS) {
      const spec = mainChartSpec(view, subDays);
      if (!spec) continue;
      const png = renderSpecToPng(spec, 1100, 420);
      if (!png) continue;
      charts.push({
        title: `Subset · ${spec.title}${from ? ` · from ${from}` : ""}`,
        note: `${label}. ${subsetResult.note || spec.note || ""}`,
        png,
      });
    }
  }
  return charts;
}

function destroySubsetChart() {
  if (subsetChart) {
    subsetChart.destroy();
    subsetChart = null;
  }
}

function readSubsetSelection() {
  // Shared Scope: Meta tree + SKUs from ads.js
  const skus =
    typeof window.selectedAdsSkus === "function" ? window.selectedAdsSkus() : [];
  const campaign_ids =
    typeof window.checkedAdsIds === "function"
      ? window.checkedAdsIds("ads-camp")
      : [];
  const adset_ids =
    typeof window.checkedAdsIds === "function"
      ? window.checkedAdsIds("ads-adset")
      : [];
  return { skus, handles: [], campaign_ids, adset_ids };
}

function renderSubsetChart(view, days) {
  destroySubsetChart();
  const canvas = el("subset-chart");
  const spec = mainChartSpec(view, days);
  if (!spec || !canvas) return;
  const title = el("subset-chart-title");
  const note = el("subset-chart-note");
  const from = subsetResult?.start_date;
  if (title) {
    title.textContent = from ? `${spec.title} · from ${from}` : spec.title;
  }
  if (note) {
    note.textContent = subsetResult?.note
      ? `${spec.note} ${subsetResult.note}`
      : spec.note;
  }
  subsetChart = new Chart(canvas.getContext("2d"), {
    type: spec.type,
    data: spec.data,
    options: {
      ...spec.options,
      responsive: true,
      maintainAspectRatio: true,
      animation: false,
    },
    plugins: spec.plugins,
  });
}

function renderSubsetResults(data) {
  subsetResult = data;
  const box = el("subset-results");
  if (!box) return;
  box.hidden = false;
  const t = data.totals || {};
  const pnl = t.cum_pnl;
  const pnlCls = pnl == null ? "" : pnl >= 0 ? "success" : "danger";
  const mer = t.mer3d;
  const merCls =
    mer == null ? "" : mer >= 2 ? "success" : mer >= 1.5 ? "warning" : "danger";
  const startSrc = data.selection?.start_source?.name;
  el("subset-stats").innerHTML = `
    <div class="stat"><div class="stat-value">${money(t.revenue, 0)}</div><div class="stat-label">SKU revenue</div></div>
    <div class="stat"><div class="stat-value">${money(t.meta_spend, 0)}</div><div class="stat-label">Selected ads</div></div>
    <div class="stat"><div class="stat-value ${merCls}">${
      mer == null ? "—" : mer.toFixed(2) + "x"
    }</div><div class="stat-label">Trailing 3-day MER</div></div>
    <div class="stat"><div class="stat-value ${pnlCls}">${money(
      pnl,
      0,
    )}</div><div class="stat-label">Cum P&amp;L (subset)</div></div>
  `;
  const note = el("subset-note");
  if (note) {
    note.textContent = [
      data.label || "Subset",
      data.start_date ? `from ${data.start_date}` : null,
      startSrc ? `start ad set: ${startSrc}` : null,
      t.units != null ? `${t.units} units` : null,
      t.store_mer != null ? `MER ${t.store_mer}x` : null,
    ]
      .filter(Boolean)
      .join(" · ");
  }
  if (data.warnings?.length) showWarnings(data.warnings);
  const view = el("subset-chart-view")?.value || "cumPnl";
  renderSubsetChart(view, data.days || []);
}

function clearSubsetResults() {
  subsetResult = null;
  destroySubsetChart();
  const box = el("subset-results");
  if (box) box.hidden = true;
  const stats = el("subset-stats");
  if (stats) stats.innerHTML = "";
}

async function applySubset() {
  const sel = readSubsetSelection();
  if (!sel.skus.length && !sel.handles.length) {
    throw new Error("Select at least one SKU in Scope for the subset graph.");
  }
  if (!sel.adset_ids.length && !sel.campaign_ids.length) {
    throw new Error("Select at least one Meta ad set (or campaign) in Scope.");
  }
  const data = await api("/api/pnl/subset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(sel),
  });
  renderSubsetResults(data);
  return data;
}

window.applySubset = applySubset;

function initSubsetUi() {
  el("subset-chart-view")?.addEventListener("change", () => {
    if (subsetResult?.days) {
      renderSubsetChart(el("subset-chart-view").value, subsetResult.days);
    }
  });
}

async function exportPnlPdf() {
  if (!snapshot?.pnl) {
    showWarnings(["Refresh the P&L before exporting."]);
    return;
  }
  const btn = el("btn-pnl-export");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Exporting…";
  }
  try {
    const charts = captureAllChartsForExport();
    const res = await fetch("/api/pnl/export", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/pdf",
      },
      body: JSON.stringify({
        snapshot,
        charts,
      }),
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = body.detail || JSON.stringify(body);
      } catch (_) {}
      throw new Error(detail);
    }
    const blob = await res.blob();
    const cd = res.headers.get("Content-Disposition") || "";
    const match = /filename="([^"]+)"/.exec(cd);
    const filename = match ? match[1] : "profit-admin-pnl.pdf";
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (e) {
    showWarnings([`PDF export failed: ${e.message}`]);
  } finally {
    if (btn) {
      btn.textContent = "Export PDF";
      btn.disabled = !snapshot?.pnl;
    }
  }
}

function renderAll(data) {
  snapshot = data;
  showWarnings(data.warnings);
  renderStats(data);
  const days = data.pnl?.days || [];
  renderDailyTable(days);
  renderProductTable(data.product_pnl || []);
  renderUnitTable(data.unit_economics || []);
  renderChart(el("chart-view").value, days);
  setPnlExportEnabled(Boolean(data?.pnl));
}

async function loadLatest() {
  try {
    const data = await api("/api/snapshot/latest");
    renderAll(data);
  } catch (_) {
    // no snapshot yet — fine
  }
}

async function doRefresh() {
  const btn = el("btn-refresh");
  btn.disabled = true;
  btn.textContent = "Refreshing…";
  try {
    const data = await api("/api/refresh", { method: "POST" });
    renderAll(data);
    if (typeof window.onDeskRefreshed === "function") {
      await window.onDeskRefreshed();
    }
  } catch (e) {
    showWarnings([`Refresh failed: ${e.message}`]);
  } finally {
    btn.disabled = false;
    btn.textContent = "Refresh data";
  }
}

el("btn-refresh").addEventListener("click", doRefresh);
el("btn-pnl-export")?.addEventListener("click", exportPnlPdf);
el("chart-view").addEventListener("change", () => {
  if (snapshot?.pnl?.days) renderChart(el("chart-view").value, snapshot.pnl.days);
});
initSubsetUi();

loadLatest();
