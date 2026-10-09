"""Bootstraps the platform superadmin and a ready-to-explore demo company."""
from __future__ import annotations

import hashlib
import itertools

import json
import random
from datetime import date, datetime, timedelta

from .. import db, excel_io, sample_data
from ..analysis.engine import analyse
from ..core import config
from ..core.deps import start_trial
from ..core.security import hash_password
from .gst import build_invoice

DEMO_EMAIL = "demo@nexasolutions.in"
DEMO_PASSWORD = "demo12345"

PRODUCTS = [
    # name, sku, hsn, category, unit, cost, sell, gst, service
    ("Website Design Package", "SRV-WEB-01", "998314", "Services", "NOS", 18000, 45000, 18, 1),
    ("Mobile App Development", "SRV-APP-01", "998314", "Services", "NOS", 120000, 285000, 18, 1),
    ("Annual Maintenance Contract", "SRV-AMC-01", "998313", "Services", "NOS", 9000, 24000, 18, 1),
    ("Cloud Hosting (per month)", "SRV-HOST-01", "998315", "Services", "NOS", 1400, 2500, 18, 1),
    ("SEO Retainer", "SRV-SEO-01", "998365", "Marketing", "NOS", 14000, 32000, 18, 1),
    ("Social Media Management", "SRV-SMM-01", "998365", "Marketing", "NOS", 11000, 21000, 18, 1),
    ("Logo & Brand Identity", "SRV-BRD-01", "998391", "Design", "NOS", 7000, 18000, 18, 1),
    ("Dell Latitude 3540 Laptop", "HW-LAP-01", "8471", "Hardware", "NOS", 52000, 58500, 18, 0),
    ("HP LaserJet Printer", "HW-PRN-01", "8443", "Hardware", "NOS", 16800, 19500, 18, 0),
    ("Logitech MX Keyboard", "HW-KBD-01", "8471", "Hardware", "NOS", 7200, 8900, 18, 0),
    ("24-inch LED Monitor", "HW-MON-01", "8528", "Hardware", "NOS", 11500, 12100, 18, 0),
    ("Networking Switch 24-port", "HW-NET-01", "8517", "Hardware", "NOS", 14200, 15000, 18, 0),
    ("Office Chair (Ergonomic)", "FUR-CHR-01", "9401", "Furniture", "NOS", 8400, 9100, 18, 0),
    ("Training Workshop (per day)", "SRV-TRN-01", "999293", "Services", "DAY", 6000, 15000, 18, 1),
    ("Data Migration Service", "SRV-MIG-01", "998316", "Services", "NOS", 22000, 38000, 18, 1),
    ("Printed Marketing Collateral", "GDS-PRT-01", "4911", "Goods", "PCS", 48, 42, 12, 0),
    ("Stationery Kit", "GDS-STA-01", "4820", "Goods", "PCS", 310, 330, 12, 0),
    ("Software Licence Resale", "SRV-LIC-01", "997331", "Services", "NOS", 9800, 10200, 18, 1),
]

CUSTOMERS = [
    ("Sharma Textiles Pvt Ltd", "06AABCS1429B1ZX", "06", "Gurugram", "B2B"),
    ("Mehta Industries Limited", "27AAPFU0939F1ZV", "27", "Mumbai", "B2B"),
    ("Krishna Retail LLP", "29AAGCK1234M1Z8", "29", "Bengaluru", "B2B"),
    ("Delhi Logistics Co", "07AAACD2727Q1ZL", "07", "New Delhi", "B2B"),
    ("Patel Agro Exports", "24AABCP5678K1ZT", "24", "Ahmedabad", "B2B"),
    ("Chennai Software Services", "33AAFCC9876J1ZQ", "33", "Chennai", "B2B"),
    ("Kolkata Trading House", "19AADCK4321H1ZR", "19", "Kolkata", "B2B"),
    ("Rohtak Hardware Store", None, "06", "Rohtak", "B2C"),
    ("Walk-in Customer", None, "06", "Gurugram", "B2C"),
    ("Hyderabad Media Group", "36AACCH3344L1ZP", "36", "Hyderabad", "B2B"),
]

VENDORS = [
    ("Amazon Web Services India", "29AAGCA1234F1ZM", "29", "Bengaluru"),
    ("Tata Communications Ltd", "27AAACT2716Q1ZK", "27", "Mumbai"),
    ("Office Supplies Mart", "06AADCO1122N1ZF", "06", "Gurugram"),
]


def _superadmin() -> None:
    if db.q1("SELECT id FROM users WHERE role='superadmin'"):
        return
    db.insert("users", {
        "id": db.new_id("usr_"), "company_id": None, "name": "Platform Admin",
        "email": config.SUPERADMIN_EMAIL.lower(),
        "password_hash": hash_password(config.SUPERADMIN_PASSWORD),
        "role": "superadmin", "created_at": db.now_iso(),
    })


def _demo_company() -> None:
    if db.q1("SELECT id FROM users WHERE email=?", (DEMO_EMAIL,)):
        return
    rnd = random.Random(7)
    cid = db.new_id("cmp_")
    db.insert("companies", {
        "id": cid, "name": sample_data.COMPANY_NAME, "legal_name": sample_data.COMPANY_NAME,
        "gstin": "06AABCN4567P1Z5", "state_code": "06", "pan": "AABCN4567P",
        "address": "4th Floor, Cyber Hub Tower B, Sector 24", "city": "Gurugram",
        "pincode": "122002", "email": DEMO_EMAIL, "phone": "+91 98100 45678",
        "website": "nexasolutions.in", "industry": "IT Services & Consulting",
        "team_size": "51-200", "invoice_prefix": "NSL", "financial_year": "2026-27",
        "created_at": db.now_iso(),
    })
    uid = db.new_id("usr_")
    db.insert("users", {
        "id": uid, "company_id": cid, "name": "Rohit Mehra", "email": DEMO_EMAIL,
        "phone": "+91 98100 45678", "password_hash": hash_password(DEMO_PASSWORD),
        "role": "owner", "created_at": db.now_iso(), "last_login": db.now_iso(),
    })
    for name, email, role in [("Sneha Kulkarni", "sneha@nexasolutions.in", "admin"),
                              ("Vikram Shah", "vikram@nexasolutions.in", "member"),
                              ("Ananya Iyer", "ananya@nexasolutions.in", "viewer")]:
        db.insert("users", {
            "id": db.new_id("usr_"), "company_id": cid, "name": name, "email": email,
            "password_hash": hash_password(DEMO_PASSWORD), "role": role,
            "created_at": db.now_iso(),
        })

    # active paid subscription so the demo shows the full product
    sid = db.new_id("sub_")
    db.insert("subscriptions", {
        "id": sid, "company_id": cid, "plan_code": "growth", "billing_cycle": "monthly",
        "status": "active", "amount": config.PLAN_MAP["growth"]["price_monthly"],
        "provider": "simulated", "started_at": db.now_iso(),
        "current_period_end": (datetime.now() + timedelta(days=23)).isoformat(timespec="seconds"),
        "created_at": db.now_iso(),
    })
    for i in range(3):
        when = (datetime.now() - timedelta(days=30 * (i + 1))).isoformat(timespec="seconds")
        db.insert("payments", {
            "id": db.new_id("pay_"), "company_id": cid, "subscription_id": sid,
            "amount": config.PLAN_MAP["growth"]["price_monthly"], "status": "paid",
            "provider": "simulated", "plan_code": "growth", "billing_cycle": "monthly",
            "receipt_no": f"CL-DEMO{i+1:03d}", "created_at": when, "paid_at": when,
        })

    prod_ids = []
    for name, sku, hsn, cat, unit, cost, sell, gst, svc in PRODUCTS:
        pid = db.new_id("prd_")
        prod_ids.append((pid, name, hsn, unit, cost, sell, gst))
        db.insert("products", {
            "id": pid, "company_id": cid, "name": name, "sku": sku, "hsn": hsn,
            "category": cat, "unit": unit, "cost_price": cost, "selling_price": sell,
            "gst_rate": gst, "is_service": svc, "created_at": db.now_iso(),
            "updated_at": db.now_iso(),
        })

    cust_ids = []
    for name, gstin, state, city, ctype in CUSTOMERS:
        cuid = db.new_id("cus_")
        cust_ids.append((cuid, name, gstin, state))
        db.insert("customers", {
            "id": cuid, "company_id": cid, "name": name, "gstin": gstin, "state_code": state,
            "city": city, "customer_type": ctype, "created_at": db.now_iso(),
        })
    vend_ids = []
    for name, gstin, state, city in VENDORS:
        vid = db.new_id("cus_")
        vend_ids.append((vid, name, gstin, state))
        db.insert("customers", {
            "id": vid, "company_id": cid, "name": name, "gstin": gstin, "state_code": state,
            "city": city, "customer_type": "B2B", "is_vendor": 1, "created_at": db.now_iso(),
        })

    counter = 0
    today = date.today()
    for months_ago in range(3, -1, -1):
        base = (today.replace(day=1) - timedelta(days=months_ago * 30)).replace(day=1)
        for n in range(rnd.randint(5, 9)):
            cuid, cname, cgstin, cstate = rnd.choice(cust_ids)
            picks = rnd.sample(prod_ids, rnd.randint(1, 3))
            lines = [{
                "name": p[1], "hsn": p[2], "unit": p[3], "qty": rnd.randint(1, 4),
                "rate": p[5], "gst_rate": p[6], "cost_price": p[4],
                "discount_pct": rnd.choice([0, 0, 0, 5, 10]),
            } for p in picks]
            calc = build_invoice(lines, "06", cstate)
            counter += 1
            inv_date = (base + timedelta(days=rnd.randint(0, 26))).isoformat()
            iid = db.new_id("inv_")
            paid_roll = rnd.random()
            status = "paid" if paid_roll < 0.6 else ("partial" if paid_roll < 0.75 else "unpaid")
            db.insert("invoices", {
                "id": iid, "company_id": cid, "number": f"NSL/2627/{counter:04d}",
                "doc_type": "sale", "invoice_date": inv_date,
                "due_date": (date.fromisoformat(inv_date) + timedelta(days=15)).isoformat(),
                "customer_id": cuid, "customer_name": cname, "customer_gstin": cgstin,
                "place_of_supply": cstate, "supply_type": calc["supply_type"],
                "subtotal": calc["subtotal"], "discount_total": calc["discount_total"],
                "taxable_total": calc["taxable_total"], "cgst": calc["cgst"],
                "sgst": calc["sgst"], "igst": calc["igst"], "round_off": calc["round_off"],
                "total": calc["total"], "cost_total": calc["cost_total"],
                "profit": calc["profit"], "margin_pct": calc["margin_pct"],
                "status": status,
                "amount_paid": calc["total"] if status == "paid" else (
                    round(calc["total"] * 0.5, 2) if status == "partial" else 0),
                "created_by": uid, "created_at": inv_date + "T11:00:00+05:30",
                "updated_at": db.now_iso(),
            })
            for i, item in enumerate(calc["items"]):
                db.insert("invoice_items", {
                    "id": db.new_id("itm_"), "invoice_id": iid, "company_id": cid,
                    "product_id": picks[i][0], "name": item["name"], "hsn": item["hsn"],
                    "unit": item["unit"], "qty": item["qty"], "rate": item["rate"],
                    "discount_pct": item["discount_pct"], "gst_rate": item["gst_rate"],
                    "taxable": item["taxable"], "cgst": item["cgst"], "sgst": item["sgst"],
                    "igst": item["igst"], "total": item["total"],
                    "cost_price": item["cost_price"], "profit": item["profit"], "sort_order": i,
                })

        # a couple of purchase bills each month so input tax credit is real
        for _ in range(2):
            vid, vname, vgstin, vstate = rnd.choice(vend_ids)
            lines = [{"name": "Input services / goods", "hsn": "998313", "qty": 1,
                      "rate": rnd.randint(18000, 65000), "gst_rate": 18, "cost_price": 0}]
            calc = build_invoice(lines, "06", vstate)
            counter += 1
            inv_date = (base + timedelta(days=rnd.randint(0, 26))).isoformat()
            iid = db.new_id("inv_")
            db.insert("invoices", {
                "id": iid, "company_id": cid, "number": f"PUR/2627/{counter:04d}",
                "doc_type": "purchase", "invoice_date": inv_date, "due_date": inv_date,
                "customer_id": vid, "customer_name": vname, "customer_gstin": vgstin,
                "place_of_supply": "06", "supply_type": calc["supply_type"],
                "subtotal": calc["subtotal"], "taxable_total": calc["taxable_total"],
                "cgst": calc["cgst"], "sgst": calc["sgst"], "igst": calc["igst"],
                "round_off": calc["round_off"], "total": calc["total"], "status": "paid",
                "amount_paid": calc["total"], "created_by": uid,
                "created_at": inv_date + "T11:00:00+05:30", "updated_at": db.now_iso(),
            })
            for i, item in enumerate(calc["items"]):
                db.insert("invoice_items", {
                    "id": db.new_id("itm_"), "invoice_id": iid, "company_id": cid,
                    "name": item["name"], "hsn": item["hsn"], "unit": item["unit"],
                    "qty": item["qty"], "rate": item["rate"], "gst_rate": item["gst_rate"],
                    "taxable": item["taxable"], "cgst": item["cgst"], "sgst": item["sgst"],
                    "igst": item["igst"], "total": item["total"], "sort_order": i,
                })
    db.update("companies", cid, {"invoice_counter": counter})

    # a stored cost-leak analysis so the dashboard is populated on first login
    frames = excel_io.frames_from_records(sample_data.sample_dataset())
    prof = excel_io.profile(frames)
    result = analyse(frames, company=sample_data.COMPANY_NAME)
    db.insert("analyses", {
        "id": db.new_id("ana_"), "company_id": cid, "company": sample_data.COMPANY_NAME,
        "source": "demo", "filename": "sample_nexa_solutions.xlsx", "created_at": db.now_iso(),
        "profile_json": json.dumps(prof, default=str),
        "subs_json": json.dumps(
            frames["subscriptions"].to_dict("records") if "subscriptions" in frames else [],
            default=str),
        "result_json": json.dumps(json.loads(json.dumps(result, default=str)), default=str),
    })

    for ev, n in [("login", 24), ("invoice_created", 31), ("analysis_run", 6),
                  ("report_exported", 4), ("calculator_used", 9), ("product_created", 18)]:
        for i in range(n):
            db.insert("usage_events", {
                "id": db.new_id(), "company_id": cid, "user_id": uid, "event": ev,
                "meta": "{}",
                "created_at": (datetime.now() - timedelta(days=rnd.randint(0, 45),
                                                          hours=rnd.randint(0, 23))
                               ).isoformat(timespec="seconds"),
            })


def _extra_companies() -> None:
    """A few more tenants so the admin panel is not a single-row table."""
    if db.count("companies") > 2:
        return
    rnd = random.Random(11)
    seeds = [
        ("Bright Retail Ventures", "starter", "active", "Jaipur", 12),
        ("Orbit Digital Agency", "growth", "active", "Pune", 34),
        ("Sunrise Manufacturing Co", "scale", "active", "Coimbatore", 61),
        ("Kadam Logistics", "starter", "trialing", "Nashik", 4),
        ("Finvue Consulting LLP", "growth", "trialing", "Noida", 9),
        ("Zephyr Foods Pvt Ltd", "starter", "cancelled", "Indore", 2),
    ]
    for name, plan, status, city, events in seeds:
        cid = db.new_id("cmp_")
        created = (datetime.now() - timedelta(days=rnd.randint(5, 120))).isoformat(timespec="seconds")
        db.insert("companies", {
            "id": cid, "name": name, "legal_name": name, "state_code": "06", "city": city,
            "email": f"owner@{name.split()[0].lower()}.in", "created_at": created,
        })
        uid = db.new_id("usr_")
        db.insert("users", {
            "id": uid, "company_id": cid, "name": "Owner",
            "email": f"owner@{name.split()[0].lower()}.in",
            "password_hash": hash_password("demo12345"), "role": "owner", "created_at": created,
        })
        end = (datetime.now() + timedelta(days=rnd.randint(3, 28))).isoformat(timespec="seconds")
        db.insert("subscriptions", {
            "id": db.new_id("sub_"), "company_id": cid, "plan_code": plan,
            "billing_cycle": rnd.choice(["monthly", "monthly", "yearly"]),
            "status": status, "amount": config.PLAN_MAP[plan]["price_monthly"],
            "provider": "simulated", "started_at": created, "current_period_end": end,
            "created_at": created,
        })
        if status == "active":
            for i in range(rnd.randint(1, 4)):
                when = (datetime.now() - timedelta(days=30 * (i + 1))).isoformat(timespec="seconds")
                db.insert("payments", {
                    "id": db.new_id("pay_"), "company_id": cid,
                    "amount": config.PLAN_MAP[plan]["price_monthly"], "status": "paid",
                    "provider": "simulated", "plan_code": plan, "billing_cycle": "monthly",
                    "receipt_no": f"CL-{rnd.randint(10000,99999)}",
                    "created_at": when, "paid_at": when,
                })
        for _ in range(events):
            db.insert("usage_events", {
                "id": db.new_id(), "company_id": cid, "user_id": uid,
                "event": rnd.choice(["login", "invoice_created", "analysis_run",
                                     "product_created", "report_exported"]),
                "meta": "{}",
                "created_at": (datetime.now() - timedelta(days=rnd.randint(0, 40))
                               ).isoformat(timespec="seconds"),
            })


def run() -> None:
    """Populate demo data.

    IDs are made deterministic for the duration of seeding. On serverless hosts
    the database lives in /tmp and is rebuilt on every cold start, so a token
    issued by one instance must still resolve to the same user row on the next
    one — random UUIDs would 401 the user straight back to the landing page.
    """
    counter = itertools.count(1)
    real_new_id = db.new_id

    def stable_id(prefix: str = "") -> str:
        digest = hashlib.sha1(f"costleak-seed|{prefix}|{next(counter)}".encode()).hexdigest()
        return f"{prefix}{digest[:12]}"

    db.new_id = stable_id
    try:
        _superadmin()
        _demo_company()
        _extra_companies()
    finally:
        db.new_id = real_new_id
