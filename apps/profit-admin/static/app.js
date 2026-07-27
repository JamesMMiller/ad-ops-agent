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

function destroyChart() {
  if (chart) {
    chart.destroy();
    chart = null;
  }
}

function renderChart(view, days) {
  destroyChart();
  const labels = days.map((d) => d.label);
  const ctx = el("main-chart").getContext("2d");
  const title = el("chart-title");
  const note = el("chart-note");

  const common = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: { display: true, position: "bottom" },
    },
    scales: {
      y: { beginAtZero: false },
    },
  };

  if (view === "cumPnl") {
    title.textContent = "Cumulative estimated P&L";
    note.textContent =
      "Revenue − landed COGS − fees − Meta − KIE − amortised Shopify Basic. £0 = break-even.";
    chart = new Chart(ctx, {
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
        plugins: {
          ...common.plugins,
          annotation: undefined,
        },
        scales: {
          y: {
            beginAtZero: false,
            ticks: { callback: (v) => `£${v}` },
          },
        },
      },
      plugins: [
        {
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
        },
      ],
    });
    return;
  }

  if (view === "cumRevCost") {
    title.textContent = "Cumulative revenue vs total costs";
    note.textContent =
      "Costs include COGS, fees, Meta, KIE, and daily Shopify slice. Profit when green overtakes red.";
    chart = new Chart(ctx, {
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
    });
    return;
  }

  if (view === "dailyStack") {
    title.textContent = "Daily cost stack";
    note.textContent = "Composition of spend each day (stacked).";
    chart = new Chart(ctx, {
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
            data: days.map((d) =>
              Math.round((d.fees + d.shopify) * 100) / 100,
            ),
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
    });
    return;
  }

  if (view === "mer") {
    title.textContent = "Trailing 3-day MER";
    note.textContent =
      "Store revenue ÷ Meta spend over a 3-day window. ~2.0x is a healthy target after COGS.";
    chart = new Chart(ctx, {
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
      plugins: [
        {
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
        },
      ],
    });
  }
}

function renderAll(data) {
  snapshot = data;
  showWarnings(data.warnings);
  renderStats(data);
  const days = data.pnl?.days || [];
  renderDailyTable(days);
  renderUnitTable(data.unit_economics || []);
  renderChart(el("chart-view").value, days);
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
  } catch (e) {
    showWarnings([`Refresh failed: ${e.message}`]);
  } finally {
    btn.disabled = false;
    btn.textContent = "Refresh";
  }
}

el("btn-refresh").addEventListener("click", doRefresh);
el("chart-view").addEventListener("change", () => {
  if (snapshot?.pnl?.days) renderChart(el("chart-view").value, snapshot.pnl.days);
});

loadLatest();
