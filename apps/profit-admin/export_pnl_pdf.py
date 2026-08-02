"""Build a structured PDF report from a Profit Admin P&L snapshot."""

from __future__ import annotations

import base64
import re
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from concept_copy import (
    CHART_PRODUCT_CONTRIB,
    DAILY_BREAKDOWN,
    PNL_INTRO,
    PNL_KPI,
    PRODUCT_PNL,
    UNIT_ECONOMICS,
    chart_note_for_view,
)

_ACCENT = colors.HexColor("#1f4b99")
_HEADER_BG = colors.HexColor("#1f2937")
_ROW_ALT = colors.HexColor("#f6f6f4")
_GOOD = colors.HexColor("#067647")
_BAD = colors.HexColor("#b42318")
_MUTED = colors.HexColor("#6b6b6b")
_BORDER = colors.HexColor("#e3e3e0")


def _money(n: Any, digits: int = 2) -> str:
    if n is None:
        return "—"
    try:
        v = float(n)
    except (TypeError, ValueError):
        return "—"
    return f"£{v:,.{digits}f}"


def _pct(n: Any) -> str:
    if n is None:
        return "—"
    try:
        return f"{round(float(n) * 100)}%"
    except (TypeError, ValueError):
        return "—"


def _x(n: Any) -> str:
    if n is None:
        return "—"
    try:
        return f"{float(n):.2f}×"
    except (TypeError, ValueError):
        return "—"


def _decode_data_url(data_url: str | None) -> bytes | None:
    if not data_url or not isinstance(data_url, str):
        return None
    m = re.match(r"^data:image/(?:png|jpeg);base64,(.+)$", data_url, re.I | re.S)
    if not m:
        return None
    try:
        return base64.b64decode(m.group(1))
    except Exception:
        return None


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "PnLTitle",
            parent=base["Heading1"],
            fontSize=18,
            textColor=_ACCENT,
            spaceAfter=4,
            leading=22,
        ),
        "subtitle": ParagraphStyle(
            "PnLSubtitle",
            parent=base["Normal"],
            fontSize=9,
            textColor=_MUTED,
            spaceAfter=10,
        ),
        "h2": ParagraphStyle(
            "PnLH2",
            parent=base["Heading2"],
            fontSize=12,
            textColor=colors.HexColor("#1a1a1a"),
            spaceBefore=12,
            spaceAfter=6,
            leading=15,
        ),
        "body": ParagraphStyle(
            "PnLBody",
            parent=base["Normal"],
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#1a1a1a"),
        ),
        "note": ParagraphStyle(
            "PnLNote",
            parent=base["Normal"],
            fontSize=8,
            textColor=_MUTED,
            spaceAfter=6,
            leading=10,
        ),
        "kpi_label": ParagraphStyle(
            "PnLKpiLabel",
            parent=base["Normal"],
            fontSize=8,
            textColor=_MUTED,
            alignment=TA_LEFT,
        ),
        "kpi_value": ParagraphStyle(
            "PnLKpiValue",
            parent=base["Normal"],
            fontSize=14,
            leading=17,
            textColor=colors.HexColor("#1a1a1a"),
            alignment=TA_LEFT,
        ),
        "cell": ParagraphStyle(
            "PnLCell",
            parent=base["Normal"],
            fontSize=7.5,
            leading=9.5,
        ),
        "cell_r": ParagraphStyle(
            "PnLCellR",
            parent=base["Normal"],
            fontSize=7.5,
            leading=9.5,
            alignment=TA_RIGHT,
        ),
        "th": ParagraphStyle(
            "PnLTh",
            parent=base["Normal"],
            fontSize=7.5,
            textColor=colors.white,
            leading=9.5,
        ),
        "th_r": ParagraphStyle(
            "PnLThR",
            parent=base["Normal"],
            fontSize=7.5,
            textColor=colors.white,
            leading=9.5,
            alignment=TA_RIGHT,
        ),
        "footer": ParagraphStyle(
            "PnLFooter",
            parent=base["Normal"],
            fontSize=7.5,
            textColor=_MUTED,
        ),
    }


def _table_style(ncols: int, *, money_cols: set[int] | None = None) -> TableStyle:
    money_cols = money_cols or set()
    cmds: list[tuple] = [
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.25, _BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _ROW_ALT]),
    ]
    for c in money_cols:
        cmds.append(("ALIGN", (c, 0), (c, -1), "RIGHT"))
    return TableStyle(cmds)


def _kpi_cards(totals: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    pnl = totals.get("cum_pnl")
    pnl_color = _GOOD if isinstance(pnl, (int, float)) and pnl >= 0 else _BAD
    mer = totals.get("mer3d")
    cards = [
        ("Revenue", _money(totals.get("revenue"), 0)),
        ("Meta spend", _money(totals.get("meta_spend"), 0)),
        ("Trailing 3-day MER", _x(mer) if mer is not None else "—"),
        ("Cumulative P&L", _money(pnl, 0)),
    ]
    data = []
    row_labels = []
    row_values = []
    for label, value in cards:
        row_labels.append(Paragraph(label, styles["kpi_label"]))
        val_style = ParagraphStyle(
            f"kpi_{label}",
            parent=styles["kpi_value"],
            textColor=pnl_color if label == "Cumulative P&L" else colors.HexColor("#1a1a1a"),
        )
        row_values.append(Paragraph(value, val_style))
    data.append(row_labels)
    data.append(row_values)
    t = Table(data, colWidths=[45 * mm] * 4)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.6, _BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, _BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return t


def _summary_table(totals: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    rows = [
        [Paragraph("Metric", styles["th"]), Paragraph("Amount", styles["th_r"])],
        [Paragraph("Revenue", styles["cell"]), Paragraph(_money(totals.get("revenue")), styles["cell_r"])],
        [Paragraph("Landed COGS", styles["cell"]), Paragraph(_money(totals.get("landed_cogs")), styles["cell_r"])],
        [Paragraph("Checkout fees", styles["cell"]), Paragraph(_money(totals.get("fees")), styles["cell_r"])],
        [Paragraph("Meta spend", styles["cell"]), Paragraph(_money(totals.get("meta_spend")), styles["cell_r"])],
        [Paragraph("KIE (est. £)", styles["cell"]), Paragraph(_money(totals.get("kie_gbp")), styles["cell_r"])],
        [
            Paragraph("Shopify amortised", styles["cell"]),
            Paragraph(_money(totals.get("shopify_amortised")), styles["cell_r"]),
        ],
        [
            Paragraph("Store MER (rev ÷ ads)", styles["cell"]),
            Paragraph(_x(totals.get("store_mer")), styles["cell_r"]),
        ],
        [
            Paragraph("Meta ROAS (attr rev ÷ ads)", styles["cell"]),
            Paragraph(_x(totals.get("meta_roas")), styles["cell_r"]),
        ],
        [
            Paragraph("Orders", styles["cell"]),
            Paragraph(str(totals.get("orders") if totals.get("orders") is not None else "—"), styles["cell_r"]),
        ],
        [
            Paragraph("<b>Cumulative P&L</b>", styles["cell"]),
            Paragraph(f"<b>{_money(totals.get('cum_pnl'))}</b>", styles["cell_r"]),
        ],
    ]
    t = Table(rows, colWidths=[120 * mm, 60 * mm])
    t.setStyle(_table_style(2, money_cols={1}))
    return t


def _daily_table(days: list[dict[str, Any]], styles: dict[str, ParagraphStyle]) -> Table | None:
    if not days:
        return None
    header = [
        Paragraph(h, styles["th"] if i == 0 else styles["th_r"])
        for i, h in enumerate(
            ["Day", "Revenue", "Ads", "COGS", "KIE", "Day P&L", "Cum P&L", "3d MER"]
        )
    ]
    data = [header]
    for d in days:
        data.append(
            [
                Paragraph(str(d.get("label") or d.get("date") or ""), styles["cell"]),
                Paragraph(_money(d.get("rev")), styles["cell_r"]),
                Paragraph(_money(d.get("ads")), styles["cell_r"]),
                Paragraph(_money(d.get("cogs")), styles["cell_r"]),
                Paragraph(_money(d.get("kie_gbp")), styles["cell_r"]),
                Paragraph(_money(d.get("day_pnl")), styles["cell_r"]),
                Paragraph(_money(d.get("cum_pnl")), styles["cell_r"]),
                Paragraph(_x(d.get("mer3d")) if d.get("mer3d") is not None else "—", styles["cell_r"]),
            ]
        )
    widths = [18 * mm, 24 * mm, 22 * mm, 22 * mm, 20 * mm, 24 * mm, 24 * mm, 20 * mm]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(_table_style(8, money_cols={1, 2, 3, 4, 5, 6, 7}))
    return t


def _product_table(rows: list[dict[str, Any]], styles: dict[str, ParagraphStyle]) -> Table | None:
    if not rows:
        return None
    header = [
        Paragraph(h, styles["th"] if i == 0 else styles["th_r"])
        for i, h in enumerate(
            ["Product", "Orders", "Units", "Revenue", "COGS", "Fees", "Contrib", "Margin", "Avg £"]
        )
    ]
    data = [header]
    for r in rows:
        name = str(r.get("product") or r.get("title") or r.get("name") or "—")
        data.append(
            [
                Paragraph(name[:48], styles["cell"]),
                Paragraph(str(r.get("orders") if r.get("orders") is not None else "—"), styles["cell_r"]),
                Paragraph(str(r.get("units") if r.get("units") is not None else "—"), styles["cell_r"]),
                Paragraph(_money(r.get("revenue") if "revenue" in r else r.get("rev")), styles["cell_r"]),
                Paragraph(_money(r.get("cogs")), styles["cell_r"]),
                Paragraph(_money(r.get("fees")), styles["cell_r"]),
                Paragraph(_money(r.get("contrib")), styles["cell_r"]),
                Paragraph(_pct(r.get("margin")), styles["cell_r"]),
                Paragraph(_money(r.get("avg_unit")), styles["cell_r"]),
            ]
        )
    widths = [42 * mm, 14 * mm, 14 * mm, 20 * mm, 18 * mm, 16 * mm, 20 * mm, 14 * mm, 16 * mm]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(_table_style(9, money_cols=set(range(1, 9))))
    return t


def _unit_table(rows: list[dict[str, Any]], styles: dict[str, ParagraphStyle]) -> Table | None:
    if not rows:
        return None
    header = [
        Paragraph(h, styles["th"] if i == 0 else styles["th_r"])
        for i, h in enumerate(
            ["Product", "Sell", "Landed", "Contrib", "Margin", "Min ROAS", "Max CPA"]
        )
    ]
    data = [header]
    for r in rows:
        data.append(
            [
                Paragraph(str(r.get("product") or "—")[:48], styles["cell"]),
                Paragraph(_money(r.get("sell")), styles["cell_r"]),
                Paragraph(_money(r.get("landed")), styles["cell_r"]),
                Paragraph(_money(r.get("contrib")), styles["cell_r"]),
                Paragraph(_pct(r.get("margin")), styles["cell_r"]),
                Paragraph(_x(r.get("min_roas")), styles["cell_r"]),
                Paragraph(_money(r.get("max_cpa")), styles["cell_r"]),
            ]
        )
    widths = [50 * mm, 22 * mm, 22 * mm, 22 * mm, 18 * mm, 22 * mm, 22 * mm]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(_table_style(7, money_cols=set(range(1, 7))))
    return t


def _chart_image(data_url: str | None, *, max_width: float, max_height: float) -> Image | None:
    raw = _decode_data_url(data_url)
    if not raw:
        return None
    img = Image(BytesIO(raw))
    img.hAlign = "LEFT"
    # Preserve aspect ratio within bounds
    iw, ih = img.imageWidth, img.imageHeight
    if iw <= 0 or ih <= 0:
        return None
    scale = min(max_width / iw, max_height / ih)
    img.drawWidth = iw * scale
    img.drawHeight = ih * scale
    return img


def _append_charts(
    story: list[Any],
    charts: list[dict[str, Any]],
    styles: dict[str, ParagraphStyle],
    *,
    section_title: str | None = "Charts",
) -> None:
    usable: list[tuple[str, str | None, Any]] = []
    for c in charts or []:
        if not isinstance(c, dict):
            continue
        img = _chart_image(c.get("png"), max_width=180 * mm, max_height=78 * mm)
        if not img:
            continue
        usable.append((str(c.get("title") or "Chart"), c.get("note"), img))
    if not usable:
        return
    if section_title:
        story.append(Paragraph(section_title, styles["h2"]))
    for title, note, img in usable:
        block: list[Any] = [Paragraph(title, styles["h2"])]
        if note:
            block.append(Paragraph(str(note), styles["note"]))
        block.append(img)
        block.append(Spacer(1, 6))
        story.append(KeepTogether(block))


def build_pnl_pdf(
    snapshot: dict[str, Any],
    *,
    charts: list[dict[str, Any]] | None = None,
    chart_png: str | None = None,
    chart_title: str | None = None,
) -> bytes:
    """Return PDF bytes for the P&L desk snapshot."""
    styles = _styles()
    pnl = snapshot.get("pnl") or {}
    totals = pnl.get("totals") or {}
    days = pnl.get("days") or []
    products = snapshot.get("product_pnl") or []
    units = snapshot.get("unit_economics") or []
    shop = ((snapshot.get("sources") or {}).get("shopify") or {}).get("shop") or {}
    shop_name = shop.get("name") or "Our Tech Accessories"
    refreshed = snapshot.get("refreshed_at") or ""
    try:
        refreshed_lbl = (
            datetime.fromisoformat(refreshed.replace("Z", "+00:00")).strftime("%d %b %Y %H:%M UTC")
            if refreshed
            else "—"
        )
    except ValueError:
        refreshed_lbl = refreshed or "—"

    chart_list = list(charts or [])
    if not chart_list and chart_png:
        chart_list = [{"title": chart_title or "Chart", "note": None, "png": chart_png}]

    # Split product contribution chart so it sits with the product table.
    main_charts: list[dict[str, Any]] = []
    product_charts: list[dict[str, Any]] = []
    for c in chart_list:
        title = str((c or {}).get("title") or "").lower()
        if "contribution by product" in title or (
            "product" in title and "contribution" in title
        ):
            product_charts.append(c)
        else:
            main_charts.append(c)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title="Profit Admin — P&L",
        author="Our Tech Profit Admin",
    )

    story: list[Any] = []
    story.append(Paragraph("Profit Admin — P&amp;L", styles["title"]))
    story.append(
        Paragraph(
            f"{shop_name} · Refreshed {refreshed_lbl} · Exported "
            f"{datetime.now(timezone.utc).strftime('%d %b %Y %H:%M UTC')}",
            styles["subtitle"],
        )
    )
    story.append(Paragraph(PNL_INTRO, styles["note"]))
    story.append(Paragraph(PNL_KPI, styles["note"]))

    story.append(_kpi_cards(totals, styles))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Cost stack summary", styles["h2"]))
    story.append(
        Paragraph(
            "Store MER = Shopify revenue ÷ Meta spend. "
            "Meta ROAS = attributed purchase value ÷ Meta spend (Insights). "
            "They can disagree when attribution or product mix differs.",
            styles["note"],
        )
    )
    story.append(_summary_table(totals, styles))

    # Ensure chart notes are populated even if the UI omitted them.
    for c in main_charts:
        if not c.get("note"):
            title = str(c.get("title") or "").lower()
            if "3-day mer" in title or title.endswith(" mer"):
                c["note"] = chart_note_for_view("mer")
            elif "revenue vs" in title:
                c["note"] = chart_note_for_view("cumRevCost")
            elif "cost stack" in title:
                c["note"] = chart_note_for_view("dailyStack")
            elif "cumulative" in title and "p&l" in title.replace("＆", "&"):
                c["note"] = chart_note_for_view("cumPnl")

    _append_charts(story, main_charts, styles, section_title=None)

    daily = _daily_table(days, styles)
    if daily:
        story.append(Paragraph("Daily breakdown", styles["h2"]))
        story.append(Paragraph(DAILY_BREAKDOWN, styles["note"]))
        story.append(daily)

    prod = _product_table(products, styles)
    if prod or product_charts:
        story.append(Paragraph("Product profitability", styles["h2"]))
        story.append(Paragraph(PRODUCT_PNL, styles["note"]))
        if prod:
            story.append(prod)
        for c in product_charts:
            if not c.get("note"):
                c["note"] = CHART_PRODUCT_CONTRIB
        _append_charts(story, product_charts, styles, section_title=None)

    unit = _unit_table(units, styles)
    if unit:
        story.append(Paragraph("Unit economics (ACTIVE SKUs)", styles["h2"]))
        story.append(Paragraph(UNIT_ECONOMICS, styles["note"]))
        story.append(unit)

    warnings = snapshot.get("warnings") or []
    if warnings:
        story.append(Paragraph("Warnings", styles["h2"]))
        for w in warnings:
            story.append(Paragraph(f"• {str(w)}", styles["note"]))

    story.append(Spacer(1, 10))
    story.append(
        Paragraph(
            "Generated by Our Tech Profit Admin · figures are estimates",
            styles["footer"],
        )
    )

    doc.build(story)
    return buf.getvalue()
