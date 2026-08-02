/* Unified desk — saved views, section toggles, Apply / Reload orchestration */

const SECTION_KEYS = [
  "desk_kpis",
  "daily",
  "product_pnl",
  "unit_economics",
  "subset",
  "ads",
  "ads_pnl",
  "warehouse",
];

const DEFAULT_SECTIONS = {
  desk_kpis: true,
  daily: true,
  product_pnl: true,
  unit_economics: false,
  subset: false,
  ads: false,
  ads_pnl: false,
  warehouse: false,
};

let activeViewId = null;
let viewsListCache = [];
let deskApplying = false;

const vEl = (id) => document.getElementById(id);

function readSectionsFromUi() {
  const out = { ...DEFAULT_SECTIONS };
  document.querySelectorAll("#section-toggles input[data-section]").forEach((inp) => {
    out[inp.dataset.section] = !!inp.checked;
  });
  return out;
}

function writeSectionsToUi(sections) {
  const s = { ...DEFAULT_SECTIONS, ...(sections || {}) };
  document.querySelectorAll("#section-toggles input[data-section]").forEach((inp) => {
    const key = inp.dataset.section;
    inp.checked = !!s[key];
  });
  applySectionVisibility();
}

function applySectionVisibility() {
  const sections = readSectionsFromUi();
  for (const key of SECTION_KEYS) {
    const node = vEl(`sec-${key}`);
    if (node) node.hidden = !sections[key];
  }
  // Subset enabled flag for app.js compatibility
  const subEn = vEl("subset-enabled");
  if (subEn) subEn.checked = !!sections.subset;

  // Ads profitability lives inside ads results visually but has its own section wrapper
  const adsPnl = vEl("ads-pnl-section");
  if (adsPnl && !sections.ads_pnl) {
    adsPnl.hidden = true;
  }

  // Lazy-init warehouse when first enabled
  if (sections.warehouse && typeof window.ensureWarehouseReady === "function") {
    window.ensureWarehouseReady().catch((e) => {
      if (typeof showWarnings === "function") {
        showWarnings([`Warehouse setup failed: ${e.message}`]);
      }
    });
  }
}

function collectViewPayload(name) {
  const scope =
    typeof window.collectAdsScopeState === "function"
      ? window.collectAdsScopeState()
      : {};
  const warehouse =
    typeof window.collectWarehouseState === "function"
      ? window.collectWarehouseState()
      : {};
  const ui = {
    chart_view: vEl("chart-view")?.value || "cumPnl",
    subset_chart_view: vEl("subset-chart-view")?.value || "cumPnl",
    ads_chart_view: vEl("ads-chart-view")?.value || "spend",
    ads_pnl_chart_view: vEl("ads-pnl-chart-view")?.value || "cumPnl",
    ads_overlay: !!vEl("ads-overlay")?.checked,
  };
  return {
    name: name || "Untitled view",
    sections: readSectionsFromUi(),
    scope,
    warehouse,
    ui,
  };
}

async function hydrateView(view) {
  if (!view) return;
  writeSectionsToUi(view.sections);

  if (typeof window.initAdsView === "function") {
    await window.initAdsView();
  }
  if (view.sections?.warehouse && typeof window.ensureWarehouseReady === "function") {
    await window.ensureWarehouseReady();
  }

  if (typeof window.applyAdsScopeState === "function" && view.scope) {
    window.applyAdsScopeState(view.scope);
  }
  if (typeof window.applyWarehouseState === "function" && view.warehouse) {
    window.applyWarehouseState(view.warehouse);
  }

  const ui = view.ui || {};
  if (ui.chart_view && vEl("chart-view")) vEl("chart-view").value = ui.chart_view;
  if (ui.subset_chart_view && vEl("subset-chart-view")) {
    vEl("subset-chart-view").value = ui.subset_chart_view;
  }
  if (ui.ads_chart_view && vEl("ads-chart-view")) {
    vEl("ads-chart-view").value = ui.ads_chart_view;
  }
  if (ui.ads_pnl_chart_view && vEl("ads-pnl-chart-view")) {
    vEl("ads-pnl-chart-view").value = ui.ads_pnl_chart_view;
  }
  if (vEl("ads-overlay")) vEl("ads-overlay").checked = !!ui.ads_overlay;

  applySectionVisibility();
}

async function refreshViewsList(selectId) {
  const data = await api("/api/views");
  viewsListCache = data.views || [];
  const sel = vEl("view-select");
  if (!sel) return;
  const keep = selectId != null ? selectId : activeViewId;
  sel.innerHTML =
    `<option value="">— Untitled —</option>` +
    viewsListCache
      .map(
        (v) =>
          `<option value="${escapeHtml(v.id)}">${escapeHtml(v.name || v.id)}</option>`,
      )
      .join("");
  sel.value = keep || "";
  activeViewId = sel.value || null;
  const del = vEl("btn-view-delete");
  if (del) del.disabled = !activeViewId;
}

async function loadViewById(id) {
  if (!id) {
    activeViewId = null;
    const del = vEl("btn-view-delete");
    if (del) del.disabled = true;
    return;
  }
  const view = await api(`/api/views/${encodeURIComponent(id)}`);
  activeViewId = view.id;
  await hydrateView(view);
  const sel = vEl("view-select");
  if (sel) sel.value = view.id;
  const del = vEl("btn-view-delete");
  if (del) del.disabled = false;
}

async function saveView({ asNew } = {}) {
  let name;
  if (asNew || !activeViewId) {
    name = window.prompt("View name", collectViewPayload().name);
    if (!name) return;
  } else {
    const current = viewsListCache.find((v) => v.id === activeViewId);
    name = current?.name || "Untitled view";
  }
  const payload = collectViewPayload(name);
  let saved;
  if (!asNew && activeViewId) {
    saved = await api(`/api/views/${encodeURIComponent(activeViewId)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } else {
    saved = await api("/api/views", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }
  activeViewId = saved.id;
  await refreshViewsList(saved.id);
}

async function deleteActiveView() {
  if (!activeViewId) return;
  if (!window.confirm("Delete this saved view?")) return;
  await api(`/api/views/${encodeURIComponent(activeViewId)}`, { method: "DELETE" });
  activeViewId = null;
  await refreshViewsList("");
}

async function runDeskApply({ pinAds = true } = {}) {
  if (deskApplying) return;
  deskApplying = true;
  const btn = vEl("btn-desk-apply");
  const reloadBtn = vEl("btn-view-reload");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Applying…";
  }
  if (reloadBtn) reloadBtn.disabled = true;

  const sections = readSectionsFromUi();
  const warnings = [];

  try {
    // Ensure Meta/SKU pickers ready when ads/subset/warehouse need them
    if (sections.ads || sections.ads_pnl || sections.subset || sections.warehouse) {
      if (typeof window.initAdsView === "function") {
        await window.initAdsView();
      }
    }
    if (sections.warehouse && typeof window.ensureWarehouseReady === "function") {
      await window.ensureWarehouseReady();
    }

    // Desk sections use latest snapshot (already loaded / refresh)
    if (sections.subset && typeof window.applySubset === "function") {
      try {
        await window.applySubset();
      } catch (e) {
        warnings.push(`Subset: ${e.message}`);
      }
    }

    if ((sections.ads || sections.ads_pnl) && typeof window.applyAdsReport === "function") {
      try {
        await window.applyAdsReport({ pin: pinAds });
        // Show/hide ads profitability section after render
        const pnlSec = vEl("ads-pnl-section");
        const adsBox = vEl("ads-results");
        if (adsBox && sections.ads) adsBox.hidden = false;
        if (pnlSec) {
          if (sections.ads_pnl && window.adsReportHasPnl?.()) {
            pnlSec.hidden = false;
          } else if (!sections.ads_pnl) {
            pnlSec.hidden = true;
          }
        }
      } catch (e) {
        warnings.push(`Ads: ${e.message}`);
      }
    } else {
      const adsBox = vEl("ads-results");
      if (adsBox && !sections.ads) adsBox.hidden = true;
      const pnlSec = vEl("ads-pnl-section");
      if (pnlSec && !sections.ads_pnl) pnlSec.hidden = true;
    }

    if (sections.warehouse && typeof window.runWarehouseCalc === "function") {
      try {
        await window.runWarehouseCalc();
      } catch (e) {
        warnings.push(`Warehouse: ${e.message}`);
      }
    }

    if (warnings.length && typeof showWarnings === "function") {
      showWarnings(warnings);
    }
  } finally {
    deskApplying = false;
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Apply";
    }
    if (reloadBtn) reloadBtn.disabled = false;
  }
}

async function reloadActiveView() {
  if (activeViewId) {
    await loadViewById(activeViewId);
  }
  await runDeskApply({ pinAds: true });
}

/** Called from app.js after Refresh data succeeds */
window.onDeskRefreshed = async function onDeskRefreshed() {
  const sections = readSectionsFromUi();
  const needsApply =
    sections.subset || sections.ads || sections.ads_pnl || sections.warehouse;
  if (needsApply) {
    await runDeskApply({ pinAds: false });
  }
};

function wireViewsUi() {
  document.querySelectorAll("#section-toggles input[data-section]").forEach((inp) => {
    inp.addEventListener("change", applySectionVisibility);
  });

  vEl("btn-desk-apply")?.addEventListener("click", () => {
    runDeskApply({ pinAds: true }).catch((e) =>
      showWarnings([`Apply failed: ${e.message}`]),
    );
  });
  vEl("btn-view-reload")?.addEventListener("click", () => {
    reloadActiveView().catch((e) => showWarnings([`Reload failed: ${e.message}`]));
  });
  vEl("btn-view-save")?.addEventListener("click", () => {
    saveView({ asNew: false }).catch((e) =>
      showWarnings([`Save failed: ${e.message}`]),
    );
  });
  vEl("btn-view-save-as")?.addEventListener("click", () => {
    saveView({ asNew: true }).catch((e) =>
      showWarnings([`Save as failed: ${e.message}`]),
    );
  });
  vEl("btn-view-delete")?.addEventListener("click", () => {
    deleteActiveView().catch((e) =>
      showWarnings([`Delete failed: ${e.message}`]),
    );
  });
  vEl("view-select")?.addEventListener("change", (e) => {
    const id = e.target.value;
    if (!id) {
      activeViewId = null;
      const del = vEl("btn-view-delete");
      if (del) del.disabled = true;
      return;
    }
    loadViewById(id)
      .then(() => runDeskApply({ pinAds: false }))
      .catch((err) => showWarnings([`Load view failed: ${err.message}`]));
  });

  applySectionVisibility();
}

async function bootViews() {
  wireViewsUi();
  try {
    await refreshViewsList();
  } catch (e) {
    console.warn("Views list failed:", e);
  }

  // Ensure Meta tree + SKUs ready for scope
  if (typeof window.initAdsView === "function") {
    try {
      await window.initAdsView();
    } catch (e) {
      showWarnings([`Scope setup failed: ${e.message}`]);
    }
  }

  const fromUrl = new URLSearchParams(location.search).get("view");
  if (fromUrl && fromUrl !== "ads" && fromUrl !== "warehouse" && fromUrl !== "pnl") {
    try {
      await loadViewById(fromUrl);
      await runDeskApply({ pinAds: false });
    } catch (e) {
      showWarnings([`Could not load view ${fromUrl}: ${e.message}`]);
    }
  }
}

bootViews();
