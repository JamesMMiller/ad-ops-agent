"""Explanatory copy for Profit Admin sections and charts.

Used by PDF exports; keep in sync with static/concepts.js for the UI.
"""

from __future__ import annotations

# ── P&L ──────────────────────────────────────────────────────────────────────

PNL_INTRO = (
    "Whole-store desk: Shopify revenue and landed costs vs Meta spend, KIE credits, "
    "and amortised Shopify Basic. Figures are estimates — confirm in each platform."
)

PNL_KPI = (
    "Revenue = paid Shopify sales. Meta spend = Insights account spend. "
    "Trailing 3-day MER = store revenue ÷ Meta spend over the last 3 days "
    "(~2.0× is a healthy post-COGS target; ≥1.5× watch). "
    "Cumulative P&L = running total of day P&L from the snapshot start."
)

CHART_CUM_PNL = (
    "Running profit/loss: revenue − landed COGS − checkout fees − Meta − KIE − "
    "daily Shopify Basic slice. Crosses £0 at break-even."
)

CHART_REV_COST = (
    "Green = cumulative revenue; red = cumulative costs (COGS, fees, Meta, KIE, Shopify). "
    "Profit when green stays above red."
)

CHART_DAILY_STACK = (
    "Each bar is one day’s cost mix: landed COGS, Meta ads, KIE credits, and fees + Shopify. "
    "Use it to see which cost line is driving a bad day."
)

CHART_MER = (
    "Marketing efficiency ratio: store revenue ÷ Meta spend on a trailing 3-day window. "
    "Not the same as Meta ROAS (which uses attributed purchase value). "
    "Guides at ~1.5× (watch) and ~2.0× (healthy after COGS)."
)

CHART_PRODUCT_CONTRIB = (
    "Contribution by product before Meta and KIE: line revenue − landed COGS − allocated fees. "
    "Positive bars fund ads; they are not full P&L."
)

DAILY_BREAKDOWN = (
    "One row per day. Day P&L = revenue − COGS − fees − ads − KIE − Shopify slice. "
    "Cum P&L stacks those days. 3d MER = trailing 3-day store revenue ÷ Meta spend."
)

PRODUCT_PNL = (
    "Sold units only. Contribution = line revenue − landed COGS "
    "(Shopify unitCost + CJ postageAmount) − checkout fees allocated by line share "
    "(~1.5% + £0.25 per order, split by revenue). "
    "Meta ads and KIE are not attributed per product — use Ads → SKU mode for that join."
)

UNIT_ECONOMICS = (
    "ACTIVE catalog SKUs (not only what sold). Landed = unitCost + postage. "
    "Contrib = sell − landed − fee estimate. Margin = contrib ÷ sell. "
    "Min ROAS = sell ÷ contrib (ads must return at least this multiple of spend to cover the unit). "
    "Max CPA = contrib (highest cost-per-purchase that still leaves £0 unit contribution)."
)

SUBSET_PNL = (
    "Scoped P&L for selected SKUs and Meta objects. Series starts on the earliest selected "
    "ad set start date. Ads = selected Meta spend only; revenue/COGS = matching Shopify lines. "
    "KIE and Shopify plan amortisation are omitted so the subset stays comparable."
)

# ── Ads ──────────────────────────────────────────────────────────────────────

ADS_INTRO = (
    "Meta Insights for selected campaigns, ad sets, and ads, joined to Shopify P&L for the "
    "same dates. Leave products empty for whole-store P&L; pick SKUs for product economics "
    "vs those ads. Leaf-prefer: if a parent and child are both ticked, only the child counts "
    "(no double-count)."
)

ADS_META_KPI = (
    "Spend / purchases / attr. revenue from Meta Insights (attribution as configured on the ad set). "
    "ROAS = attr. revenue ÷ spend. CPA = spend ÷ purchases. "
    "CTR = clicks ÷ impressions; CPC = spend ÷ clicks; CPM = spend per 1,000 impressions. "
    "Attr. revenue is Meta’s view — Store MER on the P&L strip uses Shopify revenue instead."
)

ADS_CHART_SPEND = "Daily Meta spend for the selection (combined), or per object when Overlay is on."

ADS_CHART_PURCH_REV = (
    "Purchases (count) and attributed purchase value from Meta. "
    "Useful to see whether spend days actually converted."
)

ADS_CHART_ROAS = (
    "Daily Meta ROAS = attr. revenue ÷ spend. Compare with Store MER on the profitability strip — "
    "they often disagree when attribution or SKU mix differs."
)

ADS_CHART_CTR = "Click-through rate over time. Rising CTR with flat ROAS often means cheap clicks, weak checkout."

ADS_OVERLAY = (
    "Overlay plots each selected object as its own series (capped at the top 12 by spend). "
    "Off = one combined series for the whole selection."
)

ADS_BREAKDOWN = (
    "One row per selected leaf object after leaf-prefer. "
    "Parent column shows campaign / ad set for context. Sort by spend or ROAS to find winners and losers."
)

ADS_PROFITABILITY = (
    "STORE mode: whole-store Shopify P&L for the date window; Meta spend = selected objects only "
    "(may be a subset of account spend). Includes KIE + Shopify amort when from Refresh. "
    "SKU mode: revenue/COGS/fees for selected products only vs those ads; KIE/Shopify amort omitted. "
    "Store MER = Shopify revenue ÷ selected Meta spend. Meta ROAS = attr. revenue ÷ spend."
)

# ── Warehouse ────────────────────────────────────────────────────────────────

WAREHOUSE_INTRO = (
    "Forward estimate of CJ 3PL stocking: inbound, storage (FIFO), outbound, postage, and optional ads. "
    "Fees from cjdropshipping.com/service-fee (USD→GBP estimates). "
    "Confirm last-mile postage on CJ Shipping Calculation. Overseas stock-in MOQ: ≥10/variant and ≥100 total."
)

WAREHOUSE_CHART = (
    "Costs and contribution over the sell horizon. Sawtooth jumps = restock events. "
    "Compare cumulative P&L to remaining inventory when stock is modelled."
)

WAREHOUSE_FORMULAS = (
    "ROAS = revenue ÷ ads. ROAS (after COGS) = (revenue − landed COGS) ÷ ads. "
    "POAS = profit ÷ ads (profit after COGS, fees, storage, ads). "
    "Margin (inc ads) = profit ÷ revenue."
)


def chart_note_for_view(view: str) -> str:
    """Map mainChartSpec view keys to PDF/UI notes."""
    return {
        "cumPnl": CHART_CUM_PNL,
        "cumRevCost": CHART_REV_COST,
        "dailyStack": CHART_DAILY_STACK,
        "mer": CHART_MER,
    }.get(view, "")


def as_dict() -> dict[str, str]:
    """Optional API payload / tests."""
    return {k: v for k, v in globals().items() if k.isupper() and isinstance(v, str)}
