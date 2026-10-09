"""SQLite data layer for the multi-tenant app.

Every tenant-owned table carries `company_id`; every query in the routers is
scoped by it. The connection helper and the tiny query functions below are the
only storage-aware code in the project, so moving to Supabase/PostgreSQL means
re-implementing this one file (swap `?` for `%s` and sqlite3 for psycopg).
"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30))


def now_iso() -> str:
    return datetime.now(IST).isoformat(timespec="seconds")


def today_iso() -> str:
    return datetime.now(IST).date().isoformat()


def new_id(prefix: str = "") -> str:
    return (prefix + uuid.uuid4().hex[:12]) if prefix else uuid.uuid4().hex[:12]


def _resolve_db_path() -> Path:
    candidates = []
    if os.getenv("COSTLEAK_DB"):
        candidates.append(Path(os.getenv("COSTLEAK_DB")))
    candidates.append(Path(__file__).resolve().parents[2] / "data" / "costleak.db")
    candidates.append(Path(tempfile.gettempdir()) / "costleak.db")
    for path in candidates:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            probe = path.parent / ".costleak_write_test"
            probe.touch()
            probe.unlink()
            return path
        except OSError:
            continue
    return Path(tempfile.gettempdir()) / "costleak.db"


DB_PATH = _resolve_db_path()


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ------------------------------------------------------------- tiny ORM ---
def q(sql: str, params: tuple | list = ()) -> list[dict]:
    with connect() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def q1(sql: str, params: tuple | list = ()) -> dict | None:
    rows = q(sql, params)
    return rows[0] if rows else None


def ex(sql: str, params: tuple | list = ()) -> None:
    with connect() as c:
        c.execute(sql, params)


def insert(table: str, data: dict) -> str:
    data = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in data.items()}
    cols = ",".join(data)
    marks = ",".join("?" * len(data))
    with connect() as c:
        c.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(data.values()))
    return data.get("id", "")


def update(table: str, rid: str, data: dict, company_id: str | None = None) -> None:
    data = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in data.items()}
    sets = ",".join(f"{k}=?" for k in data)
    sql = f"UPDATE {table} SET {sets} WHERE id=?"
    params = list(data.values()) + [rid]
    if company_id:
        sql += " AND company_id=?"
        params.append(company_id)
    ex(sql, params)


def delete(table: str, rid: str, company_id: str | None = None) -> None:
    sql = f"DELETE FROM {table} WHERE id=?"
    params = [rid]
    if company_id:
        sql += " AND company_id=?"
        params.append(company_id)
    ex(sql, params)


def loads(value, default=None):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


# --------------------------------------------------------------- schema ---
SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    legal_name TEXT, gstin TEXT, pan TEXT,
    state_code TEXT DEFAULT '06',
    address TEXT, city TEXT, pincode TEXT,
    email TEXT, phone TEXT, website TEXT,
    industry TEXT, team_size TEXT,
    logo_url TEXT,
    invoice_prefix TEXT DEFAULT 'INV',
    invoice_counter INTEGER DEFAULT 0,
    financial_year TEXT DEFAULT '2026-27',
    status TEXT DEFAULT 'active',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    company_id TEXT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'owner',      -- superadmin | owner | admin | member | viewer
    status TEXT DEFAULT 'active',
    last_login TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_users_company ON users(company_id);

CREATE TABLE IF NOT EXISTS subscriptions (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    plan_code TEXT NOT NULL,
    billing_cycle TEXT DEFAULT 'monthly',
    status TEXT NOT NULL,                    -- trialing | active | past_due | cancelled
    amount REAL DEFAULT 0,
    provider TEXT DEFAULT 'simulated',       -- simulated | razorpay
    provider_ref TEXT,
    started_at TEXT, current_period_end TEXT, cancelled_at TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_subs_company ON subscriptions(company_id);

CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    subscription_id TEXT,
    amount REAL NOT NULL,
    currency TEXT DEFAULT 'INR',
    status TEXT NOT NULL,                    -- created | paid | failed | refunded
    provider TEXT DEFAULT 'simulated',
    provider_order_id TEXT, provider_payment_id TEXT,
    plan_code TEXT, billing_cycle TEXT,
    receipt_no TEXT,
    created_at TEXT NOT NULL, paid_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_pay_company ON payments(company_id);

CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    name TEXT NOT NULL,
    sku TEXT, hsn TEXT, category TEXT, unit TEXT DEFAULT 'NOS',
    cost_price REAL DEFAULT 0,               -- what it costs the company
    selling_price REAL DEFAULT 0,            -- what they charge (ex-GST)
    gst_rate REAL DEFAULT 18,
    cess_rate REAL DEFAULT 0,
    opening_stock REAL DEFAULT 0,
    low_margin_alert INTEGER DEFAULT 0,
    is_service INTEGER DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL, updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_prod_company ON products(company_id);

CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    name TEXT NOT NULL,
    gstin TEXT, state_code TEXT DEFAULT '06',
    email TEXT, phone TEXT, address TEXT, city TEXT, pincode TEXT,
    customer_type TEXT DEFAULT 'B2B',        -- B2B | B2C
    is_vendor INTEGER DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cust_company ON customers(company_id);

CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    number TEXT NOT NULL,
    doc_type TEXT DEFAULT 'sale',            -- sale | purchase
    invoice_date TEXT NOT NULL, due_date TEXT,
    customer_id TEXT, customer_name TEXT, customer_gstin TEXT,
    place_of_supply TEXT,
    supply_type TEXT,                        -- intra | inter
    subtotal REAL DEFAULT 0, discount_total REAL DEFAULT 0, taxable_total REAL DEFAULT 0,
    cgst REAL DEFAULT 0, sgst REAL DEFAULT 0, igst REAL DEFAULT 0, cess REAL DEFAULT 0,
    round_off REAL DEFAULT 0, total REAL DEFAULT 0,
    cost_total REAL DEFAULT 0, profit REAL DEFAULT 0, margin_pct REAL DEFAULT 0,
    status TEXT DEFAULT 'unpaid',            -- draft | unpaid | partial | paid | cancelled
    amount_paid REAL DEFAULT 0,
    notes TEXT, terms TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL, updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_inv_company ON invoices(company_id, invoice_date);

CREATE TABLE IF NOT EXISTS invoice_items (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    company_id TEXT NOT NULL,
    product_id TEXT,
    name TEXT NOT NULL, hsn TEXT, unit TEXT,
    qty REAL DEFAULT 1, rate REAL DEFAULT 0, discount_pct REAL DEFAULT 0,
    gst_rate REAL DEFAULT 18,
    taxable REAL DEFAULT 0, cgst REAL DEFAULT 0, sgst REAL DEFAULT 0, igst REAL DEFAULT 0,
    total REAL DEFAULT 0,
    cost_price REAL DEFAULT 0, profit REAL DEFAULT 0,
    sort_order INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_items_invoice ON invoice_items(invoice_id);

CREATE TABLE IF NOT EXISTS analyses (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    company TEXT NOT NULL,
    source TEXT NOT NULL,
    filename TEXT,
    created_at TEXT NOT NULL,
    profile_json TEXT NOT NULL,
    result_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_analyses_company ON analyses(company_id, created_at);

CREATE TABLE IF NOT EXISTS finding_state (
    analysis_id TEXT NOT NULL,
    finding_id TEXT NOT NULL,
    status TEXT, owner TEXT, notes_json TEXT, updated_at TEXT,
    PRIMARY KEY (analysis_id, finding_id)
);

CREATE TABLE IF NOT EXISTS usage_events (
    id TEXT PRIMARY KEY,
    company_id TEXT, user_id TEXT,
    event TEXT NOT NULL, meta TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_usage ON usage_events(company_id, created_at);
"""


def init() -> None:
    with connect() as c:
        c.executescript(SCHEMA)
        # lightweight migrations for databases created by earlier versions
        for table, column, decl in (("analyses", "subs_json", "TEXT"),):
            cols = {r[1] for r in c.execute(f"PRAGMA table_info({table})")}
            if column not in cols:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


# ----------------------------------------------------------- usage/audit ---
def track(event: str, company_id: str | None = None, user_id: str | None = None,
          meta: dict | None = None) -> None:
    try:
        insert("usage_events", {
            "id": new_id(), "company_id": company_id, "user_id": user_id,
            "event": event, "meta": json.dumps(meta or {}), "created_at": now_iso(),
        })
    except Exception:
        pass  # analytics must never break a request


def count(table: str, where: str = "1=1", params: tuple | list = ()) -> int:
    row = q1(f"SELECT COUNT(*) AS n FROM {table} WHERE {where}", params)
    return int(row["n"]) if row else 0


def month_key(dt: str | None = None) -> str:
    return (dt or now_iso())[:7]
