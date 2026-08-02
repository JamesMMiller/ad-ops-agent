/* Warehouse / CJ 3PL planner — loaded after app.js */

let whMeta = null;
let whCatalog = [];
let whChart = null;
let whResult = null;
let whMetaStructure = null;

const whEl = (id) => document.getElementById(id);

let whWired = false;

async function ensureWarehouseReady() {
  if (!whMeta) await initWarehouse();
}

window.ensureWarehouseReady = ensureWarehouseReady;

async function initWarehouse() {
  const [meta, cat] = await Promise.all([
    api("/api/warehouse/meta"),
    api("/api/catalog").catch(() => ({ catalog: [] })),
  ]);
  whMeta = meta;
  whCatalog = cat.catalog || [];

  const fx = whEl("wh-fx");
  if (fx) {
    fx.textContent = `FX ≈ ${Number(meta.usdgbp).toFixed(4)} USDGBP · fees ${
      Math.round(meta.fee_pct * 1000) / 10
    }% + £${meta.fee_fixed_gbp}`;
  }

  const whSelect = whEl("wh-warehouse");
  if (whSelect && !whSelect.options.length) {
    whSelect.innerHTML = (meta.warehouses || [])
      .map(
        (w) =>
          `<option value="${w.id}" ${w.id === "GB" ? "selected" : ""}>${escapeHtml(
            w.label,
          )}</option>`,
      )
      .join("");
  }

  await refreshLanes();
  applyLastMileDefaults();
  updatePostageHint();
  updateSkuCount();

  if (!whWired) {
    wireWarehouseControls();
    whWired = true;
  }

  // Sync costs/label from shared Scope SKUs
  onSkuChange();
}

function wireWarehouseControls() {
  const whSelect = whEl("wh-warehouse");
  whSelect?.addEventListener("change", async () => {
    await refreshLanes();
    applyLastMileDefaults();
  });
  whEl("wh-postage")?.addEventListener("change", updatePostageHint);
  whEl("btn-wh-export")?.addEventListener("click", exportWarehouseExcel);

  // Shared Scope SKU select drives warehouse defaults
  document.getElementById("ads-sku")?.addEventListener("change", onSkuChange);

  const restockToggle = whEl("wh-restock");
  if (restockToggle) {
    restockToggle.addEventListener("change", syncRestockFields);
    syncRestockFields();
  }
  const trackToggle = whEl("wh-track-stock");
  if (trackToggle) {
    trackToggle.addEventListener("change", syncTrackStockFields);
    syncTrackStockFields();
  }
  const pastToggle = whEl("wh-past");
  if (pastToggle) {
    pastToggle.addEventListener("change", () => {
      syncPastFields().catch((e) => showWarnings([`Past performance setup: ${e.message}`]));
    });
    syncPastFields().catch(() => {});
  }
}

async function syncPastFields() {
  const on = !!whEl("wh-past")?.checked;
  const fields = whEl("wh-past-fields");
  if (fields) fields.hidden = !on;
  // Past Meta/SKU come from shared Scope — no separate pickers
  const adsPreset = document.getElementById("ads-preset")?.value;
  const whPreset = whEl("wh-past-preset");
  if (whPreset && adsPreset && adsPreset !== "custom") {
    if ([...whPreset.options].some((o) => o.value === adsPreset)) {
      whPreset.value = adsPreset;
    }
  }
}

function selectedSkuRows() {
  // Shared Scope #ads-sku (value = sku string) + catalog lookup
  const sel = document.getElementById("ads-sku");
  if (!sel) return [];
  const skus = [...sel.selectedOptions].map((o) => o.value).filter(Boolean);
  if (!skus.length) return [];
  const bySku = new Map((whCatalog || []).map((r) => [r.sku, r]));
  return skus.map((sku) => {
    const row = bySku.get(sku);
    if (row) return row;
    const opt = [...sel.options].find((o) => o.value === sku);
    return {
      sku,
      handle: opt?.dataset?.handle || "",
      product: opt?.textContent || sku,
      variant: "",
      price: null,
      unit_cost: null,
    };
  });
}

function updateSkuCount() {
  const el = whEl("wh-sku-count");
  if (!el) return;
  const rows = selectedSkuRows();
  if (!rows.length) {
    el.textContent = "No SKUs in Scope — enter costs manually.";
    return;
  }
  const handles = new Set(rows.map((r) => r.handle).filter(Boolean));
  el.textContent = `${rows.length} SKU${rows.length === 1 ? "" : "s"} from Scope · ${
    handles.size
  } product${handles.size === 1 ? "" : "s"}`;
}

function readPastSelection() {
  const rows = selectedSkuRows();
  const handles = [...new Set(rows.map((r) => r.handle).filter(Boolean))];
  const skus = [...new Set(rows.map((r) => r.sku).filter(Boolean))];
  let campaign_ids = [];
  let adset_ids = [];
  if (typeof window.checkedAdsIds === "function") {
    campaign_ids = window.checkedAdsIds("ads-camp");
    adset_ids = window.checkedAdsIds("ads-adset");
  }
  const adsPreset = document.getElementById("ads-preset")?.value;
  let past_date_preset = whEl("wh-past-preset")?.value || "maximum";
  if (adsPreset && adsPreset !== "custom") past_date_preset = adsPreset;
  return {
    show_past_performance: !!whEl("wh-past")?.checked,
    past_handles: skus.length ? [] : handles,
    past_skus: skus,
    past_campaign_ids: campaign_ids,
    past_adset_ids: adset_ids,
    past_date_preset,
  };
}

function syncTrackStockFields() {
  const on = !!whEl("wh-track-stock")?.checked;
  document.querySelectorAll(".wh-stock-only").forEach((el) => {
    el.hidden = !on;
    el.querySelectorAll("input, select").forEach((inp) => {
      inp.disabled = !on;
    });
  });
  const hint = whEl("wh-mode-hint");
  if (hint) {
    hint.textContent = on
      ? "On: track how much stock you hold (inbound, storage, restock, stockouts). Off: stock doesn’t matter — open demand at your sell rate."
      : "Stock ignored — sell rate × horizon, no inbound/storage/restock. Turn on Wholesale / dropship to plan inventory.";
  }
  const adsHint = whEl("wh-ads-hint");
  if (adsHint) {
    adsHint.textContent = on
      ? "Ads: daily spend applies on days with stock (unless you uncheck stop); cost/purchase is per unit sold."
      : "Ads: daily spend every day of the horizon; cost/purchase per unit sold. Stock not tracked.";
  }
  if (on) syncRestockFields();
}

function syncRestockFields() {
  const on = whEl("wh-restock")?.checked;
  const fields = whEl("wh-restock-fields");
  if (!fields) return;
  fields.hidden = !on;
  for (const id of ["wh-restock-qty", "wh-restock-every"]) {
    const el = whEl(id);
    if (el) el.disabled = !on;
  }
}

function updatePostageHint() {
  const postage = whEl("wh-postage");
  if (!postage) return;
  const included = postage.value === "included";
  const hint = whEl("wh-postage-hint");
  if (!hint) return;
  hint.textContent = included
    ? "Postage Included: rates go into landed COGS, margin, and overall P&L (free shipping / you pay)."
    : "Postage Excluded: rates are for transit estimates only — matches P&L desk unit economics (customer pays).";
}

function onSkuChange() {
  const rows = selectedSkuRows();
  updateSkuCount();
  if (!rows.length) {
      return;
  }

  const products = [...new Set(rows.map((r) => r.product).filter(Boolean))];
  const variants = rows
    .map((r) => (r.variant && r.variant !== "Default Title" ? r.variant : null))
    .filter(Boolean);
  let label = products.join(" + ");
  if (products.length === 1 && variants.length) {
    label =
      variants.length <= 3
        ? `${products[0]} · ${variants.join(", ")}`
        : `${products[0]} · ${variants.length} variants`;
  } else if (products.length > 1) {
    label = `${products.length} products · ${rows.length} SKUs`;
  }
  if (whEl("wh-label")) whEl("wh-label").value = label;

  const prices = rows.map((r) => r.price).filter((n) => n != null && !Number.isNaN(n));
  const costs = rows.map((r) => r.unit_cost).filter((n) => n != null && !Number.isNaN(n));
  if (prices.length && whEl("wh-sell")) {
    whEl("wh-sell").value = (
      prices.reduce((a, b) => a + b, 0) / prices.length
    ).toFixed(2);
  }
  if (costs.length && whEl("wh-cost")) {
    whEl("wh-cost").value = (
      costs.reduce((a, b) => a + b, 0) / costs.length
    ).toFixed(2);
  }
}

async function refreshLanes() {
  const whSelect = whEl("wh-warehouse");
  const sel = whEl("wh-lane");
  if (!whSelect || !sel) return;
  const wh = whSelect.value;
  const data = await api(`/api/warehouse/lanes/${wh}`);
  const preferred =
    wh === "GB"
      ? "CN_GB_air_ordinary"
      : wh === "DE"
        ? "CN_DE_air_ordinary"
        : wh === "PL"
          ? "CN_PL_air_ordinary"
          : wh === "US"
            ? "CN_US_air_ordinary"
            : "none";
  sel.innerHTML = (data.lanes || [])
    .map((l) => {
      const days = l.days && l.days !== "—" ? ` · ${l.days}` : "";
      const price = l.usd_per_kg ? ` · $${l.usd_per_kg}/kg` : "";
      return `<option value="${l.id}" ${l.id === preferred ? "selected" : ""}>${escapeHtml(
        l.lane,
      )}${days}${price}</option>`;
    })
    .join("");
}

function applyLastMileDefaults() {
  const wh = whEl("wh-warehouse")?.value;
  if (!wh) return;
  const defaults = (whMeta?.default_last_mile_usd || {})[wh] || {};
  if (whEl("lm-uk")) whEl("lm-uk").value = defaults.UK ?? 3.5;
  if (whEl("lm-eu")) whEl("lm-eu").value = defaults.EU ?? 8;
  if (whEl("lm-us")) whEl("lm-us").value = defaults.US ?? 12;
  if (whEl("lm-can")) whEl("lm-can").value = defaults.CAN ?? 14;
}

function readMix() {
  const uk = Number(whEl("mix-uk").value) || 0;
  const eu = Number(whEl("mix-eu").value) || 0;
  const us = Number(whEl("mix-us").value) || 0;
  const can = Number(whEl("mix-can").value) || 0;
  const t = uk + eu + us + can || 1;
  return { UK: uk / t, EU: eu / t, US: us / t, CAN: can / t };
}

function collectWarehouseState() {
  return {
    label: whEl("wh-label")?.value || "",
    show_past: !!whEl("wh-past")?.checked,
    track_stock: !!whEl("wh-track-stock")?.checked,
    warehouse: whEl("wh-warehouse")?.value || "GB",
    stock_lane: whEl("wh-lane")?.value || "none",
    qty: Number(whEl("wh-qty")?.value) || 100,
    rate: Number(whEl("wh-rate")?.value) || 1,
    horizon: Number(whEl("wh-horizon")?.value) || 180,
    sell: Number(whEl("wh-sell")?.value) || 0,
    cost: Number(whEl("wh-cost")?.value) || 0,
    weight: Number(whEl("wh-weight")?.value) || 0.15,
    cbm: Number(whEl("wh-cbm")?.value) || 0.001,
    cartons: Number(whEl("wh-cartons")?.value) || 1,
    ads: Number(whEl("wh-ads")?.value) || 0,
    cpa: whEl("wh-cpa")?.value ?? "",
    postage: whEl("wh-postage")?.value || "included",
    peak: !!whEl("wh-peak")?.checked,
    stop_ads: whEl("wh-stop-ads")?.checked !== false,
    restock: !!whEl("wh-restock")?.checked,
    restock_qty: Number(whEl("wh-restock-qty")?.value) || 100,
    restock_every: Number(whEl("wh-restock-every")?.value) || 30,
    mix: {
      uk: Number(whEl("mix-uk")?.value) || 0,
      eu: Number(whEl("mix-eu")?.value) || 0,
      us: Number(whEl("mix-us")?.value) || 0,
      can: Number(whEl("mix-can")?.value) || 0,
    },
    last_mile: {
      uk: Number(whEl("lm-uk")?.value) || 0,
      eu: Number(whEl("lm-eu")?.value) || 0,
      us: Number(whEl("lm-us")?.value) || 0,
      can: Number(whEl("lm-can")?.value) || 0,
    },
  };
}

async function applyWarehouseState(state) {
  if (!state) return;
  await ensureWarehouseReady();
  const set = (id, val) => {
    const node = whEl(id);
    if (node != null && val != null) node.value = val;
  };
  const setCheck = (id, val) => {
    const node = whEl(id);
    if (node) node.checked = !!val;
  };
  set("wh-label", state.label);
  setCheck("wh-past", state.show_past);
  setCheck("wh-track-stock", state.track_stock !== false);
  set("wh-warehouse", state.warehouse);
  if (state.warehouse) await refreshLanes();
  set("wh-lane", state.stock_lane);
  set("wh-qty", state.qty);
  set("wh-rate", state.rate);
  set("wh-horizon", state.horizon);
  set("wh-sell", state.sell);
  set("wh-cost", state.cost);
  set("wh-weight", state.weight);
  set("wh-cbm", state.cbm);
  set("wh-cartons", state.cartons);
  set("wh-ads", state.ads);
  if (state.cpa !== undefined && state.cpa !== null) set("wh-cpa", state.cpa);
  set("wh-postage", state.postage);
  setCheck("wh-peak", state.peak);
  setCheck("wh-stop-ads", state.stop_ads !== false);
  setCheck("wh-restock", state.restock);
  set("wh-restock-qty", state.restock_qty);
  set("wh-restock-every", state.restock_every);
  if (state.mix) {
    set("mix-uk", state.mix.uk);
    set("mix-eu", state.mix.eu);
    set("mix-us", state.mix.us);
    set("mix-can", state.mix.can);
  }
  if (state.last_mile) {
    set("lm-uk", state.last_mile.uk);
    set("lm-eu", state.last_mile.eu);
    set("lm-us", state.last_mile.us);
    set("lm-can", state.last_mile.can);
  }
  syncTrackStockFields();
  syncRestockFields();
  await syncPastFields();
  updateSkuCount();
  updatePostageHint();
}

async function runWarehouseCalc() {
  await ensureWarehouseReady();
  const body = {
    warehouse: whEl("wh-warehouse").value,
    qty: Number(whEl("wh-qty").value),
    unit_weight_kg: Number(whEl("wh-weight").value),
    unit_cbm: Number(whEl("wh-cbm").value),
    unit_product_cost_gbp: Number(whEl("wh-cost").value),
    sell_price_gbp: Number(whEl("wh-sell").value),
    sell_rate_per_day: Number(whEl("wh-rate").value),
    horizon_days: Number(whEl("wh-horizon").value),
    stock_lane: whEl("wh-lane").value,
    cartons: Number(whEl("wh-cartons").value),
    peak_season: whEl("wh-peak").checked,
    include_postage: whEl("wh-postage").value === "included",
    daily_ad_spend_gbp: Number(whEl("wh-ads").value) || 0,
    ad_cost_per_purchase_gbp: Number(whEl("wh-cpa").value) || 0,
    stop_ads_when_stock_zero: whEl("wh-stop-ads")?.checked !== false,
    restock_enabled: !!whEl("wh-restock")?.checked,
    restock_qty: Number(whEl("wh-restock-qty")?.value) || 0,
    restock_every_days: Number(whEl("wh-restock-every")?.value) || 30,
    track_stock: !!whEl("wh-track-stock")?.checked,
    ...readPastSelection(),
    dest_mix: readMix(),
    last_mile_usd: {
      UK: Number(whEl("lm-uk").value),
      EU: Number(whEl("lm-eu").value),
      US: Number(whEl("lm-us").value),
      CAN: Number(whEl("lm-can").value),
    },
  };
  const data = await api("/api/warehouse/calculate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  whResult = data;
  const exportBtn = whEl("btn-wh-export");
  if (exportBtn) exportBtn.disabled = false;
  renderWarehouse(data);
  return data;
}

window.collectWarehouseState = collectWarehouseState;
window.applyWarehouseState = applyWarehouseState;
window.runWarehouseCalc = runWarehouseCalc;

async function exportWarehouseExcel() {
  if (!whResult) {
    showWarnings(["Run Apply with Warehouse enabled before exporting."]);
    return;
  }
  const btn = whEl("btn-wh-export");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Exporting…";
  }
  try {
    const label = whEl("wh-label")?.value || "plan";
    const res = await fetch("/api/warehouse/export", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/octet-stream" },
      body: JSON.stringify({ result: whResult, label }),
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
    const filename = match ? match[1] : "profit-admin-export.xlsx";
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (e) {
    showWarnings([`Export failed: ${e.message}`]);
  } finally {
    if (btn) {
      btn.disabled = !whResult;
      btn.textContent = "Export Excel";
    }
  }
}

function renderPastPerformance(past) {
  const box = whEl("wh-past-results");
  if (!box) return;
  if (!past) {
    box.hidden = true;
    box.innerHTML = "";
    return;
  }
  box.hidden = false;
  const s = past.shopify;
  const m = past.meta;
  const c = past.combined || {};
  const summary = past.summary;
  const preset = past.date_preset || "maximum";

  let kpiHtml = "";
  if (summary?.unit_economics) {
    const u = summary.unit_economics;
    const op = summary.overall_pnl || {};
    const t = summary.totals || {};
    const profit = op.profit_gbp;
    const profitCls =
      profit == null ? "" : profit >= 0 ? "success" : "danger";
    const marginInc =
      u.margin_after_ads == null
        ? "—"
        : `${Math.round(u.margin_after_ads * 100)}%`;
    const marginIncCls =
      u.margin_after_ads == null
        ? ""
        : u.margin_after_ads >= 0
          ? "success"
          : "danger";
    const roasVal = t.roas ?? op.roas ?? u.roas;
    const roasLabel = roasVal == null ? "—" : `${Number(roasVal).toFixed(2)}×`;
    const roasCls =
      roasVal == null ? "" : roasVal >= 2 ? "success" : roasVal >= 1 ? "" : "danger";
    const roasCogsVal = t.roas_after_cogs ?? op.roas_after_cogs ?? u.roas_after_cogs;
    const roasCogsLabel =
      roasCogsVal == null ? "—" : `${Number(roasCogsVal).toFixed(2)}×`;
    const roasCogsCls =
      roasCogsVal == null
        ? ""
        : roasCogsVal >= 1
          ? "success"
          : roasCogsVal >= 0
            ? ""
            : "danger";
    const adsNote =
      summary.ads_gbp > 0
        ? ` · ads £${Number(t.ads_gbp / (t.units_sold || 1)).toFixed(2)}/unit (Meta)`
        : " · no Meta spend selected";

    kpiHtml = `
      <p class="detail-meta muted">${escapeHtml(
        summary.label || "Historic",
      )} · ${escapeHtml(preset)} · Shopify sales${adsNote}</p>
      <div class="wh-kpi">
        <div><div class="stat-value ${profitCls}">${money(
          profit,
          0,
        )}</div><div class="stat-label">Overall P&amp;L</div></div>
        <div><div class="stat-value ${marginIncCls}">${marginInc}</div><div class="stat-label">Margin (inc ads)</div></div>
        <div><div class="stat-value ${roasCls}">${roasLabel}</div><div class="stat-label">ROAS</div></div>
        <div><div class="stat-value ${roasCogsCls}">${roasCogsLabel}</div><div class="stat-label">ROAS (after COGS)</div></div>
        <div><div class="stat-value ${
          u.contribution_after_ads_gbp >= 0 ? "success" : "danger"
        }">${money(
          u.contribution_after_ads_gbp,
        )}</div><div class="stat-label">Contrib after ads</div></div>
        <div><div class="stat-value">${money(
          u.landed_cogs_gbp,
        )}</div><div class="stat-label">Landed COGS</div></div>
      </div>
      <p class="muted footnote">
        Landed COGS = product £${Number(u.product_cost_gbp ?? 0).toFixed(2)}/u
        + CJ postage £${Number(u.postage_gbp ?? 0).toFixed(2)}/u
        (total postage ${money(summary.postage_gbp ?? s?.postage)}).
      </p>
      <p class="muted footnote">ROAS = revenue ÷ ads. ROAS (after COGS) = contribution before ads ÷ ads (product + CJ postage + fees). POAS = profit ÷ ads.</p>
      <p class="muted footnote">${escapeHtml(summary.source_note || "")} ${escapeHtml(
        c.note || "",
      )}</p>
    `;
  }

  const objRows = (m?.by_object || [])
    .slice(0, 12)
    .map(
      (o) => `<tr>
        <td>${escapeHtml(o.level)}</td>
        <td>${escapeHtml(o.name || o.id)}</td>
        <td>${money(o.spend)}</td>
        <td>${o.purchases}</td>
        <td>${o.cpa == null ? "—" : money(o.cpa)}</td>
        <td>${o.roas == null ? "—" : `${Number(o.roas).toFixed(2)}×`}</td>
      </tr>`,
    )
    .join("");

  const detailBits = [];
  if (s) {
    detailBits.push(
      `Shopify: ${s.units} units · ${money(s.revenue)} rev · ${money(s.cogs)} COGS · ${money(
        s.fees,
      )} fees · ${s.orders} orders`,
    );
  }
  if (m) {
    detailBits.push(
      `Meta: ${money(m.spend)} spend · ${m.purchases} purch · CPA ${
        m.cpa == null ? "—" : money(m.cpa)
      } · attr ROAS ${m.roas == null ? "—" : `${Number(m.roas).toFixed(2)}×`}`,
    );
  }
  if (summary?.totals?.poas != null) {
    detailBits.push(`POAS ${Number(summary.totals.poas).toFixed(2)}×`);
  }

  const applyCpa =
    m?.cpa != null
      ? `<button type="button" class="btn" id="btn-apply-past-cpa">Use Meta CPA £${Number(
          m.cpa,
        ).toFixed(2)} in planner</button>`
      : c.cpa_shopify_units != null
        ? `<button type="button" class="btn" id="btn-apply-past-cpa">Use historic ads/unit £${Number(
            c.cpa_shopify_units,
          ).toFixed(2)} in planner</button>`
        : "";

  box.innerHTML = `
    <div class="wh-past-banner">
      <h2>Past performance (same KPIs as planner)</h2>
      ${kpiHtml}
      ${
        detailBits.length
          ? `<p class="muted footnote">${detailBits
              .map((b) => escapeHtml(b))
              .join(" · ")}</p>`
          : ""
      }
      ${
        objRows
          ? `<div class="table-wrap"><table>
              <thead><tr><th>Level</th><th>Name</th><th>Spend</th><th>Purch</th><th>CPA</th><th>ROAS</th></tr></thead>
              <tbody>${objRows}</tbody>
            </table></div>`
          : ""
      }
      <div class="wh-actions">${applyCpa}</div>
    </div>
  `;

  const btn = whEl("btn-apply-past-cpa");
  if (btn) {
    btn.addEventListener("click", () => {
      const val = m?.cpa ?? c.cpa_shopify_units;
      if (val != null && whEl("wh-cpa")) {
        whEl("wh-cpa").value = Number(val).toFixed(2);
      }
    });
  }
}

function renderWarehouse(data) {
  const results = whEl("wh-results");
  results.hidden = false;

  const warn = [...(data.warnings || [])];
  if (data.past_performance?.warnings?.length) {
    warn.push(...data.past_performance.warnings);
  }
  if (warn.length) showWarnings(warn);
  else showWarnings([]);

  renderPastPerformance(data.past_performance);

  const u = data.unit_economics || {};
  const t = data.totals || {};
  const op = data.overall_pnl || {};
  const label = whEl("wh-label").value || data.warehouse;
  const postageOn = u.include_postage !== false;
  const profit = op.profit_gbp;
  const profitCls =
    profit == null ? "" : profit >= 0 ? "success" : "danger";

  const adsDaily = Number(data.inputs?.daily_ad_spend_gbp) || 0;
  const adsCpa = Number(data.inputs?.ad_cost_per_purchase_gbp) || 0;
  const adsBits = [];
  if (adsDaily) {
    adsBits.push(
      data.inputs?.stop_ads_when_stock_zero
        ? `£${adsDaily.toFixed(0)}/day (stops at 0)`
        : `£${adsDaily.toFixed(0)}/day`,
    );
  }
  if (adsCpa) adsBits.push(`£${adsCpa.toFixed(2)}/purchase`);
  const adsNote = adsBits.length ? ` · ads ${adsBits.join(" + ")}` : "";
  const trackStock = data.inputs?.track_stock !== false;
  const rs = data.restock;
  const restockNote =
    trackStock && rs?.enabled && rs.events
      ? ` · restock ${rs.qty}× every ${rs.every_days}d (${rs.events}×)`
      : "";
  const modeNote = trackStock
    ? " · wholesale/dropship (stock tracked)"
    : " · stock ignored";

  const marginInc =
    u.margin_after_ads == null ? "—" : `${Math.round(u.margin_after_ads * 100)}%`;
  const marginIncCls =
    u.margin_after_ads == null
      ? ""
      : u.margin_after_ads >= 0
        ? "success"
        : "danger";
  const roasVal = t.roas ?? op.roas ?? u.roas;
  const roasLabel = roasVal == null ? "—" : `${Number(roasVal).toFixed(2)}×`;
  const roasCls =
    roasVal == null ? "" : roasVal >= 2 ? "success" : roasVal >= 1 ? "" : "danger";
  const roasCogsVal = t.roas_after_cogs ?? op.roas_after_cogs ?? u.roas_after_cogs;
  const roasCogsLabel =
    roasCogsVal == null ? "—" : `${Number(roasCogsVal).toFixed(2)}×`;
  const roasCogsCls =
    roasCogsVal == null
      ? ""
      : roasCogsVal >= 1
        ? "success"
        : roasCogsVal >= 0
          ? ""
          : "danger";

  whEl("wh-summary").innerHTML = `
    <h3>${escapeHtml(label)}</h3>
    <p class="detail-meta muted">${escapeHtml(data.warehouse)} · ${escapeHtml(
      data.inputs?.stock_lane_label || "",
    )} · postage ${postageOn ? "included" : "excluded"}${adsNote}${restockNote}${modeNote}</p>
    <div class="wh-kpi">
      <div><div class="stat-value ${profitCls}">${money(
        profit,
        0,
      )}</div><div class="stat-label">Overall P&amp;L</div></div>
      <div><div class="stat-value ${marginIncCls}">${marginInc}</div><div class="stat-label">Margin (inc ads)</div></div>
      <div><div class="stat-value ${roasCls}">${roasLabel}</div><div class="stat-label">ROAS</div></div>
      <div><div class="stat-value ${roasCogsCls}">${roasCogsLabel}</div><div class="stat-label">ROAS (after COGS)</div></div>
      <div><div class="stat-value ${u.contribution_after_ads_gbp >= 0 ? "success" : "danger"}">${money(
        u.contribution_after_ads_gbp,
      )}</div><div class="stat-label">Contrib after ads</div></div>
      <div><div class="stat-value">${money(u.landed_cogs_gbp)}</div><div class="stat-label">Landed COGS</div></div>
    </div>
    <p class="muted footnote">ROAS = revenue ÷ ads. ROAS (after COGS) = contribution before ads ÷ ads (landed COGS + fees). POAS = profit ÷ ads.</p>
    <p class="muted footnote">${escapeHtml(data.disclaimer || "")}</p>
    ${
      data.moq && !data.moq.met
        ? `<p class="wh-moq">MOQ not met (need ≥${data.moq.total} total / ≥${data.moq.per_variant} per variant for overseas).</p>`
        : ""
    }
  `;

  whEl("wh-stats").innerHTML = [
    ["Units sold", t.units_sold],
    ...(trackStock
      ? [
          ["Units left", t.units_left],
          ["Units received", t.units_received ?? t.units_sold],
          [
            "Sell-through",
            t.sell_through_pct == null
              ? "—"
              : `${Math.round(t.sell_through_pct * 100)}%`,
          ],
          [
            "Days to clear",
            t.days_to_clear ?? (data.restock?.enabled ? "n/a (restock)" : "—"),
          ],
          ["Inbound £", money(t.inbound_gbp)],
          ["Storage £", money(t.storage_gbp)],
        ]
      : []),
    ["Outbound £", money(t.outbound_gbp)],
    ["Postage £", postageOn ? money(t.last_mile_in_cogs_gbp) : `${money(t.last_mile_gbp)} excl.`],
    ["Ads £", money(t.ads_gbp)],
    ["Revenue £", money(t.revenue_gbp)],
    ["ROAS", t.roas == null ? "—" : `${Number(t.roas).toFixed(2)}×`],
    [
      "ROAS (after COGS)",
      t.roas_after_cogs == null ? "—" : `${Number(t.roas_after_cogs).toFixed(2)}×`,
    ],
    ["POAS", t.poas == null ? "—" : `${Number(t.poas).toFixed(2)}×`],
    [
      "Net margin",
      t.net_margin == null ? "—" : `${Math.round(t.net_margin * 100)}%`,
    ],
  ]
    .map(
      ([lab, val]) =>
        `<div class="stat"><div class="stat-value">${val}</div><div class="stat-label">${lab}</div></div>`,
    )
    .join("");

  const unitRows = [
    ["Sell price", money(u.sell_price_gbp)],
    ["Product cost", money(u.product_cost_gbp)],
    ...(trackStock
      ? [
          ["Inbound (allocated)", money(u.inbound_alloc_gbp)],
          ["Storage (allocated)", money(u.storage_alloc_gbp)],
        ]
      : []),
    ["Outbound fee", money(u.outbound_gbp)],
    [
      postageOn ? "Postage (in COGS)" : "Postage (excluded)",
      postageOn
        ? money(u.last_mile_gbp)
        : `${money(u.last_mile_actual_gbp)} not in COGS`,
    ],
    ["Landed COGS", money(u.landed_cogs_gbp)],
    ["Checkout fee", money(u.checkout_fee_gbp)],
    ["Contribution", money(u.contribution_gbp)],
    ["Margin (ex ads)", u.margin == null ? "—" : `${Math.round(u.margin * 100)}%`],
    ["Ads / sold unit", money(u.ads_alloc_gbp)],
    ["Contrib after ads", money(u.contribution_after_ads_gbp)],
    [
      "Margin (inc ads)",
      u.margin_after_ads == null ? "—" : `${Math.round(u.margin_after_ads * 100)}%`,
    ],
    ["ROAS", u.roas == null ? "—" : `${Number(u.roas).toFixed(2)}×`],
    [
      "ROAS (after COGS)",
      u.roas_after_cogs == null ? "—" : `${Number(u.roas_after_cogs).toFixed(2)}×`,
    ],
    ["POAS", u.poas == null ? "—" : `${Number(u.poas).toFixed(2)}×`],
  ];
  whEl("wh-unit-table").querySelector("tbody").innerHTML = unitRows
    .map(([k, v]) => `<tr><th>${k}</th><td>${v}</td></tr>`)
    .join("");

  const transitBody = whEl("wh-transit-table").querySelector("tbody");
  const stockDays = data.transit?.stock_to_warehouse || "—";
  const lm = data.transit?.last_mile || {};
  transitBody.innerHTML = [
    ["Stock CN → warehouse", stockDays],
    ["Warehouse → UK", lm.UK || "—"],
    ["Warehouse → EU", lm.EU || "—"],
    ["Warehouse → US", lm.US || "—"],
    ["Warehouse → CAN", lm.CAN || "—"],
  ]
    .map(([k, v]) => `<tr><td>${escapeHtml(k)}</td><td>${escapeHtml(v)}</td></tr>`)
    .join("");

  whEl("wh-mile-table").querySelector("tbody").innerHTML = (data.milestones || [])
    .map(
      (m) => `<tr>
        <td>${m.label}</td>
        <td>${m.cum_sold}</td>
        <td>${m.remaining}</td>
        <td>${money(m.cum_storage_gbp)}</td>
        <td class="${m.cum_pnl_gbp >= 0 ? "pos" : "neg"}">${money(m.cum_pnl_gbp)}</td>
      </tr>`,
    )
    .join("");

  // Update milestones header to say P&L
  const mileHead = whEl("wh-mile-table").querySelector("thead tr");
  if (mileHead) {
    mileHead.innerHTML =
      "<th></th><th>Sold</th><th>Left</th><th>Storage</th><th>Cum P&amp;L</th>";
  }

  const ot = data.one_time_usd || {};
  whEl("wh-inbound-table").querySelector("tbody").innerHTML = [
    ["Inspection (per SKU)", `$${ot.inspection}`],
    ["Unload (cartons)", `$${ot.unload}`],
    ["Inbound units", `$${ot.inbound_units}`],
    ["SKU labels", `$${ot.labels}`],
    ["Stock shipping CN→WH", `$${ot.stock_shipping}`],
    ["Total USD (initial)", `$${ot.total}`],
    ["Total GBP (initial)", money(data.one_time_gbp)],
    ...(data.restock?.enabled
      ? [
          [
            "Restock inbound (all events)",
            money((data.totals?.inbound_gbp || 0) - (data.one_time_gbp || 0)),
          ],
          ["Restock events", String(data.restock.events)],
        ]
      : []),
  ]
    .map(([k, v]) => `<tr><th>${k}</th><td>${v}</td></tr>`)
    .join("");

  renderOverallPnl(op, trackStock);
  renderWhChart(data);
}

function renderOverallPnl(op, trackStock = true) {
  const note = whEl("wh-pnl-note");
  const tbody = whEl("wh-pnl-table").querySelector("tbody");
  const verdict = whEl("wh-pnl-verdict");
  if (!op || !tbody) return;

  if (note) note.textContent = op.note || "";

  const c = op.costs || {};
  const rows = [
    ["Revenue", money(op.revenue_gbp), "rev"],
    ["Product COGS (sold)", money(c.product_cogs_gbp), "cost"],
    ...(trackStock
      ? [
          ["Inbound (full stock-in)", money(c.inbound_gbp), "cost"],
          ["Storage", money(c.storage_gbp), "cost"],
        ]
      : []),
    ["Outbound fees", money(c.outbound_gbp), "cost"],
    [
      op.include_postage ? "Postage" : "Postage (excluded)",
      op.include_postage
        ? money(c.postage_gbp)
        : `${money(op.postage_excluded_gbp)} not in P&L`,
      op.include_postage ? "cost" : "memo",
    ],
    ["Checkout fees", money(c.checkout_fees_gbp), "cost"],
    ["Ads", money(c.ads_gbp), "cost"],
    [
      "ROAS",
      op.roas == null ? "—" : `${Number(op.roas).toFixed(2)}×`,
      "memo",
    ],
    [
      "ROAS (after COGS)",
      op.roas_after_cogs == null ? "—" : `${Number(op.roas_after_cogs).toFixed(2)}×`,
      "memo",
    ],
    [
      "POAS (profit ÷ ads)",
      op.poas == null ? "—" : `${Number(op.poas).toFixed(2)}×`,
      "memo",
    ],
    [
      "Net margin (inc ads)",
      op.net_margin == null ? "—" : `${Math.round(op.net_margin * 100)}%`,
      "memo",
    ],
    ["Total costs", money(op.total_costs_gbp), "sub"],
    [
      op.is_profit ? "Profit" : "Loss",
      money(op.profit_gbp),
      op.is_profit ? "profit" : "loss",
    ],
    ...(trackStock
      ? [["Leftover stock (at product cost)", money(op.inventory_residual_gbp), "memo"]]
      : []),
  ];

  tbody.innerHTML = rows
    .map(([k, v, kind]) => {
      const cls =
        kind === "profit"
          ? "wh-pnl-profit"
          : kind === "loss"
            ? "wh-pnl-loss"
            : kind === "sub"
              ? "wh-pnl-sub"
              : kind === "rev"
                ? "wh-pnl-rev"
                : kind === "memo"
                  ? "wh-pnl-memo"
                  : "";
      return `<tr class="${cls}"><th>${k}</th><td>${v}</td></tr>`;
    })
    .join("");

  if (verdict) {
    const p = op.profit_gbp;
    if (p == null) {
      verdict.innerHTML = "";
      return;
    }
    if (p >= 0) {
      verdict.innerHTML = `<div class="wh-pnl-banner profit">Estimated profit ${money(
        p,
        0,
      )} over the horizon</div>`;
    } else {
      verdict.innerHTML = `<div class="wh-pnl-banner loss">Estimated loss ${money(
        p,
        0,
      )} over the horizon</div>`;
    }
  }
}

function renderWhChart(data) {
  const days = data.days || [];
  const ctx = whEl("wh-chart");
  if (whChart) {
    whChart.destroy();
    whChart = null;
  }
  const ads =
    (data.inputs?.daily_ad_spend_gbp || 0) +
    (data.inputs?.ad_cost_per_purchase_gbp || 0);
  const restockOn = data.restock?.enabled;
  const trackStock = data.inputs?.track_stock !== false;
  whEl("wh-chart-note").textContent = trackStock
    ? [
        ads
          ? "Cumulative P&L (after ads) vs remaining inventory."
          : "Cumulative P&L vs remaining inventory.",
        "Inbound sunk on stock-in days.",
        restockOn ? "Sawtooth = restock events." : "",
      ]
        .filter(Boolean)
        .join(" ")
    : ads
      ? "Cumulative P&L (after ads) vs units sold. Stock not tracked."
      : "Cumulative P&L vs units sold. Stock not tracked.";

  const step = Math.max(1, Math.floor(days.length / 90));
  const sampled = days.filter((_, i) => i % step === 0 || i === days.length - 1);

  const datasets = [
    {
      label: trackStock ? "Remaining units" : "Cum sold",
      data: sampled.map((d) => (trackStock ? d.remaining : d.cum_sold)),
      borderColor: "#6b6b6b",
      yAxisID: "y1",
      tension: 0.2,
    },
    {
      label: "Cum P&L (£)",
      data: sampled.map((d) => d.cum_pnl_gbp),
      borderColor: "#067647",
      yAxisID: "y",
      tension: 0.2,
    },
    {
      label: "Cum ads (£)",
      data: sampled.map((d) => d.cum_ads_gbp),
      borderColor: "#b42318",
      yAxisID: "y",
      tension: 0.2,
      hidden: !ads,
    },
  ];

  whChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: sampled.map((d) => `D${d.day}`),
      datasets,
    },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { position: "bottom" } },
      scales: {
        y: {
          position: "left",
          ticks: { callback: (v) => `£${v}` },
        },
        y1: {
          position: "right",
          grid: { drawOnChartArea: false },
          beginAtZero: true,
        },
      },
    },
  });
}

/* Tab navigation removed — unified desk orchestrated by views.js */
