"""Request dependencies: current user, tenant scoping and plan-limit enforcement."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import Depends, Header, HTTPException

from .. import db
from . import config
from .security import read_token


def current_user(authorization: str = Header(default=""), t: str = "") -> dict:
    """Bearer header normally; ?t=<token> for links the browser opens directly
    (PDF and CSV downloads, where headers cannot be attached)."""
    if authorization.lower().startswith("bearer "):
        raw = authorization.split(" ", 1)[1].strip()
    elif t:
        raw = t.strip()
    else:
        raise HTTPException(401, "Please sign in to continue.")
    data = read_token(raw)
    if not data:
        raise HTTPException(401, "Your session has expired. Please sign in again.")
    user = db.q1("SELECT * FROM users WHERE id=?", (data.get("uid"),))
    if not user or user["status"] != "active":
        raise HTTPException(401, "Account not found or disabled.")
    return user


def optional_user(authorization: str = Header(default=""), t: str = "") -> dict | None:
    try:
        return current_user(authorization, t)
    except HTTPException:
        return None


def superadmin(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "superadmin":
        raise HTTPException(403, "Platform admin access only.")
    return user


def company_user(user: dict = Depends(current_user)) -> dict:
    if not user.get("company_id"):
        raise HTTPException(403, "This account is not linked to a company.")
    return user


def require_role(*roles: str):
    def dep(user: dict = Depends(company_user)) -> dict:
        if user["role"] not in roles and user["role"] != "owner":
            raise HTTPException(403, f"Requires one of: {', '.join(roles)}.")
        return user
    return dep


# ------------------------------------------------------------ billing ----
def get_subscription(company_id: str) -> dict | None:
    return db.q1(
        "SELECT * FROM subscriptions WHERE company_id=? AND status IN ('trialing','active','past_due')"
        " ORDER BY created_at DESC LIMIT 1", (company_id,))


def subscription_state(company_id: str) -> dict:
    sub = get_subscription(company_id)
    if not sub:
        return {"plan_code": "starter", "status": "none", "plan": config.PLAN_MAP["starter"],
                "days_left": 0, "active": False}
    plan = config.PLAN_MAP.get(sub["plan_code"], config.PLAN_MAP["starter"])
    days_left = 0
    if sub.get("current_period_end"):
        try:
            end = datetime.fromisoformat(sub["current_period_end"])
            days_left = max((end - datetime.now(end.tzinfo)).days, 0)
        except Exception:
            days_left = 0
    return {**sub, "plan": plan, "days_left": days_left,
            "active": sub["status"] in ("trialing", "active")}


def usage_snapshot(company_id: str) -> dict:
    month = db.month_key()
    return {
        "users": db.count("users", "company_id=? AND status='active'", (company_id,)),
        "products": db.count("products", "company_id=?", (company_id,)),
        "customers": db.count("customers", "company_id=?", (company_id,)),
        "invoices_total": db.count("invoices", "company_id=?", (company_id,)),
        "invoices_per_month": db.count(
            "invoices", "company_id=? AND substr(created_at,1,7)=?", (company_id, month)),
        "analyses_per_month": db.count(
            "analyses", "company_id=? AND substr(created_at,1,7)=?", (company_id, month)),
    }


def enforce_limit(company_id: str, key: str, adding: int = 1) -> None:
    """Raise 402 when the company's plan limit for `key` would be exceeded."""
    state = subscription_state(company_id)
    limit = state["plan"]["limits"].get(key)
    if limit is None:
        return
    used = usage_snapshot(company_id).get(key, 0)
    if used + adding > limit:
        raise HTTPException(402, {
            "code": "plan_limit",
            "message": f"Your {state['plan']['name']} plan allows {limit} {key.replace('_', ' ')}. "
                       f"You have used {used}. Upgrade to continue.",
            "limit": limit, "used": used, "key": key, "plan": state["plan"]["code"],
        })


def start_trial(company_id: str, plan_code: str = "growth") -> dict:
    end = (datetime.now() + timedelta(days=config.TRIAL_DAYS)).isoformat(timespec="seconds")
    sid = db.new_id("sub_")
    db.insert("subscriptions", {
        "id": sid, "company_id": company_id, "plan_code": plan_code, "billing_cycle": "monthly",
        "status": "trialing", "amount": 0, "provider": "simulated",
        "started_at": db.now_iso(), "current_period_end": end, "created_at": db.now_iso(),
    })
    return db.q1("SELECT * FROM subscriptions WHERE id=?", (sid,))
