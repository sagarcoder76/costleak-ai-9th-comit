"""GST tax-invoice PDF (ReportLab)."""
from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle)

from .gst import state_name

NAVY = colors.HexColor("#0F2A4A")
TEAL = colors.HexColor("#0E9F8E")
LIGHT = colors.HexColor("#F2F5F9")
GREY = colors.HexColor("#64748B")
LINE = colors.HexColor("#D8E0EA")


def inr(n) -> str:
    n = float(n or 0)
    neg = n < 0
    whole = f"{abs(n):.2f}"
    ip, dp = whole.split(".")
    if len(ip) > 3:
        head, tail = ip[:-3], ip[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:]); head = head[:-2]
        if head:
            parts.insert(0, head)
        ip = ",".join(parts) + "," + tail
    return ("-" if neg else "") + ip + "." + dp


def build(data: dict) -> bytes:
    inv, items, company = data["invoice"], data["items"], data["company"]
    ss = getSampleStyleSheet()
    S = {
        "h": ParagraphStyle("h", parent=ss["Normal"], fontSize=8.6, leading=11.4),
        "sm": ParagraphStyle("sm", parent=ss["Normal"], fontSize=7.4, textColor=GREY, leading=9.6),
        "b": ParagraphStyle("b", parent=ss["Normal"], fontSize=9, leading=12,
                            fontName="Helvetica-Bold", textColor=NAVY),
    }
    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4, leftMargin=13 * mm, rightMargin=13 * mm,
                          topMargin=13 * mm, bottomMargin=12 * mm,
                          title=f"Invoice {inv['number']}")
    W = doc.width
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")

    def deco(canv, _d):
        canv.saveState()
        canv.setFillColor(NAVY)
        canv.rect(0, A4[1] - 6 * mm, A4[0], 6 * mm, stroke=0, fill=1)
        canv.setFillColor(GREY); canv.setFont("Helvetica", 6.4)
        canv.drawString(13 * mm, 7 * mm, "Generated with CostLeak AI — GST invoicing & cost intelligence")
        canv.drawRightString(A4[0] - 13 * mm, 7 * mm, f"Page {canv.getPageNumber()}")
        canv.restoreState()

    doc.addPageTemplates([PageTemplate(id="m", frames=[frame], onPage=deco)])
    el = []

    title = "TAX INVOICE" if inv["doc_type"] == "sale" else "PURCHASE BILL"
    head = Table([[
        Paragraph(f"<font size=14 color='#0F2A4A'><b>{company['name']}</b></font><br/>"
                  f"<font size=7.4 color='#64748B'>{company.get('address') or ''}"
                  f"{(', ' + company['city']) if company.get('city') else ''}"
                  f"{(' - ' + company['pincode']) if company.get('pincode') else ''}<br/>"
                  f"{state_name(company.get('state_code'))}"
                  f"{('<br/>GSTIN: ' + company['gstin']) if company.get('gstin') else ''}"
                  f"{('<br/>' + company['email']) if company.get('email') else ''}"
                  f"{(' · ' + company['phone']) if company.get('phone') else ''}</font>", S["h"]),
        Paragraph(f"<para align=right><font size=15 color='#0E9F8E'><b>{title}</b></font><br/>"
                  f"<font size=8><b>{inv['number']}</b></font><br/>"
                  f"<font size=7.4 color='#64748B'>Date: {inv['invoice_date']}<br/>"
                  f"Due: {inv.get('due_date') or '—'}<br/>"
                  f"Supply: {'Intra-state' if inv['supply_type']=='intra' else 'Inter-state'}</font></para>", S["h"]),
    ]], colWidths=[W * 0.58, W * 0.42])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    el += [head, Spacer(1, 2)]

    bill = Table([[
        Paragraph(f"<font size=7 color='#64748B'><b>BILL TO</b></font><br/>"
                  f"<font size=9><b>{inv['customer_name']}</b></font><br/>"
                  f"<font size=7.4 color='#64748B'>"
                  f"{('GSTIN: ' + inv['customer_gstin'] + '<br/>') if inv.get('customer_gstin') else 'Unregistered / B2C<br/>'}"
                  f"Place of supply: {data.get('place_of_supply_name')} ({inv['place_of_supply']})</font>", S["h"]),
        Paragraph(f"<para align=right><font size=7 color='#64748B'><b>AMOUNT DUE</b></font><br/>"
                  f"<font size=16 color='#0F2A4A'><b>Rs {inr(inv['total'] - (inv.get('amount_paid') or 0))}</b></font><br/>"
                  f"<font size=7.4 color='#64748B'>Status: {str(inv['status']).upper()}</font></para>", S["h"]),
    ]], colWidths=[W * 0.62, W * 0.38])
    bill.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                              ("BOX", (0, 0), (-1, -1), 0.4, LINE),
                              ("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("TOPPADDING", (0, 0), (-1, -1), 7),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                              ("LEFTPADDING", (0, 0), (-1, -1), 8),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 8)]))
    el += [bill, Spacer(1, 9)]

    intra = inv["supply_type"] == "intra"
    if intra:
        cols = ["#", "Item & description", "HSN", "Qty", "Rate", "Taxable", "CGST", "SGST", "Amount"]
        widths = [7, 0, 16, 13, 20, 22, 20, 20, 24]
    else:
        cols = ["#", "Item & description", "HSN", "Qty", "Rate", "Taxable", "IGST", "Amount"]
        widths = [7, 0, 16, 13, 20, 22, 24, 24]
    fixed = sum(widths) * mm
    widths = [(W - fixed) if w == 0 else w * mm for w in widths]

    rows = [cols]
    for i, it in enumerate(items, 1):
        base = [str(i),
                Paragraph(f"<b>{it['name']}</b>" +
                          (f"<br/><font size=6.6 color='#64748B'>Discount {it['discount_pct']}%</font>"
                           if it.get("discount_pct") else ""), S["sm"]),
                it.get("hsn") or "—",
                f"{it['qty']:g} {it.get('unit') or ''}",
                inr(it["rate"]), inr(it["taxable"])]
        if intra:
            base += [f"{inr(it['cgst'])}\n({it['gst_rate']/2:g}%)", f"{inr(it['sgst'])}\n({it['gst_rate']/2:g}%)"]
        else:
            base += [f"{inr(it['igst'])}\n({it['gst_rate']:g}%)"]
        base.append(inr(it["total"]))
        rows.append(base)

    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.4),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.3, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
    ]))
    el += [t, Spacer(1, 8)]

    tax_rows = [["Rate", "Taxable", "CGST", "SGST", "IGST"]]
    for b in data.get("tax_breakup", []):
        tax_rows.append([f"{b['gst_rate']:g}%", inr(b["taxable"]), inr(b["cgst"]),
                         inr(b["sgst"]), inr(b["igst"])])
    tax_tbl = Table(tax_rows, colWidths=[16 * mm, 24 * mm, 20 * mm, 20 * mm, 20 * mm])
    tax_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("GRID", (0, 0), (-1, -1), 0.3, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))

    money = [["Subtotal", inr(inv["subtotal"])]]
    if inv.get("discount_total"):
        money.append(["Discount", "- " + inr(inv["discount_total"])])
    money.append(["Taxable value", inr(inv["taxable_total"])])
    if intra:
        money += [["CGST", inr(inv["cgst"])], ["SGST", inr(inv["sgst"])]]
    else:
        money.append(["IGST", inr(inv["igst"])])
    if inv.get("round_off"):
        money.append(["Round off", inr(inv["round_off"])])
    money.append(["TOTAL", "Rs " + inr(inv["total"])])
    money_tbl = Table(money, colWidths=[32 * mm, 30 * mm])
    money_tbl.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8), ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, NAVY),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, -1), (-1, -1), NAVY), ("FONTSIZE", (0, -1), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))

    el.append(Table([[tax_tbl, money_tbl]], colWidths=[W - 64 * mm, 64 * mm],
                    style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                      ("LEFTPADDING", (0, 0), (-1, -1), 0)])))
    el += [Spacer(1, 7),
           Paragraph(f"<font size=7.4><b>Amount in words:</b> {data.get('amount_in_words','')}</font>", S["h"])]

    if inv.get("notes") or inv.get("terms"):
        el.append(Spacer(1, 7))
        el.append(Paragraph(
            (f"<b>Notes:</b> {inv['notes']}<br/>" if inv.get("notes") else "") +
            (f"<b>Terms:</b> {inv['terms']}" if inv.get("terms") else ""), S["sm"]))

    el += [Spacer(1, 16), Table([[
        Paragraph("<font size=6.8 color='#64748B'>This is a computer-generated invoice. "
                  "Subject to the jurisdiction of the supplier's registered state. "
                  "E&amp;OE.</font>", S["sm"]),
        Paragraph(f"<para align=center><font size=7.4 color='#64748B'>For <b>{company['name']}</b>"
                  "<br/><br/><br/>Authorised Signatory</font></para>", S["sm"]),
    ]], colWidths=[W * 0.58, W * 0.42],
        style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                          ("LEFTPADDING", (0, 0), (-1, -1), 0)]))]

    doc.build(el)
    return buf.getvalue()
