"""Analysis engine: runs every registered rule and builds dashboard aggregates."""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from . import rules as R

# Rules run in this order so that one line of spend is never counted twice:
# a tool retired by consolidation is not also billed as "unused seats", etc.
RULE_ORDER = [
    "duplicate_payment", "duplicate_software", "high_cost_low_usage",
    "unused_seats", "upcoming_renewal", "price_increase", "manual_work", "overtime",
]


def _monthly_expense_total(exp: pd.DataFrame) -> tuple[float, int]:
    if exp is None or exp.empty:
        return 0.0, 1
    total = float(exp["Amount"].sum())
    months = 1
    if exp["Date"].notna().any():
        months = max(1, int(exp["Date"].dt.to_period("M").nunique()))
    return total, months


def analyse(frames: dict[str, pd.DataFrame], config: dict | None = None,
            company: str = "Your Company") -> dict:
    cfg = {**R.DEFAULT_CONFIG, **(config or {})}
    findings: list[dict] = []
    rule_log = []
    ctx: dict = {}
    for name, fn in sorted(R.REGISTRY, key=lambda nf: RULE_ORDER.index(nf[0])
                           if nf[0] in RULE_ORDER else 99):
        try:
            got = fn(frames, cfg, ctx) or []
        except Exception as exc:  # a broken rule must never kill the report
            rule_log.append({"rule": name, "status": "error", "detail": str(exc), "findings": 0})
            continue
        rule_log.append({"rule": name, "status": "ok", "findings": len(got)})
        findings.extend(got)

    findings.sort(key=lambda f: (-f["monthly_waste"], -f["priority_score"]))
    for i, f in enumerate(findings, 1):
        f["rank"] = i

    exp = frames.get("expenses", pd.DataFrame())
    total_spend, months = _monthly_expense_total(exp)
    monthly_spend = total_spend / months

    subs = frames.get("subscriptions", pd.DataFrame())
    subs_monthly = 0.0
    if subs is not None and not subs.empty:
        subs_monthly = float(sum(R.monthly(c, bc) for c, bc in zip(subs["Cost"], subs["Billing Cycle"])))

    monthly_waste = float(sum(f["monthly_waste"] for f in findings))
    top5 = sum(f["monthly_waste"] for f in findings[:5])

    kpis = {
        "company": company,
        "analysis_date": date.today().strftime("%d %b %Y"),
        "total_spend_uploaded": round(total_spend, 2),
        "months_covered": months,
        "monthly_spend": round(monthly_spend, 2),
        "subscription_monthly_spend": round(subs_monthly, 2),
        "monthly_waste": round(monthly_waste, 2),
        "annual_savings": round(monthly_waste * 12, 2),
        "waste_pct": round((monthly_waste / monthly_spend * 100) if monthly_spend else 0, 1),
        "findings_count": len(findings),
        "critical_count": sum(1 for f in findings if f["priority"] == "Critical"),
        "high_count": sum(1 for f in findings if f["priority"] == "High"),
        "top5_monthly": round(top5, 2),
        "top5_annual": round(top5 * 12, 2),
    }

    return {
        "kpis": kpis,
        "findings": findings,
        "charts": build_charts(frames, findings, months),
        "rule_log": rule_log,
        "config": cfg,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def build_charts(frames: dict[str, pd.DataFrame], findings: list[dict], months: int) -> dict:
    exp = frames.get("expenses", pd.DataFrame())
    charts: dict = {"spend_by_category": [], "spend_by_department": [], "top_vendors": [],
                    "monthly_trend": [], "waste_heatmap": [], "savings_by_priority": [],
                    "waste_by_category": []}

    if exp is not None and not exp.empty:
        e = exp.copy()
        e["Category"] = e["Category"].fillna("Uncategorised").replace("", "Uncategorised")
        e["Department"] = e["Department"].fillna("Unassigned").replace("", "Unassigned")

        cat = e.groupby("Category")["Amount"].sum().sort_values(ascending=False)
        charts["spend_by_category"] = [{"label": k, "value": round(v / months, 2)} for k, v in cat.items()]

        dep = e.groupby("Department")["Amount"].sum().sort_values(ascending=False)
        charts["spend_by_department"] = [{"label": k, "value": round(v / months, 2)} for k, v in dep.items()]

        ven = e.groupby("Vendor")["Amount"].sum().sort_values(ascending=False).head(10)
        charts["top_vendors"] = [{"label": k, "value": round(v / months, 2)} for k, v in ven.items()]

        if e["Date"].notna().any():
            tr = e.dropna(subset=["Date"]).groupby(e["Date"].dt.to_period("M"))["Amount"].sum().sort_index()
            charts["monthly_trend"] = [{"label": str(k), "value": round(float(v), 2)} for k, v in tr.items()]

        # heatmap: department x finding-category waste
        depts = list(dep.index)[:8]
    else:
        depts = sorted({f["department"] for f in findings if f["department"] not in ("—", "Multiple")})[:8]

    cats = ["Duplicate Payment", "Unused License", "Duplicate Software", "Price Increase",
            "Manual Work", "Overtime", "Unused Resource"]
    grid = []
    for d in depts:
        for c in cats:
            v = sum(f["monthly_waste"] for f in findings
                    if f["department"] == d and f["category"] == c)
            grid.append({"department": d, "category": c, "value": round(v, 2)})
    charts["waste_heatmap"] = {"departments": depts, "categories": cats, "cells": grid}

    pr_order = ["Critical", "High", "Medium", "Low"]
    charts["savings_by_priority"] = [
        {"label": p,
         "value": round(sum(f["monthly_waste"] for f in findings if f["priority"] == p), 2),
         "count": sum(1 for f in findings if f["priority"] == p)}
        for p in pr_order
    ]
    charts["waste_by_category"] = [
        {"label": c, "value": round(sum(f["monthly_waste"] for f in findings if f["category"] == c), 2)}
        for c in cats
        if any(f["category"] == c for f in findings)
    ]
    return charts
