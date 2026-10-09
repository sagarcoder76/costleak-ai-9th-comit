"""One-page executive PDF report (ReportLab)."""
from __future__ import annotations

import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle)
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie

NAVY = colors.HexColor("#0F2A4A")
TEAL = colors.HexColor("#0E9F8E")
RED = colors.HexColor("#D64545")
GREEN = colors.HexColor("#1E9E62")
LIGHT = colors.HexColor("#F2F5F9")
GREY = colors.HexColor("#64748B")

PALETTE = [colors.HexColor(h) for h in
           ("#0F2A4A", "#0E9F8E", "#3B82F6", "#F59E0B", "#D64545",
            "#8B5CF6", "#14B8A6", "#64748B", "#EC4899", "#22C55E")]


def inr(n: float) -> str:
    n = round(float(n or 0))
    neg = n < 0
    s = str(abs(int(n)))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:]); head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return ("-" if neg else "") + "Rs " + s


def _styles():
    ss = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle("h1", parent=ss["Title"], fontSize=19, textColor=NAVY,
                             spaceAfter=2, alignment=0, fontName="Helvetica-Bold"),
        "sub": ParagraphStyle("sub", parent=ss["Normal"], fontSize=9, textColor=GREY),
        "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontSize=11.5, textColor=NAVY,
                             spaceBefore=8, spaceAfter=4, fontName="Helvetica-Bold"),
        "body": ParagraphStyle("body", parent=ss["Normal"], fontSize=8.4, leading=11.2),
        "small": ParagraphStyle("small", parent=ss["Normal"], fontSize=7.2, textColor=GREY, leading=9),
        "kpi": ParagraphStyle("kpi", parent=ss["Normal"], fontSize=14, alignment=TA_CENTER,
                              fontName="Helvetica-Bold", textColor=NAVY),
        "kpil": ParagraphStyle("kpil", parent=ss["Normal"], fontSize=6.8, alignment=TA_CENTER,
                               textColor=GREY),
    }


def _kpi_table(k, S, width):
    cells = [
        ("Monthly spend", inr(k["monthly_spend"]), NAVY),
        ("Est. monthly waste", inr(k["monthly_waste"]), RED),
        ("Est. annual savings", inr(k["annual_savings"]), GREEN),
        ("Findings", str(k["findings_count"]), NAVY),
        ("Critical", str(k["critical_count"]), RED),
        ("Top-5 actioned / mo", inr(k["top5_monthly"]), GREEN),
    ]
    row_v, row_l = [], []
    for label, value, col in cells:
        row_v.append(Paragraph(f'<font color="{col.hexval()}">{value}</font>', S["kpi"]))
        row_l.append(Paragraph(label.upper(), S["kpil"]))
    t = Table([row_v, row_l], colWidths=[width / 6.0] * 6, rowHeights=[20, 12])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8E0EA")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


def _bar_chart(data, width, height, title):
    d = Drawing(width, height)
    d.add(String(0, height - 9, title, fontName="Helvetica-Bold", fontSize=8,
                 fillColor=NAVY.clone()))
    items = data[:6]
    bc = VerticalBarChart()
    bc.x, bc.y = 24, 26
    bc.width, bc.height = width - 36, height - 48
    bc.data = [[max(i["value"], 0) for i in items]] or [[0]]
    bc.categoryAxis.categoryNames = [str(i["label"])[:12] for i in items]
    bc.categoryAxis.labels.angle = 20
    bc.categoryAxis.labels.dy = -6
    bc.categoryAxis.labels.fontSize = 6
    bc.valueAxis.labels.fontSize = 6
    bc.valueAxis.valueMin = 0
    bc.bars[0].fillColor = TEAL
    bc.barSpacing = 2
    d.add(bc)
    return d


def _pie_chart(data, width, height, title):
    d = Drawing(width, height)
    d.add(String(0, height - 9, title, fontName="Helvetica-Bold", fontSize=8, fillColor=NAVY.clone()))
    items = [i for i in data if i["value"] > 0][:6]
    if not items:
        return d
    p = Pie()
    p.x, p.y = 6, 8
    p.width = p.height = height - 36
    p.data = [i["value"] for i in items]
    p.labels = [f"{str(i['label'])[:10]}" for i in items]
    p.sideLabels = True
    p.simpleLabels = True
    p.slices.fontSize = 6
    p.slices.strokeColor = colors.white
    p.slices.strokeWidth = 0.6
    for idx in range(len(items)):
        p.slices[idx].fillColor = PALETTE[idx % len(PALETTE)]
    d.add(p)
    return d


def build_pdf(analysis: dict) -> bytes:
    S = _styles()
    res = analysis["result"]
    k = res["kpis"]
    findings = res["findings"]
    charts = res["charts"]

    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4, leftMargin=13 * mm, rightMargin=13 * mm,
                          topMargin=12 * mm, bottomMargin=10 * mm,
                          title=f"CostLeak AI — {analysis['company']}")
    width = doc.width
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")

    def decorate(canv, _doc):
        canv.saveState()
        canv.setFillColor(NAVY)
        canv.rect(0, A4[1] - 7 * mm, A4[0], 7 * mm, stroke=0, fill=1)
        canv.setFillColor(GREY)
        canv.setFont("Helvetica", 6.5)
        canv.drawString(13 * mm, 6 * mm,
                        "CostLeak AI — Estimated savings based on uploaded data. Figures are estimates, not audited results.")
        canv.drawRightString(A4[0] - 13 * mm, 6 * mm, f"Page {canv.getPageNumber()}")
        canv.restoreState()

    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=decorate)])

    el = []
    el.append(Paragraph("Cost Leak — Executive Savings Report", S["h1"]))
    el.append(Paragraph(
        f"<b>{analysis['company']}</b> &nbsp;|&nbsp; Analysis date: {k['analysis_date']} "
        f"&nbsp;|&nbsp; Data covered: {k['months_covered']} month(s), total uploaded spend {inr(k['total_spend_uploaded'])}",
        S["sub"]))
    el.append(Spacer(1, 7))
    el.append(_kpi_table(k, S, width))
    el.append(Spacer(1, 6))

    el.append(Paragraph(
        f"Estimated waste is <b>{k['waste_pct']}%</b> of monthly spend. Actioning the top five findings "
        f"alone recovers an estimated <b>{inr(k['top5_monthly'])}/month</b> ({inr(k['top5_annual'])}/year).",
        S["body"]))
    el.append(Spacer(1, 4))

    ch = Table([[
        _bar_chart(charts.get("spend_by_category", []), width / 2 - 6, 96, "Monthly spend by category"),
        _pie_chart(charts.get("waste_by_category", []), width / 2 - 6, 96, "Estimated waste by finding type"),
    ]], colWidths=[width / 2, width / 2])
    ch.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    el.append(ch)

    el.append(Paragraph("Top 5 savings opportunities", S["h2"]))
    rows = [["#", "Finding", "Type", "Dept", "Monthly", "Annual", "Pri."]]
    for i, f in enumerate(findings[:5], 1):
        rows.append([str(i),
                     Paragraph(f["title"], S["body"]),
                     Paragraph(f["category"], S["small"]),
                     Paragraph(str(f["department"]), S["small"]),
                     inr(f["monthly_waste"]), inr(f["annual_waste"]), f["priority"]])
    t = Table(rows, colWidths=[8 * mm, width - 8 * mm - 26 * mm - 20 * mm - 48 * mm - 14 * mm,
                               26 * mm, 20 * mm, 24 * mm, 24 * mm, 14 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.2),
        ("ALIGN", (4, 0), (6, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D8E0EA")),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    el.append(t)

    el.append(Paragraph("Recommended 30-60-90 day action plan", S["h2"]))
    plan_rows = [["When", "Action", "Owner", "Est. monthly recovery"]]
    buckets = [("0-30 days", [f for f in findings if f["priority"] in ("Critical",)]),
               ("30-60 days", [f for f in findings if f["priority"] == "High"]),
               ("60-90 days", [f for f in findings if f["priority"] in ("Medium", "Low")])]
    for when, fs in buckets:
        if not fs:
            continue
        fs = sorted(fs, key=lambda x: -x["monthly_waste"])
        bullet = "<br/>".join(f"• {x['recommended_action']}" for x in fs[:3])
        plan_rows.append([when, Paragraph(bullet, S["small"]),
                          Paragraph(", ".join(sorted({x["owner"] for x in fs[:3]})), S["small"]),
                          inr(sum(x["monthly_waste"] for x in fs))])
    pt = Table(plan_rows, colWidths=[22 * mm, width - 22 * mm - 28 * mm - 30 * mm, 28 * mm, 30 * mm],
               repeatRows=1)
    pt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.2),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (3, 1), (3, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D8E0EA")),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    el.append(pt)

    el.append(Spacer(1, 5))
    el.append(Paragraph(
        "<b>Disclaimer:</b> Savings are estimates based on uploaded data. Figures assume the recommended "
        "actions are implemented in full and that the uploaded expense, subscription, process and overtime "
        "records are accurate and complete. Validate each finding with the relevant budget owner before "
        "cancelling contracts or recovering payments.", S["small"]))

    doc.build(el)
    return buf.getvalue()
