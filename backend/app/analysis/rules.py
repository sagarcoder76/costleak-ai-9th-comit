"""Rule-based cost-leak detection.

Every rule is a plain function registered with @rule. It receives the parsed
frames plus a config dict and returns a list of Finding dicts. To add a new
detection rule, write a function and decorate it — nothing else to wire up.
"""
from __future__ import annotations

import math
from datetime import date

import pandas as pd

from .explain import explain

# ---------------------------------------------------------------- registry --
REGISTRY: list[tuple[str, callable]] = []


def rule(name: str):
    def deco(fn):
        REGISTRY.append((name, fn))
        return fn
    return deco


DEFAULT_CONFIG = {
    "duplicate_window_days": 20,
    "duplicate_amount_tolerance": 0.02,     # 2%
    "price_increase_threshold": 0.20,       # 20%
    "high_cost_subscription": 10000,        # INR / month
    "low_usage_ratio": 0.50,                # <50% seats used = low usage
    "inactive_days": 30,                    # no login in N days
    "renewal_window_days": 45,
    "overtime_month_threshold": 25,         # hours / employee / month
    "overtime_repeat_months": 3,
    "automation_savings": {"High": 0.60, "Medium": 0.40, "Low": 0.20},
    "recoverable_duplicate_ratio": 1.0,     # duplicates are 100% recoverable once
    "consolidation_savings": 1.0,
    "overlap_usage_ceiling": 0.60,    # runner-up tool must be <60% utilised to suggest dropping it           # drop the cheaper overlapping tool
}

OVERLAP_GROUPS: list[dict] = [
    {"group": "Design & creative", "tools": ["canva", "adobe express", "crello", "visme"]},
    {"group": "Video conferencing", "tools": ["zoom", "google meet", "webex", "gotomeeting"]},
    {"group": "Team chat", "tools": ["slack", "microsoft teams", "ms teams", "google chat"]},
    {"group": "Project management", "tools": ["trello", "asana", "jira", "monday", "clickup", "basecamp"]},
    {"group": "Cloud storage", "tools": ["google drive", "dropbox", "onedrive", "box.com", "box business"]},
    {"group": "Helpdesk / support", "tools": ["freshdesk", "zendesk", "intercom", "helpscout"]},
    {"group": "E-signature", "tools": ["docusign", "adobe sign", "zoho sign", "signeasy"]},
    {"group": "Docs & wiki", "tools": ["notion", "confluence", "coda"]},
    {"group": "CRM", "tools": ["salesforce", "hubspot", "zoho crm", "freshsales", "pipedrive"]},
]

CRITICAL_CATEGORIES = {"Duplicate Payment"}


# ------------------------------------------------------------------ helpers -
def monthly(cost: float, cycle) -> float:
    c = str(cycle or "Monthly").strip().lower()
    if c.startswith("year") or c in ("annual", "annually", "yearly", "pa"):
        return cost / 12.0
    if c.startswith("quarter"):
        return cost / 3.0
    if c.startswith("half") or "semi" in c:
        return cost / 6.0
    if c.startswith("week"):
        return cost * 52 / 12.0
    if c.startswith("one") or c in ("onetime", "one time"):
        return 0.0
    return float(cost)


def priority_for(monthly_waste: float, category: str) -> str:
    if category in CRITICAL_CATEGORIES or monthly_waste > 50000:
        return "Critical"
    if monthly_waste >= 10000:
        return "High"
    if monthly_waste >= 2000:
        return "Medium"
    return "Low"


_EASE = {"Duplicate Payment": 1.0, "Unused License": 0.9, "Duplicate Software": 0.7,
         "Price Increase": 0.6, "Unused Resource": 0.7, "Manual Work": 0.4, "Overtime": 0.35}
_CONF = {"High": 1.0, "Medium": 0.7, "Low": 0.45}


def priority_score(monthly_waste: float, confidence: str, category: str, recurring: bool) -> float:
    impact = math.log10(max(monthly_waste, 1)) / 6.0
    return round(100 * (
        0.55 * min(impact, 1.0)
        + 0.20 * _CONF.get(confidence, 0.7)
        + 0.15 * _EASE.get(category, 0.5)
        + 0.10 * (1.0 if recurring else 0.3)
    ), 1)


def make_finding(*, fid, title, category, monthly_waste, confidence, evidence,
                 action, department="—", vendor="—", recurring=True, how, owner="Unassigned"):
    monthly_waste = round(float(monthly_waste), 2)
    prio = priority_for(monthly_waste, category)
    f = {
        "id": fid,
        "title": title,
        "category": category,
        "department": department,
        "vendor": vendor,
        "monthly_waste": monthly_waste,
        "annual_waste": round(monthly_waste * 12, 2),
        "confidence": confidence,
        "priority": prio,
        "priority_score": priority_score(monthly_waste, confidence, category, recurring),
        "recommended_action": action,
        "owner": owner,
        "status": "Identified",
        "notes": [],
        "evidence": evidence,
        "calculation": how,
        "recurring": recurring,
    }
    f["explanation"] = explain(f)
    return f


def _fmt(n: float) -> str:
    """Indian-format currency for text inside findings."""
    n = round(float(n))
    s = str(abs(int(n)))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return ("-" if n < 0 else "") + "₹" + s


def _claim(ctx, software: str, by: str) -> bool:
    """One subscription produces at most one waste finding (no double counting)."""
    claims = ctx.setdefault("claimed_software", {})
    key = str(software).strip().lower()
    if key in claims:
        return False
    claims[key] = by
    return True


def _claimed(ctx, software: str) -> bool:
    return str(software).strip().lower() in ctx.get("claimed_software", {})


# -------------------------------------------------------------------- rules -
@rule("duplicate_payment")
def duplicate_payments(frames, cfg, ctx):
    df = frames.get("expenses")
    if df is None or df.empty:
        return []
    out = []
    win = pd.Timedelta(days=cfg["duplicate_window_days"])
    tol = cfg["duplicate_amount_tolerance"]
    d = df.dropna(subset=["Date"]).sort_values("Date")
    for vendor, grp in d.groupby(d["Vendor"].astype(str).str.strip().str.lower()):
        rows = grp.to_dict("records")
        used = set()
        for i in range(len(rows)):
            if i in used:
                continue
            cluster = [rows[i]]
            for j in range(i + 1, len(rows)):
                if j in used:
                    continue
                a, b = rows[i]["Amount"], rows[j]["Amount"]
                if a <= 0:
                    continue
                if abs(a - b) / a <= tol and (rows[j]["Date"] - rows[i]["Date"]) <= win:
                    cluster.append(rows[j])
                    used.add(j)
            if len(cluster) < 2:
                continue
            used.add(i)
            extra = sum(r["Amount"] for r in cluster[1:])
            same_invoice = len({str(r.get("Invoice Number")) for r in cluster}) == 1
            days = (cluster[-1]["Date"] - cluster[0]["Date"]).days
            conf = "High" if (same_invoice or days <= 10) else "Medium"
            name = str(cluster[0]["Vendor"])
            per = ctx.setdefault("dup_excess", {})
            for r in cluster[1:]:
                k = (str(r["Vendor"]).strip().lower(), pd.Timestamp(r["Date"]).to_period("M"))
                per[k] = per.get(k, 0.0) + float(r["Amount"])
            out.append(make_finding(
                fid=f"DUP-{len(out)+1:02d}",
                title=f"Possible duplicate payment to {name} — {len(cluster)} payments of ~{_fmt(cluster[0]['Amount'])} within {max(days,1)} days",
                category="Duplicate Payment",
                monthly_waste=extra * cfg["recoverable_duplicate_ratio"],
                confidence=conf,
                department=str(cluster[0].get("Department") or "—"),
                vendor=name,
                recurring=False,
                evidence=[{
                    "Date": pd.Timestamp(r["Date"]).strftime("%d %b %Y"),
                    "Vendor": str(r["Vendor"]),
                    "Invoice": str(r.get("Invoice Number") or "—"),
                    "Department": str(r.get("Department") or "—"),
                    "Amount": round(float(r["Amount"]), 2),
                    "Note": str(r.get("Notes") or ""),
                } for r in cluster],
                how=(f"{len(cluster)} payments to the same vendor within {cfg['duplicate_window_days']} days, "
                     f"amounts matching within {int(tol*100)}%. Excess over the first payment = "
                     f"{_fmt(extra)} recoverable."),
                action=f"Pull the invoices for {name}, confirm with AP, and raise a refund/credit-note request for {_fmt(extra)}.",
            ))
    return out


@rule("duplicate_software")
def overlapping_software(frames, cfg, ctx):
    subs = frames.get("subscriptions")
    if subs is None or subs.empty:
        return []
    subs = subs.copy()
    subs["_m"] = [monthly(c, bc) for c, bc in zip(subs["Cost"], subs["Billing Cycle"])]
    out = []
    for group in OVERLAP_GROUPS:
        hits = []
        for _, r in subs.iterrows():
            text = f"{r['Software']} {r.get('Vendor') or ''}".lower()
            if any(t in text for t in group["tools"]) and r["_m"] > 0:
                hits.append(r)
        if len(hits) < 2:
            continue
        hits.sort(key=lambda r: r["_m"], reverse=True)
        def _util(r):
            paid = float(r["Seats Paid"] or 0)
            return (float(r["Seats Used"] or 0) / paid) if paid else 1.0
        # Only recommend consolidation when the runner-up tools are genuinely under-used;
        # two well-adopted tools may be serving different real needs.
        drop = [r for r in hits[1:] if _util(r) < cfg["overlap_usage_ceiling"]]
        if not drop:
            continue
        hits = [hits[0]] + drop
        saving = sum(r["_m"] for r in drop) * cfg["consolidation_savings"]
        if saving <= 0:
            continue
        keep = hits[0]
        for r in hits:
            _claim(ctx, r["Software"], "duplicate_software")
        usage = {str(r["Software"]): (float(r["Seats Used"]) / float(r["Seats Paid"])
                                      if float(r["Seats Paid"] or 0) else 0) for r in hits}
        conf = "High" if min(usage.values()) < 0.5 else "Medium"
        out.append(make_finding(
            fid=f"OVL-{len(out)+1:02d}",
            title=f"Overlapping {group['group'].lower()} tools: {', '.join(str(r['Software']) for r in hits)}",
            category="Duplicate Software",
            monthly_waste=saving,
            confidence=conf,
            department=str(keep.get("Department") or "—"),
            vendor=", ".join(sorted({str(r.get("Vendor") or "—") for r in hits})),
            evidence=[{
                "Software": str(r["Software"]),
                "Vendor": str(r.get("Vendor") or "—"),
                "Monthly Cost": round(float(r["_m"]), 2),
                "Seats Paid": int(r["Seats Paid"] or 0),
                "Seats Used": int(r["Seats Used"] or 0),
                "Utilisation": f"{usage[str(r['Software'])]*100:.0f}%",
                "Department": str(r.get("Department") or "—"),
            } for r in hits],
            how=(f"{len(hits)} tools in the '{group['group']}' category are paid for simultaneously. "
                 f"Keeping the most-used/most-expensive one ({keep['Software']}, {_fmt(keep['_m'])}/mo) and "
                 f"retiring the rest saves {_fmt(saving)}/month."),
            action=(f"Standardise {group['group'].lower()} on {keep['Software']}. Migrate users off "
                    f"{', '.join(str(r['Software']) for r in drop)} before their next renewal and cancel."),
        ))
    return out


@rule("unused_seats")
def unused_seats(frames, cfg, ctx):
    subs = frames.get("subscriptions")
    if subs is None or subs.empty:
        return []
    out = []
    for _, r in subs.iterrows():
        paid, used = float(r["Seats Paid"] or 0), float(r["Seats Used"] or 0)
        m = monthly(float(r["Cost"] or 0), r["Billing Cycle"])
        if paid <= 0 or m <= 0 or _claimed(ctx, r["Software"]):
            continue
        unused = max(paid - used, 0)
        if unused < 1:
            continue
        if not _claim(ctx, r["Software"], "unused_seats"):
            continue
        per_seat = m / paid
        waste = unused * per_seat
        if waste < 500:
            continue
        util = used / paid
        conf = "High" if util < 0.6 else "Medium"
        out.append(make_finding(
            fid=f"SEAT-{len(out)+1:02d}",
            title=f"{int(unused)} unused seats on {r['Software']} — {_fmt(waste)}/month",
            category="Unused License",
            monthly_waste=waste,
            confidence=conf,
            department=str(r.get("Department") or "—"),
            vendor=str(r.get("Vendor") or "—"),
            owner=str(r.get("Owner") or "Unassigned"),
            evidence=[{
                "Software": str(r["Software"]),
                "Seats Paid": int(paid), "Seats Used": int(used), "Unused": int(unused),
                "Utilisation": f"{util*100:.0f}%",
                "Cost per Seat / month": round(per_seat, 2),
                "Monthly Cost": round(m, 2),
                "Last Activity": pd.Timestamp(r["Last Activity Date"]).strftime("%d %b %Y")
                                 if pd.notna(r.get("Last Activity Date")) else "—",
                "Renewal": pd.Timestamp(r["Renewal Date"]).strftime("%d %b %Y")
                           if pd.notna(r.get("Renewal Date")) else "—",
            }],
            how=(f"Unused seats = {int(paid)} paid − {int(used)} used = {int(unused)}. "
                 f"Cost per seat = {_fmt(m)} ÷ {int(paid)} = {_fmt(per_seat)}. "
                 f"Monthly waste = {int(unused)} × {_fmt(per_seat)} = {_fmt(waste)}; annual = {_fmt(waste*12)}."),
            action=(f"Ask {r.get('Owner') or 'the tool owner'} to confirm active users, then downgrade "
                    f"{r['Software']} to {int(used)+max(1,int(unused*0.1))} seats at the next renewal."),
        ))
    return out


@rule("price_increase")
def price_increase(frames, cfg, ctx):
    df = frames.get("expenses")
    if df is None or df.empty:
        return []
    d = df.dropna(subset=["Date"]).copy()
    if d.empty:
        return []
    d["_m"] = d["Date"].dt.to_period("M")
    piv = d.groupby(["Vendor", "_m"])["Amount"].sum().reset_index()
    dup = ctx.get("dup_excess", {})
    if dup:
        piv["Amount"] = [a - dup.get((str(v).strip().lower(), m), 0.0)
                         for v, m, a in zip(piv["Vendor"], piv["_m"], piv["Amount"])]
    out = []
    thr = cfg["price_increase_threshold"]
    for vendor, grp in piv.groupby("Vendor"):
        grp = grp.sort_values("_m")
        if len(grp) < 3:
            continue
        current = float(grp.iloc[-1]["Amount"])
        baseline = float(grp.iloc[:-1]["Amount"].mean())
        if baseline <= 0:
            continue
        delta = (current - baseline) / baseline
        if delta < thr:
            continue
        extra = current - baseline
        if extra < 1000:
            continue
        dept = str(d[d["Vendor"] == vendor]["Department"].mode().iloc[0]) if not d[d["Vendor"] == vendor]["Department"].dropna().empty else "—"
        out.append(make_finding(
            fid=f"PRC-{len(out)+1:02d}",
            title=f"{vendor} cost increased {delta*100:.0f}% vs its {len(grp)-1}-month average",
            category="Price Increase",
            monthly_waste=extra,
            confidence="High" if len(grp) >= 4 else "Medium",
            department=dept, vendor=str(vendor),
            evidence=[{"Month": str(r["_m"]), "Spend": round(float(r["Amount"]), 2)}
                      for _, r in grp.iterrows()],
            how=(f"Latest month {_fmt(current)} vs prior {len(grp)-1}-month average {_fmt(baseline)} "
                 f"= +{delta*100:.1f}% ({_fmt(extra)}/month above baseline). Threshold is {int(thr*100)}%."),
            action=(f"Review the {vendor} invoice line-by-line for new SKUs or usage spikes, and open a "
                    f"renewal/rate negotiation before the next billing cycle."),
        ))
    return out


@rule("high_cost_low_usage")
def high_cost_low_usage(frames, cfg, ctx):
    subs = frames.get("subscriptions")
    if subs is None or subs.empty:
        return []
    out = []
    today = pd.Timestamp(date.today())
    for _, r in subs.iterrows():
        m = monthly(float(r["Cost"] or 0), r["Billing Cycle"])
        paid, used = float(r["Seats Paid"] or 0), float(r["Seats Used"] or 0)
        util = (used / paid) if paid else 1.0
        inactive_days = None
        if pd.notna(r.get("Last Activity Date")):
            inactive_days = int((today - pd.Timestamp(r["Last Activity Date"])).days)
        stale = inactive_days is not None and inactive_days >= cfg["inactive_days"]
        if m < cfg["high_cost_subscription"] or (util >= cfg["low_usage_ratio"] and not stale):
            continue
        if _claimed(ctx, r["Software"]):
            continue
        waste = m * (1 - util) if not stale else m
        if waste < 1000 or not _claim(ctx, r["Software"], "high_cost_low_usage"):
            continue
        out.append(make_finding(
            fid=f"LOWU-{len(out)+1:02d}",
            title=(f"High-cost, low-usage subscription: {r['Software']} "
                   f"({_fmt(m)}/mo, {util*100:.0f}% seats active)"),
            category="Unused Resource",
            monthly_waste=waste,
            confidence="High" if stale else "Medium",
            department=str(r.get("Department") or "—"),
            vendor=str(r.get("Vendor") or "—"),
            owner=str(r.get("Owner") or "Unassigned"),
            evidence=[{
                "Software": str(r["Software"]), "Monthly Cost": round(m, 2),
                "Seats Paid": int(paid), "Seats Used": int(used),
                "Utilisation": f"{util*100:.0f}%",
                "Days since last activity": inactive_days if inactive_days is not None else "—",
                "Renewal": pd.Timestamp(r["Renewal Date"]).strftime("%d %b %Y")
                           if pd.notna(r.get("Renewal Date")) else "—",
                "Notes": str(r.get("Notes") or ""),
            }],
            how=(f"Subscription exceeds the {_fmt(cfg['high_cost_subscription'])}/month review threshold. "
                 + (f"No activity for {inactive_days} days → treated as fully recoverable ({_fmt(waste)}/mo)."
                    if stale else
                    f"Waste = monthly cost × (1 − utilisation) = {_fmt(m)} × (1 − {util:.2f}) = {_fmt(waste)}.")),
            action=(f"Run a 2-week usage audit on {r['Software']}. If adoption stays below "
                    f"{int(cfg['low_usage_ratio']*100)}%, cancel or move to a lower tier at renewal."),
        ))
    return out


@rule("upcoming_renewal")
def upcoming_renewals(frames, cfg, ctx):
    subs = frames.get("subscriptions")
    if subs is None or subs.empty:
        return []
    today = pd.Timestamp(date.today())
    window = cfg["renewal_window_days"]
    rows = []
    for _, r in subs.iterrows():
        if pd.isna(r.get("Renewal Date")):
            continue
        days = int((pd.Timestamp(r["Renewal Date"]) - today).days)
        if not (0 <= days <= window):
            continue
        paid, used = float(r["Seats Paid"] or 0), float(r["Seats Used"] or 0)
        util = (used / paid) if paid else 1.0
        if util >= 0.8:
            continue
        if _claimed(ctx, r["Software"]):
            continue
        rows.append((r, days, util, monthly(float(r["Cost"] or 0), r["Billing Cycle"])))
    if not rows:
        return []
    waste = sum(m * (1 - u) for _, _, u, m in rows)
    rows.sort(key=lambda x: x[1])
    return [make_finding(
        fid="REN-01",
        title=f"{len(rows)} under-used subscriptions renew in the next {window} days — act before auto-renewal",
        category="Unused Resource",
        monthly_waste=waste,
        confidence="Medium",
        department="Multiple",
        vendor=", ".join(sorted({str(r.get("Vendor") or "—") for r, _, _, _ in rows})[:5]),
        evidence=[{
            "Software": str(r["Software"]),
            "Renewal": pd.Timestamp(r["Renewal Date"]).strftime("%d %b %Y"),
            "Days left": days,
            "Monthly Cost": round(m, 2),
            "Utilisation": f"{u*100:.0f}%",
            "Owner": str(r.get("Owner") or "Unassigned"),
        } for r, days, u, m in rows],
        how=("For each renewal inside the window, waste = monthly cost × (1 − utilisation); "
             f"summed across {len(rows)} subscriptions = {_fmt(waste)}/month if renewed as-is."),
        action="Put each renewal on the finance calendar now and right-size seats or cancel before auto-renew.",
    )]


@rule("manual_work")
def manual_work(frames, cfg, ctx):
    df = frames.get("processes")
    if df is None or df.empty:
        return []
    out = []
    for _, r in df.iterrows():
        tasks = float(r["Tasks Per Month"] or 0)
        mins = float(r["Minutes Per Task"] or 0)
        rate = float(r["Hourly Cost"] or 0)
        if tasks <= 0 or mins <= 0 or rate <= 0:
            continue
        base = tasks * mins * rate / 60.0
        err = float(r["Error Rate"] or 0)
        err = err / 100.0 if err > 1 else err
        cost = base * (1 + err)
        feas = str(r.get("Automation Feasibility") or "Medium").strip().title()
        pct = cfg["automation_savings"].get(feas, 0.40)
        saving = cost * pct
        if saving < 1000:
            continue
        hours = tasks * mins / 60.0
        out.append(make_finding(
            fid=f"MAN-{len(out)+1:02d}",
            title=f"{r['Process Name']} costs {_fmt(cost)}/month in manual effort — automating {int(pct*100)}% saves {_fmt(saving)}/month",
            category="Manual Work",
            monthly_waste=saving,
            confidence="High" if feas == "High" else "Medium",
            department=str(r.get("Department") or "—"),
            vendor="Internal process",
            evidence=[{
                "Process": str(r["Process Name"]),
                "Tasks / month": int(tasks), "Minutes / task": round(mins, 1),
                "Employees involved": int(float(r.get("Employees Involved") or 0)),
                "Hourly cost": round(rate, 2),
                "Hours / month": round(hours, 1),
                "Rework rate": f"{err*100:.0f}%",
                "Automation feasibility": feas,
            }],
            how=(f"Monthly manual cost = {int(tasks)} tasks × {mins:g} min × {_fmt(rate)}/hr ÷ 60 = {_fmt(base)}; "
                 f"+{err*100:.0f}% rework = {_fmt(cost)} ({hours:.0f} person-hours). "
                 f"{feas} automation feasibility → {int(pct*100)}% saving = {_fmt(saving)}/month "
                 f"({_fmt(saving*12)}/year)."),
            action=(f"Automate {r['Process Name']} ({feas.lower()} feasibility) — OCR/RPA or a native "
                    f"integration. Redeploy ~{hours*pct:.0f} hours/month to higher-value work."),
        ))
    return out


@rule("overtime")
def overtime(frames, cfg, ctx):
    df = frames.get("overtime")
    if df is None or df.empty:
        return []
    out = []
    thr = cfg["overtime_month_threshold"]
    for dept, grp in df.groupby(df["Department"].astype(str)):
        per_month = grp.groupby("Month").apply(
            lambda g: pd.Series({
                "hours": float(g["Overtime Hours"].sum()),
                "cost": float((g["Overtime Hours"] * g["Overtime Rate"]).sum()),
                "headcount": int(g["Employee ID"].nunique() or len(g)),
            }), include_groups=False).reset_index().sort_values("Month")
        if per_month.empty:
            continue
        breached = per_month[per_month["hours"] / per_month["headcount"].clip(lower=1) >= thr]
        if len(breached) < cfg["overtime_repeat_months"]:
            continue
        avg_cost = float(per_month["cost"].mean())
        # Treat overtime above the threshold as the avoidable portion.
        avoidable = 0.0
        for _, m in per_month.iterrows():
            excess = max(m["hours"] - thr * max(m["headcount"], 1), 0)
            avoidable += excess / max(m["hours"], 1) * m["cost"]
        avoidable /= len(per_month)
        if avoidable < 1000:
            continue
        out.append(make_finding(
            fid=f"OT-{len(out)+1:02d}",
            title=f"Repeated overtime in {dept} across {len(breached)} months — {_fmt(avoidable)}/month avoidable",
            category="Overtime",
            monthly_waste=avoidable,
            confidence="Medium",
            department=dept, vendor="Internal workload",
            evidence=[{
                "Month": str(r["Month"]), "Overtime hours": round(float(r["hours"]), 1),
                "Employees": int(r["headcount"]),
                "Hours / employee": round(float(r["hours"]) / max(int(r["headcount"]), 1), 1),
                "Overtime cost": round(float(r["cost"]), 2),
            } for _, r in per_month.iterrows()],
            how=(f"{dept} exceeded {thr} overtime hours per employee in {len(breached)} of "
                 f"{len(per_month)} months (avg overtime bill {_fmt(avg_cost)}/month). Hours above the "
                 f"threshold are treated as process/workload waste = {_fmt(avoidable)}/month."),
            action=(f"Review {dept} workload distribution and shift planning; the sustained pattern usually "
                    f"signals an understaffed or manual step rather than genuine peak demand."),
        ))
    return out
