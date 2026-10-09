# CostLeak AI — PPT outline (11 slides, ~7 minutes)

Rule of thumb: **one idea per slide, max 6 lines of text, numbers big.**
Colours: deep blue `#0F2A4A` (titles), teal `#0E9F8E` (savings), red `#D64545` (waste),
white/light grey background.

---

## Slide 1 — Title

**CostLeak AI**
Find hidden money leaks in your company before they become annual losses.

- Your name · Team name · Event · Date
- Small line at the bottom: *AI-powered company cost-waste analyzer*

*Say:* "Every company is losing money it can't see. We built the tool that finds it."

---

## Slide 2 — The Problem

**Nobody owns the leak.**

- Finance sees invoices. IT sees subscriptions. HR sees overtime. **Nobody sees the overlap.**
- An invoice paid twice. 18 licences nobody logs into. Canva *and* Adobe Express on two cards.
- A vendor who quietly raised prices 40% at renewal.
- Each one is small. Together they are **5–15% of monthly operating spend.**

*Visual:* 4 disconnected spreadsheet icons with a question mark in the middle.

---

## Slide 3 — Why existing tools don't solve it

**Trackers record. They don't analyse.**

| Expense trackers | Enterprise procurement tools | CostLeak AI |
|---|---|---|
| Show what you spent | Cost more than the waste they find | Shows what to **stop** spending |
| No recommendations | 3-month implementation | Works in 2 minutes from Excel |

*Say:* "We're not building another expense tracker. We're building the layer that tells you what to do."

---

## Slide 4 — Our Solution

**Upload Excel → get a ranked list of savings findings.**

Four steps: **Upload → Validate → Analyse → Act**

Real output examples (put these in boxes, big text):
- 🧾 Duplicate payment to Tata Communications — **₹19,800 recoverable**
- 🎫 34 unused seats on Notion Business — **₹3,740/month**
- 🧩 Three cloud-storage tools doing one job — **₹12,200/month**
- ⏱️ Invoice data entry costs ₹1,35,000/month → automation saves **₹81,000/month**

---

## Slide 5 — Live Demo / Screenshots

**See it on real data: Nexa Solutions Pvt. Ltd.**

Three big numbers across the top:
**₹9.0 L** monthly spend · **₹3.0 L** estimated monthly waste · **28** findings

- Screenshot of the dashboard (KPIs + charts)
- Screenshot of one finding card showing the evidence rows

*Say:* "₹36 lakh a year, found in under a minute."

---

## Slide 6 — How the detection works

**8 rule-based detection engines — no guessing.**

1. Duplicate payments — same vendor, amount within 2%, inside 20 days
2. Overlapping software — 9 known tool-conflict groups
3. Unused seats — (paid − used) × cost per seat
4. Price increases — >20% above the vendor's own average
5. High-cost, low-usage subscriptions
6. Upcoming renewals on under-used tools
7. Manual work — tasks × minutes × hourly cost ÷ 60
8. Repeated departmental overtime

*One line at the bottom:* **The AI writes the explanations. Python does the maths.**

---

## Slide 7 — Every number is auditable

**Show the formula, not a black box.**

Worked example, big and centred:

> **Unused seats = 20 paid − 12 used = 8**
> **Cost per seat = ₹10,000 ÷ 20 = ₹500**
> **Monthly waste = 8 × ₹500 = ₹4,000 → ₹48,000/year**

- Every finding shows its evidence rows, confidence score and priority
- Labelled **Estimated Savings** — decision support, not an audit

---

## Slide 8 — Prioritisation

**Fix the ₹50,000 leak before the ₹500 one.**

- **Critical** — above ₹50,000/month or duplicate-payment risk
- **High** — ₹10,000–50,000 · **Medium** — ₹2,000–10,000 · **Low** — below ₹2,000
- Score blends: rupee impact 55% · confidence 20% · ease of action 15% · recurrence 10%
- Workflow: Identified → In Review → Approved → Actioned → Verified (with owner + comments)

---

## Slide 9 — Tech Stack

**Simple, free, production-ready.**

- **Backend:** Python, FastAPI
- **Data:** Pandas, OpenPyXL
- **Database:** SQLite (Supabase/Postgres ready)
- **Frontend:** HTML, CSS, JavaScript, Chart.js
- **Reports:** ReportLab PDF
- **Quality:** modular rule registry, 7 unit tests, Docker deploy

*Say:* "Adding a ninth detection rule is one function — the dashboard and PDF pick it up automatically."

---

## Slide 10 — Impact & What's next

**On the demo company: ₹36 lakh/year of estimated savings.**

Next:
- Bank statement and Tally/Zoho import (no Excel needed)
- Multi-month tracking: *did the saving actually happen?*
- Renewal calendar with email alerts
- Benchmarking against similar companies

---

## Slide 11 — Closing

**CostLeak AI — stop paying for what you don't use.**

- Live demo link / QR code
- GitHub repo link
- Your name + contact
- Small print: *Savings are estimates based on uploaded data.*

---

## Presenting tips

- **Slides 4 and 5 are your money slides.** If you only get 3 minutes, show those two and the demo.
- Lead with the **rupee number**, then explain the method. Judges remember ₹3 lakh, not "rule engine".
- Keep a backup screenshot of the dashboard — never rely on live wifi.
- Expected question: *"How accurate is this?"*
  Answer: "Deterministic formulas, not AI estimates. Every finding shows its evidence rows, carries a
  confidence score, and is labelled an estimate — the user validates before cancelling anything."
