"""Unit tests for the detection rules — run with:  python -m pytest -q"""
import sys, pathlib
from datetime import date, timedelta
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from backend.app import excel_io, sample_data
from backend.app.analysis import rules as R
from backend.app.analysis.engine import analyse

CFG = R.DEFAULT_CONFIG


def test_unused_seats_math():
    df = pd.DataFrame([{"Software": "ToolX", "Vendor": "V", "Cost": 10000, "Billing Cycle": "Monthly",
                        "Seats Paid": 20, "Seats Used": 12, "Last Activity Date": pd.NaT,
                        "Renewal Date": pd.NaT, "Department": "IT", "Owner": "A", "Notes": ""}])
    f = R.unused_seats({"subscriptions": df}, CFG, {})[0]
    assert f["monthly_waste"] == 4000          # 8 unused x 500/seat
    assert f["annual_waste"] == 48000
    assert f["priority"] == "Medium"


def test_manual_process_formula():
    df = pd.DataFrame([{"Process Name": "Invoice entry", "Department": "Finance", "Tasks Per Month": 900,
                        "Minutes Per Task": 18, "Employees Involved": 3, "Hourly Cost": 500,
                        "Error Rate": 0, "Automation Feasibility": "High", "Notes": ""}])
    f = R.manual_work({"processes": df}, CFG, {})[0]
    assert f["monthly_waste"] == 81000         # 1,35,000 x 60%


def test_duplicate_payment_detected():
    today = date.today()
    rows = [{"Date": today, "Vendor": "Acme", "Category": "X", "Department": "IT", "Amount": 50000,
             "Payment Mode": "NEFT", "Invoice Number": "A1", "Recurring": "No",
             "Billing Cycle": "Monthly", "Notes": ""},
            {"Date": today + timedelta(days=5), "Vendor": "Acme", "Category": "X", "Department": "IT",
             "Amount": 50000, "Payment Mode": "NEFT", "Invoice Number": "A1", "Recurring": "No",
             "Billing Cycle": "Monthly", "Notes": ""}]
    out = R.duplicate_payments({"expenses": pd.DataFrame(rows)}, CFG, {})
    assert len(out) == 1 and out[0]["monthly_waste"] == 50000
    assert out[0]["priority"] == "Critical"


def test_monthly_normalisation():
    assert R.monthly(12000, "Yearly") == 1000
    assert R.monthly(3000, "Quarterly") == 1000
    assert R.monthly(1000, "Monthly") == 1000


def test_price_increase_threshold():
    rows = []
    for i, amt in enumerate([10000, 10000, 10000, 15000]):
        rows.append({"Date": pd.Timestamp("2026-01-01") + pd.DateOffset(months=i), "Vendor": "Vx",
                     "Category": "C", "Department": "IT", "Amount": amt, "Payment Mode": "",
                     "Invoice Number": "", "Recurring": "Yes", "Billing Cycle": "Monthly", "Notes": ""})
    out = R.price_increase({"expenses": pd.DataFrame(rows)}, CFG, {})
    assert len(out) == 1 and out[0]["monthly_waste"] == 5000


def test_demo_dataset_end_to_end():
    frames = excel_io.frames_from_records(sample_data.sample_dataset())
    res = analyse(frames, company=sample_data.COMPANY_NAME)
    k = res["kpis"]
    assert k["findings_count"] > 15
    assert 800000 < k["monthly_spend"] < 1200000          # ~Rs 8-12 lakh / month
    assert k["monthly_waste"] > 0 and k["annual_savings"] == round(k["monthly_waste"] * 12, 2)
    cats = {f["category"] for f in res["findings"]}
    for required in ("Duplicate Payment", "Duplicate Software", "Unused License",
                     "Price Increase", "Manual Work", "Overtime"):
        assert required in cats, required
    assert all(r["status"] == "ok" for r in res["rule_log"])


def test_template_roundtrip():
    data = excel_io.build_workbook(with_sample=True)
    frames, warnings = excel_io.read_upload(data, "t.xlsx")
    assert set(frames) == {"expenses", "subscriptions", "processes", "overtime"}
    prof = excel_io.profile(frames)
    assert prof["total_rows"] > 200
