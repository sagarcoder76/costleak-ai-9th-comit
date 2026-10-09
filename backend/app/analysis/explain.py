"""Plain-English explanations for findings.

Works 100% offline with intelligent templates. If OPENAI_API_KEY (or
COSTLEAK_LLM_KEY) is set AND COSTLEAK_USE_LLM=1, the template is sent to an LLM
for a nicer rewrite — failures silently fall back to the template.
"""
from __future__ import annotations

import os

TEMPLATES = {
    "Duplicate Payment": (
        "Your books show the same vendor being paid more than once for what looks like the same "
        "invoice. Money already out of the bank can usually be recovered as a refund or credit note, "
        "so this is the fastest rupee you will get back. Treat it as an accounts-payable control gap, "
        "not just a one-off slip."
    ),
    "Unused License": (
        "You are paying for seats nobody logs into. Software vendors bill per seat whether or not the "
        "seat is used, so every unused licence is pure leakage that repeats every single month until "
        "someone right-sizes the plan at renewal."
    ),
    "Duplicate Software": (
        "Two or more tools in your stack do the same job and both are being paid for. This usually "
        "happens when different teams buy independently. Standardising on one tool removes the "
        "duplicate bill and also cuts training and admin overhead."
    ),
    "Price Increase": (
        "This vendor's bill jumped well above its own recent average. It is either a silent price "
        "revision, an added module, or a usage spike. Either way it deserves a conversation before "
        "the next renewal locks the higher rate in for a year."
    ),
    "Manual Work": (
        "People are spending paid hours on repetitive keyboard work. The cost is invisible because it "
        "sits inside salaries rather than an invoice — but it is real money, and a large share of it "
        "can be removed with automation or a simple integration."
    ),
    "Overtime": (
        "Overtime that repeats month after month is rarely a demand spike; it is usually a staffing or "
        "process bottleneck being paid for at premium rates. Fixing the underlying step is cheaper "
        "than funding the overtime indefinitely."
    ),
    "Unused Resource": (
        "You are paying full price for capacity that is barely touched. Either usage needs to be driven "
        "up deliberately or the spend needs to come down to match reality."
    ),
}

CLOSERS = {
    "Critical": "Escalate this week — it is the single biggest lever in this report.",
    "High": "Worth putting on this month's finance review agenda.",
    "Medium": "Easy win; bundle it with the next renewal cycle.",
    "Low": "Low value on its own, but these add up across the year.",
}


def _template(f: dict) -> str:
    base = TEMPLATES.get(f["category"], "This spend pattern looks avoidable based on your uploaded data.")
    money = (f"Estimated saving: about ₹{f['monthly_waste']:,.0f} per month "
             f"(₹{f['annual_waste']:,.0f} per year), at {f['confidence'].lower()} confidence.")
    return f"{base} {money} {CLOSERS.get(f['priority'], '')}".strip()


def explain(f: dict) -> str:
    text = _template(f)
    if os.getenv("COSTLEAK_USE_LLM") != "1":
        return text
    key = os.getenv("OPENAI_API_KEY") or os.getenv("COSTLEAK_LLM_KEY")
    if not key:
        return text
    try:  # pragma: no cover - optional path
        import json
        import urllib.request
        prompt = (
            "Rewrite this cost-saving finding for an Indian SMB business owner in 2-3 plain sentences. "
            "Keep every number exactly as given. No jargon, no markdown.\n\n"
            f"Title: {f['title']}\nCalculation: {f['calculation']}\nDraft: {text}"
        )
        req = urllib.request.Request(
            os.getenv("COSTLEAK_LLM_URL", "https://api.openai.com/v1/chat/completions"),
            data=json.dumps({
                "model": os.getenv("COSTLEAK_LLM_MODEL", "gpt-4o-mini"),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            }).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            body = json.loads(resp.read())
        return body["choices"][0]["message"]["content"].strip() or text
    except Exception:
        return text
