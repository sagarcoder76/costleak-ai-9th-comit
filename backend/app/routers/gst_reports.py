"""GST reporting: monthly summary, GSTR-1 style export, HSN summary, profit & margin."""
from __future__ import annotations

import csv
import io
from datetime import date

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from .. import db
from ..core.deps import company_user
from ..services.gst import gst_summary, r2, state_name

router = APIRouter(prefix="/api/gst", tags=["gst"])


def _month(month: str | None) -> str:
    return month or date.today().strftime("%Y-%m")


@router.get("/summary")
def summary(user: dict = Depends(company_user), month: str | None = None):
    m = _month(month)
    cid = user["company_id"]
    sales = db.q("SELECT * FROM invoices WHERE company_id=? AND doc_type='sale'"
                 " AND status!='cancelled' AND substr(invoice_date,1,7)=?", (cid, m))
    purchases = db.q("SELECT * FROM invoices WHERE company_id=? AND doc_type='purchase'"
                     " AND status!='cancelled' AND substr(invoice_date,1,7)=?", (cid, m))
    core = gst_summary(sales, purchases)

    b2b = [i for i in sales if i.get("customer_gstin")]
    b2c = [i for i in sales if not i.get("customer_gstin")]
    rate_rows = db.q(
        "SELECT i.gst_rate AS gst_rate, SUM(i.taxable) AS taxable, SUM(i.cgst) AS cgst,"
        " SUM(i.sgst) AS sgst, SUM(i.igst) AS igst FROM invoice_items i"
        " JOIN invoices v ON v.id=i.invoice_id"
        " WHERE i.company_id=? AND v.doc_type='sale' AND v.status!='cancelled'"
        " AND substr(v.invoice_date,1,7)=? GROUP BY i.gst_rate ORDER BY i.gst_rate", (cid, m))
    hsn_rows = db.q(
        "SELECT COALESCE(NULLIF(i.hsn,''),'—') AS hsn, i.unit AS uqc, SUM(i.qty) AS qty,"
        " SUM(i.taxable) AS taxable, SUM(i.cgst+i.sgst+i.igst) AS tax FROM invoice_items i"
        " JOIN invoices v ON v.id=i.invoice_id"
        " WHERE i.company_id=? AND v.doc_type='sale' AND v.status!='cancelled'"
        " AND substr(v.invoice_date,1,7)=? GROUP BY i.hsn ORDER BY taxable DESC", (cid, m))
    state_rows = db.q(
        "SELECT place_of_supply, COUNT(*) AS n, SUM(total) AS total FROM invoices"
        " WHERE company_id=? AND doc_type='sale' AND status!='cancelled'"
        " AND substr(invoice_date,1,7)=? GROUP BY place_of_supply ORDER BY total DESC", (cid, m))
    for s in state_rows:
        s["state"] = state_name(s["place_of_supply"])

    months = db.q("SELECT substr(invoice_date,1,7) AS m, doc_type,"
                  " SUM(cgst+sgst+igst) AS tax, SUM(total) AS total FROM invoices"
                  " WHERE company_id=? AND status!='cancelled'"
                  " GROUP BY m, doc_type ORDER BY m DESC LIMIT 24", (cid,))

    due_date = f"11th of the following month (GSTR-1) · 20th (GSTR-3B)"

    # ---- B2C consolidated by place of supply + rate (GSTR-1 table 7)
    b2c_rows = db.q(
        "SELECT v.place_of_supply AS pos, i.gst_rate AS gst_rate, SUM(i.taxable) AS taxable,"
        " SUM(i.cgst+i.sgst+i.igst) AS tax FROM invoice_items i"
        " JOIN invoices v ON v.id=i.invoice_id"
        " WHERE i.company_id=? AND v.doc_type='sale' AND v.status!='cancelled'"
        " AND (v.customer_gstin IS NULL OR v.customer_gstin='')"
        " AND substr(v.invoice_date,1,7)=? GROUP BY v.place_of_supply, i.gst_rate"
        " ORDER BY taxable DESC", (cid, m))
    for b in b2c_rows:
        b["pos_name"] = state_name(b["pos"])
        b["taxable"], b["tax"] = r2(b["taxable"]), r2(b["tax"])

    hsn_detail = db.q(
        "SELECT COALESCE(NULLIF(i.hsn,''),'') AS hsn, MIN(i.name) AS description,"
        " i.unit AS unit, i.gst_rate AS gst_rate, SUM(i.qty) AS qty, SUM(i.taxable) AS taxable,"
        " SUM(i.cgst+i.sgst+i.igst) AS tax FROM invoice_items i"
        " JOIN invoices v ON v.id=i.invoice_id"
        " WHERE i.company_id=? AND v.doc_type='sale' AND v.status!='cancelled'"
        " AND substr(v.invoice_date,1,7)=? GROUP BY i.hsn, i.gst_rate, i.unit"
        " ORDER BY taxable DESC", (cid, m))
    for h in hsn_detail:
        h["taxable"], h["tax"], h["qty"] = r2(h["taxable"]), r2(h["tax"]), r2(h["qty"])

    net_trend: dict[str, float] = {}
    for row in months:
        sign = 1 if row["doc_type"] == "sale" else -1
        net_trend[row["m"]] = r2(net_trend.get(row["m"], 0) + sign * (row["tax"] or 0))
    trend_list = [{"month": k, "net": max(v, 0)} for k, v in sorted(net_trend.items())][-6:]

    taxable_sales = core["taxable_sales"]
    return {
        "month": m,
        **core,
        "sales_count": len(sales),
        "purchase_count": len(purchases),
        "effective_rate": r2(core["output_tax"]["total"] / taxable_sales * 100) if taxable_sales else 0,
        "b2b_invoices": b2b,
        "b2c_rows": b2c_rows,
        "b2c_count": len(b2c),
        "hsn_detail": hsn_detail,
        "net_trend": trend_list,
        "b2b": {"count": len(b2b), "taxable": r2(sum(i["taxable_total"] for i in b2b)),
                "tax": r2(sum(i["cgst"] + i["sgst"] + i["igst"] for i in b2b))},
        "b2c": {"count": len(b2c), "taxable": r2(sum(i["taxable_total"] for i in b2c)),
                "tax": r2(sum(i["cgst"] + i["sgst"] + i["igst"] for i in b2c))},
        "rate_wise": [{**r, "taxable": r2(r["taxable"]), "cgst": r2(r["cgst"]),
                       "sgst": r2(r["sgst"]), "igst": r2(r["igst"])} for r in rate_rows],
        "hsn_summary": [{**h, "taxable": r2(h["taxable"]), "tax": r2(h["tax"])} for h in hsn_rows],
        "state_wise": state_rows,
        "trend": months,
        "filing_note": due_date,
        "disclaimer": "Computed from invoices recorded in CostLeak AI. Reconcile with your books "
                      "and GST portal before filing. This is not a substitute for professional advice.",
    }


@router.get("/profit")
def profit(user: dict = Depends(company_user), month: str | None = None):
    m = _month(month)
    cid = user["company_id"]
    inv = db.q("SELECT * FROM invoices WHERE company_id=? AND doc_type='sale'"
               " AND status!='cancelled' AND substr(invoice_date,1,7)=?", (cid, m))
    revenue = r2(sum(i["taxable_total"] for i in inv))
    cost = r2(sum(i["cost_total"] or 0 for i in inv))
    gross = r2(revenue - cost)

    by_product = db.q(
        "SELECT i.name, COALESCE(SUM(i.qty),0) AS qty, SUM(i.taxable) AS revenue,"
        " SUM(i.cost_price*i.qty) AS cost, SUM(i.profit) AS profit FROM invoice_items i"
        " JOIN invoices v ON v.id=i.invoice_id"
        " WHERE i.company_id=? AND v.doc_type='sale' AND v.status!='cancelled'"
        " AND substr(v.invoice_date,1,7)=? GROUP BY i.name ORDER BY profit ASC", (cid, m))
    for p in by_product:
        p["revenue"], p["cost"], p["profit"] = r2(p["revenue"]), r2(p["cost"]), r2(p["profit"])
        p["margin_pct"] = r2(p["profit"] / p["revenue"] * 100) if p["revenue"] else 0

    by_customer = db.q(
        "SELECT customer_name, COUNT(*) AS invoices, SUM(taxable_total) AS revenue,"
        " SUM(profit) AS profit FROM invoices WHERE company_id=? AND doc_type='sale'"
        " AND status!='cancelled' AND substr(invoice_date,1,7)=?"
        " GROUP BY customer_name ORDER BY profit DESC", (cid, m))
    for c in by_customer:
        c["revenue"], c["profit"] = r2(c["revenue"]), r2(c["profit"])
        c["margin_pct"] = r2(c["profit"] / c["revenue"] * 100) if c["revenue"] else 0

    alerts = []
    for p in by_product:
        if p["profit"] < 0:
            alerts.append({"level": "critical", "title": f"{p['name']} is sold below cost",
                           "detail": f"Revenue {p['revenue']:,.0f} vs cost {p['cost']:,.0f} — "
                                     f"losing Rs {abs(p['profit']):,.0f} this month.",
                           "action": "Raise the price or renegotiate the purchase cost."})
        elif p["revenue"] and p["margin_pct"] < 10:
            alerts.append({"level": "warning", "title": f"{p['name']} margin is only {p['margin_pct']:.1f}%",
                           "detail": f"Rs {p['profit']:,.0f} profit on Rs {p['revenue']:,.0f} of sales.",
                           "action": "A 5% price increase would roughly double the profit on this line."})
    unpriced = db.q("SELECT name FROM products WHERE company_id=? AND (cost_price IS NULL"
                    " OR cost_price<=0)", (cid,))
    if unpriced:
        alerts.append({"level": "info",
                       "title": f"{len(unpriced)} product(s) have no cost price recorded",
                       "detail": "Margin cannot be calculated for: " +
                                 ", ".join(u["name"] for u in unpriced[:5]) +
                                 ("…" if len(unpriced) > 5 else ""),
                       "action": "Add cost prices in the Products page to unlock margin tracking."})

    return {
        "month": m, "revenue": revenue, "cost": cost, "gross_profit": gross,
        "margin_pct": r2(gross / revenue * 100) if revenue else 0,
        "invoice_count": len(inv),
        "by_product": by_product, "by_customer": by_customer, "alerts": alerts,
    }


@router.get("/export.csv")
def export_csv(user: dict = Depends(company_user), month: str | None = None,
               kind: str = "gstr1"):
    m = _month(month)
    cid = user["company_id"]
    buf = io.StringIO()
    w = csv.writer(buf)

    if kind == "hsn":
        w.writerow(["HSN", "UQC", "Total Quantity", "Taxable Value", "Total Tax"])
        for h in summary(user, m)["hsn_summary"]:
            w.writerow([h["hsn"], h["uqc"], h["qty"], h["taxable"], h["tax"]])
        name = f"HSN_Summary_{m}.csv"
    else:
        w.writerow(["GSTIN/UIN of Recipient", "Receiver Name", "Invoice Number", "Invoice Date",
                    "Invoice Value", "Place Of Supply", "Reverse Charge", "Invoice Type",
                    "Rate", "Taxable Value", "Cess Amount"])
        rows = db.q("SELECT v.*, i.gst_rate, SUM(i.taxable) AS taxable FROM invoices v"
                    " JOIN invoice_items i ON i.invoice_id=v.id"
                    " WHERE v.company_id=? AND v.doc_type='sale' AND v.status!='cancelled'"
                    " AND substr(v.invoice_date,1,7)=? GROUP BY v.id, i.gst_rate"
                    " ORDER BY v.invoice_date", (cid, m))
        for r in rows:
            w.writerow([r.get("customer_gstin") or "URP", r["customer_name"], r["number"],
                        r["invoice_date"], r2(r["total"]),
                        f"{r['place_of_supply']}-{state_name(r['place_of_supply'])}",
                        "N", "Regular", r["gst_rate"], r2(r["taxable"]), 0])
        name = f"GSTR1_B2B_{m}.csv"

    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})
