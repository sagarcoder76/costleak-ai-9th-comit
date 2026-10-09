"""Signup, login, session and team management."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from .. import db
from ..core import config
from ..core.deps import company_user, current_user, enforce_limit, start_trial, subscription_state, usage_snapshot
from ..core.security import create_token, hash_password, password_problems, verify_password
from ..services.gst import validate_gstin

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SignupIn(BaseModel):
    company_name: str = Field(min_length=2, max_length=120)
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str
    phone: str | None = None
    gstin: str | None = None
    state_code: str = "06"
    industry: str | None = None
    team_size: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class InviteIn(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = "member"


def _session_payload(user: dict) -> dict:
    company = db.q1("SELECT * FROM companies WHERE id=?", (user["company_id"],)) if user["company_id"] else None
    state = subscription_state(user["company_id"]) if user["company_id"] else None
    out = {
        "token": create_token({"uid": user["id"], "role": user["role"],
                               "cid": user["company_id"]}),
        "user": {k: user[k] for k in ("id", "name", "email", "role", "company_id")},
        "company": company,
        "plans": config.PLANS,
    }
    if state:
        out["subscription"] = {
            "plan_code": state.get("plan_code"), "status": state.get("status"),
            "plan": state.get("plan"), "days_left": state.get("days_left"),
            "active": state.get("active"), "current_period_end": state.get("current_period_end"),
        }
        out["usage"] = usage_snapshot(user["company_id"])
    return out


@router.post("/signup")
def signup(body: SignupIn):
    email = body.email.lower().strip()
    if db.q1("SELECT id FROM users WHERE email=?", (email,)):
        raise HTTPException(409, "An account with this email already exists. Try signing in instead.")
    problems = password_problems(body.password)
    if problems:
        raise HTTPException(400, "Password needs " + ", ".join(problems) + ".")

    state_code = body.state_code
    if body.gstin:
        check = validate_gstin(body.gstin)
        if not check["valid"]:
            raise HTTPException(400, f"GSTIN problem: {check['message']}")
        state_code = check["state_code"]

    cid = db.new_id("cmp_")
    db.insert("companies", {
        "id": cid, "name": body.company_name.strip(), "legal_name": body.company_name.strip(),
        "gstin": (body.gstin or "").upper() or None, "state_code": state_code,
        "email": email, "phone": body.phone, "industry": body.industry,
        "team_size": body.team_size, "invoice_prefix": "INV",
        "created_at": db.now_iso(),
    })
    uid = db.new_id("usr_")
    db.insert("users", {
        "id": uid, "company_id": cid, "name": body.name.strip(), "email": email,
        "phone": body.phone, "password_hash": hash_password(body.password),
        "role": "owner", "created_at": db.now_iso(), "last_login": db.now_iso(),
    })
    start_trial(cid, "growth")
    db.track("signup", cid, uid, {"company": body.company_name})
    user = db.q1("SELECT * FROM users WHERE id=?", (uid,))
    return _session_payload(user)


@router.post("/login")
def login(body: LoginIn):
    email = body.email.lower().strip()
    user = db.q1("SELECT * FROM users WHERE email=?", (email,))
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Incorrect email or password.")
    if user["status"] != "active":
        raise HTTPException(403, "This account has been disabled. Contact your administrator.")
    db.update("users", user["id"], {"last_login": db.now_iso()})
    db.track("login", user["company_id"], user["id"])
    return _session_payload(user)


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return _session_payload(user)


@router.get("/team")
def team(user: dict = Depends(company_user)):
    rows = db.q("SELECT id,name,email,role,status,last_login,created_at FROM users"
                " WHERE company_id=? ORDER BY created_at", (user["company_id"],))
    return {"members": rows, "usage": usage_snapshot(user["company_id"])}


@router.post("/team")
def add_member(body: InviteIn, user: dict = Depends(company_user)):
    if user["role"] not in ("owner", "admin"):
        raise HTTPException(403, "Only an owner or admin can add team members.")
    enforce_limit(user["company_id"], "users")
    email = body.email.lower().strip()
    if db.q1("SELECT id FROM users WHERE email=?", (email,)):
        raise HTTPException(409, "That email is already registered.")
    problems = password_problems(body.password)
    if problems:
        raise HTTPException(400, "Password needs " + ", ".join(problems) + ".")
    if body.role not in ("admin", "member", "viewer"):
        raise HTTPException(400, "Role must be admin, member or viewer.")
    uid = db.new_id("usr_")
    db.insert("users", {
        "id": uid, "company_id": user["company_id"], "name": body.name.strip(), "email": email,
        "password_hash": hash_password(body.password), "role": body.role, "created_at": db.now_iso(),
    })
    db.track("team_member_added", user["company_id"], user["id"], {"role": body.role})
    return db.q1("SELECT id,name,email,role,status,created_at FROM users WHERE id=?", (uid,))


@router.delete("/team/{uid}")
def remove_member(uid: str, user: dict = Depends(company_user)):
    if user["role"] not in ("owner", "admin"):
        raise HTTPException(403, "Only an owner or admin can remove team members.")
    target = db.q1("SELECT * FROM users WHERE id=? AND company_id=?", (uid, user["company_id"]))
    if not target:
        raise HTTPException(404, "Team member not found.")
    if target["role"] == "owner":
        raise HTTPException(400, "The account owner cannot be removed.")
    db.update("users", uid, {"status": "disabled"}, user["company_id"])
    return {"ok": True}


class PasswordIn(BaseModel):
    current_password: str
    new_password: str


@router.post("/password")
def change_password(body: PasswordIn, user: dict = Depends(current_user)):
    if not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(400, "Your current password is incorrect.")
    problems = password_problems(body.new_password)
    if problems:
        raise HTTPException(400, "New password needs " + ", ".join(problems) + ".")
    db.update("users", user["id"], {"password_hash": hash_password(body.new_password)})
    return {"ok": True}
