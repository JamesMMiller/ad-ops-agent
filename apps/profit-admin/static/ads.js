/* Ads performance desk — Meta Insights for campaigns / ad sets / ads */

const OVERLAY_CAP = 12;
const ADS_CHART_VIEWS = ["spend", "purchRev", "roas", "ctr"];
const OVERLAY_COLORS = [
  "#1f4b99",
  "#b42318",
  "#067647",
  "#b54708",
  "#6941c6",
  "#026aa2",
  "#c11574",
  "#3e4784",
  "#875a12",
  "#027a48",
  "#912018",
  "#3538cd",
];

let adsStructure = null;
let adsSkuCatalog = null;
let adsReport = null;
let adsChart = null;
let adsPnlChart = null;
let adsSortKey = "spend";
let adsSortDir = -1;
let adsWired = false;
let adsCatalog = []; // flat searchable Meta index
let adsSelected = {
  campaign: new Set(),
  adset: new Set(),
  ad: new Set(),
};
let adsSuggestItems = [];
let adsSuggestIndex = -1;
let adsListFilter = "";
let adsFocusCamp = null;
let adsFocusAdset = null;
let adsActiveOnly = true;
let adsVisibleIds = { campaign: [], adset: [], ad: [] };
const ADS_PNL_CHART_VIEWS = ["cumPnl", "cumRevCost", "dailyStack", "mer"];

const ADS_LEVEL_LABEL = {
  campaign: "Campaign",
  adset: "Ad set",
  ad: "Ad",
};
const adsEl = (id) => document.getElementById(id);

function adsMoney(n, digits = 2) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  return `£${Number(n).toLocaleString("en-GB", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}`;
}

function adsNum(n, digits = 0) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  return Number(n).toLocaleString("en-GB", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

function adsX(n) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  return `${Number(n).toFixed(2)}×`;
}

function adsPct(n, digits = 2) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  return `${Number(n).toFixed(digits)}%`;
}

async function initAdsView() {
  if (!adsStructure) {
    const [structure, cat] = await Promise.all([
      api("/api/meta/structure"),
      api("/api/catalog").catch(() => ({ catalog: [] })),
    ]);
    adsStructure = structure;
    adsSkuCatalog = cat.catalog || [];
    buildAdsCatalog();
    fillAdsSkuSelect();
    renderAdsPickers();
    renderAdsChips();
  }
  if (!adsWired) {
    wireAdsControls();
    adsWired = true;
  }
  updateAdsSelectionNote();
  updateAdsSkuCount();
}

window.initAdsView = initAdsView;

function wireAdsControls() {
  adsEl("ads-preset")?.addEventListener("change", () => {
    syncAdsCustomDates();
    syncWhPastPresetFromScope();
  });
  adsEl("btn-ads-export")?.addEventListener("click", () => {
    exportAdsPdf().catch((e) => showWarnings([`Ads PDF export failed: ${e.message}`]));
  });
  adsEl("ads-overlay")?.addEventListener("change", () => renderAdsChart());
  adsEl("ads-chart-view")?.addEventListener("change", () => renderAdsChart());
  adsEl("ads-pnl-chart-view")?.addEventListener("change", () => renderAdsPnlChart());
  adsEl("btn-ads-camps-none")?.addEventListener("click", () => clearAdsLevel("campaign"));
  adsEl("btn-ads-adsets-none")?.addEventListener("click", () => clearAdsLevel("adset"));
  adsEl("btn-ads-ads-none")?.addEventListener("click", () => clearAdsLevel("ad"));
  adsEl("btn-ads-camps-all")?.addEventListener("click", () => selectAdsVisible("campaign"));
  adsEl("btn-ads-adsets-all")?.addEventListener("click", () => selectAdsVisible("adset"));
  adsEl("btn-ads-ads-all")?.addEventListener("click", () => selectAdsVisible("ad"));
  adsEl("btn-ads-clear-all")?.addEventListener("click", clearAllAdsSelection);
  adsEl("btn-ads-focus-clear")?.addEventListener("click", () => {
    adsFocusCamp = null;
    adsFocusAdset = null;
    renderAdsPickers();
  });
  adsEl("ads-active-only")?.addEventListener("change", (e) => {
    adsActiveOnly = !!e.target.checked;
    renderAdsPickers();
  });
  adsEl("btn-ads-sku-clear")?.addEventListener("click", () => {
    const sel = adsEl("ads-sku");
    if (!sel) return;
    [...sel.options].forEach((o) => {
      o.selected = false;
    });
    updateAdsSkuCount();
  });
  adsEl("btn-ads-sku-product")?.addEventListener("click", selectAdsSkuProductVariants);
  adsEl("ads-sku")?.addEventListener("change", updateAdsSkuCount);

  const search = adsEl("ads-search");
  if (search) {
    search.addEventListener("input", () => {
      adsListFilter = search.value.trim();
      openAdsSuggest(adsListFilter);
      renderAdsPickers();
    });
    search.addEventListener("keydown", onAdsSearchKeydown);
    search.addEventListener("focus", () => {
      if (search.value.trim()) openAdsSuggest(search.value.trim());
    });
  }

  document.addEventListener("click", (e) => {
    const box = adsEl("ads-combobox");
    if (box && !box.contains(e.target)) closeAdsSuggest();
  });

  adsEl("ads-chips")?.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-remove-level]");
    if (!btn) return;
    toggleAdsSelection(btn.dataset.removeLevel, btn.dataset.removeId, false);
  });

  adsEl("ads-table")?.querySelectorAll("th[data-sort]").forEach((th) => {
    th.style.cursor = "pointer";
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      if (adsSortKey === key) adsSortDir *= -1;
      else {
        adsSortKey = key;
        adsSortDir = key === "name" || key === "level" || key === "parent" ? 1 : -1;
      }
      renderAdsTable();
    });
  });

  // Tree list: checkbox = select (any campaign); row click = optional browse focus
  const tree = adsEl("ads-tree");
  tree?.addEventListener("change", (e) => {
    const input = e.target;
    if (!(input instanceof HTMLInputElement) || input.type !== "checkbox") return;
    const level =
      input.name === "ads-camp" ? "campaign" : input.name === "ads-adset" ? "adset" : "ad";
    // Selection must not lock browse-focus — mix ad sets/ads across campaigns.
    toggleAdsSelection(level, input.value, input.checked);
  });
  tree?.addEventListener("click", (e) => {
    const childBtn = e.target.closest("[data-select-children]");
    if (childBtn) {
      e.preventDefault();
      e.stopPropagation();
      selectAdsChildren(childBtn.dataset.selectChildren, childBtn.dataset.id);
      return;
    }
    const row = e.target.closest("[data-focus-level]");
    if (!row) return;
    if (e.target.closest("input,button,a")) return;
    const level = row.dataset.focusLevel;
    const id = row.dataset.focusId;
    if (level === "campaign") {
      adsFocusCamp = adsFocusCamp === id ? null : id;
      adsFocusAdset = null;
    } else if (level === "adset") {
      const a = (adsStructure?.adsets || []).find((x) => x.id === id);
      if (a?.campaign_id) adsFocusCamp = a.campaign_id;
      adsFocusAdset = adsFocusAdset === id ? null : id;
    }
    renderAdsPickers();
  });

  syncAdsCustomDates();
}

function syncAdsCustomDates() {
  const custom = adsEl("ads-preset")?.value === "custom";
  const sinceWrap = adsEl("ads-custom-since-wrap");
  const untilWrap = adsEl("ads-custom-until-wrap");
  if (sinceWrap) sinceWrap.hidden = !custom;
  if (untilWrap) untilWrap.hidden = !custom;
}

function buildAdsCatalog() {
  const items = [];
  for (const c of adsStructure?.campaigns || []) {
    items.push({
      level: "campaign",
      id: c.id,
      name: c.name || c.id,
      status: c.status || "",
      parent: "",
      campaign_id: c.id,
      adset_id: null,
      haystack: `${c.name || ""} ${c.status || ""} ${c.id}`.toLowerCase(),
    });
  }
  for (const a of adsStructure?.adsets || []) {
    items.push({
      level: "adset",
      id: a.id,
      name: a.name || a.id,
      status: a.status || "",
      parent: a.campaign_name || "",
      campaign_id: a.campaign_id || null,
      adset_id: a.id,
      haystack: `${a.name || ""} ${a.campaign_name || ""} ${a.status || ""} ${a.id}`.toLowerCase(),
    });
  }
  for (const a of adsStructure?.ads || []) {
    const parent = [a.campaign_name, a.adset_name].filter(Boolean).join(" · ");
    items.push({
      level: "ad",
      id: a.id,
      name: a.name || a.id,
      status: a.status || "",
      parent,
      campaign_id: a.campaign_id || null,
      adset_id: a.adset_id || null,
      haystack: `${a.name || ""} ${a.adset_name || ""} ${a.campaign_name || ""} ${a.status || ""} ${a.id}`.toLowerCase(),
    });
  }
  adsCatalog = items;
}

function isAdsStatusActive(status) {
  const s = String(status || "").toUpperCase();
  if (!s) return true;
  return s === "ACTIVE" || s === "ENABLED" || s.includes("ACTIVE");
}

function selectAdsVisible(level) {
  for (const id of adsVisibleIds[level] || []) {
    adsSelected[level].add(id);
  }
  renderAdsChips();
  renderAdsPickers();
  updateAdsSelectionNote();
}

function selectAdsChildren(kind, id) {
  // Add children to the selection without changing browse-focus, so picks
  // from other campaigns stay visible and selectable.
  if (kind === "campaign-adsets") {
    for (const a of adsStructure?.adsets || []) {
      if (a.campaign_id === id && (!adsActiveOnly || isAdsStatusActive(a.status))) {
        adsSelected.adset.add(a.id);
      }
    }
  } else if (kind === "campaign-ads") {
    for (const a of adsStructure?.ads || []) {
      if (a.campaign_id === id && (!adsActiveOnly || isAdsStatusActive(a.status))) {
        adsSelected.ad.add(a.id);
      }
    }
  } else if (kind === "adset-ads") {
    for (const ad of adsStructure?.ads || []) {
      if (ad.adset_id === id && (!adsActiveOnly || isAdsStatusActive(ad.status))) {
        adsSelected.ad.add(ad.id);
      }
    }
  }
  renderAdsChips();
  renderAdsPickers();
  updateAdsSelectionNote();
}

function scoreAdsMatch(item, tokens) {
  if (!tokens.length) return 0;
  let score = 0;
  const name = (item.name || "").toLowerCase();
  for (const t of tokens) {
    if (!item.haystack.includes(t)) return -1;
    if (name.startsWith(t)) score += 40;
    else if (name.includes(t)) score += 24;
    else score += 8;
  }
  // Prefer shorter names / active-ish status slightly
  score += Math.max(0, 12 - Math.min(name.length, 12));
  if (/active|enabled/i.test(item.status)) score += 3;
  return score;
}

function searchAdsCatalog(query, limit = 12) {
  const q = (query || "").trim().toLowerCase();
  if (!q) return [];
  const tokens = q.split(/\s+/).filter(Boolean);
  const ranked = [];
  for (const item of adsCatalog) {
    const score = scoreAdsMatch(item, tokens);
    if (score < 0) continue;
    ranked.push({ item, score });
  }
  ranked.sort((a, b) => b.score - a.score || a.item.name.localeCompare(b.item.name));
  return ranked.slice(0, limit).map((r) => r.item);
}

function isAdsSelected(level, id) {
  return adsSelected[level]?.has(id) || false;
}

function toggleAdsSelection(level, id, force) {
  const set = adsSelected[level];
  if (!set || !id) return;
  const on = force == null ? !set.has(id) : !!force;
  if (on) set.add(id);
  else set.delete(id);
  renderAdsChips();
  renderAdsPickers();
  updateAdsSelectionNote();
  // Keep suggest highlight state in sync (selected badge)
  if (!adsEl("ads-suggest")?.hidden) {
    openAdsSuggest(adsEl("ads-search")?.value || "");
  }
}

function clearAdsLevel(level) {
  adsSelected[level]?.clear();
  renderAdsChips();
  renderAdsPickers();
  updateAdsSelectionNote();
}

function clearAllAdsSelection() {
  adsSelected.campaign.clear();
  adsSelected.adset.clear();
  adsSelected.ad.clear();
  renderAdsChips();
  renderAdsPickers();
  updateAdsSelectionNote();
  closeAdsSuggest();
}

function findAdsCatalogItem(level, id) {
  return adsCatalog.find((x) => x.level === level && x.id === id) || null;
}

function openAdsSuggest(query) {
  const panel = adsEl("ads-suggest");
  const input = adsEl("ads-search");
  if (!panel || !input) return;
  adsSuggestItems = searchAdsCatalog(query, 12);
  adsSuggestIndex = adsSuggestItems.length ? 0 : -1;
  if (!adsSuggestItems.length) {
    if ((query || "").trim()) {
      panel.hidden = false;
      panel.innerHTML = `<div class="ads-suggest-empty">No matches for “${escapeHtml(
        query.trim(),
      )}”</div>`;
      input.setAttribute("aria-expanded", "true");
    } else {
      closeAdsSuggest();
    }
    return;
  }
  panel.hidden = false;
  input.setAttribute("aria-expanded", "true");
  panel.innerHTML = adsSuggestItems
    .map((item, i) => {
      const selected = isAdsSelected(item.level, item.id);
      const active = i === adsSuggestIndex ? " is-active" : "";
      const sel = selected ? " is-selected" : "";
      return `<button type="button" class="ads-suggest-item${active}${sel}" role="option"
        id="ads-opt-${i}"
        data-idx="${i}"
        aria-selected="${i === adsSuggestIndex}">
        <span class="ads-suggest-type ads-type-${escapeHtml(item.level)}">${escapeHtml(
          ADS_LEVEL_LABEL[item.level],
        )}</span>
        <span class="ads-suggest-main">
          <span class="ads-suggest-name">${escapeHtml(item.name)}</span>
          ${
            item.parent
              ? `<span class="ads-suggest-parent">${escapeHtml(item.parent)}</span>`
              : ""
          }
        </span>
        <span class="ads-suggest-meta">${escapeHtml(item.status || "")}${
          selected ? " · selected" : ""
        }</span>
      </button>`;
    })
    .join("");

  panel.querySelectorAll(".ads-suggest-item").forEach((btn) => {
    btn.addEventListener("mousedown", (e) => {
      e.preventDefault(); // keep focus in input
      const idx = Number(btn.dataset.idx);
      pickAdsSuggest(idx);
    });
  });
}

function closeAdsSuggest() {
  const panel = adsEl("ads-suggest");
  const input = adsEl("ads-search");
  if (panel) {
    panel.hidden = true;
    panel.innerHTML = "";
  }
  if (input) input.setAttribute("aria-expanded", "false");
  adsSuggestItems = [];
  adsSuggestIndex = -1;
}

function highlightAdsSuggest(idx) {
  const panel = adsEl("ads-suggest");
  if (!panel || !adsSuggestItems.length) return;
  adsSuggestIndex = Math.max(0, Math.min(idx, adsSuggestItems.length - 1));
  panel.querySelectorAll(".ads-suggest-item").forEach((el, i) => {
    el.classList.toggle("is-active", i === adsSuggestIndex);
    el.setAttribute("aria-selected", i === adsSuggestIndex ? "true" : "false");
  });
  const active = panel.querySelector(".ads-suggest-item.is-active");
  active?.scrollIntoView({ block: "nearest" });
}

function pickAdsSuggest(idx) {
  const item = adsSuggestItems[idx];
  if (!item) return;
  toggleAdsSelection(item.level, item.id, true);
  const input = adsEl("ads-search");
  if (input) {
    input.value = "";
    adsListFilter = "";
  }
  closeAdsSuggest();
  renderAdsPickers();
  input?.focus();
}

function onAdsSearchKeydown(e) {
  const panel = adsEl("ads-suggest");
  const open = panel && !panel.hidden;
  if (e.key === "ArrowDown") {
    e.preventDefault();
    if (!open) openAdsSuggest(adsEl("ads-search")?.value || "");
    else highlightAdsSuggest(adsSuggestIndex < 0 ? 0 : adsSuggestIndex + 1);
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    if (open) highlightAdsSuggest(adsSuggestIndex - 1);
  } else if (e.key === "Enter") {
    if (open && adsSuggestIndex >= 0) {
      e.preventDefault();
      pickAdsSuggest(adsSuggestIndex);
    }
  } else if (e.key === "Escape") {
    if (open) {
      e.preventDefault();
      closeAdsSuggest();
    }
  } else if (e.key === "Backspace" && !(adsEl("ads-search")?.value || "")) {
    // Remove last chip when search is empty
    const order = ["ad", "adset", "campaign"];
    for (const level of order) {
      const ids = [...adsSelected[level]];
      if (ids.length) {
        e.preventDefault();
        toggleAdsSelection(level, ids[ids.length - 1], false);
        break;
      }
    }
  }
}

function renderAdsChips() {
  const host = adsEl("ads-chips");
  if (!host) return;
  const chips = [];
  for (const level of ["campaign", "adset", "ad"]) {
    for (const id of adsSelected[level]) {
      const item = findAdsCatalogItem(level, id) || {
        level,
        id,
        name: id,
        parent: "",
        status: "",
      };
      chips.push(item);
    }
  }
  if (!chips.length) {
    host.hidden = true;
    host.innerHTML = "";
    return;
  }
  host.hidden = false;
  host.innerHTML = chips
    .map(
      (item) => `<span class="ads-chip ads-chip-${escapeHtml(item.level)}" title="${escapeHtml(
        item.parent || item.status || "",
      )}">
        <span class="ads-chip-type">${escapeHtml(ADS_LEVEL_LABEL[item.level])}</span>
        <span class="ads-chip-name">${escapeHtml(item.name)}</span>
        <button type="button" class="ads-chip-x" data-remove-level="${escapeHtml(
          item.level,
        )}" data-remove-id="${escapeHtml(item.id)}" aria-label="Remove ${escapeHtml(
          item.name,
        )}">×</button>
      </span>`,
    )
    .join("");
}

function matchesAdsListFilter(parts) {
  const q = (adsListFilter || "").trim().toLowerCase();
  if (!q) return true;
  const tokens = q.split(/\s+/).filter(Boolean);
  const hay = parts.map((p) => String(p || "").toLowerCase()).join(" ");
  return tokens.every((t) => hay.includes(t));
}

function checkedAdsIds(name) {
  const level =
    name === "ads-camp" ? "campaign" : name === "ads-adset" ? "adset" : "ad";
  return [...adsSelected[level]];
}

function statusBadge(status) {
  const s = status || "";
  const active = isAdsStatusActive(s);
  return `<span class="ads-status ${active ? "is-active" : "is-off"}">${escapeHtml(s || "—")}</span>`;
}

function renderAdsPickers() {
  const camps = adsEl("ads-campaigns");
  const sets = adsEl("ads-adsets");
  const ads = adsEl("ads-ads");
  if (!camps || !sets || !ads || !adsStructure) return;

  const campaigns = (adsStructure.campaigns || []).filter((c) => {
    if (adsActiveOnly && !isAdsStatusActive(c.status) && !adsSelected.campaign.has(c.id)) {
      return false;
    }
    return matchesAdsListFilter([c.name, c.status, c.id]);
  });

  const adsets = (adsStructure.adsets || []).filter((a) => {
    const selected = adsSelected.adset.has(a.id);
    if (adsActiveOnly && !isAdsStatusActive(a.status) && !selected) return false;
    // Browse-focus narrows the list, but keep already-selected rows from any campaign.
    if (!selected && adsFocusCamp && a.campaign_id !== adsFocusCamp) return false;
    if (selected) return true;
    return matchesAdsListFilter([a.name, a.campaign_name, a.status, a.id]);
  });

  const adRows = (adsStructure.ads || []).filter((a) => {
    const selected = adsSelected.ad.has(a.id);
    if (adsActiveOnly && !isAdsStatusActive(a.status) && !selected) return false;
    if (!selected) {
      if (adsFocusAdset && a.adset_id !== adsFocusAdset) return false;
      else if (adsFocusCamp && a.campaign_id !== adsFocusCamp) return false;
      return matchesAdsListFilter([a.name, a.adset_name, a.campaign_name, a.status, a.id]);
    }
    return true;
  });

  // Selected cross-campaign rows first, then name — easier to manage mixed picks.
  const byName = (a, b) => String(a.name || "").localeCompare(String(b.name || ""));
  adsets.sort((a, b) => {
    const sa = adsSelected.adset.has(a.id) ? 0 : 1;
    const sb = adsSelected.adset.has(b.id) ? 0 : 1;
    return sa - sb || byName(a, b);
  });
  adRows.sort((a, b) => {
    const sa = adsSelected.ad.has(a.id) ? 0 : 1;
    const sb = adsSelected.ad.has(b.id) ? 0 : 1;
    return sa - sb || byName(a, b);
  });

  adsVisibleIds = {
    campaign: campaigns.map((c) => c.id),
    adset: adsets.map((a) => a.id),
    ad: adRows.map((a) => a.id),
  };

  const countCamps = adsEl("ads-count-camps");
  const countSets = adsEl("ads-count-adsets");
  const countAds = adsEl("ads-count-ads");
  if (countCamps) countCamps.textContent = `(${campaigns.length})`;
  if (countSets) countSets.textContent = `(${adsets.length})`;
  if (countAds) countAds.textContent = `(${adRows.length})`;

  const focusNote = adsEl("ads-focus-note");
  if (focusNote) {
    if (adsFocusAdset) {
      const a = (adsStructure.adsets || []).find((x) => x.id === adsFocusAdset);
      focusNote.textContent = `Browse filter: ads in “${a?.name || adsFocusAdset}” (selected rows from other campaigns stay visible). Show all to clear.`;
    } else if (adsFocusCamp) {
      const c = (adsStructure.campaigns || []).find((x) => x.id === adsFocusCamp);
      focusNote.textContent = `Browse filter: “${c?.name || adsFocusCamp}” (you can still select across campaigns; selected rows stay visible). Show all to clear.`;
    } else {
      focusNote.textContent =
        "Tick boxes or search to select ad sets/ads across any campaigns. Optional: click a row to browse-filter that campaign.";
    }
  }

  camps.innerHTML = campaigns.length
    ? campaigns
        .map((c) => {
          const focused = adsFocusCamp === c.id;
          const checked = adsSelected.campaign.has(c.id);
          return `<div class="ads-row ${checked ? "is-checked" : ""} ${focused ? "is-focused" : ""}"
            data-focus-level="campaign" data-focus-id="${escapeHtml(c.id)}">
            <label class="ads-row-main">
              <input type="checkbox" name="ads-camp" value="${escapeHtml(c.id)}" ${
                checked ? "checked" : ""
              } />
              <span class="ads-row-text">
                <span class="ads-row-name">${escapeHtml(c.name)}</span>
                ${statusBadge(c.status)}
              </span>
            </label>
            <div class="ads-row-actions">
              <button type="button" class="btn btn-tiny" data-select-children="campaign-adsets" data-id="${escapeHtml(
                c.id,
              )}" title="Select all ad sets in this campaign">+ sets</button>
              <button type="button" class="btn btn-tiny" data-select-children="campaign-ads" data-id="${escapeHtml(
                c.id,
              )}" title="Select all ads in this campaign">+ ads</button>
            </div>
          </div>`;
        })
        .join("")
    : `<p class="muted footnote">No campaigns match.</p>`;

  sets.innerHTML = adsets.length
    ? adsets
        .map((a) => {
          const focused = adsFocusAdset === a.id;
          const checked = adsSelected.adset.has(a.id);
          return `<div class="ads-row ${checked ? "is-checked" : ""} ${focused ? "is-focused" : ""}"
            data-focus-level="adset" data-focus-id="${escapeHtml(a.id)}">
            <label class="ads-row-main">
              <input type="checkbox" name="ads-adset" value="${escapeHtml(a.id)}" ${
                checked ? "checked" : ""
              } />
              <span class="ads-row-text">
                <span class="ads-row-name">${escapeHtml(a.name)}</span>
                <span class="ads-row-parent">${escapeHtml(a.campaign_name || "")}</span>
                ${statusBadge(a.status)}
              </span>
            </label>
            <div class="ads-row-actions">
              <button type="button" class="btn btn-tiny" data-select-children="adset-ads" data-id="${escapeHtml(
                a.id,
              )}" title="Select all ads in this ad set">+ ads</button>
            </div>
          </div>`;
        })
        .join("")
    : `<p class="muted footnote">${
        adsFocusCamp ? "No ad sets in this campaign." : "No ad sets match."
      }</p>`;

  ads.innerHTML = adRows.length
    ? adRows
        .map((a) => {
          const checked = adsSelected.ad.has(a.id);
          return `<div class="ads-row ${checked ? "is-checked" : ""}"
            data-focus-level="ad" data-focus-id="${escapeHtml(a.id)}">
            <label class="ads-row-main">
              <input type="checkbox" name="ads-ad" value="${escapeHtml(a.id)}" ${
                checked ? "checked" : ""
              } />
              <span class="ads-row-text">
                <span class="ads-row-name">${escapeHtml(a.name)}</span>
                <span class="ads-row-parent">${escapeHtml(
                  [a.adset_name, a.campaign_name].filter(Boolean).join(" · "),
                )}</span>
                ${statusBadge(a.status)}
              </span>
            </label>
          </div>`;
        })
        .join("")
    : `<p class="muted footnote">${
        adsFocusAdset || adsFocusCamp ? "No ads in this scope." : "No ads match."
      }</p>`;

  updateAdsSelectionNote();
}

function updateAdsSelectionNote() {
  const nC = adsSelected.campaign.size;
  const nS = adsSelected.adset.size;
  const nA = adsSelected.ad.size;
  const note = adsEl("ads-selection-note");
  if (!note) return;
  if (!nC && !nS && !nA) {
    note.textContent = "No objects selected.";
    return;
  }
  note.textContent = `${nC} campaign(s) · ${nS} ad set(s) · ${nA} ad(s) selected.`;
}

function readAdsDateBody() {
  const preset = adsEl("ads-preset")?.value || "last_30d";
  if (preset === "custom") {
    return {
      date_preset: null,
      since: adsEl("ads-since")?.value || null,
      until: adsEl("ads-until")?.value || null,
    };
  }
  return { date_preset: preset, since: null, until: null };
}

function fillAdsSkuSelect() {
  const sel = adsEl("ads-sku");
  if (!sel) return;
  const rows = adsSkuCatalog || [];
  sel.innerHTML = rows
    .map((r) => {
      const sku = r.sku || "";
      const label = `${r.product || r.handle || "Product"} · ${r.title || ""} · ${sku}`.trim();
      return `<option value="${escapeHtml(sku)}" data-handle="${escapeHtml(
        r.handle || "",
      )}">${escapeHtml(label)}</option>`;
    })
    .join("");
}

function selectedAdsSkus() {
  const sel = adsEl("ads-sku");
  if (!sel) return [];
  return [...sel.selectedOptions].map((o) => o.value).filter(Boolean);
}

function updateAdsSkuCount() {
  const n = selectedAdsSkus().length;
  const box = adsEl("ads-sku-count");
  if (!box) return;
  box.textContent = n
    ? `${n} SKU(s) selected — SKU P&L mode.`
    : "No SKUs — store P&L mode.";
}

function selectAdsSkuProductVariants() {
  const sel = adsEl("ads-sku");
  if (!sel || !sel.selectedOptions.length) {
    showWarnings(["Select one SKU first, then use “Select all variants of first”."]);
    return;
  }
  const handle = sel.selectedOptions[0].dataset.handle || "";
  if (!handle) return;
  [...sel.options].forEach((o) => {
    o.selected = o.dataset.handle === handle;
  });
  updateAdsSkuCount();
}

function syncWhPastPresetFromScope() {
  const preset = adsEl("ads-preset")?.value;
  const whPreset = document.getElementById("wh-past-preset");
  if (!whPreset || !preset || preset === "custom") return;
  if ([...whPreset.options].some((o) => o.value === preset)) {
    whPreset.value = preset;
  }
}

function collectAdsScopeState() {
  return {
    date_preset: adsEl("ads-preset")?.value || "last_30d",
    date_from: adsEl("ads-since")?.value || null,
    date_to: adsEl("ads-until")?.value || null,
    sku_ids: selectedAdsSkus(),
    campaign_ids: [...adsSelected.campaign],
    adset_ids: [...adsSelected.adset],
    ad_ids: [...adsSelected.ad],
    active_only: !!adsEl("ads-active-only")?.checked,
  };
}

function applyAdsScopeState(scope) {
  if (!scope) return;
  const preset = scope.date_preset || "last_30d";
  if (adsEl("ads-preset")) adsEl("ads-preset").value = preset;
  if (adsEl("ads-since") && scope.date_from) adsEl("ads-since").value = scope.date_from;
  if (adsEl("ads-until") && scope.date_to) adsEl("ads-until").value = scope.date_to;
  syncAdsCustomDates();
  syncWhPastPresetFromScope();

  if (adsEl("ads-active-only") && scope.active_only != null) {
    adsEl("ads-active-only").checked = !!scope.active_only;
    adsActiveOnly = !!scope.active_only;
  }

  adsSelected.campaign = new Set(scope.campaign_ids || []);
  adsSelected.adset = new Set(scope.adset_ids || []);
  adsSelected.ad = new Set(scope.ad_ids || []);
  renderAdsPickers();
  renderAdsChips();
  updateAdsSelectionNote();

  const sel = adsEl("ads-sku");
  const want = new Set(scope.sku_ids || []);
  if (sel) {
    [...sel.options].forEach((o) => {
      o.selected = want.has(o.value);
    });
    updateAdsSkuCount();
  }
}

async function applyAdsReport(opts = {}) {
  const pin = opts.pin !== false;
  const campaign_ids = checkedAdsIds("ads-camp");
  const adset_ids = checkedAdsIds("ads-adset");
  const ad_ids = checkedAdsIds("ads-ad");
  if (!campaign_ids.length && !adset_ids.length && !ad_ids.length) {
    throw new Error("Select at least one campaign, ad set, or ad in Scope.");
  }
  const dates = readAdsDateBody();
  if (adsEl("ads-preset")?.value === "custom" && !dates.since) {
    throw new Error("Custom range needs a From date.");
  }

  showWarnings([]);
  adsReport = await api("/api/ads/performance", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      campaign_ids,
      adset_ids,
      ad_ids,
      skus: selectedAdsSkus(),
      handles: [],
      ...dates,
    }),
  });
  renderAdsResults();

  if (pin && adsReport) {
    try {
      const label =
        document.getElementById("view-select")?.selectedOptions?.[0]?.textContent ||
        "ads";
      await api("/api/ads/pin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ report: adsReport, pin_label: label }),
      });
    } catch (_) {
      /* non-fatal */
    }
  }
  return adsReport;
}

window.collectAdsScopeState = collectAdsScopeState;
window.applyAdsScopeState = applyAdsScopeState;
window.applyAdsReport = applyAdsReport;
window.selectedAdsSkus = selectedAdsSkus;
window.checkedAdsIds = checkedAdsIds;
window.adsReportHasPnl = () => Boolean(adsReport?.pnl?.days?.length);

function renderAdsResults() {
  const box = adsEl("ads-results");
  const exportBtn = adsEl("btn-ads-export");
  if (!adsReport || adsReport.warning === "No campaigns, ad sets, or ads selected.") {
    if (box) box.hidden = true;
    if (exportBtn) exportBtn.disabled = true;
    return;
  }
  if (box) box.hidden = false;
  if (exportBtn) exportBtn.disabled = false;

  if (adsReport.warning) showWarnings([adsReport.warning]);

  const since = adsReport.since || "—";
  const until = adsReport.until || "—";
  const preset = adsReport.date_preset;
  const range = adsEl("ads-range-note");
  if (range) {
    const bits = [
      preset ? `${preset}` : "custom",
      `${since} → ${until}`,
      `${(adsReport.campaign_ids || []).length} camp · ${(adsReport.adset_ids || []).length} ad set · ${(adsReport.ad_ids || []).length} ad`,
      adsReport.currency || "",
    ].filter(Boolean);
    range.textContent = bits.join(" · ");
  }

  adsEl("ads-stat-spend").textContent = adsMoney(adsReport.spend);
  adsEl("ads-stat-purch").textContent = adsNum(adsReport.purchases, 0);
  adsEl("ads-stat-rev").textContent = adsMoney(adsReport.attr_rev);
  adsEl("ads-stat-roas").textContent = adsX(adsReport.roas);
  adsEl("ads-stat-cpa").textContent = adsMoney(adsReport.cpa);
  adsEl("ads-stat-impr").textContent = adsNum(adsReport.impressions, 0);
  adsEl("ads-stat-clicks").textContent = adsNum(adsReport.clicks, 0);
  adsEl("ads-stat-ctr").textContent = adsPct(adsReport.ctr);
  adsEl("ads-stat-cpc").textContent = adsMoney(adsReport.cpc);
  adsEl("ads-stat-cpm").textContent = adsMoney(adsReport.cpm);

  renderAdsTable();
  renderAdsChart();
  renderAdsPnl();
}

function renderAdsPnl() {
  const section = adsEl("ads-pnl-section");
  const pnl = adsReport?.pnl;
  if (!section) return;
  const adsPnlOn = document.querySelector(
    '#section-toggles input[data-section="ads_pnl"]',
  )?.checked;
  if (!pnl || !pnl.days?.length || adsPnlOn === false) {
    section.hidden = true;
    if (adsPnlChart) {
      adsPnlChart.destroy();
      adsPnlChart = null;
    }
    return;
  }
  section.hidden = false;
  const mode = adsReport.pnl_mode || pnl.mode || "—";
  const badge = adsEl("ads-pnl-mode");
  if (badge) badge.textContent = String(mode).toUpperCase();
  const note = adsEl("ads-pnl-note");
  if (note) {
    note.textContent = [pnl.label, pnl.note].filter(Boolean).join(" · ");
  }
  const t = pnl.totals || {};
  adsEl("ads-pnl-rev").textContent = adsMoney(t.revenue);
  adsEl("ads-pnl-cogs").textContent = adsMoney(t.landed_cogs);
  adsEl("ads-pnl-fees").textContent = adsMoney(t.fees);
  adsEl("ads-pnl-ads").textContent = adsMoney(t.meta_spend);
  const cumEl = adsEl("ads-pnl-cum");
  cumEl.textContent = adsMoney(t.cum_pnl);
  cumEl.className = "stat-value " + (Number(t.cum_pnl) >= 0 ? "success" : "danger");
  adsEl("ads-pnl-mer").textContent = adsX(t.store_mer);
  adsEl("ads-pnl-roas").textContent = adsX(t.meta_roas);
  adsEl("ads-pnl-orders").textContent = adsNum(t.orders, 0);

  if (adsReport.warnings?.length) {
    showWarnings(adsReport.warnings);
  }
  renderAdsPnlChart();
}

function renderAdsPnlChart() {
  const canvas = adsEl("ads-pnl-chart");
  if (!canvas || !adsReport?.pnl?.days?.length) return;
  const view = adsEl("ads-pnl-chart-view")?.value || "cumPnl";
  const specFn = window.mainChartSpec;
  if (typeof specFn !== "function") return;
  const spec = specFn(view, adsReport.pnl.days);
  if (adsPnlChart) {
    adsPnlChart.destroy();
    adsPnlChart = null;
  }
  if (!spec) return;
  const note = adsEl("ads-pnl-chart-note");
  if (note) note.textContent = spec.note || "";
  adsPnlChart = new Chart(canvas.getContext("2d"), {
    type: spec.type,
    data: spec.data,
    options: {
      responsive: true,
      maintainAspectRatio: true,
      ...spec.options,
    },
    plugins: spec.plugins || [],
  });
}

function objectParentLabel(row) {
  if (row.level === "ad") {
    return [row.campaign_name, row.adset_name].filter(Boolean).join(" / ");
  }
  if (row.level === "adset") return row.campaign_name || "";
  return "";
}

function renderAdsTable() {
  const tbody = adsEl("ads-table")?.querySelector("tbody");
  if (!tbody || !adsReport) return;
  const rows = [...(adsReport.by_object || [])];
  rows.sort((a, b) => {
    let av;
    let bv;
    if (adsSortKey === "parent") {
      av = objectParentLabel(a);
      bv = objectParentLabel(b);
    } else if (adsSortKey === "name" || adsSortKey === "level") {
      av = a[adsSortKey] || "";
      bv = b[adsSortKey] || "";
    } else {
      av = a[adsSortKey] == null ? -Infinity : Number(a[adsSortKey]);
      bv = b[adsSortKey] == null ? -Infinity : Number(b[adsSortKey]);
    }
    if (av < bv) return -1 * adsSortDir;
    if (av > bv) return 1 * adsSortDir;
    return 0;
  });

  tbody.innerHTML = rows.length
    ? rows
        .map(
          (r) => `<tr>
            <td>${escapeHtml(r.level || "")}</td>
            <td>${escapeHtml(r.name || "")}</td>
            <td class="muted">${escapeHtml(objectParentLabel(r))}</td>
            <td class="num">${adsMoney(r.spend)}</td>
            <td class="num">${adsNum(r.purchases, 0)}</td>
            <td class="num">${adsMoney(r.attr_rev)}</td>
            <td class="num">${adsX(r.roas)}</td>
            <td class="num">${adsMoney(r.cpa)}</td>
            <td class="num">${adsNum(r.impressions, 0)}</td>
            <td class="num">${adsNum(r.clicks, 0)}</td>
            <td class="num">${adsPct(r.ctr)}</td>
            <td class="num">${adsMoney(r.cpc)}</td>
            <td class="num">${adsMoney(r.cpm)}</td>
          </tr>`,
        )
        .join("")
    : `<tr><td colspan="13" class="muted">No insight rows for this selection.</td></tr>`;
}

function allDatesFromReport(report) {
  const set = new Set((report.days || []).map((d) => d.date));
  for (const s of report.series || []) {
    for (const d of s.days || []) set.add(d.date);
  }
  return [...set].sort();
}

function dayMap(days) {
  const m = new Map();
  for (const d of days || []) m.set(d.date, d);
  return m;
}

function seriesMetric(day, view) {
  if (!day) return null;
  if (view === "spend") return day.spend;
  if (view === "roas") return day.roas;
  if (view === "ctr") return day.ctr;
  return null;
}

function adsChartConcept(view) {
  const C = (key, fallback) =>
    typeof window.paConcept === "function" ? window.paConcept(key, fallback) : fallback;
  if (view === "spend") return C("ADS_CHART_SPEND", "Daily Meta spend for the selection.");
  if (view === "purchRev") {
    return C(
      "ADS_CHART_PURCH_REV",
      "Purchases and attributed purchase value from Meta.",
    );
  }
  if (view === "roas") {
    return C(
      "ADS_CHART_ROAS",
      "Daily Meta ROAS = attr. revenue ÷ spend. Compare with Store MER below.",
    );
  }
  if (view === "ctr") {
    return C("ADS_CHART_CTR", "Click-through rate over time.");
  }
  return "";
}

function adsChartSpec(view, report, overlay) {
  const labels = allDatesFromReport(report);
  if (!labels.length) return null;

  const noteElHint = adsEl("ads-chart-note");
  const baseNote = adsChartConcept(view);
  let note = baseNote;

  if (view === "purchRev") {
    if (overlay) {
      const top = (report.series || []).slice(0, OVERLAY_CAP);
      if ((report.series || []).length > OVERLAY_CAP) {
        note = `${baseNote} Showing top ${OVERLAY_CAP} objects by spend (of ${report.series.length}).`;
      } else {
        note = `${baseNote} Overlay = one series per object.`;
      }
      const datasets = [];
      top.forEach((s, i) => {
        const m = dayMap(s.days);
        const color = OVERLAY_COLORS[i % OVERLAY_COLORS.length];
        datasets.push({
          label: `${s.name} · purch`,
          data: labels.map((d) => m.get(d)?.purchases ?? null),
          borderColor: color,
          backgroundColor: "transparent",
          borderDash: [4, 3],
          tension: 0.2,
          yAxisID: "y",
        });
        datasets.push({
          label: `${s.name} · rev`,
          data: labels.map((d) => m.get(d)?.attr_rev ?? null),
          borderColor: color,
          backgroundColor: "transparent",
          tension: 0.2,
          yAxisID: "y",
        });
      });
      if (noteElHint) noteElHint.textContent = note;
      return {
        title: "Purchases & attributed revenue (overlay)",
        note,
        type: "line",
        data: { labels, datasets },
        options: {
          plugins: { legend: { position: "bottom" } },
          scales: {
            y: { ticks: { callback: (v) => `£${v}` } },
          },
        },
      };
    }
    const m = dayMap(report.days);
    if (noteElHint) noteElHint.textContent = note;
    return {
      title: "Purchases & attributed revenue",
      note,
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Purchases",
            data: labels.map((d) => m.get(d)?.purchases ?? 0),
            borderColor: "#1f4b99",
            backgroundColor: "transparent",
            tension: 0.2,
            yAxisID: "y1",
          },
          {
            label: "Attr. revenue",
            data: labels.map((d) => m.get(d)?.attr_rev ?? 0),
            borderColor: "#067647",
            backgroundColor: "transparent",
            tension: 0.2,
            yAxisID: "y",
          },
        ],
      },
      options: {
        plugins: { legend: { position: "bottom" } },
        scales: {
          y: { position: "left", ticks: { callback: (v) => `£${v}` } },
          y1: {
            position: "right",
            grid: { drawOnChartArea: false },
            beginAtZero: true,
          },
        },
      },
    };
  }

  const titles = {
    spend: "Spend over time",
    roas: "ROAS over time",
    ctr: "CTR over time",
  };
  const yTick =
    view === "spend"
      ? (v) => `£${v}`
      : view === "ctr"
        ? (v) => `${v}%`
        : (v) => `${v}×`;

  if (overlay) {
    const top = (report.series || []).slice(0, OVERLAY_CAP);
    if ((report.series || []).length > OVERLAY_CAP) {
      note = `${baseNote} Showing top ${OVERLAY_CAP} objects by spend (of ${report.series.length}).`;
    } else {
      note = `${baseNote} Overlay = one series per object.`;
    }
    if (noteElHint) noteElHint.textContent = note;
    return {
      title: `${titles[view]} (overlay)`,
      note,
      type: "line",
      data: {
        labels,
        datasets: top.map((s, i) => {
          const m = dayMap(s.days);
          return {
            label: s.name,
            data: labels.map((d) => seriesMetric(m.get(d), view)),
            borderColor: OVERLAY_COLORS[i % OVERLAY_COLORS.length],
            backgroundColor: "transparent",
            tension: 0.2,
            spanGaps: true,
          };
        }),
      },
      options: {
        plugins: { legend: { position: "bottom" } },
        scales: { y: { ticks: { callback: yTick } } },
      },
    };
  }

  const m = dayMap(report.days);
  if (noteElHint) noteElHint.textContent = note;
  return {
    title: titles[view],
    note,
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: titles[view],
          data: labels.map((d) => {
            const day = m.get(d);
            if (!day) return null;
            if (view === "spend") return day.spend;
            if (view === "roas") return day.roas;
            if (view === "ctr") return day.ctr;
            return null;
          }),
          borderColor: "#1f4b99",
          backgroundColor: "rgba(31, 75, 153, 0.12)",
          fill: view === "spend",
          tension: 0.2,
          spanGaps: true,
        },
      ],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: { y: { ticks: { callback: yTick } } },
    },
  };
}

function renderAdsChart() {
  const canvas = adsEl("ads-chart");
  if (!canvas || !adsReport) return;
  const view = adsEl("ads-chart-view")?.value || "spend";
  const overlay = !!adsEl("ads-overlay")?.checked;
  const spec = adsChartSpec(view, adsReport, overlay);
  if (adsChart) {
    adsChart.destroy();
    adsChart = null;
  }
  if (!spec) return;
  adsChart = new Chart(canvas.getContext("2d"), {
    type: spec.type,
    data: spec.data,
    options: {
      responsive: true,
      maintainAspectRatio: true,
      ...spec.options,
    },
  });
}

function captureAdsChartsForExport() {
  if (!adsReport) return [];
  const overlay = !!adsEl("ads-overlay")?.checked;
  const charts = [];
  for (const view of ADS_CHART_VIEWS) {
    const spec = adsChartSpec(view, adsReport, overlay);
    if (!spec) continue;
    const png = renderSpecToPng(spec, 1100, 420);
    if (!png) continue;
    charts.push({ title: `Meta · ${spec.title}`, note: spec.note, png });
  }
  const pnlDays = adsReport.pnl?.days || [];
  const specFn = window.mainChartSpec;
  if (pnlDays.length && typeof specFn === "function") {
    const mode = (adsReport.pnl_mode || "pnl").toUpperCase();
    for (const view of ADS_PNL_CHART_VIEWS) {
      const spec = specFn(view, pnlDays);
      if (!spec) continue;
      const png = renderSpecToPng(spec, 1100, 420);
      if (!png) continue;
      charts.push({
        title: `P&L (${mode}) · ${spec.title}`,
        note: adsReport.pnl?.note || spec.note,
        png,
      });
    }
  }
  return charts;
}

async function exportAdsPdf() {
  if (!adsReport) return;
  const btn = adsEl("btn-ads-export");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Exporting…";
  }
  try {
    const charts = captureAdsChartsForExport();
    const res = await fetch("/api/ads/export", {
      method: "POST",
      headers: {
        Accept: "application/pdf",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ report: adsReport, charts }),
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
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const stamp = new Date().toISOString().slice(0, 16).replace(/[-:T]/g, "");
    a.download = `profit-admin-ads-${stamp}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Export PDF";
    }
  }
}
