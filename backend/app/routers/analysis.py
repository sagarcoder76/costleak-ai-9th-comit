"""Cost-leak analysis endpoints (tenant-scoped version of the v1 API)."""
from __future__ import annotations

import json

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from .. import db, excel_io, report, sample_data
from ..analysis import rules as R
from ..analysis.engine import analyse
from ..core.deps import company_user, enforce_limit

router = APIRouter(prefix="/api", tags=["cost-leak"])
MAX_BYTES = 15 * 1024 * 1024


def _jsonable(obj):
    return json.loads(json.dumps(obj, default=str))


def _save(user: dict, frames, company_name: str, source: str, filename: str | None):
    prof = excel_io.profile(frames)
    result = analyse(frames, company=company_name)
    aid = db.new_id("ana_")
    db.insert("analyses", {
        "id": aid, "company_id": user["company_id"], "company": company_name,
        "source": source, "filename": filename, "created_at": db.now_iso(),
        "profile_json": json.dumps(prof, default=str),
        "subs_json": json.dumps(
            frames["subscriptions"].to_dict("records") if "subscriptions" in frames else [],
            default=str),
        "result_json": json.dumps(_jsonable(result), default=str),
    })
    db.track("analysis_run", user["company_id"], user["id"],
             {"source": source, "findings": result["kpis"]["findings_count"],
              "monthly_waste": result["kpis"]["monthly_waste"]})
    return {"analysis_id": aid, "company": company_name, "profile": prof,
            "result": _jsonable(result)}


@router.get("/template")
def template(sample: bool = True):
    data = excel_io.build_workbook(with_sample=sample)
    name = "CostLeak_Template_with_sample.xlsx" if sample else "CostLeak_Template.xlsx"
    return Response(data,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.post("/upload")
async def upload(file: UploadFile = File(...), user: dict = Depends(company_user)):
    enforce_limit(user["company_id"], "analyses_per_month")
    content = await file.read()
    if not content:
        raise HTTPException(400, "The uploaded file is empty.")
    if len(content) > MAX_BYTES:
        raise HTTPException(413, "File too large. Maximum size is 15 MB.")
    try:
        frames, warnings = excel_io.read_upload(content, file.filename or "")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(400, f"Could not read this file ({type(e).__name__}). "
                                 f"Please use the CostLeak template.")
    company = db.q1("SELECT name FROM companies WHERE id=?", (user["company_id"],))
    payload = _save(user, frames, company["name"], "upload", file.filename)
    payload["warnings"] = warnings
    return payload


@router.post("/demo")
def demo(user: dict = Depends(company_user)):
    frames = excel_io.frames_from_records(sample_data.sample_dataset())
    payload = _save(user, frames, sample_data.COMPANY_NAME, "demo", "sample_nexa_solutions.xlsx")
    payload["warnings"] = []
    return payload


def _hydrate(row: dict) -> dict:
    result = json.loads(row["result_json"])
    states = db.q("SELECT * FROM finding_state WHERE analysis_id=?", (row["id"],))
    smap = {s["finding_id"]: s for s in states}
    for f in result.get("findings", []):
        s = smap.get(f["id"])
        if s:
            f["status"] = s["status"] or f["status"]
            f["owner"] = s["owner"] or f["owner"]
            f["notes"] = json.loads(s["notes_json"] or "[]")
    return {"id": row["id"], "company": row["company"], "source": row["source"],
            "filename": row["filename"], "created_at": row["created_at"],
            "profile": json.loads(row["profile_json"]), "result": result}


@router.get("/analyses")
def list_analyses(user: dict = Depends(company_user)):
    return {"analyses": db.q(
        "SELECT id, company, source, filename, created_at FROM analyses"
        " WHERE company_id=? ORDER BY created_at DESC LIMIT 30", (user["company_id"],))}


@router.get("/analysis/latest")
def latest(user: dict = Depends(company_user)):
    row = db.q1("SELECT * FROM analyses WHERE company_id=? ORDER BY created_at DESC LIMIT 1",
                (user["company_id"],))
    if not row:
        raise HTTPException(404, "No analysis yet.")
    return _hydrate(row)


@router.get("/analysis/{aid}")
def get_analysis(aid: str, user: dict = Depends(company_user)):
    row = db.q1("SELECT * FROM analyses WHERE id=? AND company_id=?", (aid, user["company_id"]))
    if not row:
        raise HTTPException(404, "Analysis not found.")
    return _hydrate(row)


class FindingUpdate(BaseModel):
    status: str | None = None
    owner: str | None = None
    note: str | None = None


@router.patch("/analysis/{aid}/finding/{fid}")
def patch_finding(aid: str, fid: str, body: FindingUpdate, user: dict = Depends(company_user)):
    allowed = {"Identified", "In Review", "Approved", "Actioned", "Verified"}
    if body.status and body.status not in allowed:
        raise HTTPException(400, f"Status must be one of {sorted(allowed)}")
    if not db.q1("SELECT id FROM analyses WHERE id=? AND company_id=?", (aid, user["company_id"])):
        raise HTTPException(404, "Analysis not found.")
    row = db.q1("SELECT * FROM finding_state WHERE analysis_id=? AND finding_id=?", (aid, fid))
    notes = json.loads(row["notes_json"]) if row and row["notes_json"] else []
    if body.note:
        notes.append({"text": body.note, "at": db.now_iso()[:16].replace("T", " ")})
    status = body.status or (row or {}).get("status")
    owner = body.owner or (row or {}).get("owner")
    db.ex("INSERT INTO finding_state (analysis_id, finding_id, status, owner, notes_json, updated_at)"
          " VALUES (?,?,?,?,?,?) ON CONFLICT(analysis_id, finding_id) DO UPDATE SET"
          " status=excluded.status, owner=excluded.owner, notes_json=excluded.notes_json,"
          " updated_at=excluded.updated_at",
          (aid, fid, status, owner, json.dumps(notes), db.now_iso()))
    db.track("finding_updated", user["company_id"], user["id"], {"status": status})
    return {"status": status, "owner": owner, "notes": notes}


class ProcessIn(BaseModel):
    process_name: str = "Manual process"
    department: str = "—"
    tasks_per_month: float = 0
    minutes_per_task: float = 0
    employees: float = 1
    hourly_cost: float = 0
    error_rate: float = 0
    feasibility: str = "Medium"


@router.post("/calculator/manual-process")
def manual_calc(body: ProcessIn, user: dict = Depends(company_user)):
    if body.tasks_per_month <= 0 or body.minutes_per_task <= 0 or body.hourly_cost <= 0:
        raise HTTPException(400, "Tasks per month, minutes per task and hourly cost must all be "
                                 "greater than zero.")
    df = pd.DataFrame([{
        "Process Name": body.process_name, "Department": body.department,
        "Tasks Per Month": body.tasks_per_month, "Minutes Per Task": body.minutes_per_task,
        "Employees Involved": body.employees, "Hourly Cost": body.hourly_cost,
        "Error Rate": body.error_rate, "Automation Feasibility": body.feasibility, "Notes": "",
    }])
    findings = R.manual_work({"processes": df}, R.DEFAULT_CONFIG, {})
    err = body.error_rate / 100 if body.error_rate > 1 else body.error_rate
    base = body.tasks_per_month * body.minutes_per_task * body.hourly_cost / 60
    cost = base * (1 + err)
    pct = R.DEFAULT_CONFIG["automation_savings"].get(body.feasibility.title(), 0.40)
    db.track("calculator_used", user["company_id"], user["id"])
    return _jsonable({
        "monthly_manual_cost": round(cost, 2), "annual_manual_cost": round(cost * 12, 2),
        "hours_per_month": round(body.tasks_per_month * body.minutes_per_task / 60, 1),
        "automation_pct": pct, "monthly_saving": round(cost * pct, 2),
        "annual_saving": round(cost * pct * 12, 2),
        "finding": findings[0] if findings else None,
    })


class SubIn(BaseModel):
    software: str
    vendor: str = "—"
    cost: float = 0
    billing_cycle: str = "Monthly"
    seats_paid: float = 0
    seats_used: float = 0
    last_activity: str | None = None
    renewal_date: str | None = None
    department: str = "—"
    owner: str = "Unassigned"


@router.post("/analyze/subscriptions")
def analyse_subs(items: list[SubIn], user: dict = Depends(company_user)):
    if not items:
        raise HTTPException(400, "Add at least one subscription.")
    rows = [{"Software": i.software, "Vendor": i.vendor, "Cost": i.cost,
             "Billing Cycle": i.billing_cycle, "Seats Paid": i.seats_paid,
             "Seats Used": i.seats_used, "Last Activity Date": i.last_activity,
             "Renewal Date": i.renewal_date, "Department": i.department,
             "Owner": i.owner, "Notes": ""} for i in items]
    frames = excel_io.frames_from_records({"subscriptions": rows})
    db.track("subscription_analyzer_used", user["company_id"], user["id"])
    return _jsonable(analyse(frames, company="Subscription Analyzer"))


@router.get("/report/{aid}.pdf")
def pdf_report(aid: str, user: dict = Depends(company_user)):
    row = db.q1("SELECT * FROM analyses WHERE id=? AND company_id=?", (aid, user["company_id"]))
    if not row:
        raise HTTPException(404, "Analysis not found.")
    pdf = report.build_pdf(_hydrate(row))
    safe = "".join(ch for ch in row["company"] if ch.isalnum() or ch in " -_").strip().replace(" ", "_")
    db.track("report_exported", user["company_id"], user["id"])
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="CostLeak_Report_{safe or "company"}.pdf"'})
