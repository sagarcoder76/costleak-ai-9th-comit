"""Endpoints shaped for the SPA: exports, aliases and aggregated views.

The other routers expose the primitives; this module adapts them into the exact
payloads the frontend renders, so views never have to reshape data client-side.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel

from .. import db
from ..core import config
from ..core.deps import company_user, current_user, subscription_state, superadmin, usage_snapshot
from ..services.gst import state_name
from . import analysis as analysis_router
from . import auth as auth_router
from . import billing as billing_router
from . import gst_reports, masters

router = APIRouter(prefix="/api", tags=["app"])


def r2(x) -> float:
    return round(float(x or 0), 2)


def _csv(rows: list[dict], headers: list[str], filename: str) -> Response:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ====================================================== analysis ==========
@router.post("/analysis/upload")
async def analysis_upload(file: UploadFile = File(...), user: dict = Depends(company_user)):
    return await analysis_router.upload(file=file, user=user)


@router.post("/analysis/sample")
def analysis_sample(user: dict = Depends(company_user)):
    return analysis_router.demo(user=user)


@router.get("/subscriptions/analysis")
def subscription_analysis(user: dict = Depends(company_user)):
    """Seat utilisation, renewals and overlaps from the latest uploaded workbook."""
    row = db.q1("SELECT * FROM analyses WHERE company_id=? ORDER BY created_at DESC LIMIT 1",
                (user["company_id"],))
    if not row:
        raise HTTPException(404, "No analysis yet.")
    subs = json.loads(row["subs_json"] or "[]")
    today = date.today()

    def pick(row: dict, *names, default=None):
        low = {str(k).strip().lower().replace(" ", "_"): v for k, v in row.items()}
        for n in names:
            v = low.get(n)
            if v not in (None, ""):
                return v
        return default

    out = []
    for s in subs:
        paid = float(pick(s, "seats_paid", "seats", "licenses", default=0) or 0)
        used = float(pick(s, "seats_used", "active_seats", default=0) or 0)
        cost = float(pick(s, "monthly_cost", "cost", "amount", "price", default=0) or 0)
        if str(pick(s, "billing_cycle", default="monthly")).lower().startswith("year"):
            cost = cost / 12
        util = (used / paid * 100) if paid else 0.0
        wasted = (cost / paid * max(paid - used, 0)) if paid else 0.0
        renewal = pick(s, "renewal_date", "next_renewal", "renews_on")
        try:
            days = (datetime.fromisoformat(str(renewal)[:19]).date() - today).days
        except Exception:
            days = 999
        out.append({
            "tool": pick(s, "software", "tool", "name", "service", default="—"),
            "vendor": pick(s, "vendor", "supplier", default="") or "",
            "category": pick(s, "category", "department", default="") or "",
            "monthly_cost": r2(cost),
            "seats_paid": int(paid), "seats_used": int(used), "utilisation": r2(util),
            "wasted": r2(wasted), "renewal_date": str(renewal)[:10] if renewal else None,
            "days_to_renewal": days,
        })
    out.sort(key=lambda x: -x["monthly_cost"])

    # overlapping tool families, derived from the findings already computed
    result = json.loads(row["result_json"])
    overlaps = [{
        "group": f.get("title", "Overlapping tools").split(":")[0],
        "tools": [str(e.get("Software") or e.get("Tool") or e.get("Vendor") or "")
                  for e in (f.get("evidence") or [])][:6],
        "monthly_saving": r2(f.get("monthly_waste")),
    } for f in result.get("findings", []) if f.get("category") == "Duplicate Software"]

    seats_paid = sum(s["seats_paid"] for s in out)
    seats_used = sum(s["seats_used"] for s in out)
    soon = [s for s in out if (s["days_to_renewal"] or 999) <= 30]
    return {
        "subscriptions": out,
        "overlaps": overlaps,
        "summary": {
            "monthly_cost": r2(sum(s["monthly_cost"] for s in out)),
            "seats_paid": seats_paid, "seats_used": seats_used,
            "utilisation": r2(seats_used / seats_paid * 100) if seats_paid else 0,
            "wasted_seats": r2(sum(s["wasted"] for s in out)),
            "renewals_30d": len(soon),
            "renewal_value": r2(sum(s["monthly_cost"] for s in soon)),
        },
    }


# ======================================================= exports ==========
@router.get("/exports/template.xlsx")
def export_template(_: dict = Depends(current_user)):
    return analysis_router.template(sample=True)


@router.get("/exports/report.pdf")
def export_report(user: dict = Depends(company_user)):
    row = db.q1("SELECT id FROM analyses WHERE company_id=? ORDER BY created_at DESC LIMIT 1",
                (user["company_id"],))
    if not row:
        raise HTTPException(404, "Run an analysis first — there is nothing to report yet.")
    return analysis_router.pdf_report(row["id"], user)


@router.get("/exports/findings.csv")
def export_findings(user: dict = Depends(company_user)):
    row = db.q1("SELECT * FROM analyses WHERE company_id=? ORDER BY created_at DESC LIMIT 1",
                (user["company_id"],))
    if not row:
        raise HTTPException(404, "Run an analysis first.")
    findings = json.loads(row["result_json"]).get("findings", [])
    rows = [{
        "priority": f["priority"], "category": f["category"], "title": f["title"],
        "vendor": f.get("vendor", ""), "department": f.get("department", ""),
        "monthly_saving": f["monthly_waste"], "annual_saving": f["annual_waste"],
        "confidence": f.get("confidence", ""), "calculation": f.get("calculation", ""),
        "action": f.get("action", ""),
    } for f in findings]
    return _csv(rows, list(rows[0].keys()) if rows else ["priority"], "CostLeak_findings.csv")


@router.get("/exports/invoices.csv")
def export_invoices(user: dict = Depends(company_user), month: str = ""):
    sql = "SELECT * FROM invoices WHERE company_id=?"
    p: list = [user["company_id"]]
    if month:
        sql += " AND substr(invoice_date,1,7)=?"
        p.append(month)
    rows = [{
        "number": i["number"], "date": i["invoice_date"], "type": i["doc_type"],
        "customer": i["customer_name"], "gstin": i.get("customer_gstin") or "",
        "place_of_supply": i["place_of_supply"], "supply_type": i["supply_type"],
        "taxable": i["taxable_total"], "cgst": i["cgst"], "sgst": i["sgst"], "igst": i["igst"],
        "total": i["total"], "status": i["status"], "cost": i.get("cost_total") or 0,
        "profit": i.get("profit") or 0, "margin_pct": i.get("margin_pct") or 0,
    } for i in db.q(sql + " ORDER BY invoice_date DESC", p)]
    return _csv(rows, ["number", "date", "type", "customer", "gstin", "place_of_supply",
                       "supply_type", "taxable", "cgst", "sgst", "igst", "total", "status",
                       "cost", "profit", "margin_pct"], "CostLeak_invoices.csv")


@router.get("/exports/products.csv")
def export_products(user: dict = Depends(company_user)):
    data = masters.list_products(user=user)
    rows = [{
        "name": p["name"], "sku": p.get("sku") or "", "hsn": p.get("hsn") or "",
        "category": p.get("category") or "", "unit": p.get("unit") or "",
        "cost_price": p["cost_price"], "selling_price": p["selling_price"],
        "gst_rate": p["gst_rate"], "profit_per_unit": p["profit"],
        "margin_pct": p["margin_pct"], "status": p["margin_status"],
    } for p in data["products"]]
    return _csv(rows, ["name", "sku", "hsn", "category", "unit", "cost_price", "selling_price",
                       "gst_rate", "profit_per_unit", "margin_pct", "status"],
                "CostLeak_products.csv")


@router.get("/exports/gstr1.csv")
def export_gstr1(user: dict = Depends(company_user), month: str = ""):
    return gst_reports.export_csv(user=user, month=month or None)


# ================================================ company / team ==========
@router.patch("/company")
def patch_company(body: masters.CompanyIn, user: dict = Depends(company_user)):
    return masters.update_company(body, user)


@router.get("/company/users")
def team(user: dict = Depends(company_user)):
    data = auth_router.team(user=user)
    return {"users": [{**m, "last_login_at": m.get("last_login")} for m in data["members"]],
            "usage": data["usage"]}


@router.post("/company/users")
def add_user(body: auth_router.InviteIn, user: dict = Depends(company_user)):
    return auth_router.add_member(body, user)


@router.delete("/company/users/{uid}")
def remove_user(uid: str, user: dict = Depends(company_user)):
    return auth_router.remove_member(uid, user)


class MeIn(BaseModel):
    name: str | None = None
    phone: str | None = None


@router.patch("/auth/me")
def patch_me(body: MeIn, user: dict = Depends(current_user)):
    data = {k: v for k, v in body.model_dump().items() if v}
    if data:
        db.update("users", user["id"], data)
    fresh = db.q1("SELECT * FROM users WHERE id=?", (user["id"],))
    return {"user": {k: fresh[k] for k in ("id", "name", "email", "role", "company_id")}}


@router.patch("/products/{pid}")
def patch_product(pid: str, body: masters.ProductIn, user: dict = Depends(company_user)):
    return masters.update_product(pid, body, user)


@router.patch("/customers/{cid}")
def patch_customer(cid: str, body: masters.CustomerIn, user: dict = Depends(company_user)):
    return masters.update_customer(cid, body, user)


# ======================================================= billing ==========
@router.get("/billing/overview")
def billing_overview(user: dict = Depends(company_user)):
    st = subscription_state(user["company_id"])
    plan = st["plan"]
    payments = db.q("SELECT * FROM payments WHERE company_id=? ORDER BY created_at DESC",
                    (user["company_id"],))
    return {
        "mode": "razorpay" if config.RAZORPAY_ENABLED else "simulated",
        "plans": config.PLANS,
        "limits": plan["limits"],
        "usage": usage_snapshot(user["company_id"]),
        "subscription": {
            "plan_code": st.get("plan_code"), "plan_name": plan["name"],
            "status": st.get("status"), "billing_cycle": st.get("billing_cycle") or "monthly",
            "trial_days_left": st.get("days_left", 0),
            "trial_ends_at": st.get("current_period_end"),
            "next_billing_at": st.get("current_period_end"),
        },
        "payments": [{
            "id": p["id"], "created_at": p["created_at"],
            "plan_name": config.PLAN_MAP.get(p["plan_code"], {}).get("name", p["plan_code"]),
            "billing_cycle": p["billing_cycle"], "reference": p.get("provider_payment_id")
            or p.get("provider_order_id") or p.get("receipt_no"),
            "method": p.get("provider"), "amount": p["amount"], "status": p["status"],
        } for p in payments],
    }


class VerifyIn(BaseModel):
    order_id: str
    simulated: bool = False
    razorpay_order_id: str | None = None
    razorpay_payment_id: str | None = None
    razorpay_signature: str | None = None


@router.post("/billing/verify")
def billing_verify(body: VerifyIn, user: dict = Depends(company_user)):
    pay = db.q1("SELECT * FROM payments WHERE company_id=? AND provider_order_id=?"
                " ORDER BY created_at DESC LIMIT 1", (user["company_id"], body.order_id))
    if not pay:
        raise HTTPException(404, "That checkout session was not found.")
    return billing_router.confirm(billing_router.ConfirmIn(
        payment_id=pay["id"], razorpay_order_id=body.razorpay_order_id,
        razorpay_payment_id=body.razorpay_payment_id,
        razorpay_signature=body.razorpay_signature), user)


# ========================================================= admin ==========
@router.get("/admin/dashboard")
def admin_dashboard(_: dict = Depends(superadmin)):
    companies = db.q("SELECT * FROM companies ORDER BY created_at DESC")
    now = datetime.now()
    d7, d30 = (now - timedelta(days=7)).isoformat(), (now - timedelta(days=30)).isoformat()

    rows, paying, trialing, mrr = [], 0, 0, 0.0
    for c in companies:
        sub = db.q1("SELECT * FROM subscriptions WHERE company_id=? AND status IN"
                    " ('trialing','active','past_due') ORDER BY created_at DESC LIMIT 1", (c["id"],))
        plan = config.PLAN_MAP.get((sub or {}).get("plan_code") or "starter", config.PLAN_MAP["starter"])
        status = (sub or {}).get("status", "none")
        if status == "active":
            paying += 1
            mrr += plan["price_yearly"] / 12 if (sub or {}).get("billing_cycle") == "yearly" else plan["price_monthly"]
        elif status == "trialing":
            trialing += 1
        owner = db.q1("SELECT email FROM users WHERE company_id=? AND role='owner' LIMIT 1", (c["id"],))
        paid = db.q1("SELECT COALESCE(SUM(amount),0) t FROM payments WHERE company_id=?"
                     " AND status='paid'", (c["id"],))
        val = db.q1("SELECT COALESCE(SUM(total),0) t FROM invoices WHERE company_id=?"
                    " AND status!='cancelled'", (c["id"],))
        last = db.q1("SELECT MAX(created_at) t FROM usage_events WHERE company_id=?", (c["id"],))
        rows.append({
            "id": c["id"], "name": c["name"], "industry": c.get("industry"),
            "owner_email": (owner or {}).get("email"), "created_at": c["created_at"],
            "plan_name": plan["name"], "plan_code": plan["code"], "subscription_status": status,
            "trial_ends_at": (sub or {}).get("current_period_end"),
            "users": db.count("users", "company_id=? AND status='active'", (c["id"],)),
            "invoices": db.count("invoices", "company_id=?", (c["id"],)),
            "analyses": db.count("analyses", "company_id=?", (c["id"],)),
            "products": db.count("products", "company_id=?", (c["id"],)),
            "invoiced_value": r2((val or {}).get("t")),
            "paid_total": r2((paid or {}).get("t")),
            "last_event_at": (last or {}).get("t"),
            "events": db.count("usage_events", "company_id=? AND created_at>=?", (c["id"], d30)),
        })

    payments = db.q("SELECT p.*, c.name AS company_name FROM payments p"
                    " LEFT JOIN companies c ON c.id=p.company_id"
                    " ORDER BY p.created_at DESC LIMIT 200")
    paid_rows = [p for p in payments if p["status"] == "paid"]

    # ---- usage aggregation
    total_companies = max(len(companies), 1)
    feat = db.q("SELECT event AS feature, COUNT(*) AS count,"
                " COUNT(DISTINCT company_id) AS companies FROM usage_events"
                " WHERE created_at>=? GROUP BY event ORDER BY count DESC", (d30,))
    for f in feat:
        f["adoption"] = r2(f["companies"] / total_companies * 100)
    daily = db.q("SELECT substr(created_at,1,10) AS date, COUNT(DISTINCT company_id) AS companies"
                 " FROM usage_events WHERE created_at>=? GROUP BY date ORDER BY date", (d30,))
    waste = 0.0
    for a in db.q("SELECT result_json FROM analyses"):
        try:
            waste += json.loads(a["result_json"])["kpis"]["monthly_waste"]
        except Exception:
            pass

    def group(key):
        agg: dict[str, int] = {}
        for r in rows:
            agg[r[key] or "—"] = agg.get(r[key] or "—", 0) + 1
        return [{"label": k, "value": v} for k, v in sorted(agg.items(), key=lambda x: -x[1])]

    by_plan = []
    for p in config.PLANS:
        n = sum(1 for r in rows if r["plan_code"] == p["code"] and r["subscription_status"] == "active")
        by_plan.append({"name": p["name"], "companies": n, "price_monthly": p["price_monthly"],
                        "mrr": n * p["price_monthly"],
                        "share": r2(n / paying * 100) if paying else 0})

    soon = (now + timedelta(days=7)).isoformat()
    expiring = [r for r in rows if r["subscription_status"] == "trialing"
                and r["trial_ends_at"] and r["trial_ends_at"] <= soon]

    return {
        "kpis": {
            "companies": len(companies), "paying": paying, "trialing": trialing,
            "new_30d": db.count("companies", "created_at>=?", (d30,)),
            "mrr": r2(mrr), "revenue_total": r2(sum(p["amount"] for p in paid_rows)),
            "payment_count": len(paid_rows),
            "conversion": r2(paying / total_companies * 100),
            "expiring_soon": len(expiring),
            "active_7d": db.q1("SELECT COUNT(DISTINCT company_id) n FROM usage_events"
                               " WHERE created_at>=?", (d7,))["n"],
        },
        "companies": rows,
        "expiring": expiring,
        "by_plan": by_plan,
        "payments": [{
            "id": p["id"], "created_at": p["created_at"], "company_name": p.get("company_name") or "—",
            "plan_name": config.PLAN_MAP.get(p["plan_code"], {}).get("name", p["plan_code"]),
            "billing_cycle": p["billing_cycle"], "method": p.get("provider"),
            "reference": p.get("provider_payment_id") or p.get("provider_order_id"),
            "amount": p["amount"], "status": p["status"],
        } for p in payments],
        "charts": {
            "signups": [{"month": m["month"], "count": m["n"]} for m in db.q(
                "SELECT substr(created_at,1,7) AS month, COUNT(*) AS n FROM companies"
                " GROUP BY month ORDER BY month")],
            "revenue": [{"month": m["month"], "amount": r2(m["amount"])} for m in db.q(
                "SELECT substr(COALESCE(paid_at,created_at),1,7) AS month, SUM(amount) AS amount"
                " FROM payments WHERE status='paid' GROUP BY month ORDER BY month")],
            "by_plan": [{"label": p["name"], "value": p["companies"]} for p in by_plan],
            "by_status": group("subscription_status"),
            "by_industry": group("industry"),
        },
        "usage": {
            "invoices": db.count("invoices"), "analyses": db.count("analyses"),
            "products": db.count("products"),
            "findings": sum(len(json.loads(a["result_json"]).get("findings", []))
                            for a in db.q("SELECT result_json FROM analyses")),
            "waste_found": r2(waste),
            "features": feat, "daily": daily,
            "recent": db.q("SELECT u.event, u.created_at, u.meta AS detail,"
                           " c.name AS company_name FROM usage_events u"
                           " LEFT JOIN companies c ON c.id=u.company_id"
                           " ORDER BY u.created_at DESC LIMIT 40"),
        },
    }


@router.get("/admin/companies/{cid}")
def admin_company(cid: str, admin: dict = Depends(superadmin)):
    d = __import__("importlib").import_module(".admin", __package__).company_detail(cid, admin)
    c = d["company"]
    sub = (d["subscriptions"] or [{}])[0]
    plan = config.PLAN_MAP.get(sub.get("plan_code") or "starter", config.PLAN_MAP["starter"])
    waste = 0.0
    for a in db.q("SELECT result_json FROM analyses WHERE company_id=?", (cid,)):
        try:
            waste += json.loads(a["result_json"])["kpis"]["monthly_waste"]
        except Exception:
            pass
    since = (datetime.now() - timedelta(days=30)).isoformat()
    val = db.q1("SELECT COALESCE(SUM(total),0) t FROM invoices WHERE company_id=?"
                " AND status!='cancelled'", (cid,))
    return {
        "company": {**c, "plan_name": plan["name"], "subscription_status": sub.get("status", "none")},
        "users": [{**u, "last_login_at": u.get("last_login")} for u in d["users"]],
        "payments": d["payments"],
        "paid_total": r2(sum(p["amount"] for p in d["payments"] if p["status"] == "paid")),
        "waste_found": r2(waste),
        "stats": {
            "invoices": db.count("invoices", "company_id=?", (cid,)),
            "invoiced_value": r2((val or {}).get("t")),
            "products": db.count("products", "company_id=?", (cid,)),
            "customers": db.count("customers", "company_id=?", (cid,)),
            "analyses": db.count("analyses", "company_id=?", (cid,)),
            "events_30d": db.count("usage_events", "company_id=? AND created_at>=?", (cid, since)),
        },
    }
