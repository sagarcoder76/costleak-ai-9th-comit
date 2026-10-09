"""Central configuration. Everything is env-overridable; nothing is required."""
from __future__ import annotations

import hashlib
import os
import secrets
import tempfile
from pathlib import Path

APP_NAME = "CostLeak AI"
VERSION = "2.0.0"

ROOT = Path(__file__).resolve().parents[3]
FRONTEND = ROOT / "frontend"

# --- security -------------------------------------------------------------
# Serverless platforms run many short-lived instances, each with its own /tmp.
# A per-process random key would be fine on one box but breaks the moment the
# next request lands on a different instance.
SERVERLESS = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME")
                  or os.getenv("FUNCTION_TARGET") or os.getenv("K_SERVICE")
                  or os.getenv("COSTLEAK_SERVERLESS"))

SECRET_KEY = os.getenv("COSTLEAK_SECRET", "")
SECRET_IS_DERIVED = False
if not SECRET_KEY and not SERVERLESS:
    # Dev / single box: reuse a key cached in the temp dir so tokens survive reloads.
    keyfile = Path(tempfile.gettempdir()) / "costleak_secret.key"
    try:
        if keyfile.exists():
            SECRET_KEY = keyfile.read_text().strip()
        else:
            SECRET_KEY = secrets.token_hex(32)
            keyfile.write_text(SECRET_KEY)
    except OSError:
        SECRET_KEY = ""

if not SECRET_KEY:
    # Serverless: every cold start is a fresh process, often a fresh container.
    # A random key here would make a token minted by one instance fail on the
    # next one (the user gets bounced back to the landing page mid-session), so
    # derive a deterministic key instead. Set COSTLEAK_SECRET in production.
    seed_material = "|".join(filter(None, [
        os.getenv("COSTLEAK_SECRET_SEED", ""),
        os.getenv("VERCEL_PROJECT_PRODUCTION_URL", ""),
        os.getenv("RENDER_SERVICE_ID", ""),
        "costleak-ai-default-key",
    ]))
    SECRET_KEY = hashlib.sha256(seed_material.encode()).hexdigest()
    SECRET_IS_DERIVED = True
TOKEN_TTL_HOURS = int(os.getenv("COSTLEAK_TOKEN_TTL", "168"))  # 7 days

# --- razorpay -------------------------------------------------------------
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
RAZORPAY_ENABLED = bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)

# --- platform -------------------------------------------------------------
SUPERADMIN_EMAIL = os.getenv("COSTLEAK_ADMIN_EMAIL", "admin@costleak.ai")
SUPERADMIN_PASSWORD = os.getenv("COSTLEAK_ADMIN_PASSWORD", "admin12345")
TRIAL_DAYS = int(os.getenv("COSTLEAK_TRIAL_DAYS", "14"))

# --- plans ----------------------------------------------------------------
# price in paise-free rupees, monthly. Limits are enforced in deps.py.
PLANS = [
    {
        "code": "starter", "name": "Starter", "price_monthly": 999, "price_yearly": 9990,
        "tagline": "For small teams getting their spend under control",
        "limits": {"users": 3, "invoices_per_month": 50, "products": 100, "analyses_per_month": 5},
        "features": ["Cost-leak analysis", "GST invoicing", "Product & customer master",
                     "PDF invoices", "Email support"],
    },
    {
        "code": "growth", "name": "Growth", "price_monthly": 2999, "price_yearly": 29990,
        "tagline": "For growing companies that want the full picture",
        "popular": True,
        "limits": {"users": 15, "invoices_per_month": 500, "products": 1000, "analyses_per_month": 50},
        "features": ["Everything in Starter", "GST reports & GSTR-1 export", "Profit & margin engine",
                     "Unlimited cost-leak findings", "Executive PDF reports", "Priority support"],
    },
    {
        "code": "scale", "name": "Scale", "price_monthly": 7999, "price_yearly": 79990,
        "tagline": "For finance teams replacing spreadsheets entirely",
        "limits": {"users": 100, "invoices_per_month": 10000, "products": 100000, "analyses_per_month": 500},
        "features": ["Everything in Growth", "Multi-user roles & permissions", "API access",
                     "Custom detection rules", "Dedicated onboarding", "WhatsApp support"],
    },
]
PLAN_MAP = {p["code"]: p for p in PLANS}

# Indian state codes for GST place-of-supply handling
STATE_CODES = {
    "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
    "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
    "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh",
    "24": "Gujarat", "26": "Dadra & Nagar Haveli and Daman & Diu", "27": "Maharashtra",
    "29": "Karnataka", "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu",
    "34": "Puducherry", "35": "Andaman & Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh",
    "38": "Ladakh", "97": "Other Territory",
}
GST_RATES = [0, 0.1, 0.25, 1, 1.5, 3, 5, 6, 7.5, 12, 18, 28]
