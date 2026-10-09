"""Company profile, product master (with cost + GST) and customer master."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import db
from ..core.config import GST_RATES, STATE_CODES
from ..core.deps import company_user, subscription_state, enforce_limit
from ..services.gst import r2, state_name, validate_gstin

router = APIRouter(prefix="/api", tags=["masters"])


# ----------------------------------------------------------- company -----
class CompanyIn(BaseModel):
    name: str | None = None
    legal_name: str | None = None
    gstin: str | None = None
    pan: str | None = None
    state_code: str | None = None
    address: str | None = None
    city: str | None = None
    pincode: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    invoice_prefix: str | None = None
    financial_year: str | None = None


@router.get("/company")
def get_company(user: dict = Depends(company_user)):
    c = db.q1("SELECT * FROM companies WHERE id=?", (user["company_id"],))
    st = subscription_state(user["company_id"])
    return {**c, "state_name": state_name(c["state_code"]), "states": STATE_CODES,
            "gst_rates": GST_RATES,
            "plan_code": st.get("plan_code"), "plan_name": st["plan"]["name"],
            "subscription_status": st.get("status"),
            "invoice_seq": db.count("invoices", "company_id=? AND doc_type='sale'",
                                    (user["company_id"],))}


@router.put("/company")
def update_company(body: CompanyIn, user: dict = Depends(company_user)):
    if user["role"] not in ("owner", "admin"):
        raise HTTPException(403, "Only an owner or admin can edit company settings.")
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    if data.get("gstin"):
        check = validate_gstin(data["gstin"])
        if not check["valid"]:
            raise HTTPException(400, f"GSTIN problem: {check['message']}")
        data["gstin"] = data["gstin"].upper()
        data["state_code"] = check["state_code"]
    if data:
        db.update("companies", user["company_id"], data)
    return get_company(user)


@router.get("/gst/validate")
def gst_validate(gstin: str):
    return validate_gstin(gstin)


# ----------------------------------------------------------- products ----
class ProductIn(BaseModel):
    name: str
    sku: str | None = None
    hsn: str | None = None
    category: str | None = None
    unit: str = "NOS"
    cost_price: float = 0
    selling_price: float = 0
    gst_rate: float = 18
    cess_rate: float = 0
    opening_stock: float = 0
    is_service: bool = False
    notes: str | None = None


def _enrich_product(p: dict) -> dict:
    cost, sell = float(p.get("cost_price") or 0), float(p.get("selling_price") or 0)
    profit = r2(sell - cost)
    margin = r2(profit / sell * 100) if sell else 0.0
    markup = r2(profit / cost * 100) if cost else 0.0
    gst = float(p.get("gst_rate") or 0)
    status = "healthy"
    if sell <= 0:
        status = "unpriced"
    elif profit < 0:
        status = "loss"
    elif margin < 10:
        status = "thin"
    elif margin < 25:
        status = "low"
    return {**p, "profit": profit, "margin_pct": margin, "markup_pct": markup,
            "price_with_gst": r2(sell * (1 + gst / 100)),
            "cost_with_gst": r2(cost * (1 + gst / 100)),
            "margin_status": status,
            "breakeven_price": r2(cost / 0.9) if cost else 0.0}


@router.get("/products")
def list_products(user: dict = Depends(company_user), search: str = "", category: str = ""):
    sql = "SELECT * FROM products WHERE company_id=?"
    params: list = [user["company_id"]]
    if search:
        sql += " AND (lower(name) LIKE ? OR lower(sku) LIKE ? OR hsn LIKE ?)"
        s = f"%{search.lower()}%"
        params += [s, s, s]
    if category:
        sql += " AND category=?"
        params.append(category)
    rows = [_enrich_product(p) for p in db.q(sql + " ORDER BY name", params)]
    totals = {
        "count": len(rows),
        "loss_making": sum(1 for r in rows if r["margin_status"] == "loss"),
        "thin_margin": sum(1 for r in rows if r["margin_status"] in ("thin", "low")),
        "avg_margin": r2(sum(r["margin_pct"] for r in rows) / len(rows)) if rows else 0,
        "categories": sorted({r["category"] for r in rows if r.get("category")}),
    }
    return {"products": rows, "summary": totals}


@router.post("/products")
def create_product(body: ProductIn, user: dict = Depends(company_user)):
    enforce_limit(user["company_id"], "products")
    pid = db.new_id("prd_")
    db.insert("products", {"id": pid, "company_id": user["company_id"],
                           **body.model_dump(), "is_service": int(body.is_service),
                           "created_at": db.now_iso(), "updated_at": db.now_iso()})
    db.track("product_created", user["company_id"], user["id"])
    return _enrich_product(db.q1("SELECT * FROM products WHERE id=?", (pid,)))


@router.put("/products/{pid}")
def update_product(pid: str, body: ProductIn, user: dict = Depends(company_user)):
    if not db.q1("SELECT id FROM products WHERE id=? AND company_id=?", (pid, user["company_id"])):
        raise HTTPException(404, "Product not found.")
    db.update("products", pid, {**body.model_dump(), "is_service": int(body.is_service),
                                "updated_at": db.now_iso()}, user["company_id"])
    return _enrich_product(db.q1("SELECT * FROM products WHERE id=?", (pid,)))


@router.delete("/products/{pid}")
def delete_product(pid: str, user: dict = Depends(company_user)):
    db.delete("products", pid, user["company_id"])
    return {"ok": True}


@router.post("/products/bulk")
def bulk_products(items: list[ProductIn], user: dict = Depends(company_user)):
    enforce_limit(user["company_id"], "products", adding=len(items))
    created = []
    for body in items:
        pid = db.new_id("prd_")
        db.insert("products", {"id": pid, "company_id": user["company_id"], **body.model_dump(),
                               "is_service": int(body.is_service),
                               "created_at": db.now_iso(), "updated_at": db.now_iso()})
        created.append(pid)
    return {"created": len(created)}


# ---------------------------------------------------------- customers ----
class CustomerIn(BaseModel):
    name: str
    gstin: str | None = None
    state_code: str = "06"
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    pincode: str | None = None
    customer_type: str = "B2B"
    is_vendor: bool = False
    notes: str | None = None


@router.get("/customers")
def list_customers(user: dict = Depends(company_user), search: str = ""):
    sql = "SELECT * FROM customers WHERE company_id=?"
    params: list = [user["company_id"]]
    if search:
        sql += " AND (lower(name) LIKE ? OR gstin LIKE ?)"
        params += [f"%{search.lower()}%", f"%{search.upper()}%"]
    rows = db.q(sql + " ORDER BY name", params)
    for r in rows:
        r["state_name"] = state_name(r["state_code"])
        stats = db.q1("SELECT COUNT(*) n, COALESCE(SUM(total),0) t FROM invoices"
                      " WHERE company_id=? AND customer_id=? AND status!='cancelled'",
                      (user["company_id"], r["id"]))
        r["invoice_count"], r["total_billed"] = stats["n"], r2(stats["t"])
    return {"customers": rows}


@router.post("/customers")
def create_customer(body: CustomerIn, user: dict = Depends(company_user)):
    data = body.model_dump()
    if data.get("gstin"):
        check = validate_gstin(data["gstin"])
        if not check["valid"]:
            raise HTTPException(400, f"GSTIN problem: {check['message']}")
        data["gstin"] = data["gstin"].upper()
        data["state_code"] = check["state_code"]
        data["customer_type"] = "B2B"
    cid = db.new_id("cus_")
    db.insert("customers", {"id": cid, "company_id": user["company_id"], **data,
                            "is_vendor": int(body.is_vendor), "created_at": db.now_iso()})
    db.track("customer_created", user["company_id"], user["id"])
    return db.q1("SELECT * FROM customers WHERE id=?", (cid,))


@router.put("/customers/{cid}")
def update_customer(cid: str, body: CustomerIn, user: dict = Depends(company_user)):
    if not db.q1("SELECT id FROM customers WHERE id=? AND company_id=?", (cid, user["company_id"])):
        raise HTTPException(404, "Customer not found.")
    data = body.model_dump()
    if data.get("gstin"):
        check = validate_gstin(data["gstin"])
        if not check["valid"]:
            raise HTTPException(400, f"GSTIN problem: {check['message']}")
        data["state_code"] = check["state_code"]
    db.update("customers", cid, {**data, "is_vendor": int(body.is_vendor)}, user["company_id"])
    return db.q1("SELECT * FROM customers WHERE id=?", (cid,))


@router.delete("/customers/{cid}")
def delete_customer(cid: str, user: dict = Depends(company_user)):
    db.delete("customers", cid, user["company_id"])
    return {"ok": True}
