"""Excel/CSV template generation, parsing and data-quality profiling."""
from __future__ import annotations

import io
import re
from datetime import date, datetime

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from . import sample_data

SHEETS: dict[str, list[str]] = {
    "Expenses": ["Date", "Vendor", "Category", "Department", "Amount", "Payment Mode",
                 "Invoice Number", "Recurring", "Billing Cycle", "Notes"],
    "Subscriptions": ["Software", "Vendor", "Cost", "Billing Cycle", "Seats Paid", "Seats Used",
                      "Last Activity Date", "Renewal Date", "Department", "Owner", "Notes"],
    "Processes": ["Process Name", "Department", "Tasks Per Month", "Minutes Per Task",
                  "Employees Involved", "Hourly Cost", "Error Rate", "Automation Feasibility", "Notes"],
    "Overtime": ["Employee ID", "Name", "Department", "Month", "Overtime Hours",
                 "Overtime Rate", "Notes"],
}

KEY_TO_SHEET = {"expenses": "Expenses", "subscriptions": "Subscriptions",
                "processes": "Processes", "overtime": "Overtime"}

REQUIRED = {
    "expenses": ["Date", "Vendor", "Amount"],
    "subscriptions": ["Software", "Cost"],
    "processes": ["Process Name", "Tasks Per Month", "Minutes Per Task", "Hourly Cost"],
    "overtime": ["Department", "Overtime Hours", "Overtime Rate"],
}

HEADER_FILL = PatternFill("solid", fgColor="0F2A4A")
HEADER_FONT = Font(color="FFFFFF", bold=True, size=11)


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def build_workbook(with_sample: bool = True) -> bytes:
    """Return an .xlsx template (optionally pre-filled with demo data)."""
    data = sample_data.sample_dataset() if with_sample else {}
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for key, sheet in KEY_TO_SHEET.items():
            cols = SHEETS[sheet]
            rows = data.get(key, [])
            df = pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)
            df.to_excel(xw, sheet_name=sheet, index=False)
            ws = xw.sheets[sheet]
            for ci, col in enumerate(cols, start=1):
                cell = ws.cell(row=1, column=ci)
                cell.fill = HEADER_FILL
                cell.font = HEADER_FONT
                cell.alignment = Alignment(horizontal="center", vertical="center")
                width = max(len(col) + 4, 14)
                if col in ("Notes", "Process Name", "Software", "Vendor"):
                    width = 28
                ws.column_dimensions[get_column_letter(ci)].width = width
            ws.freeze_panes = "A2"
        # Instructions sheet
        guide = pd.DataFrame({
            "CostLeak AI — How to use this template": [
                "1. Fill any sheet you have data for. Empty sheets are simply skipped.",
                "2. Expenses: one row per payment/invoice line. Dates as DD-MM-YYYY or YYYY-MM-DD.",
                "3. Subscriptions: Seats Paid vs Seats Used drives unused-licence detection.",
                "4. Processes: Tasks Per Month x Minutes Per Task x Hourly Cost / 60 = monthly manual cost.",
                "5. Overtime: one row per employee per month.",
                "6. Amounts in INR, numbers only (no commas or ₹ symbol).",
                "7. Error Rate can be 0.08 or 8%. Both are accepted.",
                "8. Upload the saved file at the Upload page. All findings are estimates.",
            ]
        })
        guide.to_excel(xw, sheet_name="Instructions", index=False)
        ws = xw.sheets["Instructions"]
        ws.column_dimensions["A"].width = 110
        ws.cell(row=1, column=1).fill = HEADER_FILL
        ws.cell(row=1, column=1).font = HEADER_FONT
    return buf.getvalue()


def _coerce_number(s: pd.Series) -> pd.Series:
    if s.dtype.kind in "if":
        return s.fillna(0)
    cleaned = (s.astype(str)
                 .str.replace(r"[₹,\s]", "", regex=True)
                 .str.replace(r"^$|^nan$|^None$", "0", regex=True))
    pct = cleaned.str.endswith("%")
    out = pd.to_numeric(cleaned.str.rstrip("%"), errors="coerce").fillna(0.0)
    out = out.where(~pct, out / 100.0)
    return out


def _coerce_date(s: pd.Series) -> pd.Series:
    out = pd.to_datetime(s, errors="coerce", dayfirst=True)
    return out


def _map_columns(df: pd.DataFrame, expected: list[str]) -> pd.DataFrame:
    lookup = {_norm(c): c for c in df.columns}
    out = pd.DataFrame(index=df.index)
    for col in expected:
        src = lookup.get(_norm(col))
        out[col] = df[src] if src is not None else None
    return out


def _clean(key: str, df: pd.DataFrame) -> pd.DataFrame:
    sheet = KEY_TO_SHEET[key]
    df = _map_columns(df, SHEETS[sheet])
    df = df.dropna(how="all")
    num_cols = {
        "expenses": ["Amount"],
        "subscriptions": ["Cost", "Seats Paid", "Seats Used"],
        "processes": ["Tasks Per Month", "Minutes Per Task", "Employees Involved", "Hourly Cost", "Error Rate"],
        "overtime": ["Overtime Hours", "Overtime Rate"],
    }[key]
    for c in num_cols:
        df[c] = _coerce_number(df[c])
    for c in ("Date", "Last Activity Date", "Renewal Date"):
        if c in df.columns:
            df[c] = _coerce_date(df[c])
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].apply(lambda v: v.strip() if isinstance(v, str) else v)
    return df.reset_index(drop=True)


def read_upload(content: bytes, filename: str) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """Parse an uploaded .xlsx/.csv into normalised frames. Returns (frames, warnings)."""
    warnings: list[str] = []
    frames: dict[str, pd.DataFrame] = {}
    name = (filename or "").lower()

    if name.endswith(".csv"):
        raw = pd.read_csv(io.BytesIO(content))
        key = _guess_sheet(raw)
        warnings.append(f"CSV detected — interpreted as '{KEY_TO_SHEET[key]}' data.")
        frames[key] = _clean(key, raw)
    elif name.endswith((".xlsx", ".xlsm", ".xls")):
        book = pd.read_excel(io.BytesIO(content), sheet_name=None)
        matched = set()
        for sheet_name, raw in book.items():
            if raw.empty:
                continue
            n = _norm(sheet_name)
            key = next((k for k, s in KEY_TO_SHEET.items() if _norm(s) == n), None)
            if key is None:
                key = _guess_sheet(raw)
                if key is None:
                    warnings.append(f"Sheet '{sheet_name}' not recognised — skipped.")
                    continue
                warnings.append(f"Sheet '{sheet_name}' matched to '{KEY_TO_SHEET[key]}' by its columns.")
            if key in matched:
                frames[key] = pd.concat([frames[key], _clean(key, raw)], ignore_index=True)
            else:
                frames[key] = _clean(key, raw)
                matched.add(key)
    else:
        raise ValueError("Unsupported file type. Please upload .xlsx or .csv")

    frames = {k: v for k, v in frames.items() if not v.empty}
    if not frames:
        raise ValueError("No usable rows found. Download the template and try again.")
    return frames, warnings


def _guess_sheet(df: pd.DataFrame) -> str | None:
    cols = {_norm(c) for c in df.columns}
    best, score = None, 0
    for key, sheet in KEY_TO_SHEET.items():
        expected = {_norm(c) for c in SHEETS[sheet]}
        hits = len(cols & expected)
        if hits > score:
            best, score = key, hits
    return best if score >= 3 else None


def frames_from_records(data: dict[str, list[dict]]) -> dict[str, pd.DataFrame]:
    out = {}
    for key, rows in data.items():
        if key in KEY_TO_SHEET and rows:
            out[key] = _clean(key, pd.DataFrame(rows))
    return out


def profile(frames: dict[str, pd.DataFrame]) -> dict:
    """Data-quality summary shown right after upload."""
    exp = frames.get("expenses", pd.DataFrame())
    subs = frames.get("subscriptions", pd.DataFrame())
    total_rows = int(sum(len(df) for df in frames.values()))
    issues: list[dict] = []

    missing_fields = 0
    for key, df in frames.items():
        for col in REQUIRED[key]:
            if col not in df.columns:
                continue
            blank = df[col].isna() | (df[col].astype(str).str.strip().isin(["", "nan", "None", "0"])
                                      if df[col].dtype == object else df[col].isna())
            n = int(blank.sum())
            if n:
                missing_fields += n
                issues.append({"level": "warning", "sheet": KEY_TO_SHEET[key],
                               "message": f"{n} row(s) missing '{col}'"})

    dup_rows = 0
    if not exp.empty:
        key_cols = [c for c in ("Date", "Vendor", "Amount", "Invoice Number") if c in exp.columns]
        dup_rows = int(exp.duplicated(subset=key_cols, keep="first").sum())
        if dup_rows:
            issues.append({"level": "warning", "sheet": "Expenses",
                           "message": f"{dup_rows} exactly identical expense row(s) found"})

    total_spend = float(exp["Amount"].sum()) if not exp.empty else 0.0
    months = 1
    if not exp.empty and exp["Date"].notna().any():
        months = max(1, exp["Date"].dt.to_period("M").nunique())
    unrecognised = 0
    if not exp.empty:
        unrecognised = int((exp["Category"].isna() | (exp["Category"].astype(str).str.strip() == "")).sum())
        if unrecognised:
            issues.append({"level": "info", "sheet": "Expenses",
                           "message": f"{unrecognised} row(s) have no Category — grouped as 'Uncategorised'"})
    if subs.empty:
        issues.append({"level": "info", "sheet": "Subscriptions",
                       "message": "No subscription data — licence/seat findings will be skipped"})

    return {
        "total_rows": total_rows,
        "rows_by_sheet": {KEY_TO_SHEET[k]: int(len(v)) for k, v in frames.items()},
        "total_spend": round(total_spend, 2),
        "months_covered": months,
        "avg_monthly_spend": round(total_spend / months, 2),
        "missing_fields": missing_fields,
        "duplicate_rows": dup_rows,
        "unrecognised_vendors": unrecognised,
        "issues": issues,
    }


def to_jsonable(value):
    if isinstance(value, (pd.Timestamp, datetime, date)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return value
