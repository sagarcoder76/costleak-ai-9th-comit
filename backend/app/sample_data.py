"""Realistic demo dataset for Nexa Solutions Pvt. Ltd.

All numbers are plausible Indian SMB figures. Nothing here is a "result" —
these are raw inputs that the rule engine analyses at runtime.
"""
from __future__ import annotations

from datetime import date, timedelta

COMPANY_NAME = "Nexa Solutions Pvt. Ltd."

DEPARTMENTS = [
    "Sales", "Marketing", "IT", "Operations",
    "HR", "Finance", "Customer Support", "Admin",
]

# --------------------------------------------------------------------------
# Expenses
# --------------------------------------------------------------------------
# Base recurring vendors: (vendor, category, department, amount, mode, recurring, cycle)
_BASE = [
    ("Amazon Web Services", "Cloud Infrastructure", "IT", 96000, "Bank Transfer", "Yes", "Monthly"),
    ("Google Workspace", "Software", "Admin", 34000, "Credit Card", "Yes", "Monthly"),
    ("Microsoft 365", "Software", "Admin", 26000, "Credit Card", "Yes", "Monthly"),
    ("Salesforce India", "Software", "Sales", 42000, "Bank Transfer", "Yes", "Monthly"),
    ("HubSpot", "Software", "Marketing", 24000, "Credit Card", "Yes", "Monthly"),
    ("Zoom Video Communications", "Software", "Operations", 11600, "Credit Card", "Yes", "Monthly"),
    ("Slack Technologies", "Software", "IT", 14800, "Credit Card", "Yes", "Monthly"),
    ("Atlassian (Jira)", "Software", "IT", 13500, "Credit Card", "Yes", "Monthly"),
    ("Asana", "Software", "Marketing", 7200, "Credit Card", "Yes", "Monthly"),
    ("Trello (Business)", "Software", "Operations", 4400, "Credit Card", "Yes", "Monthly"),
    ("Canva Pro Teams", "Software", "Marketing", 6200, "Credit Card", "Yes", "Monthly"),
    ("Adobe Creative Cloud", "Software", "Marketing", 21000, "Credit Card", "Yes", "Monthly"),
    ("Dropbox Business", "Software", "Operations", 5400, "Credit Card", "Yes", "Monthly"),
    ("Freshdesk", "Software", "Customer Support", 16400, "Credit Card", "Yes", "Monthly"),
    ("Zoho Books", "Software", "Finance", 4600, "Credit Card", "Yes", "Monthly"),
    ("Razorpay Fees", "Payment Gateway", "Finance", 26200, "Auto Debit", "Yes", "Monthly"),
    ("Tata Communications", "Internet & Telecom", "Admin", 19800, "Bank Transfer", "Yes", "Monthly"),
    ("Airtel Business", "Internet & Telecom", "Admin", 12400, "Auto Debit", "Yes", "Monthly"),
    ("WeWork Galaxy Bengaluru", "Office Rent", "Admin", 168000, "Bank Transfer", "Yes", "Monthly"),
    ("BESCOM Electricity", "Utilities", "Admin", 27500, "Bank Transfer", "Yes", "Monthly"),
    ("Sodexo Meal Cards", "Employee Benefits", "HR", 32000, "Bank Transfer", "Yes", "Monthly"),
    ("Naukri RecruiterLite", "Recruitment", "HR", 9000, "Credit Card", "Yes", "Monthly"),
    ("Ola Corporate", "Travel", "Sales", 21800, "Corporate Card", "No", "Monthly"),
    ("MakeMyTrip Corporate", "Travel", "Sales", 34200, "Corporate Card", "No", "Monthly"),
    ("Google Ads", "Marketing Spend", "Marketing", 96000, "Credit Card", "Yes", "Monthly"),
    ("Meta Ads", "Marketing Spend", "Marketing", 54000, "Credit Card", "Yes", "Monthly"),
    ("Sharma & Associates (CA)", "Professional Services", "Finance", 45000, "Bank Transfer", "Yes", "Quarterly"),
    ("CleanPro Facility Services", "Facility", "Admin", 19500, "Bank Transfer", "Yes", "Monthly"),
    ("Secure24 Security", "Facility", "Admin", 22000, "Bank Transfer", "Yes", "Monthly"),
    ("Blue Dart Express", "Logistics", "Operations", 17300, "Bank Transfer", "No", "Monthly"),
]

# Vendors whose cost jumps in the latest month (price-increase signal)
_PRICE_SPIKES = {
    "Amazon Web Services": 1.23,   # +23%
    "Freshdesk": 1.31,             # +31%
}

_MONTH_DRIFT = [0.94, 0.97, 1.0, 1.01, 0.99, 1.0]  # 6 months of mild noise


def _month_starts(n: int = 6, today: date | None = None) -> list[date]:
    today = today or date.today()
    first = today.replace(day=1)
    months = []
    for i in range(n - 1, -1, -1):
        y, m = first.year, first.month - i
        while m <= 0:
            m += 12
            y -= 1
        months.append(date(y, m, 1))
    return months


def expense_rows(today: date | None = None) -> list[dict]:
    months = _month_starts(6, today)
    rows: list[dict] = []
    inv = 1000
    for idx, mstart in enumerate(months):
        is_last = idx == len(months) - 1
        for day_off, (vendor, cat, dept, amt, mode, rec, cycle) in enumerate(_BASE):
            if cycle == "Quarterly" and idx % 3 != 0:
                continue
            factor = _MONTH_DRIFT[idx % len(_MONTH_DRIFT)]
            if is_last and vendor in _PRICE_SPIKES:
                factor = _PRICE_SPIKES[vendor]
            inv += 1
            rows.append({
                "Date": mstart + timedelta(days=min(day_off % 26, 25)),
                "Vendor": vendor,
                "Category": cat,
                "Department": dept,
                "Amount": round(amt * factor, 2),
                "Payment Mode": mode,
                "Invoice Number": f"INV-{mstart.strftime('%y%m')}-{inv}",
                "Recurring": rec,
                "Billing Cycle": cycle,
                "Notes": "",
            })

    last = months[-1]
    prev = months[-2]
    # --- Planted duplicate payment #1 (same amount, 9 days apart)
    rows.append({
        "Date": last + timedelta(days=12),
        "Vendor": "Tata Communications", "Category": "Internet & Telecom", "Department": "Admin",
        "Amount": 19800, "Payment Mode": "Bank Transfer",
        "Invoice Number": "TCL-77120", "Recurring": "No", "Billing Cycle": "Monthly",
        "Notes": "Re-processed after payment-failure alert",
    })
    # --- Planted duplicate payment #2 (near-identical amount, same invoice re-sent)
    rows.append({
        "Date": prev + timedelta(days=20),
        "Vendor": "Blue Dart Express", "Category": "Logistics", "Department": "Operations",
        "Amount": 17450, "Payment Mode": "Bank Transfer",
        "Invoice Number": "BD-99341-R", "Recurring": "No", "Billing Cycle": "Monthly",
        "Notes": "Duplicate invoice copy received from vendor",
    })
    # --- Planted duplicate payment #3
    rows.append({
        "Date": last + timedelta(days=8),
        "Vendor": "CleanPro Facility Services", "Category": "Facility", "Department": "Admin",
        "Amount": 19500, "Payment Mode": "Bank Transfer",
        "Invoice Number": "CP-5521-B", "Recurring": "No", "Billing Cycle": "Monthly",
        "Notes": "Second transfer in the same cycle",
    })
    return rows


# --------------------------------------------------------------------------
# Subscriptions
# --------------------------------------------------------------------------
def subscription_rows(today: date | None = None) -> list[dict]:
    today = today or date.today()

    def d(days: int) -> date:
        return today + timedelta(days=days)

    data = [
        # Software, Vendor, Cost, Cycle, Paid, Used, LastAct, Renewal, Dept, Owner, Notes
        ("Salesforce Sales Cloud", "Salesforce India", 42000, "Monthly", 40, 31, d(-2), d(54), "Sales", "Rohit Mehra", ""),
        ("HubSpot Marketing Pro", "HubSpot", 24000, "Monthly", 25, 18, d(-1), d(96), "Marketing", "Ananya Iyer", ""),
        ("Slack Business+", "Slack Technologies", 14800, "Monthly", 80, 68, d(-1), d(140), "IT", "Vikram Shah", ""),
        ("Microsoft Teams (E3 add-on)", "Microsoft 365", 6200, "Monthly", 80, 14, d(-11), d(25), "IT", "Vikram Shah", "Bundled licence, low adoption"),
        ("Zoom Business", "Zoom Video Communications", 11600, "Monthly", 45, 16, d(-4), d(18), "Operations", "Priya Nair", ""),
        ("Google Meet (Workspace add-on)", "Google Workspace", 5200, "Monthly", 60, 54, d(-1), d(210), "Admin", "Priya Nair", ""),
        ("Canva Pro Teams", "Canva", 6200, "Monthly", 20, 12, d(-3), d(72), "Marketing", "Ananya Iyer", ""),
        ("Adobe Express", "Adobe", 5100, "Monthly", 12, 3, d(-24), d(40), "Marketing", "Ananya Iyer", "Overlaps with Canva"),
        ("Adobe Creative Cloud", "Adobe", 21000, "Monthly", 10, 8, d(-2), d(63), "Marketing", "Ananya Iyer", ""),
        ("Jira Software", "Atlassian", 13500, "Monthly", 55, 47, d(-1), d(120), "IT", "Vikram Shah", ""),
        ("Asana Business", "Asana", 7200, "Monthly", 30, 6, d(-29), d(21), "Marketing", "Ananya Iyer", "Team migrated to Jira"),
        ("Trello Business Class", "Atlassian", 4400, "Monthly", 25, 5, d(-35), d(11), "Operations", "Priya Nair", ""),
        ("Dropbox Business", "Dropbox", 5400, "Monthly", 30, 7, d(-18), d(29), "Operations", "Priya Nair", ""),
        ("Google Drive (Workspace)", "Google Workspace", 18000, "Monthly", 120, 114, d(-1), d(210), "Admin", "Priya Nair", ""),
        ("OneDrive for Business", "Microsoft 365", 6800, "Monthly", 80, 28, d(-6), d(25), "Admin", "Vikram Shah", ""),
        ("Freshdesk Pro", "Freshdesk", 16400, "Monthly", 35, 31, d(-1), d(48), "Customer Support", "Kabir Das", ""),
        ("Zoho Books", "Zoho", 4600, "Monthly", 12, 10, d(-2), d(88), "Finance", "Sneha Kulkarni", ""),
        ("Naukri RecruiterLite", "Naukri", 9000, "Monthly", 6, 2, d(-39), d(16), "HR", "Meera Joshi", "Hiring freeze since Q2"),
        ("Figma Organization", "Figma", 12400, "Monthly", 25, 21, d(-1), d(133), "IT", "Vikram Shah", ""),
        ("Notion Business", "Notion Labs", 6600, "Monthly", 60, 26, d(-12), d(35), "Operations", "Priya Nair", ""),
        ("LinkedIn Sales Navigator", "LinkedIn", 13800, "Monthly", 20, 8, d(-15), d(27), "Sales", "Rohit Mehra", ""),
        ("Zendesk Suite", "Zendesk", 9800, "Monthly", 18, 3, d(-46), d(9), "Customer Support", "Kabir Das", "Running in parallel with Freshdesk"),
        ("DocuSign Business", "DocuSign", 5200, "Monthly", 15, 6, d(-23), d(58), "Admin", "Sneha Kulkarni", ""),
        ("Calendly Teams", "Calendly", 3100, "Monthly", 25, 22, d(-1), d(170), "Sales", "Rohit Mehra", ""),
    ]
    return [{
        "Software": s, "Vendor": v, "Cost": c, "Billing Cycle": bc,
        "Seats Paid": sp, "Seats Used": su, "Last Activity Date": la,
        "Renewal Date": rd, "Department": dp, "Owner": ow, "Notes": nt,
    } for s, v, c, bc, sp, su, la, rd, dp, ow, nt in data]


# --------------------------------------------------------------------------
# Processes
# --------------------------------------------------------------------------
def process_rows() -> list[dict]:
    data = [
        ("Invoice data entry into Tally", "Finance", 900, 18, 3, 500, 0.00, "High",
         "Vendor invoices keyed in manually from PDF and email"),
        ("Weekly MIS report compilation", "Operations", 16, 150, 2, 600, 0.05, "High", ""),
        ("Sales order to CRM re-entry", "Sales", 150, 10, 2, 420, 0.06, "Medium", ""),
        ("Monthly payroll reconciliation", "HR", 60, 20, 2, 600, 0.04, "Medium", ""),
        ("Customer refund approvals (email chain)", "Customer Support", 70, 15, 2, 380, 0.08, "Medium", ""),
        ("Vendor onboarding documentation", "Admin", 20, 45, 1, 420, 0.05, "Low", ""),
    ]
    return [{
        "Process Name": p, "Department": d, "Tasks Per Month": t, "Minutes Per Task": m,
        "Employees Involved": e, "Hourly Cost": h, "Error Rate": er,
        "Automation Feasibility": af, "Notes": n,
    } for p, d, t, m, e, h, er, af, n in data]


# --------------------------------------------------------------------------
# Overtime
# --------------------------------------------------------------------------
def overtime_rows(today: date | None = None) -> list[dict]:
    months = [m.strftime("%Y-%m") for m in _month_starts(4, today)]
    staff = [
        ("NSL-0121", "Arjun Rao", "Operations", [38, 42, 40, 46], 300),
        ("NSL-0134", "Farhan Qureshi", "Operations", [34, 36, 39, 41], 280),
        ("NSL-0156", "Divya Menon", "Operations", [31, 33, 32, 37], 290),
        ("NSL-0188", "Harpreet Kaur", "Customer Support", [18, 21, 16, 23], 260),
        ("NSL-0190", "Imran Sheikh", "Customer Support", [14, 17, 20, 19], 260),
        ("NSL-0201", "Sanjay Patel", "Finance", [10, 8, 12, 9], 400),
        ("NSL-0233", "Ritu Agarwal", "IT", [6, 5, 8, 6], 480),
    ]
    rows = []
    for emp_id, name, dept, hours, rate in staff:
        for mon, hrs in zip(months, hours):
            rows.append({
                "Employee ID": emp_id, "Name": name, "Department": dept,
                "Month": mon, "Overtime Hours": hrs, "Overtime Rate": rate,
                "Notes": "",
            })
    return rows


def sample_dataset(today: date | None = None) -> dict[str, list[dict]]:
    return {
        "expenses": expense_rows(today),
        "subscriptions": subscription_rows(today),
        "processes": process_rows(),
        "overtime": overtime_rows(today),
    }
