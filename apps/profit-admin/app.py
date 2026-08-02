"""
Profit Admin — local ops dashboard (embed-ready API).

Run from repo root:
  python -m venv .venv-profit && source .venv-profit/bin/activate
  pip install -r apps/profit-admin/requirements.txt
  uvicorn app:app --app-dir apps/profit-admin --reload --port 8787

Or:
  cd apps/profit-admin && uvicorn app:app --reload --port 8787
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from auth import AuthDep
from ads_pnl import build_ads_performance_with_pnl
from collectors.meta_collector import list_structure as meta_list_structure
from collectors.shopify_collector import list_catalog
from config import fee_fixed_gbp, fee_pct, kie_log_path, port, repo_root, resolve_usdgbp
from export_ads_pdf import build_ads_pdf
from export_pnl_pdf import build_pnl_pdf
from export_xlsx import build_workbook
from past_performance import build_past_performance
from pnl import build_product_pnl
from refresh import run_refresh
from snapshots import list_snapshots, read_latest, read_snapshot
from subset_pnl import build_subset_pnl
from views import delete_view, list_views, pin_ads_report, read_view, write_view
from warehouse_fees import CalcInput, calculate, meta as warehouse_meta, stock_lanes_for_warehouse

STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Our Tech Profit Admin", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


class WarehouseCalcBody(BaseModel):
    warehouse: str = "GB"
    qty: int = Field(100, ge=1)
    unit_weight_kg: float = Field(0.15, gt=0)
    unit_cbm: float = Field(0.001, gt=0)
    unit_product_cost_gbp: float = Field(3.0, ge=0)
    sell_price_gbp: float = Field(19.99, ge=0)
    sell_rate_per_day: float = Field(1.0, ge=0)
    horizon_days: int = Field(180, ge=1, le=730)
    stock_lane: str = "none"
    cartons: int = Field(1, ge=1)
    pieces_per_order: int = Field(1, ge=1)
    peak_season: bool = False
    include_postage: bool = True
    daily_ad_spend_gbp: float = Field(0.0, ge=0)
    ad_cost_per_purchase_gbp: float = Field(0.0, ge=0)
    stop_ads_when_stock_zero: bool = True
    restock_enabled: bool = False
    restock_qty: int = Field(0, ge=0)
    restock_every_days: int = Field(30, ge=1, le=365)
    track_stock: bool = True
    dest_mix: dict[str, float] | None = None
    last_mile_usd: dict[str, float] | None = None
    show_past_performance: bool = False
    past_handles: list[str] = Field(default_factory=list)
    past_skus: list[str] = Field(default_factory=list)
    past_campaign_ids: list[str] = Field(default_factory=list)
    past_adset_ids: list[str] = Field(default_factory=list)
    past_date_preset: str = "maximum"


class PastPerformanceBody(BaseModel):
    handles: list[str] = Field(default_factory=list)
    skus: list[str] = Field(default_factory=list)
    campaign_ids: list[str] = Field(default_factory=list)
    adset_ids: list[str] = Field(default_factory=list)
    date_preset: str = "maximum"


class WarehouseExportBody(BaseModel):
    """Full calculate payload (+ optional label) to turn into Excel."""
    result: dict[str, Any]
    label: str | None = None


class PnlChartExport(BaseModel):
    title: str
    note: str | None = None
    png: str


class PnlExportBody(BaseModel):
    """Snapshot (+ chart images) to turn into PDF."""
    snapshot: dict[str, Any] | None = None
    charts: list[PnlChartExport] = Field(default_factory=list)
    # Legacy single-chart fields (still accepted)
    chart_png: str | None = None
    chart_title: str | None = None


class PnlSubsetBody(BaseModel):
    """SKU + Meta selection for a subset P&L time series."""
    skus: list[str] = Field(default_factory=list)
    handles: list[str] = Field(default_factory=list)
    adset_ids: list[str] = Field(default_factory=list)
    campaign_ids: list[str] = Field(default_factory=list)


class AdsPerformanceBody(BaseModel):
    """Meta object selection + optional SKUs + date window for Ads + P&L desk."""
    campaign_ids: list[str] = Field(default_factory=list)
    adset_ids: list[str] = Field(default_factory=list)
    ad_ids: list[str] = Field(default_factory=list)
    skus: list[str] = Field(default_factory=list)
    handles: list[str] = Field(default_factory=list)
    date_preset: str | None = None
    since: str | None = None
    until: str | None = None


class AdsChartExport(BaseModel):
    title: str
    note: str | None = None
    png: str


class AdsExportBody(BaseModel):
    """Ads performance report (+ chart images) to turn into PDF."""
    report: dict[str, Any]
    charts: list[AdsChartExport] = Field(default_factory=list)
    pin: bool = False
    pin_label: str | None = None


class DeskViewBody(BaseModel):
    """Saved desk view — filters/config only (no result payloads)."""
    name: str = "Untitled view"
    sections: dict[str, Any] = Field(default_factory=dict)
    scope: dict[str, Any] = Field(default_factory=dict)
    warehouse: dict[str, Any] = Field(default_factory=dict)
    ui: dict[str, Any] = Field(default_factory=dict)
    id: str | None = None
    created_at: str | None = None


def _with_product_pnl(payload: dict) -> dict:
    """Backfill product dig-in for snapshots saved before this field existed."""
    if payload.get("product_pnl") is not None:
        return payload
    sources = payload.get("sources") or {}
    shopify = sources.get("shopify")
    cj = sources.get("cj")
    if shopify:
        payload = {**payload, "product_pnl": build_product_pnl(shopify, cj=cj)}
    else:
        payload = {**payload, "product_pnl": []}
    return payload


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health(_auth: AuthDep) -> dict:
    root = repo_root()
    shopify_ok = bool(
        __import__("os").getenv("SHOPIFY_SHOP")
        and __import__("os").getenv("SHOPIFY_CLIENT_ID")
        and __import__("os").getenv("SHOPIFY_CLIENT_SECRET")
    )
    meta_ok = bool(
        __import__("os").getenv("META_ACCESS_TOKEN")
        and __import__("os").getenv("META_AD_ACCOUNT_ID")
    )
    kie_ok = kie_log_path().exists()
    cj_ok = bool(__import__("os").getenv("CJ_API_KEY"))
    latest = read_latest()
    return {
        "ok": True,
        "port_default": port(),
        "repo": str(root),
        "connectors": {
            "shopify_env": shopify_ok,
            "meta_env": meta_ok,
            "kie_log": kie_ok,
            "cj_env": cj_ok,
        },
        "has_snapshot": latest is not None,
        "last_refreshed_at": (latest or {}).get("refreshed_at"),
    }


@app.post("/api/refresh")
def refresh(_auth: AuthDep) -> dict:
    try:
        return run_refresh()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/snapshot/latest")
def snapshot_latest(_auth: AuthDep) -> dict:
    latest = read_latest()
    if not latest:
        raise HTTPException(status_code=404, detail="No snapshot yet — hit Refresh")
    return _with_product_pnl(latest)


@app.get("/api/snapshots")
def snapshots(_auth: AuthDep) -> dict:
    return {"snapshots": list_snapshots()}


@app.get("/api/snapshot/{snapshot_id}")
def snapshot_one(snapshot_id: str, _auth: AuthDep) -> dict:
    snap = read_snapshot(snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return _with_product_pnl(snap)


@app.get("/api/views")
def views_list(_auth: AuthDep) -> dict:
    return {"views": list_views()}


@app.get("/api/views/{view_id}")
def views_one(view_id: str, _auth: AuthDep) -> dict:
    view = read_view(view_id)
    if not view:
        raise HTTPException(status_code=404, detail="View not found")
    return view


@app.post("/api/views")
def views_create(body: DeskViewBody, _auth: AuthDep) -> dict:
    return write_view(body.model_dump(exclude_none=True))


@app.put("/api/views/{view_id}")
def views_update(view_id: str, body: DeskViewBody, _auth: AuthDep) -> dict:
    if not read_view(view_id):
        raise HTTPException(status_code=404, detail="View not found")
    payload = body.model_dump(exclude_none=True)
    payload["id"] = view_id
    return write_view(payload, view_id=view_id)


@app.delete("/api/views/{view_id}")
def views_delete(view_id: str, _auth: AuthDep) -> dict:
    if not delete_view(view_id):
        raise HTTPException(status_code=404, detail="View not found")
    return {"ok": True, "id": view_id}


@app.get("/api/catalog")
def catalog(_auth: AuthDep) -> dict:
    """Shopify variants for warehouse SKU picker."""
    try:
        rows = list_catalog()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Shopify catalog failed: {e}") from e
    return {"catalog": rows, "count": len(rows)}


@app.get("/api/warehouse/meta")
def warehouse_fee_meta(_auth: AuthDep) -> dict:
    data = warehouse_meta()
    data["usdgbp"] = resolve_usdgbp()
    data["fee_pct"] = fee_pct()
    data["fee_fixed_gbp"] = fee_fixed_gbp()
    return data


@app.get("/api/warehouse/lanes/{warehouse}")
def warehouse_lanes(warehouse: str, _auth: AuthDep) -> dict:
    wh = warehouse.upper()
    try:
        lanes = stock_lanes_for_warehouse(wh)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"warehouse": wh, "lanes": lanes}


@app.get("/api/meta/structure")
def meta_structure(_auth: AuthDep) -> dict:
    """Campaigns + ad sets + ads for historic / Ads performance pickers."""
    try:
        return meta_list_structure()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Meta structure failed: {e}") from e


@app.post("/api/ads/performance")
def ads_performance(body: AdsPerformanceBody, _auth: AuthDep) -> dict[str, Any]:
    """Meta insights + profitability (SKU P&L if products picked, else whole-store)."""
    try:
        return build_ads_performance_with_pnl(
            campaign_ids=body.campaign_ids,
            adset_ids=body.adset_ids,
            ad_ids=body.ad_ids,
            skus=body.skus,
            handles=body.handles,
            date_preset=body.date_preset,
            since=body.since,
            until=body.until,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ads performance failed: {e}") from e


@app.post("/api/ads/export")
def ads_export(body: AdsExportBody, _auth: AuthDep) -> Response:
    if not body.report or not isinstance(body.report, dict):
        raise HTTPException(status_code=400, detail="Missing ads report to export")
    if body.pin:
        try:
            pin_ads_report(body.report, label=body.pin_label)
        except Exception:
            pass
    charts = [c.model_dump() for c in body.charts]
    try:
        data = build_ads_pdf(body.report, charts=charts)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF export failed: {e}") from e
    stamp = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime(
        "%Y%m%d-%H%M"
    )
    filename = f"profit-admin-ads-{stamp}.pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/ads/pin")
def ads_pin(body: AdsExportBody, _auth: AuthDep) -> dict:
    """Persist an Ads Apply payload under outputs/profit-admin/reports/."""
    if not body.report or not isinstance(body.report, dict):
        raise HTTPException(status_code=400, detail="Missing ads report to pin")
    path = pin_ads_report(body.report, label=body.pin_label)
    return {"ok": True, "path": str(path)}


@app.post("/api/warehouse/past-performance")
def warehouse_past_performance(body: PastPerformanceBody, _auth: AuthDep) -> dict[str, Any]:
    try:
        return build_past_performance(
            handles=body.handles,
            skus=body.skus,
            campaign_ids=body.campaign_ids,
            adset_ids=body.adset_ids,
            date_preset=body.date_preset or "maximum",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/api/pnl/subset")
def pnl_subset(body: PnlSubsetBody, _auth: AuthDep) -> dict[str, Any]:
    try:
        return build_subset_pnl(
            skus=body.skus,
            handles=body.handles,
            adset_ids=body.adset_ids,
            campaign_ids=body.campaign_ids,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Subset P&L failed: {e}") from e


@app.post("/api/pnl/export")
def pnl_export(body: PnlExportBody, _auth: AuthDep) -> Response:
    snap = body.snapshot
    if not snap:
        snap = read_latest()
        if snap:
            snap = _with_product_pnl(snap)
    if not snap or not isinstance(snap, dict):
        raise HTTPException(status_code=400, detail="No snapshot to export — hit Refresh first")
    if not snap.get("pnl"):
        raise HTTPException(status_code=400, detail="Snapshot is missing P&L data")
    charts = [c.model_dump() for c in body.charts]
    if not charts and body.chart_png:
        charts = [{"title": body.chart_title or "Chart", "note": None, "png": body.chart_png}]
    try:
        data = build_pnl_pdf(snap, charts=charts)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF export failed: {e}") from e
    stamp = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime(
        "%Y%m%d-%H%M"
    )
    filename = f"profit-admin-pnl-{stamp}.pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/warehouse/export")
def warehouse_export(body: WarehouseExportBody, _auth: AuthDep) -> Response:
    if not body.result or not isinstance(body.result, dict):
        raise HTTPException(status_code=400, detail="Missing calculation result to export")
    try:
        data = build_workbook(body.result, label=body.label)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Export failed: {e}") from e
    stamp = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime(
        "%Y%m%d-%H%M"
    )
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in (body.label or "plan"))[:40]
    filename = f"profit-admin-{safe}-{stamp}.xlsx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/warehouse/calculate")
def warehouse_calculate(body: WarehouseCalcBody, _auth: AuthDep) -> dict[str, Any]:
    wh = body.warehouse.upper()
    if wh not in ("CN", "US", "PL", "DE", "GB"):
        raise HTTPException(status_code=400, detail=f"Unknown warehouse: {body.warehouse}")
    try:
        result = calculate(
            CalcInput(
                warehouse=wh,  # type: ignore[arg-type]
                qty=body.qty,
                unit_weight_kg=body.unit_weight_kg,
                unit_cbm=body.unit_cbm,
                unit_product_cost_gbp=body.unit_product_cost_gbp,
                sell_price_gbp=body.sell_price_gbp,
                sell_rate_per_day=body.sell_rate_per_day,
                horizon_days=body.horizon_days,
                stock_lane=body.stock_lane,
                cartons=body.cartons,
                pieces_per_order=body.pieces_per_order,
                peak_season=body.peak_season,
                include_postage=body.include_postage,
                daily_ad_spend_gbp=body.daily_ad_spend_gbp,
                ad_cost_per_purchase_gbp=body.ad_cost_per_purchase_gbp,
                stop_ads_when_stock_zero=body.stop_ads_when_stock_zero,
                restock_enabled=body.restock_enabled,
                restock_qty=body.restock_qty,
                restock_every_days=body.restock_every_days,
                track_stock=body.track_stock,
                dest_mix=body.dest_mix,
                last_mile_usd=body.last_mile_usd,
                checkout_fee_pct=fee_pct(),
                checkout_fee_fixed_gbp=fee_fixed_gbp(),
                usdgbp=resolve_usdgbp(),
            )
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if body.show_past_performance:
        try:
            result["past_performance"] = build_past_performance(
                handles=body.past_handles,
                skus=body.past_skus,
                campaign_ids=body.past_campaign_ids,
                adset_ids=body.past_adset_ids,
                date_preset=body.past_date_preset or "maximum",
            )
        except Exception as e:
            result["past_performance"] = {
                "shopify": None,
                "meta": None,
                "combined": {},
                "warnings": [f"Past performance failed: {e}"],
                "date_preset": body.past_date_preset,
            }
    return result
