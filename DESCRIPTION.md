# CostLeak AI — project descriptions

Copy-paste blocks for different places. Pick the one that fits the box you're filling.

---

## 1. One-liner (GitHub "About", 120 chars)

> AI-powered cost-waste analyzer: upload company expenses in Excel, get ranked savings findings in rupees.

**Suggested GitHub topics:** `fastapi` `pandas` `fintech` `cost-optimization` `saas-management` `expense-analysis` `python` `excel` `india` `hackathon`

---

## 2. Short description (tagline + 2 lines)

**CostLeak AI — find hidden money leaks in your company before they become annual losses.**

Upload your company expense and subscription data in Excel. CostLeak AI runs eight rule-based detection
engines over it and tells you exactly where money is leaking — duplicate payments, unused software seats,
overlapping tools, silent price hikes, manual-work cost and repeated overtime — with an estimated rupee
saving per month and per year for every single finding.

---

## 3. Elevator pitch (30 seconds, for a judge or investor)

Most Indian SMBs lose 5–15% of their operating spend to leaks nobody owns: an invoice paid twice, 18 licences
nobody logs into, Canva *and* Adobe Express on two different cards, a vendor who quietly raised prices 40%.
No one notices because each leak is small and the data sits in four different spreadsheets.

CostLeak AI is an expense *analyzer*, not another expense tracker. You upload one Excel file and in seconds
get a ranked list of findings — each with the evidence rows, the exact formula used, a confidence score, a
recommended action and an owner. A one-page executive PDF goes straight to your founder or CFO.

On our demo company it surfaces ₹3 lakh of estimated monthly waste inside ₹9 lakh of monthly spend —
about ₹36 lakh a year, found in under a minute.

---

## 4. Problem / Solution / How it works (hackathon submission form)

**The problem**
Small and medium businesses in India bleed money through cost leaks that no single person owns. Finance sees
invoices, IT sees subscriptions, HR sees overtime — nobody sees the overlap. Duplicate payments, licences
nobody uses, redundant SaaS tools, unnoticed price increases and expensive manual data entry quietly add up
to lakhs per year. Existing tools either just *record* expenses or are enterprise procurement platforms that
cost more than the waste they find.

**The solution**
CostLeak AI turns a single Excel upload into an evidence-backed savings report. It does not ask the business
to change how they work — it reads the spreadsheets they already maintain and returns money-shaped answers:

- "Possible duplicate payment to Tata Communications — ₹19,800 recoverable"
- "34 unused seats on Notion Business — ₹3,740/month"
- "Overlapping cloud storage tools: Google Drive, OneDrive, Dropbox — save ₹12,200/month"
- "Invoice data entry costs ₹1,35,000/month; automating 60% saves ₹81,000/month"
- "Amazon Web Services cost increased 25% vs its 5-month average — review renewal"

**How it works**
1. **Upload** — drag in an `.xlsx`/`.csv` with four sheets (Expenses, Subscriptions, Processes, Overtime). A
   forgiving parser handles messy real-world data: `₹` symbols, thousands separators, `8%` vs `0.08`,
   day-first dates, renamed columns, partial uploads.
2. **Validate** — a data-quality summary reports total rows, total spend, missing fields, duplicate rows and
   uncategorised vendors *before* any conclusions are drawn.
3. **Analyse** — eight rule-based detection engines run in a fixed order, with claim-tracking so the same
   rupee is never counted twice by two different rules.
4. **Prioritise** — every finding is scored on rupee impact (55%), data confidence (20%), ease of action
   (15%) and recurrence (10%), then bucketed Critical / High / Medium / Low.
5. **Act** — assign an owner, move findings through Identified → In Review → Approved → Actioned → Verified,
   leave comments, and export a one-page executive PDF with a 30-60-90 day action plan.

**What makes it different**
- **Answers, not dashboards.** The output is a ranked list of things to *do*, each with a rupee number.
- **Every number is auditable.** Each finding shows the evidence rows and the formula — e.g. unused seats =
  (20 paid − 12 used) × (₹10,000 ÷ 20) = ₹4,000/month. Nothing is a black box.
- **The AI never does the maths.** All calculations are deterministic Python. An LLM is optional and only
  rewrites explanations into friendlier prose; the app is fully functional with no API key and no internet.
- **Honest about uncertainty.** Every figure is labelled *Estimated Savings*, carries a confidence score, and
  the report ships with an explicit disclaimer. It is decision support, not an audit.

---

## 5. Technical description (for a README or tech-stack slide)

CostLeak AI is a FastAPI + vanilla-JS web application with no build step and no external services.

| Layer | Choice | Why |
|---|---|---|
| Backend | FastAPI (Python 3.10+) | Async, auto-generated OpenAPI docs, trivial to deploy |
| Data | pandas + openpyxl | Robust Excel/CSV parsing and column normalisation |
| Detection | Pure-Python rule engine | Deterministic, testable, auditable — not an LLM guess |
| Storage | SQLite, JSON-blob schema | Zero setup; `db.py` is the only storage-aware file, so Supabase/Postgres is a drop-in swap |
| Frontend | HTML/CSS/JS + Chart.js | No toolchain, loads instantly, fully responsive |
| Reporting | ReportLab | Real one-page PDF with charts, plus browser print-to-PDF |
| AI (optional) | Any OpenAI-compatible endpoint | Rephrases findings only; silently falls back to templates |

**Detection rules:** duplicate payments (same vendor, amounts within 2%, inside a 20-day window) ·
overlapping software (9 known tool-conflict groups) · unused seats · price increases >20% vs a vendor's own
trailing average · high-cost low-usage subscriptions · upcoming renewals on under-used tools · manual process
cost (`tasks × minutes × hourly cost ÷ 60`) · repeated departmental overtime.

Rules live in a decorator registry — adding a ninth rule is one function, and the dashboard, findings page,
charts, priority scoring and PDF pick it up automatically. Seven unit tests cover every formula plus an
end-to-end run on the demo dataset.

---

## 6. Demo script (60 seconds, for a live walkthrough)

1. **Landing page** → "Most companies have no idea where 10% of their money goes." Click **View Demo**.
2. **Dashboard** → "Nexa Solutions, a 100-person Bengaluru services company. ₹9 lakh monthly spend,
   ₹3 lakh of it estimated waste across 28 findings. The heatmap shows which department leaks which way."
3. **Findings** → open the duplicate-payment card. "Here are the two actual payment rows, four days apart,
   same invoice number. This is recoverable cash, not a projection." Assign an owner, set status *In Review*.
4. **Manual Cost calculator** → type 900 invoices × 18 minutes × ₹500/hr. "₹1,35,000 a month of salary time
   you're not invoicing anyone for. Automate 60% and that's ₹81,000 a month back."
5. **Reports** → download the PDF. "One page. Goes to the founder. Done."

---

## 7. Social / LinkedIn post

I built **CostLeak AI** — upload your company's expenses in Excel, and it tells you where the money is
leaking.

Not another expense tracker. It reads your expense, subscription, process and overtime sheets and returns
findings like:

🧾 Duplicate payment to a telecom vendor — ₹19,800 recoverable
🧩 Three cloud-storage tools doing one job — ₹12,200/month
⏱️ Manual invoice entry costing ₹1,35,000/month — automation saves ₹81,000

On the demo dataset: ₹9 lakh monthly spend → ₹3 lakh estimated monthly waste. ~₹36 lakh a year, found in
under a minute.

Every number shows its own formula and evidence rows. The calculations are deterministic Python, not an LLM
guess — the AI only writes the explanations, and the whole thing runs with no API key.

Stack: FastAPI · pandas · SQLite · Chart.js · ReportLab.

---

> **Always include the disclaimer:** *Savings are estimates based on uploaded data.* Validate each finding
> with the relevant budget owner before cancelling contracts or recovering payments.
