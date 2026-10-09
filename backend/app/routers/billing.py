"""Subscription billing for CostLeak AI itself.

Works in two modes:
  * razorpay  — when RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET are set. Creates a real
    order via the Razorpay REST API and verifies the signature on return.
  * simulated — when no keys are configured. Identical flow and database records,
    but the payment is marked paid immediately so the product is fully usable.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .. import db
from ..core import config
from ..core.deps import company_user, subscription_state, usage_snapshot

router = APIRouter(prefix="/api/billing", tags=["billing"])

RZP_API = "https://api.razorpay.com/v1"


def _rzp_call(path: str, payload: dict) -> dict:
    auth = base64.b64encode(
        f"{config.RAZORPAY_KEY_ID}:{config.RAZORPAY_KEY_SECRET}".encode()).decode()
    req = urllib.request.Request(
        f"{RZP_API}{path}", data=json.dumps(payload).encode(),
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:400]
        raise HTTPException(502, f"Razorpay rejected the request: {detail}")
    except Exception as e:
        raise HTTPException(502, f"Could not reach Razorpay: {e}")


def _price(plan: dict, cycle: str) -> int:
    return int(plan["price_yearly"] if cycle == "yearly" else plan["price_monthly"])


@router.get("/plans")
def plans(user: dict = Depends(company_user)):
    state = subscription_state(user["company_id"])
    return {
        "plans": config.PLANS,
        "current": {"plan_code": state.get("plan_code"), "status": state.get("status"),
                    "days_left": state.get("days_left"),
                    "billing_cycle": state.get("billing_cycle"),
                    "current_period_end": state.get("current_period_end")},
        "usage": usage_snapshot(user["company_id"]),
        "limits": state["plan"]["limits"],
        "provider": "razorpay" if config.RAZORPAY_ENABLED else "simulated",
        "razorpay_key_id": config.RAZORPAY_KEY_ID if config.RAZORPAY_ENABLED else None,
        "trial_days": config.TRIAL_DAYS,
    }


class CheckoutIn(BaseModel):
    plan_code: str
    billing_cycle: str = "monthly"


@router.post("/checkout")
def checkout(body: CheckoutIn, user: dict = Depends(company_user)):
    if user["role"] != "owner":
        raise HTTPException(403, "Only the account owner can change the subscription.")
    plan = config.PLAN_MAP.get(body.plan_code)
    if not plan:
        raise HTTPException(400, "Unknown plan.")
    if body.billing_cycle not in ("monthly", "yearly"):
        raise HTTPException(400, "Billing cycle must be monthly or yearly.")

    amount = _price(plan, body.billing_cycle)
    company = db.q1("SELECT * FROM companies WHERE id=?", (user["company_id"],))
    pid = db.new_id("pay_")
    receipt = f"CL-{pid[-8:].upper()}"

    if config.RAZORPAY_ENABLED:
        order = _rzp_call("/orders", {
            "amount": amount * 100, "currency": "INR", "receipt": receipt,
            "notes": {"company_id": company["id"], "plan": plan["code"],
                      "cycle": body.billing_cycle},
        })
        db.insert("payments", {
            "id": pid, "company_id": company["id"], "amount": amount, "status": "created",
            "provider": "razorpay", "provider_order_id": order["id"],
            "plan_code": plan["code"], "billing_cycle": body.billing_cycle,
            "receipt_no": receipt, "created_at": db.now_iso(),
        })
        return {"mode": "razorpay", "order_id": order["id"], "amount": amount,
                "currency": "INR", "key_id": config.RAZORPAY_KEY_ID, "payment_id": pid,
                "name": config.APP_NAME, "description": f"{plan['name']} ({body.billing_cycle})",
                "prefill": {"name": user["name"], "email": user["email"],
                            "contact": company.get("phone") or ""}}

    # ---- simulated mode -------------------------------------------------
    db.insert("payments", {
        "id": pid, "company_id": company["id"], "amount": amount, "status": "created",
        "provider": "simulated", "provider_order_id": f"order_sim_{pid[-8:]}",
        "plan_code": plan["code"], "billing_cycle": body.billing_cycle,
        "receipt_no": receipt, "created_at": db.now_iso(),
    })
    return {"mode": "simulated", "payment_id": pid, "amount": amount,
            "order_id": f"order_sim_{pid[-8:]}",
            "description": f"{plan['name']} ({body.billing_cycle})",
            "note": "Razorpay keys are not configured, so this checkout is simulated. "
                    "Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to take real payments."}


class ConfirmIn(BaseModel):
    payment_id: str
    razorpay_order_id: str | None = None
    razorpay_payment_id: str | None = None
    razorpay_signature: str | None = None


def _activate(company_id: str, plan_code: str, cycle: str, amount: float,
              provider: str, ref: str | None) -> dict:
    days = 365 if cycle == "yearly" else 30
    end = (datetime.now() + timedelta(days=days)).isoformat(timespec="seconds")
    db.ex("UPDATE subscriptions SET status='cancelled', cancelled_at=? WHERE company_id=?"
          " AND status IN ('trialing','active','past_due')", (db.now_iso(), company_id))
    sid = db.new_id("sub_")
    db.insert("subscriptions", {
        "id": sid, "company_id": company_id, "plan_code": plan_code, "billing_cycle": cycle,
        "status": "active", "amount": amount, "provider": provider, "provider_ref": ref,
        "started_at": db.now_iso(), "current_period_end": end, "created_at": db.now_iso(),
    })
    return db.q1("SELECT * FROM subscriptions WHERE id=?", (sid,))


@router.post("/confirm")
def confirm(body: ConfirmIn, user: dict = Depends(company_user)):
    pay = db.q1("SELECT * FROM payments WHERE id=? AND company_id=?",
                (body.payment_id, user["company_id"]))
    if not pay:
        raise HTTPException(404, "Payment record not found.")
    if pay["status"] == "paid":
        return {"ok": True, "already": True}

    if pay["provider"] == "razorpay":
        if not (body.razorpay_order_id and body.razorpay_payment_id and body.razorpay_signature):
            raise HTTPException(400, "Missing Razorpay confirmation fields.")
        expected = hmac.new(
            config.RAZORPAY_KEY_SECRET.encode(),
            f"{body.razorpay_order_id}|{body.razorpay_payment_id}".encode(),
            hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, body.razorpay_signature):
            db.update("payments", pay["id"], {"status": "failed"})
            raise HTTPException(400, "Payment signature verification failed.")

    db.update("payments", pay["id"], {
        "status": "paid", "paid_at": db.now_iso(),
        "provider_payment_id": body.razorpay_payment_id or f"pay_sim_{pay['id'][-8:]}"})
    sub = _activate(user["company_id"], pay["plan_code"], pay["billing_cycle"],
                    pay["amount"], pay["provider"], body.razorpay_payment_id)
    db.track("subscription_activated", user["company_id"], user["id"],
             {"plan": pay["plan_code"], "amount": pay["amount"], "cycle": pay["billing_cycle"]})
    return {"ok": True, "subscription": sub, "plan": config.PLAN_MAP[pay["plan_code"]]}


@router.post("/webhook")
async def webhook(request: Request):
    """Razorpay server-to-server events (payment.captured)."""
    raw = await request.body()
    sig = request.headers.get("x-razorpay-signature", "")
    if config.RAZORPAY_WEBHOOK_SECRET:
        expected = hmac.new(config.RAZORPAY_WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise HTTPException(400, "Invalid webhook signature.")
    event = json.loads(raw or b"{}")
    if event.get("event") == "payment.captured":
        entity = event["payload"]["payment"]["entity"]
        pay = db.q1("SELECT * FROM payments WHERE provider_order_id=?", (entity.get("order_id"),))
        if pay and pay["status"] != "paid":
            db.update("payments", pay["id"], {"status": "paid", "paid_at": db.now_iso(),
                                              "provider_payment_id": entity.get("id")})
            _activate(pay["company_id"], pay["plan_code"], pay["billing_cycle"],
                      pay["amount"], "razorpay", entity.get("id"))
    return {"ok": True}


@router.post("/cancel")
def cancel(user: dict = Depends(company_user)):
    if user["role"] != "owner":
        raise HTTPException(403, "Only the account owner can cancel the subscription.")
    db.ex("UPDATE subscriptions SET status='cancelled', cancelled_at=? WHERE company_id=?"
          " AND status IN ('trialing','active','past_due')", (db.now_iso(), user["company_id"]))
    db.track("subscription_cancelled", user["company_id"], user["id"])
    return {"ok": True}


@router.get("/payments")
def payment_history(user: dict = Depends(company_user)):
    rows = db.q("SELECT * FROM payments WHERE company_id=? ORDER BY created_at DESC",
                (user["company_id"],))
    return {"payments": rows,
            "total_paid": round(sum(p["amount"] for p in rows if p["status"] == "paid"), 2)}
