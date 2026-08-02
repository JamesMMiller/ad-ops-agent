"""Build a structured PDF report from an Ads performance payload."""

from __future__ import annotations

import base64
import re
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
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
    ADS_BREAKDOWN,
    ADS_CHART_CTR,
    ADS_CHART_PURCH_REV,
    ADS_CHART_ROAS,
    ADS_CHART_SPEND,
    ADS_INTRO,
    ADS_META_KPI,
    ADS_OVERLAY,
    ADS_PROFITABILITY,
    chart_note_for_view,
)

_ACCENT = colors.HexColor("#1f4b99")
_HEADER_BG = colors.HexColor("#1f2937")
_ROW_ALT = colors.HexColor("#f6f6f4")
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


def _num(n: Any, digits: int = 0) -> str:
    if n is None:
        return "—"
    try:
        v = float(n)
    except (TypeError, ValueError):
        return "—"
    if digits == 0:
        return f"{int(round(v)):,}"
    return f"{v:,.{digits}f}"


def _x(n: Any) -> str:
    if n is None:
        return "—"
    try:
        return f"{float(n):.2f}×"
    except (TypeError, ValueError):
        return "—"


def _pct(n: Any, digits: int = 2) -> str:
    if n is None:
        return "—"
    try:
        return f"{float(n):.{digits}f}%"
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


def _esc(s: Any) -> str:
    t = str(s or "")
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "AdsTitle",
            parent=base["Heading1"],
            fontSize=18,
            textColor=_ACCENT,
            spaceAfter=4,
            leading=22,
        ),
        "subtitle": ParagraphStyle(
            "AdsSubtitle",
            parent=base["Normal"],
            fontSize=9,
            textColor=_MUTED,
            spaceAfter=10,
        ),
        "h2": ParagraphStyle(
            "AdsH2",
            parent=base["Heading2"],
            fontSize=12,
            textColor=colors.HexColor("#1a1a1a"),
            spaceBefore=12,
            spaceAfter=6,
            leading=15,
        ),
        "note": ParagraphStyle(
            "AdsNote",
            parent=base["Normal"],
            fontSize=8,
            textColor=_MUTED,
            spaceAfter=6,
            leading=10,
        ),
        "kpi_label": ParagraphStyle(
            "AdsKpiLabel",
            parent=base["Normal"],
            fontSize=7.5,
            textColor=_MUTED,
            alignment=TA_LEFT,
        ),
        "kpi_value": ParagraphStyle(
            "AdsKpiValue",
            parent=base["Normal"],
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#1a1a1a"),
            alignment=TA_LEFT,
        ),
        "cell": ParagraphStyle(
            "AdsCell",
            parent=base["Normal"],
            fontSize=7,
            leading=9,
        ),
        "cell_r": ParagraphStyle(
            "AdsCellR",
            parent=base["Normal"],
            fontSize=7,
            leading=9,
            alignment=TA_RIGHT,
        ),
        "th": ParagraphStyle(
            "AdsTh",
            parent=base["Normal"],
            fontSize=7,
            textColor=colors.white,
            leading=9,
        ),
        "th_r": ParagraphStyle(
            "AdsThR",
            parent=base["Normal"],
            fontSize=7,
            textColor=colors.white,
            leading=9,
            alignment=TA_RIGHT,
        ),
        "footer": ParagraphStyle(
            "AdsFooter",
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
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("GRID", (0, 0), (-1, -1), 0.25, _BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _ROW_ALT]),
    ]
    for c in money_cols:
        cmds.append(("ALIGN", (c, 0), (c, -1), "RIGHT"))
    return TableStyle(cmds)


def _kpi_table(cards: list[tuple[str, str]], styles: dict[str, ParagraphStyle], cols: int = 5) -> Table:
    cards = list(cards)
    # Pad to full rows
    while len(cards) % cols:
        cards.append(("", ""))
    data: list[list] = []
    for start in range(0, len(cards), cols):
        chunk = cards[start : start + cols]
        data.append([Paragraph(label, styles["kpi_label"]) for label, _ in chunk])
        data.append([Paragraph(value or " ", styles["kpi_value"]) for _, value in chunk])
    t = Table(data, colWidths=[(260 / cols) * mm] * cols)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.6, _BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, _BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return t


def _kpi_cards(report: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    cards = [
        ("Spend", _money(report.get("spend"))),
        ("Purchases", _num(report.get("purchases"), 0)),
        ("Attr. revenue", _money(report.get("attr_rev"))),
        ("ROAS", _x(report.get("roas"))),
        ("CPA", _money(report.get("cpa"))),
        ("Impressions", _num(report.get("impressions"), 0)),
        ("Clicks", _num(report.get("clicks"), 0)),
        ("CTR", _pct(report.get("ctr"))),
        ("CPC", _money(report.get("cpc"))),
        ("CPM", _money(report.get("cpm"))),
    ]
    return _kpi_table(cards, styles, cols=5)


def _pnl_kpi_cards(pnl: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    t = pnl.get("totals") or {}
    cards = [
        ("Revenue", _money(t.get("revenue"))),
        ("Landed COGS", _money(t.get("landed_cogs"))),
        ("Fees", _money(t.get("fees"))),
        ("Meta spend", _money(t.get("meta_spend"))),
        ("Cum. P&L", _money(t.get("cum_pnl"))),
        ("Store MER", _x(t.get("store_mer"))),
        ("Meta ROAS", _x(t.get("meta_roas"))),
        ("Orders", _num(t.get("orders"), 0)),
        ("KIE (est.)", _money(t.get("kie_gbp"))),
        ("Shopify amort.", _money(t.get("shopify_amortised"))),
    ]
    return _kpi_table(cards, styles, cols=5)


def _breakdown_table(
    by_object: list[dict[str, Any]], styles: dict[str, ParagraphStyle]
) -> Table | None:
    if not by_object:
        return None
    headers = [
        "Level",
        "Name",
        "Parent",
        "Spend",
        "Purch",
        "Attr rev",
        "ROAS",
        "CPA",
        "Impr",
        "Clicks",
        "CTR",
        "CPC",
        "CPM",
    ]
    data = [
        [
            Paragraph(h, styles["th"] if i < 3 else styles["th_r"])
            for i, h in enumerate(headers)
        ]
    ]
    for row in by_object[:80]:
        level = row.get("level") or ""
        parent = row.get("campaign_name") or ""
        if level == "ad" and row.get("adset_name"):
            parent = f"{parent} / {row.get('adset_name')}"
        data.append(
            [
                Paragraph(_esc(level), styles["cell"]),
                Paragraph(_esc(row.get("name")), styles["cell"]),
                Paragraph(_esc(parent), styles["cell"]),
                Paragraph(_money(row.get("spend")), styles["cell_r"]),
                Paragraph(_num(row.get("purchases"), 0), styles["cell_r"]),
                Paragraph(_money(row.get("attr_rev")), styles["cell_r"]),
                Paragraph(_x(row.get("roas")), styles["cell_r"]),
                Paragraph(_money(row.get("cpa")), styles["cell_r"]),
                Paragraph(_num(row.get("impressions"), 0), styles["cell_r"]),
                Paragraph(_num(row.get("clicks"), 0), styles["cell_r"]),
                Paragraph(_pct(row.get("ctr")), styles["cell_r"]),
                Paragraph(_money(row.get("cpc")), styles["cell_r"]),
                Paragraph(_money(row.get("cpm")), styles["cell_r"]),
            ]
        )
    widths = [14, 52, 40, 18, 14, 18, 14, 16, 18, 14, 14, 14, 14]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1)
    t.setStyle(_table_style(13, money_cols=set(range(3, 13))))
    return t


def _chart_flowables(
    charts: list[dict[str, Any]], styles: dict[str, ParagraphStyle]
) -> list:
    out: list = []
    for ch in charts:
        title = ch.get("title") or "Chart"
        note = ch.get("note")
        raw = _decode_data_url(ch.get("png"))
        if not raw:
            continue
        block: list = [Paragraph(_esc(title), styles["h2"])]
        if note:
            block.append(Paragraph(_esc(note), styles["note"]))
        img = Image(BytesIO(raw))
        # Fit landscape page width (~270mm usable)
        max_w = 270 * mm
        max_h = 90 * mm
        iw, ih = img.imageWidth, img.imageHeight
        scale = min(max_w / iw, max_h / ih, 1.0)
        img.drawWidth = iw * scale
        img.drawHeight = ih * scale
        block.append(img)
        block.append(Spacer(1, 4 * mm))
        out.append(KeepTogether(block))
    return out


def build_ads_pdf(
    report: dict[str, Any],
    *,
    charts: list[dict[str, Any]] | None = None,
) -> bytes:
    """Render Ads performance report to PDF bytes."""
    styles = _styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title="Profit Admin — Ads performance",
    )
    story: list = []

    since = report.get("since") or "—"
    until = report.get("until") or "—"
    preset = report.get("date_preset")
    range_label = f"{since} → {until}"
    if preset:
        range_label = f"{preset} ({range_label})"

    n_camp = len(report.get("campaign_ids") or [])
    n_adset = len(report.get("adset_ids") or [])
    n_ad = len(report.get("ad_ids") or [])
    sel = f"{n_camp} campaign(s) · {n_adset} ad set(s) · {n_ad} ad(s)"

    story.append(Paragraph("Ads performance", styles["title"]))
    story.append(
        Paragraph(
            f"Our Tech Accessories · {range_label} · {sel} · "
            f"exported {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            styles["subtitle"],
        )
    )
    if report.get("warning"):
        story.append(Paragraph(_esc(report["warning"]), styles["note"]))

    story.append(Paragraph(_esc(ADS_INTRO), styles["note"]))

    story.append(Paragraph("Meta performance", styles["h2"]))
    story.append(Paragraph(_esc(ADS_META_KPI), styles["note"]))
    story.append(_kpi_cards(report, styles))
    story.append(Spacer(1, 4 * mm))

    pnl = report.get("pnl")
    if pnl and isinstance(pnl, dict):
        mode = report.get("pnl_mode") or pnl.get("mode") or "—"
        story.append(Paragraph(f"Profitability ({_esc(mode)} mode)", styles["h2"]))
        story.append(Paragraph(_esc(ADS_PROFITABILITY), styles["note"]))
        if pnl.get("note"):
            story.append(Paragraph(_esc(pnl["note"]), styles["note"]))
        if pnl.get("label"):
            story.append(Paragraph(_esc(f"Scope: {pnl['label']}"), styles["note"]))
        story.append(_pnl_kpi_cards(pnl, styles))
        story.append(Spacer(1, 4 * mm))

    table = _breakdown_table(report.get("by_object") or [], styles)
    if table:
        story.append(Paragraph("Breakdown by object", styles["h2"]))
        story.append(Paragraph(_esc(ADS_BREAKDOWN), styles["note"]))
        story.append(table)
        story.append(Spacer(1, 3 * mm))

    chart_list = list(charts or [])
    for c in chart_list:
        if not c.get("note"):
            title = str(c.get("title") or "").lower()
            if "spend" in title:
                c["note"] = ADS_CHART_SPEND
            elif "purchas" in title or "attr" in title:
                c["note"] = ADS_CHART_PURCH_REV
            elif "roas" in title:
                c["note"] = ADS_CHART_ROAS
            elif "ctr" in title:
                c["note"] = ADS_CHART_CTR
            elif "p&l" in title.replace("＆", "&") or "mer" in title:
                if "mer" in title:
                    c["note"] = chart_note_for_view("mer")
                elif "revenue vs" in title:
                    c["note"] = chart_note_for_view("cumRevCost")
                elif "stack" in title:
                    c["note"] = chart_note_for_view("dailyStack")
                else:
                    c["note"] = chart_note_for_view("cumPnl")

    chart_blocks = _chart_flowables(chart_list, styles)
    if chart_blocks:
        story.append(Paragraph("Charts", styles["h2"]))
        story.append(Paragraph(_esc(ADS_OVERLAY), styles["note"]))
        story.extend(chart_blocks)

    for w in report.get("warnings") or []:
        story.append(Paragraph(_esc(w), styles["note"]))

    story.append(
        Paragraph(
            "Meta Insights joined to Shopify P&L for the same window. "
            "SKU mode omits KIE/Shopify amortisation; store mode includes them when from Refresh. "
            "Estimates — confirm in Ads Manager / Shopify.",
            styles["footer"],
        )
    )

    doc.build(story)
    return buf.getvalue()
