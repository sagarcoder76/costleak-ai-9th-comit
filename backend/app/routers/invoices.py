"""GST invoice generator: create, list, update status, PDF."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from .. import db
from ..core.deps import company_user, enforce_limit
from ..services import invoice_pdf
from ..services.gst import build_invoice, r2, state_name

router = APIRouter(prefix="/api/invoices", tags=["invoices"])


class ItemIn(BaseModel):
    product_id: str | None = None
    name: str
    hsn: str | None = ""
    unit: str = "NOS"
    qty: float = 1
    rate: float = 0
    discount_pct: float = 0
    gst_rate: float = 18
    cost_price: float = 0


class InvoiceIn(BaseModel):
    doc_type: str = "sale"                 # sale | purchase
    customer_id: str | None = None
    customer_name: str | None = None
    customer_gstin: str | None = None
    place_of_supply: str | None = None
    invoice_date: str | None = None
    due_days: int = 15
    items: list[ItemIn]
    extra_discount: float = 0
    notes: str | None = None
    terms: str | None = None
    status: str = "unpaid"


def _next_number(company: dict) -> str:
    counter = int(company.get("invoice_counter") or 0) + 1
    db.update("companies", company["id"], {"invoice_counter": counter})
    prefix = company.get("invoice_prefix") or "INV"
    fy = (company.get("financial_year") or "").replace("-", "")[-4:] or datetime.now().strftime("%y")
    return f"{prefix}/{fy}/{counter:04d}"


@router.get("")
def list_invoices(user: dict = Depends(company_user), doc_type: str = "", status: str = "",
                  month: str = "", search: str = "", limit: int = 200):
    sql = "SELECT * FROM invoices WHERE company_id=?"
    params: list = [user["company_id"]]
    if doc_type:
        sql += " AND doc_type=?"; params.append(doc_type)
    if status:
        sql += " AND status=?"; params.append(status)
    if month:
        sql += " AND substr(invoice_date,1,7)=?"; params.append(month)
    if search:
        sql += " AND (lower(customer_name) LIKE ? OR lower(number) LIKE ?)"
        s = f"%{search.lower()}%"; params += [s, s]
    rows = db.q(sql + " ORDER BY invoice_date DESC, created_at DESC LIMIT ?", params + [limit])
    sales = [r for r in rows if r["doc_type"] == "sale" and r["status"] != "cancelled"]
    return {
        "invoices": rows,
        "summary": {
            "count": len(rows),
            "total_sales": r2(sum(r["total"] for r in sales)),
            "outstanding": r2(sum(r["total"] - (r["amount_paid"] or 0)
                                  for r in sales if r["status"] in ("unpaid", "partial"))),
            "tax_collected": r2(sum(r["cgst"] + r["sgst"] + r["igst"] for r in sales)),
            "profit": r2(sum(r["profit"] or 0 for r in sales)),
        },
    }


@router.get("/{iid}")
def get_invoice(iid: str, user: dict = Depends(company_user)):
    inv = db.q1("SELECT * FROM invoices WHERE id=? AND company_id=?", (iid, user["company_id"]))
    if not inv:
        raise HTTPException(404, "Invoice not found.")
    items = db.q("SELECT * FROM invoice_items WHERE invoice_id=? ORDER BY sort_order", (iid,))
    company = db.q1("SELECT * FROM companies WHERE id=?", (user["company_id"],))
    recomputed = build_invoice(
        [{"name": i["name"], "qty": i["qty"], "rate": i["rate"], "gst_rate": i["gst_rate"],
          "discount_pct": i["discount_pct"], "hsn": i["hsn"] or "", "unit": i["unit"] or "NOS",
          "cost_price": i["cost_price"]} for i in items],
        company["state_code"], inv["place_of_supply"])
    return {"invoice": inv, "items": items, "company": company,
            "tax_breakup": recomputed["tax_breakup"], "hsn_summary": recomputed["hsn_summary"],
            "amount_in_words": recomputed["amount_in_words"],
            "place_of_supply_name": state_name(inv["place_of_supply"])}


@router.post("")
def create_invoice(body: InvoiceIn, user: dict = Depends(company_user)):
    if not body.items:
        raise HTTPException(400, "Add at least one line item to the invoice.")
    enforce_limit(user["company_id"], "invoices_per_month")
    company = db.q1("SELECT * FROM companies WHERE id=?", (user["company_id"],))

    customer = None
    if body.customer_id:
        customer = db.q1("SELECT * FROM customers WHERE id=? AND company_id=?",
                         (body.customer_id, user["company_id"]))
        if not customer:
            raise HTTPException(404, "Customer not found.")
    cust_name = (customer or {}).get("name") or body.customer_name
    if not cust_name:
        raise HTTPException(400, "Select a customer or enter a name.")
    pos = body.place_of_supply or (customer or {}).get("state_code") or company["state_code"]

    # Fill missing cost prices from the product master so margin is always real.
    lines = []
    for it in body.items:
        d = it.model_dump()
        if d.get("product_id") and not d.get("cost_price"):
            p = db.q1("SELECT cost_price, hsn, gst_rate FROM products WHERE id=? AND company_id=?",
                      (d["product_id"], user["company_id"]))
            if p:
                d["cost_price"] = p["cost_price"]
                d["hsn"] = d.get("hsn") or p["hsn"]
        lines.append(d)

    calc = build_invoice(lines, company["state_code"], pos, body.extra_discount)
    inv_date = body.invoice_date or date.today().isoformat()
    due = (datetime.fromisoformat(inv_date) + timedelta(days=body.due_days)).date().isoformat()
    iid = db.new_id("inv_")
    number = _next_number(company)

    db.insert("invoices", {
        "id": iid, "company_id": user["company_id"], "number": number, "doc_type": body.doc_type,
        "invoice_date": inv_date, "due_date": due,
        "customer_id": body.customer_id, "customer_name": cust_name,
        "customer_gstin": (customer or {}).get("gstin") or body.customer_gstin,
        "place_of_supply": pos, "supply_type": calc["supply_type"],
        "subtotal": calc["subtotal"], "discount_total": calc["discount_total"],
        "taxable_total": calc["taxable_total"], "cgst": calc["cgst"], "sgst": calc["sgst"],
        "igst": calc["igst"], "round_off": calc["round_off"], "total": calc["total"],
        "cost_total": calc["cost_total"], "profit": calc["profit"], "margin_pct": calc["margin_pct"],
        "status": body.status, "notes": body.notes, "terms": body.terms,
        "created_by": user["id"], "created_at": db.now_iso(), "updated_at": db.now_iso(),
    })
    for i, item in enumerate(calc["items"]):
        db.insert("invoice_items", {
            "id": db.new_id("itm_"), "invoice_id": iid, "company_id": user["company_id"],
            "product_id": lines[i].get("product_id"), "name": item["name"], "hsn": item["hsn"],
            "unit": item["unit"], "qty": item["qty"], "rate": item["rate"],
            "discount_pct": item["discount_pct"], "gst_rate": item["gst_rate"],
            "taxable": item["taxable"], "cgst": item["cgst"], "sgst": item["sgst"],
            "igst": item["igst"], "total": item["total"],
            "cost_price": item["cost_price"], "profit": item["profit"], "sort_order": i,
        })
    db.track("invoice_created", user["company_id"], user["id"],
             {"total": calc["total"], "type": body.doc_type})
    return get_invoice(iid, user)


class StatusIn(BaseModel):
    status: str | None = None
    amount_paid: float | None = None


@router.patch("/{iid}")
def update_status(iid: str, body: StatusIn, user: dict = Depends(company_user)):
    inv = db.q1("SELECT * FROM invoices WHERE id=? AND company_id=?", (iid, user["company_id"]))
    if not inv:
        raise HTTPException(404, "Invoice not found.")
    data = {}
    if body.status:
        if body.status not in ("draft", "unpaid", "partial", "paid", "cancelled"):
            raise HTTPException(400, "Invalid status.")
        data["status"] = body.status
        if body.status == "paid":
            data["amount_paid"] = inv["total"]
    if body.amount_paid is not None:
        data["amount_paid"] = r2(body.amount_paid)
        if data["amount_paid"] >= inv["total"]:
            data["status"] = "paid"
        elif data["amount_paid"] > 0:
            data["status"] = "partial"
    data["updated_at"] = db.now_iso()
    db.update("invoices", iid, data, user["company_id"])
    return get_invoice(iid, user)


@router.delete("/{iid}")
def cancel_invoice(iid: str, user: dict = Depends(company_user)):
    db.update("invoices", iid, {"status": "cancelled", "updated_at": db.now_iso()},
              user["company_id"])
    return {"ok": True}


@router.post("/preview")
def preview(body: InvoiceIn, user: dict = Depends(company_user)):
    """Live totals while the user types — no database writes."""
    company = db.q1("SELECT * FROM companies WHERE id=?", (user["company_id"],))
    pos = body.place_of_supply or company["state_code"]
    return build_invoice([i.model_dump() for i in body.items], company["state_code"],
                         pos, body.extra_discount)


@router.get("/{iid}/pdf")
def invoice_pdf_route(iid: str, user: dict = Depends(company_user)):
    data = get_invoice(iid, user)
    pdf = invoice_pdf.build(data)
    safe = data["invoice"]["number"].replace("/", "-")
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="Invoice_{safe}.pdf"'})
