# CostLeak AI

**Find hidden money leaks, run GST invoicing and track product margins — in one app.**
Built for Indian SMBs. FastAPI + vanilla-JS SPA + SQLite. No build step, no npm install, no CDN.

---

## What it does

| Module | What you get |
|---|---|
| **Cost-leak engine** | 8 deterministic rules over your expense/subscription workbook: duplicate payments, duplicate & overlapping software, unused seats, vendor price hikes, high-cost/low-usage tools, upcoming renewals, automatable manual work, departmental overtime. Each finding shows its **formula** and **evidence rows**. |
| **GST invoicing** | Tax invoices and purchase bills with GSTIN validation (format + state + checksum), HSN/SAC, place-of-supply logic (intra → CGST+SGST, inter → IGST), amount in words, round-off, printable PDF. |
| **Product & cost database** | Cost price, selling price, GST rate, HSN per product → profit per unit, margin %, break-even price and **"selling below cost"** alerts. |
| **GST & tax reports** | Output tax vs input tax credit, net payable head-by-head, rate-wise breakup, B2B / B2C (GSTR-1 style) tables, HSN summary, CSV exports. |
| **Multi-tenant SaaS** | Company signup/login, roles (owner / admin / member / viewer), per-company data isolation on every query, plan limits enforced server-side. |
| **Subscriptions & billing** | Starter / Growth / Scale plans, 14-day trial, Razorpay checkout scaffolded with test keys and a **simulated fallback** when no keys are set. |
| **Platform admin** | Companies, MRR, conversion, plan mix, revenue trend, feature adoption, per-tenant drill-down. |

All rupee figures are computed from your data at runtime and labelled **Estimated Savings** — nothing is hardcoded.

---

## Run it

```bash
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000     # or: ./run.sh
```

Open <http://localhost:8000>.

**Demo logins** (seeded automatically on first run):

| Role | Email | Password |
|---|---|---|
| Company owner | `demo@nexasolutions.in` | `demo12345` |
| Platform admin | `admin@costleak.ai` | `admin12345` |

Or click **"Try the live demo"** on the landing page.

Tests: `python -m pytest -q` (7 passing rule tests).

---

## Architecture

```
main.py                     deploy entrypoint (re-exports the app)
backend/app/
  main.py                   FastAPI app, routers, SPA catch-all, cached static
  db.py                     SQLite layer, schema, migrations, tenant helpers
  core/                     config (plans, limits, GST data), security (tokens,
                            password hashing), deps (auth, tenancy, plan limits)
  routers/                  auth · masters · invoices · gst_reports · billing ·
                            admin · analysis · compat (SPA-shaped payloads, exports)
  services/                 gst (tax engine, GSTIN validation, words) ·
                            invoice_pdf · seed (demo tenants & data)
  analysis/                 rules · engine · explain  (the 8 detection rules)
  excel_io.py               tolerant workbook/CSV reader + profiler
frontend/
  index.html                app shell
  css/app.css               design system (dark landing + light app + dark mode)
  js/core.js                state, API client, 20s cache, router, formatters
  js/charts.js              dependency-free canvas charts (bar/hbar/line/donut)
  js/ui.js                  components + authenticated app shell
  js/app.js                 route table (views are lazy-imported per route)
  js/views/*.js             one module per screen
tests/test_rules.py         rule unit tests
```

**Speed:** no framework, no CDN, no bundler. The landing page ships one CSS file and
~12 KB of JS; each app screen is imported only when first visited and GET responses are
cached client-side for 20 seconds. Static assets are served with `Cache-Control` and
responses are gzipped.

**Theme:** dark 3D animated landing (canvas wireframe + particles, disabled under
`prefers-reduced-motion`), light high-contrast dashboard behind login, with a dark-mode
toggle in the top bar.

---

## Payments

Without keys the app runs in **simulated mode** — checkout activates the plan instantly
and records a payment marked `simulated`, so the whole flow is demoable. Set:

```bash
export RAZORPAY_KEY_ID=rzp_test_xxxxxxxx
export RAZORPAY_KEY_SECRET=xxxxxxxxxxxxx
```

and the same UI opens the real Razorpay test checkout, verifies the signature server-side
and activates the subscription.

---

## Deploy

### Vercel (demo only)

Vercel has **native FastAPI support**: it looks for a FastAPI instance named `app`
in a root entrypoint (`main.py` here) and sends every request to it with the original
path intact.

1. Import the repo. **Framework Preset: FastAPI.** Root Directory: the folder that
   contains `main.py`, `backend/`, `frontend/`.
2. Leave Build Command and Output Directory empty.
3. Optional but recommended: add `COSTLEAK_SECRET` = any long random string.

`vercel.json` only sets environment variables. **Do not add a catch-all rewrite**
(`"/(.*)" → "/api/index"`): Vercel's backend framework routing now forwards the
*rewritten* path to the app, so FastAPI sees `/api/index` for every request and
nothing matches — or, if that function does not exist, the edge returns
`404 NOT_FOUND` for every URL. This project needs no rewrites at all.

Two caveats that are properties of the platform, not bugs:

- The SQLite file lives in `/tmp`: rebuilt and re-seeded on every cold start, not
  shared between instances. Great for demos, useless for real customer data.
- Session tokens are signed with a key derived deterministically when
  `COSTLEAK_SECRET` is unset, so a token still validates when the next request hits
  a different instance.

### Persistent hosting (recommended for real use)

`Procfile`, `render.yaml`, `Dockerfile` and `runtime.txt` are included. Render (with a
mounted disk), Railway, Fly.io or any VM keeps one process and one database file, which
is what a multi-tenant app actually needs.

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Set `COSTLEAK_DB` to a writable path (e.g. `/tmp/costleak.db`) on ephemeral hosts.

---

## Honest limitations

- Savings are **estimates** from the rows you upload, not predictions or guarantees.
- GST summaries must be reconciled with your books and GSTR-2B before filing; this is not
  a substitute for a professional.
- SQLite single-node storage; auth uses signed stateless tokens (no refresh/rotation).
- Razorpay webhooks are scaffolded but not idempotency-hardened for production volume.
