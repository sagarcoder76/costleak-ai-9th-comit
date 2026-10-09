"""Platform admin: who signed up, who is paying, who is actually using the product."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import db
from ..core import config
from ..core.deps import superadmin
from ..services.gst import r2

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/overview")
def overview(_: dict = Depends(superadmin)):
    companies = db.q("SELECT * FROM companies ORDER BY created_at DESC")
    subs = db.q("SELECT * FROM subscriptions WHERE status IN ('trialing','active')")
    paid = [s for s in subs if s["status"] == "active"]
    payments = db.q("SELECT * FROM payments WHERE status='paid'")

    mrr = 0.0
    for s in paid:
        plan = config.PLAN_MAP.get(s["plan_code"])
        if not plan:
            continue
        mrr += plan["price_yearly"] / 12 if s["billing_cycle"] == "yearly" else plan["price_monthly"]

    now = datetime.now()
    d30 = (now - timedelta(days=30)).isoformat()
    d7 = (now - timedelta(days=7)).isoformat()

    plan_mix = {}
    for s in subs:
        key = f"{s['plan_code']}:{s['status']}"
        plan_mix[key] = plan_mix.get(key, 0) + 1

    signups = db.q("SELECT substr(created_at,1,10) AS day, COUNT(*) AS n FROM companies"
                   " GROUP BY day ORDER BY day DESC LIMIT 30")
    revenue_trend = db.q("SELECT substr(paid_at,1,7) AS month, SUM(amount) AS amount,"
                         " COUNT(*) AS n FROM payments WHERE status='paid'"
                         " GROUP BY month ORDER BY month DESC LIMIT 12")

    cancelled = db.count("subscriptions", "status='cancelled'")
    churn = r2(cancelled / max(len(companies), 1) * 100)

    return {
        "kpis": {
            "companies": len(companies),
            "active_subscriptions": len(paid),
            "trials": len([s for s in subs if s["status"] == "trialing"]),
            "mrr": r2(mrr),
            "arr": r2(mrr * 12),
            "lifetime_revenue": r2(sum(p["amount"] for p in payments)),
            "users": db.count("users", "role!='superadmin'"),
            "signups_30d": db.count("companies", "created_at>=?", (d30,)),
            "active_7d": len({e["company_id"] for e in
                              db.q("SELECT DISTINCT company_id FROM usage_events WHERE created_at>=?", (d7,))
                              if e["company_id"]}),
            "invoices_total": db.count("invoices"),
            "invoice_value": r2((db.q1("SELECT COALESCE(SUM(total),0) t FROM invoices"
                                       " WHERE status!='cancelled'") or {"t": 0})["t"]),
            "analyses_total": db.count("analyses"),
            "churn_pct": churn,
            "arpu": r2(mrr / len(paid)) if paid else 0,
        },
        "plan_mix": plan_mix,
        "plans": config.PLANS,
        "signups_trend": list(reversed(signups)),
        "revenue_trend": list(reversed(revenue_trend)),
        "provider": "razorpay" if config.RAZORPAY_ENABLED else "simulated",
    }


@router.get("/companies")
def companies(_: dict = Depends(superadmin), search: str = "", limit: int = 200):
    sql = "SELECT * FROM companies"
    params: list = []
    if search:
        sql += " WHERE lower(name) LIKE ?"
        params.append(f"%{search.lower()}%")
    rows = db.q(sql + " ORDER BY created_at DESC LIMIT ?", params + [limit])
    out = []
    for c in rows:
        sub = db.q1("SELECT * FROM subscriptions WHERE company_id=? AND status IN"
                    " ('trialing','active','past_due') ORDER BY created_at DESC LIMIT 1", (c["id"],))
        plan = config.PLAN_MAP.get((sub or {}).get("plan_code", ""), {})
        last = db.q1("SELECT MAX(created_at) AS t FROM usage_events WHERE company_id=?", (c["id"],))
        rev = db.q1("SELECT COALESCE(SUM(amount),0) AS t FROM payments"
                    " WHERE company_id=? AND status='paid'", (c["id"],))
        out.append({
            **c,
            "plan": plan.get("name", "—"),
            "plan_code": (sub or {}).get("plan_code"),
            "sub_status": (sub or {}).get("status", "none"),
            "period_end": (sub or {}).get("current_period_end"),
            "users": db.count("users", "company_id=? AND status='active'", (c["id"],)),
            "invoices": db.count("invoices", "company_id=?", (c["id"],)),
            "products": db.count("products", "company_id=?", (c["id"],)),
            "analyses": db.count("analyses", "company_id=?", (c["id"],)),
            "events": db.count("usage_events", "company_id=?", (c["id"],)),
            "last_active": (last or {}).get("t"),
            "revenue": r2((rev or {}).get("t", 0)),
        })
    return {"companies": out}


@router.get("/company/{cid}")
def company_detail(cid: str, _: dict = Depends(superadmin)):
    company = db.q1("SELECT * FROM companies WHERE id=?", (cid,))
    if not company:
        raise HTTPException(404, "Company not found.")
    return {
        "company": company,
        "users": db.q("SELECT id,name,email,role,status,last_login,created_at FROM users"
                      " WHERE company_id=?", (cid,)),
        "subscriptions": db.q("SELECT * FROM subscriptions WHERE company_id=?"
                              " ORDER BY created_at DESC", (cid,)),
        "payments": db.q("SELECT * FROM payments WHERE company_id=? ORDER BY created_at DESC", (cid,)),
        "recent_events": db.q("SELECT * FROM usage_events WHERE company_id=?"
                              " ORDER BY created_at DESC LIMIT 50", (cid,)),
        "feature_usage": db.q("SELECT event, COUNT(*) AS n FROM usage_events WHERE company_id=?"
                              " GROUP BY event ORDER BY n DESC", (cid,)),
    }


@router.get("/usage")
def usage(_: dict = Depends(superadmin), days: int = 30):
    since = (datetime.now() - timedelta(days=days)).isoformat()
    return {
        "by_event": db.q("SELECT event, COUNT(*) AS n FROM usage_events WHERE created_at>=?"
                         " GROUP BY event ORDER BY n DESC", (since,)),
        "by_day": db.q("SELECT substr(created_at,1,10) AS day, COUNT(*) AS n FROM usage_events"
                       " WHERE created_at>=? GROUP BY day ORDER BY day", (since,)),
        "recent": db.q("SELECT u.*, c.name AS company_name FROM usage_events u"
                       " LEFT JOIN companies c ON c.id=u.company_id"
                       " ORDER BY u.created_at DESC LIMIT 80"),
    }


class CompanyStatusIn(BaseModel):
    status: str


@router.patch("/company/{cid}")
def set_status(cid: str, body: CompanyStatusIn, _: dict = Depends(superadmin)):
    if body.status not in ("active", "suspended"):
        raise HTTPException(400, "Status must be active or suspended.")
    db.update("companies", cid, {"status": body.status})
    return {"ok": True}


class GrantIn(BaseModel):
    plan_code: str
    days: int = 30


@router.post("/company/{cid}/grant")
def grant_plan(cid: str, body: GrantIn, _: dict = Depends(superadmin)):
    """Manually give a company a plan — for sales demos, goodwill or support."""
    if body.plan_code not in config.PLAN_MAP:
        raise HTTPException(400, "Unknown plan.")
    end = (datetime.now() + timedelta(days=body.days)).isoformat(timespec="seconds")
    db.ex("UPDATE subscriptions SET status='cancelled', cancelled_at=? WHERE company_id=?"
          " AND status IN ('trialing','active','past_due')", (db.now_iso(), cid))
    sid = db.new_id("sub_")
    db.insert("subscriptions", {
        "id": sid, "company_id": cid, "plan_code": body.plan_code, "billing_cycle": "monthly",
        "status": "active", "amount": 0, "provider": "manual",
        "started_at": db.now_iso(), "current_period_end": end, "created_at": db.now_iso(),
    })
    return {"ok": True, "subscription_id": sid}
