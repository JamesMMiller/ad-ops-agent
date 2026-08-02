"""
CJ 3PL warehouse fee tables + cost projection.

Fee source (USD): https://cjdropshipping.com/service-fee
Confirm live rates on that page — tables here are a snapshot for planning.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Warehouse = Literal["CN", "US", "PL", "DE", "GB"]

WAREHOUSES: list[dict[str, str]] = [
    {"id": "GB", "label": "UK (GB)", "note": "Manchester / UK network"},
    {"id": "DE", "label": "Germany (DE)", "note": "EU fulfilment"},
    {"id": "PL", "label": "Poland (PL)", "note": "EU fulfilment"},
    {"id": "US", "label": "United States (US)", "note": "US domestic"},
    {"id": "CN", "label": "China (CN)", "note": "Lowest fees; longest last-mile"},
]

# MOQ for overseas (non-CN) inbound stocking — from CJ service-fee page
OVERSEAS_MOQ_PER_VARIANT = 10
OVERSEAS_MOQ_TOTAL = 100

# Inbound fee bands: (max_kg inclusive upper, fee_usd) ; last band may be special
# >20kg: DE $0.94/10kg, GB $0.55/10kg, PL flat $0.25
INBOUND_FEE: dict[str, list[tuple[float, float]]] = {
    "CN": [(0.5, 0.0), (1.0, 0.0), (3.0, 0.0), (5.0, 0.0), (10.0, 0.0), (15.0, 0.0), (20.0, 0.0)],
    "US": [(0.5, 0.0), (1.0, 0.0), (3.0, 0.0), (5.0, 0.0), (10.0, 0.0), (15.0, 0.0), (20.0, 0.0)],
    "PL": [(0.5, 0.25), (1.0, 0.25), (3.0, 0.25), (5.0, 0.25), (10.0, 0.25), (15.0, 0.25), (20.0, 0.25)],
    "DE": [(0.5, 0.15), (1.0, 0.2), (3.0, 0.38), (5.0, 0.56), (10.0, 0.94), (15.0, 1.23), (20.0, 1.98)],
    "GB": [(0.5, 0.13), (1.0, 0.17), (3.0, 0.31), (5.0, 0.38), (10.0, 0.44), (15.0, 0.55), (20.0, 0.77)],
}
INBOUND_OVER_20_PER_10KG = {"CN": 0.0, "US": 0.0, "PL": 0.25, "DE": 0.94, "GB": 0.55}

INSPECTION_FEE_PER_SKU = {"CN": 0.0, "US": 0.0, "PL": 0.0, "DE": 2.2, "GB": 2.2}
UNLOAD_PER_CARTON = {"CN": 0.0, "US": 0.0, "PL": 0.0, "DE": 1.3, "GB": 1.5}

LABEL_SKU = {"CN": 0.03, "US": 0.2, "PL": 0.34, "DE": 0.54, "GB": 0.55}

# Outbound: (max_kg, fee); then extra weight /10kg and extra piece
OUTBOUND_FEE: dict[str, list[tuple[float, float]]] = {
    "CN": [
        (0.5, 0.30),
        (1.0, 0.30),
        (3.0, 0.40),
        (5.0, 0.40),
        (8.0, 0.50),
        (10.0, 0.50),
        (15.0, 0.60),
        (20.0, 0.60),
        (30.0, 0.60),
        (31.5, 0.80),
        (40.0, 1.00),
    ],
    "US": [
        (0.5, 0.50),
        (1.0, 0.50),
        (3.0, 0.85),
        (5.0, 0.93),
        (8.0, 1.39),
        (10.0, 1.43),
        (15.0, 2.13),
        (20.0, 2.83),
        (30.0, 4.23),
        (31.5, 4.44),
        (40.0, 5.63),
    ],
    "PL": [
        (0.5, 1.01),
        (1.0, 1.01),
        (3.0, 1.26),
        (5.0, 1.26),
        (8.0, 1.77),
        (10.0, 1.77),
        (15.0, 2.27),
        (20.0, 2.27),
        (30.0, 2.27),
        (31.5, 2.91),
        (40.0, 3.79),
    ],
    "DE": [
        (0.5, 0.34),
        (1.0, 0.39),
        (3.0, 0.44),
        (5.0, 0.58),
        (8.0, 0.85),
        (10.0, 0.85),
        (15.0, 1.19),
        (20.0, 1.42),
        (30.0, 2.64),
        (31.5, 2.64),
        (40.0, 3.86),
    ],
    "GB": [
        (0.5, 0.33),
        (1.0, 0.33),
        (3.0, 0.45),
        (5.0, 0.65),
        (8.0, 1.09),
        (10.0, 1.09),
        (15.0, 1.53),
        (20.0, 2.21),
        (30.0, 3.63),
        (31.5, 3.63),
        (40.0, 5.05),
    ],
}
OUTBOUND_EXTRA_PER_10KG = {"CN": 1.00, "US": 1.40, "PL": 3.79, "DE": 1.22, "GB": 1.42}
OUTBOUND_EXTRA_PIECE = {"CN": 0.10, "US": 0.30, "PL": 0.51, "DE": 0.28, "GB": 0.33}

# Stocking: (max_days inclusive upper of band, usd_per_cbm_per_day)
# Free periods differ by warehouse
STOCKING_BANDS: dict[str, list[tuple[int, float]]] = {
    "CN": [
        (30, 0.0),
        (60, 0.0),
        (90, 0.0),
        (120, 0.20),
        (180, 0.30),
        (270, 0.40),
        (360, 0.50),
        (10_000, 0.60),
    ],
    "US": [
        (30, 0.0),
        (60, 0.0),
        (90, 0.63),
        (120, 0.63),
        (180, 1.26),
        (270, 1.89),
        (360, 1.89),
        (10_000, 3.78),
    ],
    "PL": [
        (30, 0.0),
        (60, 0.40),
        (90, 0.57),
        (120, 0.86),
        (180, 1.14),
        (270, 1.71),
        (360, 2.00),
        (10_000, 3.99),
    ],
    "DE": [
        (30, 0.0),
        (60, 0.44),
        (90, 0.51),
        (120, 0.81),
        (180, 1.18),
        (270, 2.19),
        (360, 2.55),
        (10_000, 3.35),
    ],
    "GB": [
        (30, 0.0),
        (60, 0.54),
        (90, 0.54),
        (120, 0.83),
        (180, 1.07),
        (270, 1.85),
        (360, 2.24),
        (10_000, 4.46),
    ],
}
PEAK_SEASON_EXTRA = {"CN": 0.0, "US": 0.21, "PL": 0.28, "DE": 0.25, "GB": 0.29}  # Oct–Dec

# CN → overseas warehouse stock shipping (USD/kg) — reference only
STOCK_SHIPPING: dict[str, dict[str, Any]] = {
    "CN_US_air_ordinary": {"lane": "CN→US Air Ordinary", "days": "10–15", "usd_per_kg": 7.50},
    "CN_US_air_sensitive": {"lane": "CN→US Air Sensitive", "days": "11–16", "usd_per_kg": 9.50},
    "CN_US_sea_ordinary": {"lane": "CN→US Sea Ordinary", "days": "25–30", "usd_per_kg": 4.50},
    "CN_US_sea_sensitive": {"lane": "CN→US Sea Sensitive", "days": "25–30", "usd_per_kg": 5.50},
    "CN_PL_air_ordinary": {"lane": "CN→PL Air Ordinary", "days": "12–15", "usd_per_kg": 10.00},
    "CN_PL_air_sensitive": {"lane": "CN→PL Air Sensitive", "days": "14–17", "usd_per_kg": 13.00},
    "CN_PL_sea_ordinary": {"lane": "CN→PL Sea Ordinary", "days": "45–60", "usd_per_kg": 4.50},
    "CN_PL_sea_sensitive": {"lane": "CN→PL Sea Sensitive", "days": "45–60", "usd_per_kg": 6.50},
    "CN_DE_air_ordinary": {"lane": "CN→DE Air Ordinary", "days": "13–18", "usd_per_kg": 10.00},
    "CN_DE_air_sensitive": {"lane": "CN→DE Air Sensitive", "days": "14–20", "usd_per_kg": 13.00},
    "CN_DE_sea_ordinary": {"lane": "CN→DE Sea Ordinary", "days": "60–65", "usd_per_kg": 4.00},
    "CN_DE_sea_sensitive": {"lane": "CN→DE Sea Sensitive", "days": "60–65", "usd_per_kg": 4.50},
    "CN_GB_air_ordinary": {"lane": "CN→GB Air Ordinary", "days": "13–18", "usd_per_kg": 8.50},
    "CN_GB_air_sensitive": {"lane": "CN→GB Air Sensitive", "days": "13–18", "usd_per_kg": 11.00},
    "CN_GB_sea_ordinary": {"lane": "CN→GB Sea Ordinary", "days": "60–65", "usd_per_kg": 4.00},
    "CN_GB_sea_sensitive": {"lane": "CN→GB Sea Sensitive", "days": "60–65", "usd_per_kg": 4.50},
    "none": {"lane": "Already at warehouse / local inbound", "days": "—", "usd_per_kg": 0.0},
}

# Estimated last-mile transit from warehouse → customer (planning ranges, not CJ SLA)
LAST_MILE_TRANSIT: dict[str, dict[str, str]] = {
    "GB": {"UK": "2–5 days", "EU": "5–12 days", "US": "8–15 days", "CAN": "8–18 days"},
    "DE": {"UK": "5–10 days", "EU": "2–5 days", "US": "8–15 days", "CAN": "8–18 days"},
    "PL": {"UK": "5–12 days", "EU": "2–6 days", "US": "8–16 days", "CAN": "9–18 days"},
    "US": {"UK": "8–15 days", "EU": "8–16 days", "US": "2–5 days", "CAN": "3–7 days"},
    "CN": {"UK": "10–20 days", "EU": "10–20 days", "US": "8–15 days", "CAN": "10–20 days"},
}

# Default last-mile shipping estimates (USD/order) — editable in UI; CJ says check Shipping Calculation
DEFAULT_LAST_MILE_USD: dict[str, dict[str, float]] = {
    "GB": {"UK": 3.50, "EU": 8.00, "US": 12.00, "CAN": 14.00},
    "DE": {"UK": 7.00, "EU": 4.00, "US": 12.00, "CAN": 14.00},
    "PL": {"UK": 7.50, "EU": 4.50, "US": 12.50, "CAN": 14.50},
    "US": {"UK": 12.00, "EU": 13.00, "US": 4.50, "CAN": 7.00},
    "CN": {"UK": 6.00, "EU": 6.00, "US": 5.50, "CAN": 7.00},
}


def _band_fee(weight_kg: float, bands: list[tuple[float, float]], over_40_per_10kg: float) -> float:
    if weight_kg <= 0:
        return bands[0][1]
    for upper, fee in bands:
        if weight_kg <= upper:
            return fee
    # above 40kg: last band + extra per 10kg over 40
    extra = max(0.0, weight_kg - 40.0)
    return bands[-1][1] + (extra / 10.0) * over_40_per_10kg


def inbound_unit_fee(warehouse: str, weight_kg: float) -> float:
    bands = INBOUND_FEE[warehouse]
    if weight_kg <= 20:
        for upper, fee in bands:
            if weight_kg <= upper:
                return fee
        return bands[-1][1]
    # >20kg
    if warehouse == "PL":
        return 0.25
    per10 = INBOUND_OVER_20_PER_10KG[warehouse]
    if per10 <= 0:
        return 0.0
    return (weight_kg / 10.0) * per10


def outbound_unit_fee(warehouse: str, weight_kg: float, pieces: int = 1) -> float:
    base = _band_fee(weight_kg, OUTBOUND_FEE[warehouse], OUTBOUND_EXTRA_PER_10KG[warehouse])
    extra_pieces = max(0, pieces - 1) * OUTBOUND_EXTRA_PIECE[warehouse]
    return base + extra_pieces


def stocking_rate(warehouse: str, age_days: int, peak_season: bool = False) -> float:
    """USD per CBM per day for stock of given age (1-indexed day in warehouse)."""
    rate = 0.0
    for upper, r in STOCKING_BANDS[warehouse]:
        if age_days <= upper:
            rate = r
            break
    if peak_season:
        rate += PEAK_SEASON_EXTRA.get(warehouse, 0.0)
    return rate


def stock_lanes_for_warehouse(warehouse: str) -> list[dict[str, Any]]:
    if warehouse == "CN":
        return [{"id": "none", **STOCK_SHIPPING["none"]}]
    prefix = f"CN_{warehouse}_"
    out = [{"id": "none", **STOCK_SHIPPING["none"]}]
    for k, v in STOCK_SHIPPING.items():
        if k.startswith(prefix):
            out.append({"id": k, **v})
    return out


@dataclass
class CalcInput:
    warehouse: Warehouse
    qty: int
    unit_weight_kg: float
    unit_cbm: float
    unit_product_cost_gbp: float
    sell_price_gbp: float
    sell_rate_per_day: float
    horizon_days: int = 180
    stock_lane: str = "none"
    cartons: int = 1
    pieces_per_order: int = 1
    peak_season: bool = False
    dest_mix: dict[str, float] | None = None  # UK/EU/US/CAN fractions summing ~1
    last_mile_usd: dict[str, float] | None = None
    include_postage: bool = True
    daily_ad_spend_gbp: float = 0.0
    ad_cost_per_purchase_gbp: float = 0.0
    stop_ads_when_stock_zero: bool = True
    restock_enabled: bool = False
    restock_qty: int = 0
    restock_every_days: int = 30
    # When True: track warehouse/wholesale inventory (stockouts, storage, restock).
    # When False: ignore stock levels — sell rate × horizon with no inbound/storage.
    track_stock: bool = True
    checkout_fee_pct: float = 0.015
    checkout_fee_fixed_gbp: float = 0.25
    usdgbp: float = 0.75


def _usd_to_gbp(usd: float, rate: float) -> float:
    return usd * rate


def _inbound_batch_usd(
    wh: Warehouse,
    batch_qty: int,
    unit_weight_kg: float,
    cartons: int,
    lane: dict[str, Any],
    *,
    include_inspection: bool,
) -> dict[str, float]:
    """CJ inbound fees for one stock-in batch."""
    q = max(0, int(batch_qty))
    w = max(0.001, float(unit_weight_kg))
    inspection = INSPECTION_FEE_PER_SKU[wh] if include_inspection and q else 0.0
    unload = UNLOAD_PER_CARTON[wh] * max(1, cartons) if q else 0.0
    inbound_units = inbound_unit_fee(wh, w) * q
    labels = LABEL_SKU[wh] * q
    stock_ship = float(lane.get("usd_per_kg", 0.0)) * w * q
    total = inspection + unload + inbound_units + labels + stock_ship
    return {
        "inspection": inspection,
        "unload": unload,
        "inbound_units": inbound_units,
        "labels": labels,
        "stock_shipping": stock_ship,
        "total": total,
    }


def _sell_fifo(
    batches: list[dict[str, float]], need: float
) -> tuple[float, list[dict[str, float]]]:
    """Pull `need` units from oldest batches; return sold qty and remaining batches."""
    sold = 0.0
    left = need
    for batch in batches:
        if left <= 0:
            break
        take = min(batch["qty"], left)
        batch["qty"] -= take
        left -= take
        sold += take
    return sold, [b for b in batches if b["qty"] > 1e-9]


def calculate(inp: CalcInput) -> dict[str, Any]:
    track_stock = bool(inp.track_stock)
    wh = inp.warehouse
    qty = max(0, int(inp.qty)) if track_stock else 0
    w = max(0.001, float(inp.unit_weight_kg))
    cbm = max(1e-6, float(inp.unit_cbm))
    rate = max(0.0, float(inp.sell_rate_per_day))
    horizon = max(1, int(inp.horizon_days))
    fx = float(inp.usdgbp)
    include_postage = bool(inp.include_postage)
    daily_ads = max(0.0, float(inp.daily_ad_spend_gbp))
    cpa_ads = max(0.0, float(inp.ad_cost_per_purchase_gbp))
    stop_ads = bool(inp.stop_ads_when_stock_zero) if track_stock else False
    restock_on = bool(inp.restock_enabled) if track_stock else False
    restock_qty = max(0, int(inp.restock_qty)) if restock_on else 0
    restock_every = max(1, int(inp.restock_every_days)) if restock_on else 0

    warnings: list[str] = []
    if track_stock and wh != "CN":
        if qty < OVERSEAS_MOQ_TOTAL:
            warnings.append(
                f"CJ overseas MOQ is ≥{OVERSEAS_MOQ_TOTAL} units total "
                f"(and ≥{OVERSEAS_MOQ_PER_VARIANT}/variant). You entered {qty}."
            )
        if qty < OVERSEAS_MOQ_PER_VARIANT:
            warnings.append(f"Per-variant MOQ is ≥{OVERSEAS_MOQ_PER_VARIANT} pcs.")
        if restock_on and restock_qty and restock_qty < OVERSEAS_MOQ_TOTAL:
            warnings.append(
                f"Restock qty {restock_qty} is below overseas MOQ ≥{OVERSEAS_MOQ_TOTAL}."
            )

    lane = STOCK_SHIPPING.get(inp.stock_lane) or STOCK_SHIPPING["none"]
    stock_ship_days = lane["days"]
    cartons = max(1, int(inp.cartons))

    if track_stock:
        initial_inbound = _inbound_batch_usd(
            wh, qty, w, cartons, lane, include_inspection=True
        )
    else:
        initial_inbound = {
            "inspection": 0.0,
            "unload": 0.0,
            "inbound_units": 0.0,
            "labels": 0.0,
            "stock_shipping": 0.0,
            "total": 0.0,
        }
    inspection = initial_inbound["inspection"]
    unload = initial_inbound["unload"]
    inbound_units = initial_inbound["inbound_units"]
    labels = initial_inbound["labels"]
    stock_ship_usd = initial_inbound["stock_shipping"]
    inbound_total_usd = initial_inbound["total"]

    if track_stock and qty > 0 and restock_qty > 0:
        restock_cartons = max(1, round(cartons * restock_qty / qty))
    else:
        restock_cartons = 1

    outbound_per_order_usd = outbound_unit_fee(wh, w * inp.pieces_per_order, inp.pieces_per_order)

    mix = inp.dest_mix or {"UK": 0.7, "EU": 0.2, "US": 0.05, "CAN": 0.05}
    total_mix = sum(max(0.0, v) for v in mix.values()) or 1.0
    mix = {k: max(0.0, v) / total_mix for k, v in mix.items()}

    lm_table = inp.last_mile_usd or DEFAULT_LAST_MILE_USD[wh]
    avg_last_mile_usd = sum(
        mix.get(d, 0.0) * float(lm_table.get(d, 0.0)) for d in ("UK", "EU", "US", "CAN")
    )
    lm_in_cogs_usd = avg_last_mile_usd if include_postage else 0.0

    batches: list[dict[str, float]] = (
        [{"qty": float(qty), "arrived": 0.0}] if track_stock and qty else []
    )
    days: list[dict[str, Any]] = []
    cum_storage_usd = 0.0
    cum_outbound_usd = 0.0
    cum_last_mile_usd = 0.0
    cum_sold = 0.0
    cum_revenue_gbp = 0.0
    cum_fees_gbp = 0.0
    cum_ads_gbp = 0.0
    cum_inbound_usd = inbound_total_usd
    cum_restock_units = 0
    restock_events = 0
    restock_days: list[int] = []

    for day in range(1, horizon + 1):
        inbound_day_usd = inbound_total_usd if (track_stock and day == 1) else 0.0
        restocked = 0

        if (
            track_stock
            and restock_on
            and restock_qty > 0
            and restock_every > 0
            and day % restock_every == 0
        ):
            batch_fees = _inbound_batch_usd(
                wh,
                restock_qty,
                w,
                restock_cartons,
                lane,
                include_inspection=False,
            )
            inbound_day_usd += batch_fees["total"]
            cum_inbound_usd += batch_fees["total"]
            batches.append({"qty": float(restock_qty), "arrived": float(day)})
            cum_restock_units += restock_qty
            restock_events += 1
            restocked = restock_qty
            restock_days.append(day)

        if track_stock:
            remaining_before = sum(b["qty"] for b in batches)
            sold, batches = _sell_fifo(batches, rate)
            remaining = sum(b["qty"] for b in batches)
        else:
            remaining_before = float("inf")
            sold = rate
            remaining = 0.0
        cum_sold += sold

        storage_day = 0.0
        if track_stock:
            for batch in batches:
                age = max(1, day - int(batch["arrived"]))
                storage_day += batch["qty"] * cbm * stocking_rate(wh, age, inp.peak_season)
            if storage_day > 0:
                storage_day = max(0.01, round(storage_day, 2))
            else:
                storage_day = 0.0
        cum_storage_usd += storage_day

        out_day = sold * outbound_per_order_usd
        lm_day = sold * avg_last_mile_usd
        lm_cogs_day = sold * lm_in_cogs_usd
        cum_outbound_usd += out_day
        cum_last_mile_usd += lm_day

        rev = sold * inp.sell_price_gbp
        cum_revenue_gbp += rev
        fees = sold * (inp.sell_price_gbp * inp.checkout_fee_pct + inp.checkout_fee_fixed_gbp)
        cum_fees_gbp += fees

        if track_stock:
            daily_on = (not stop_ads) or remaining_before > 0
        else:
            daily_on = True
        ads_day = (daily_ads if daily_on else 0.0) + (sold * cpa_ads)
        cum_ads_gbp += ads_day

        product_cogs = sold * inp.unit_product_cost_gbp
        inbound_day_gbp = _usd_to_gbp(inbound_day_usd, fx)
        out_gbp = _usd_to_gbp(out_day, fx)
        lm_cogs_gbp = _usd_to_gbp(lm_cogs_day, fx)
        stor_gbp = _usd_to_gbp(storage_day, fx)

        day_cogs = product_cogs + inbound_day_gbp + out_gbp + lm_cogs_gbp + stor_gbp
        day_gross = rev - day_cogs - fees
        day_pnl = day_gross - ads_day

        days.append(
            {
                "day": day,
                "remaining": round(remaining, 2) if track_stock else None,
                "sold": round(sold, 2),
                "restocked": restocked,
                "cum_sold": round(cum_sold, 2),
                "storage_usd": storage_day,
                "cum_storage_usd": round(cum_storage_usd, 2),
                "cum_storage_gbp": round(_usd_to_gbp(cum_storage_usd, fx), 2),
                "outbound_usd": round(out_day, 4),
                "last_mile_usd": round(lm_day, 4),
                "ads_gbp": round(ads_day, 2),
                "cum_ads_gbp": round(cum_ads_gbp, 2),
                "inbound_gbp": round(inbound_day_gbp, 2),
                "revenue_gbp": round(rev, 2),
                "cum_revenue_gbp": round(cum_revenue_gbp, 2),
                "day_cogs_gbp": round(day_cogs, 2),
                "day_contrib_gbp": round(day_gross, 2),
                "day_pnl_gbp": round(day_pnl, 2),
                "cum_contrib_gbp": None,
                "cum_pnl_gbp": None,
            }
        )

    cum_contrib = 0.0
    cum_pnl = 0.0
    for d in days:
        cum_contrib += d["day_contrib_gbp"]
        cum_pnl += d["day_pnl_gbp"]
        d["cum_contrib_gbp"] = round(cum_contrib, 2)
        d["cum_pnl_gbp"] = round(cum_pnl, 2)

    units_sold = cum_sold
    units_left = sum(b["qty"] for b in batches) if track_stock else 0.0
    total_received = (qty + cum_restock_units) if track_stock else units_sold

    total_storage_gbp = _usd_to_gbp(cum_storage_usd, fx)
    total_outbound_gbp = _usd_to_gbp(cum_outbound_usd, fx)
    total_last_mile_gbp = _usd_to_gbp(cum_last_mile_usd, fx)
    total_last_mile_in_cogs_gbp = total_last_mile_gbp if include_postage else 0.0
    total_inbound_gbp = _usd_to_gbp(cum_inbound_usd, fx)
    product_cogs_sold = units_sold * inp.unit_product_cost_gbp
    inventory_residual_gbp = units_left * inp.unit_product_cost_gbp if track_stock else 0.0
    inbound_on_unsold = (
        (units_left / total_received) * total_inbound_gbp
        if track_stock and total_received
        else 0.0
    )

    days_to_clear = (qty / rate) if track_stock and rate > 0 and not restock_on else None
    sell_through_pct = (
        (units_sold / total_received)
        if track_stock and total_received
        else (1.0 if units_sold else 0.0)
    )

    if units_sold > 0:
        per_unit_inbound = (
            total_inbound_gbp / total_received if track_stock and total_received else 0.0
        )
        per_unit_storage = total_storage_gbp / units_sold if track_stock else 0.0
        per_unit_outbound = total_outbound_gbp / units_sold
        per_unit_last_mile_actual = total_last_mile_gbp / units_sold
        per_unit_last_mile = per_unit_last_mile_actual if include_postage else 0.0
        per_unit_product = inp.unit_product_cost_gbp
        per_unit_ads = cum_ads_gbp / units_sold
        landed_cogs = (
            per_unit_product
            + per_unit_inbound
            + per_unit_storage
            + per_unit_outbound
            + per_unit_last_mile
        )
        fee_per_unit = inp.sell_price_gbp * inp.checkout_fee_pct + inp.checkout_fee_fixed_gbp
        contrib = inp.sell_price_gbp - landed_cogs - fee_per_unit
        margin = contrib / inp.sell_price_gbp if inp.sell_price_gbp else None
        contrib_after_ads = contrib - per_unit_ads
        margin_after_ads = (
            contrib_after_ads / inp.sell_price_gbp if inp.sell_price_gbp else None
        )
        unit_gross_contrib = units_sold * contrib
    else:
        per_unit_inbound = (
            total_inbound_gbp / total_received if track_stock and total_received else 0.0
        )
        per_unit_storage = 0.0
        per_unit_outbound = 0.0
        per_unit_last_mile_actual = 0.0
        per_unit_last_mile = 0.0
        per_unit_product = inp.unit_product_cost_gbp
        per_unit_ads = 0.0
        landed_cogs = per_unit_product + per_unit_inbound
        fee_per_unit = inp.sell_price_gbp * inp.checkout_fee_pct + inp.checkout_fee_fixed_gbp
        contrib = None
        margin = None
        contrib_after_ads = None
        margin_after_ads = None
        unit_gross_contrib = 0.0

    costs_breakdown = {
        "product_cogs_gbp": round(product_cogs_sold, 2),
        "inbound_gbp": round(total_inbound_gbp, 2),
        "storage_gbp": round(total_storage_gbp, 2),
        "outbound_gbp": round(total_outbound_gbp, 2),
        "postage_gbp": round(total_last_mile_in_cogs_gbp, 2),
        "checkout_fees_gbp": round(cum_fees_gbp, 2),
        "ads_gbp": round(cum_ads_gbp, 2),
    }
    total_costs = sum(costs_breakdown.values())
    overall_pnl = cum_revenue_gbp - total_costs
    # Classic ROAS = revenue / ads
    roas = (cum_revenue_gbp / cum_ads_gbp) if cum_ads_gbp > 0 else None
    # Contribution / ads — revenue after COGS, fees, outbound, storage, inbound (not ads).
    # Often called contribution ROAS / “ROAS after COGS”; related to POAS when using profit.
    costs_ex_ads = total_costs - cum_ads_gbp
    contrib_ex_ads = cum_revenue_gbp - costs_ex_ads
    roas_after_cogs = (contrib_ex_ads / cum_ads_gbp) if cum_ads_gbp > 0 else None
    # POAS = net profit / ads (profit already deducts ad spend)
    poas = (overall_pnl / cum_ads_gbp) if cum_ads_gbp > 0 else None
    net_margin = (overall_pnl / cum_revenue_gbp) if cum_revenue_gbp > 0 else None

    if days:
        days[-1]["cum_pnl_gbp"] = round(overall_pnl, 2)

    milestones = []
    for label, target_day in (("30d", 30), ("60d", 60), ("90d", 90), ("180d", 180)):
        if target_day <= horizon and days:
            row = days[min(target_day, len(days)) - 1]
            milestones.append(
                {
                    "label": label,
                    "day": target_day,
                    "remaining": row["remaining"],
                    "cum_sold": row["cum_sold"],
                    "cum_storage_gbp": row["cum_storage_gbp"],
                    "cum_revenue_gbp": row["cum_revenue_gbp"],
                    "cum_contrib_gbp": row["cum_contrib_gbp"],
                    "cum_ads_gbp": row["cum_ads_gbp"],
                    "cum_pnl_gbp": row["cum_pnl_gbp"],
                }
            )

    postage_note = (
        "Postage included in COGS / P&L (merchant-paid / free shipping)."
        if include_postage
        else "Postage excluded from COGS / P&L (customer pays shipping) — estimates still shown."
    )
    if track_stock:
        ads_note = (
            "Daily ads stop when stock is 0."
            if stop_ads
            else "Daily ads run every day of the horizon even if stock is 0."
        )
        stock_note = " Wholesale/dropship stock tracking is on (inbound, storage, restock)."
    else:
        ads_note = "Stock not tracked — daily ads run every day; sell rate × horizon."
        stock_note = " Stock levels ignored (open demand / no warehouse inventory model)."
    restock_note = (
        f" Repeat restock: {restock_qty} units every {restock_every} days "
        f"({restock_events} events in horizon)."
        if track_stock and restock_on and restock_qty
        else ""
    )

    return {
        "source": "https://cjdropshipping.com/service-fee",
        "disclaimer": (
            "CJ fees are USD estimates from the published service-fee page. "
            "Last-mile postage is editable planning defaults — confirm on CJ Shipping Calculation. "
            + ("Storage uses FIFO batch age × unit CBM × age band. " if track_stock else "")
            + f"{postage_note} "
            f"{ads_note} "
            "Optional ad cost per purchase is charged per unit sold."
            f"{stock_note}{restock_note}"
        ),
        "warnings": warnings,
        "warehouse": wh,
        "inputs": {
            "qty": qty if track_stock else 0,
            "unit_weight_kg": w,
            "unit_cbm": cbm,
            "unit_product_cost_gbp": inp.unit_product_cost_gbp,
            "sell_price_gbp": inp.sell_price_gbp,
            "sell_rate_per_day": rate,
            "horizon_days": horizon,
            "stock_lane": inp.stock_lane if track_stock else "none",
            "stock_lane_label": lane["lane"] if track_stock else "— (stock not tracked)",
            "stock_inbound_days": stock_ship_days if track_stock else "—",
            "dest_mix": mix,
            "usdgbp": fx,
            "peak_season": inp.peak_season if track_stock else False,
            "include_postage": include_postage,
            "daily_ad_spend_gbp": daily_ads,
            "ad_cost_per_purchase_gbp": cpa_ads,
            "stop_ads_when_stock_zero": stop_ads,
            "restock_enabled": restock_on,
            "restock_qty": restock_qty if restock_on else 0,
            "restock_every_days": restock_every if restock_on else 0,
            "track_stock": track_stock,
            "wholesale_dropship": track_stock,
        },
        "moq": {
            "per_variant": OVERSEAS_MOQ_PER_VARIANT,
            "total": OVERSEAS_MOQ_TOTAL,
            "applies": track_stock and wh != "CN",
            "met": (not track_stock)
            or wh == "CN"
            or (qty >= OVERSEAS_MOQ_TOTAL and qty >= OVERSEAS_MOQ_PER_VARIANT),
        },
        "transit": {
            "stock_to_warehouse": stock_ship_days if track_stock else "—",
            "last_mile": LAST_MILE_TRANSIT[wh],
        },
        "one_time_usd": {
            "inspection": inspection,
            "unload": unload,
            "inbound_units": round(inbound_units, 2),
            "labels": round(labels, 2),
            "stock_shipping": round(stock_ship_usd, 2),
            "total": round(inbound_total_usd, 2),
            "note": (
                "Initial stock-in only; restock inbound is included in totals.inbound_gbp."
                if track_stock
                else "Stock not tracked — no inbound fees."
            ),
        },
        "one_time_gbp": round(_usd_to_gbp(inbound_total_usd, fx), 2),
        "restock": {
            "enabled": track_stock and restock_on and restock_qty > 0,
            "qty": restock_qty if restock_on else 0,
            "every_days": restock_every if restock_on else 0,
            "events": restock_events,
            "units_added": cum_restock_units,
            "days": restock_days,
            "cartons_per_event": restock_cartons if restock_on and restock_qty else 0,
        },
        "per_order_usd": {
            "outbound": round(outbound_per_order_usd, 2),
            "avg_last_mile": round(avg_last_mile_usd, 2),
        },
        "totals": {
            "units_sold": round(units_sold, 2),
            "units_left": round(units_left, 2) if track_stock else None,
            "units_received": total_received if track_stock else round(units_sold, 2),
            "sell_through_pct": round(sell_through_pct, 4),
            "days_to_clear": round(days_to_clear, 1) if days_to_clear is not None else None,
            "storage_usd": round(cum_storage_usd, 2),
            "storage_gbp": round(total_storage_gbp, 2),
            "outbound_gbp": round(total_outbound_gbp, 2),
            "last_mile_gbp": round(total_last_mile_gbp, 2),
            "last_mile_in_cogs_gbp": round(total_last_mile_in_cogs_gbp, 2),
            "product_cogs_gbp": round(product_cogs_sold, 2),
            "inbound_gbp": round(total_inbound_gbp, 2),
            "revenue_gbp": round(cum_revenue_gbp, 2),
            "checkout_fees_gbp": round(cum_fees_gbp, 2),
            "ads_gbp": round(cum_ads_gbp, 2),
            "contrib_gbp": round(unit_gross_contrib, 2),
            "inbound_on_unsold_gbp": round(inbound_on_unsold, 2),
            "inventory_residual_gbp": round(inventory_residual_gbp, 2),
            "roas": round(roas, 2) if roas is not None else None,
            "roas_after_cogs": round(roas_after_cogs, 2) if roas_after_cogs is not None else None,
            "poas": round(poas, 2) if poas is not None else None,
            "net_margin": round(net_margin, 4) if net_margin is not None else None,
        },
        "overall_pnl": {
            "revenue_gbp": round(cum_revenue_gbp, 2),
            "costs": costs_breakdown,
            "total_costs_gbp": round(total_costs, 2),
            "profit_gbp": round(overall_pnl, 2),
            "is_profit": overall_pnl >= 0,
            "include_postage": include_postage,
            "postage_excluded_gbp": round(
                0.0 if include_postage else total_last_mile_gbp, 2
            ),
            "inventory_residual_gbp": round(inventory_residual_gbp, 2),
            "roas": round(roas, 2) if roas is not None else None,
            "roas_after_cogs": round(roas_after_cogs, 2) if roas_after_cogs is not None else None,
            "poas": round(poas, 2) if poas is not None else None,
            "net_margin": round(net_margin, 4) if net_margin is not None else None,
            "note": (
                "Profit = revenue − product COGS (sold)"
                + (" − full inbound (incl. restocks) − storage" if track_stock else "")
                + " − outbound"
                + (" − postage" if include_postage else " (postage excluded)")
                + " − checkout fees − ads. "
                + (
                    "Leftover stock is not a P&L loss; residual product cost shown separately."
                    if track_stock
                    else "Stock not tracked."
                )
            ),
        },
        "unit_economics": {
            "sell_price_gbp": inp.sell_price_gbp,
            "product_cost_gbp": round(per_unit_product, 4),
            "inbound_alloc_gbp": round(per_unit_inbound, 4),
            "storage_alloc_gbp": round(per_unit_storage, 4),
            "outbound_gbp": round(per_unit_outbound, 4),
            "last_mile_gbp": round(per_unit_last_mile, 4),
            "last_mile_actual_gbp": round(per_unit_last_mile_actual, 4),
            "include_postage": include_postage,
            "landed_cogs_gbp": round(landed_cogs, 4),
            "checkout_fee_gbp": round(fee_per_unit, 4),
            "ads_alloc_gbp": round(per_unit_ads, 4),
            "contribution_gbp": round(contrib, 4) if contrib is not None else None,
            "margin": round(margin, 4) if margin is not None else None,
            "contribution_after_ads_gbp": (
                round(contrib_after_ads, 4) if contrib_after_ads is not None else None
            ),
            "margin_after_ads": (
                round(margin_after_ads, 4) if margin_after_ads is not None else None
            ),
            "roas": round(roas, 2) if roas is not None else None,
            "roas_after_cogs": round(roas_after_cogs, 2) if roas_after_cogs is not None else None,
            "poas": round(poas, 2) if poas is not None else None,
        },
        "milestones": milestones,
        "days": days,
        "last_mile_defaults_usd": DEFAULT_LAST_MILE_USD[wh],
        "stock_lanes": stock_lanes_for_warehouse(wh),
    }



def meta() -> dict[str, Any]:
    return {
        "warehouses": WAREHOUSES,
        "moq": {"per_variant": OVERSEAS_MOQ_PER_VARIANT, "total": OVERSEAS_MOQ_TOTAL},
        "stock_shipping": STOCK_SHIPPING,
        "last_mile_transit": LAST_MILE_TRANSIT,
        "default_last_mile_usd": DEFAULT_LAST_MILE_USD,
        "source": "https://cjdropshipping.com/service-fee",
    }
