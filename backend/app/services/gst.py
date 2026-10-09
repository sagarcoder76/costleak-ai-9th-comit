"""GST calculation engine (India).

Pure functions — no database, no framework. Every rupee figure the invoice
module produces comes from here, so the tax logic is testable in isolation.

Rules implemented:
  * Place of supply decides the tax split:
      - supplier state == place of supply  -> CGST + SGST (rate split in half)
      - different state                    -> IGST (full rate)
  * Line-level discount is applied before tax (as required on a tax invoice).
  * Values are rounded to 2 decimals per line; the invoice total is rounded to
    the nearest rupee with the difference carried as `round_off`.
  * GSTIN is validated structurally (15 chars, state code, PAN block, checksum).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict

from ..core.config import STATE_CODES

GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")
_CHECK_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def r2(x: float) -> float:
    return round(float(x or 0) + 1e-9, 2)


# --------------------------------------------------------------- GSTIN ----
def gstin_checksum(gstin14: str) -> str:
    total = 0
    for i, ch in enumerate(gstin14):
        v = _CHECK_CHARS.index(ch)
        prod = v * (2 if i % 2 else 1)
        total += prod // 36 + prod % 36
    return _CHECK_CHARS[(36 - total % 36) % 36]


def validate_gstin(gstin: str | None) -> dict:
    """Returns {valid, state_code, state, pan, message}."""
    if not gstin:
        return {"valid": False, "message": "No GSTIN provided (treated as unregistered / B2C)"}
    g = gstin.strip().upper()
    if len(g) != 15:
        return {"valid": False, "message": "GSTIN must be exactly 15 characters"}
    if not GSTIN_RE.match(g):
        return {"valid": False, "message": "GSTIN format is invalid"}
    if g[:2] not in STATE_CODES:
        return {"valid": False, "message": f"Unknown state code '{g[:2]}'"}
    if gstin_checksum(g[:14]) != g[14]:
        return {"valid": False, "message": "GSTIN checksum does not match — please re-check"}
    return {"valid": True, "state_code": g[:2], "state": STATE_CODES[g[:2]],
            "pan": g[2:12], "message": "Valid GSTIN"}


def state_name(code: str | None) -> str:
    return STATE_CODES.get(str(code or "").zfill(2), "—")


# ---------------------------------------------------------------- lines ---
@dataclass
class TaxLine:
    name: str
    qty: float = 1
    rate: float = 0.0            # selling price per unit, exclusive of GST
    gst_rate: float = 18.0       # percent
    discount_pct: float = 0.0
    hsn: str = ""
    unit: str = "NOS"
    cost_price: float = 0.0      # per unit cost to the company
    product_id: str | None = None
    # computed
    gross: float = field(default=0.0, init=False)
    discount: float = field(default=0.0, init=False)
    taxable: float = field(default=0.0, init=False)
    cgst: float = field(default=0.0, init=False)
    sgst: float = field(default=0.0, init=False)
    igst: float = field(default=0.0, init=False)
    tax: float = field(default=0.0, init=False)
    total: float = field(default=0.0, init=False)
    cost_total: float = field(default=0.0, init=False)
    profit: float = field(default=0.0, init=False)
    margin_pct: float = field(default=0.0, init=False)


def compute_line(line: TaxLine, intra_state: bool) -> TaxLine:
    line.gross = r2(line.qty * line.rate)
    line.discount = r2(line.gross * (line.discount_pct or 0) / 100)
    line.taxable = r2(line.gross - line.discount)
    tax = r2(line.taxable * (line.gst_rate or 0) / 100)
    if intra_state:
        line.cgst = r2(tax / 2)
        line.sgst = r2(tax - line.cgst)   # keeps halves adding back to `tax`
        line.igst = 0.0
    else:
        line.cgst = line.sgst = 0.0
        line.igst = tax
    line.tax = r2(line.cgst + line.sgst + line.igst)
    line.total = r2(line.taxable + line.tax)
    line.cost_total = r2(line.qty * (line.cost_price or 0))
    line.profit = r2(line.taxable - line.cost_total)
    line.margin_pct = r2(line.profit / line.taxable * 100) if line.taxable else 0.0
    return line


def is_intra_state(supplier_state: str | None, place_of_supply: str | None) -> bool:
    s = str(supplier_state or "").zfill(2)
    p = str(place_of_supply or s).zfill(2)
    return s == p


def build_invoice(lines: list[dict], supplier_state: str, place_of_supply: str,
                  extra_discount: float = 0.0, round_total: bool = True) -> dict:
    """Core entry point: raw line dicts -> fully computed invoice totals."""
    intra = is_intra_state(supplier_state, place_of_supply)
    computed = [compute_line(TaxLine(**{k: v for k, v in ln.items()
                                        if k in TaxLine.__dataclass_fields__}), intra)
                for ln in lines]

    subtotal = r2(sum(l.gross for l in computed))
    discount_total = r2(sum(l.discount for l in computed) + (extra_discount or 0))
    taxable_total = r2(sum(l.taxable for l in computed) - (extra_discount or 0))
    cgst = r2(sum(l.cgst for l in computed))
    sgst = r2(sum(l.sgst for l in computed))
    igst = r2(sum(l.igst for l in computed))
    cost_total = r2(sum(l.cost_total for l in computed))
    gross_total = r2(taxable_total + cgst + sgst + igst)

    total = round(gross_total) if round_total else gross_total
    round_off = r2(total - gross_total)
    profit = r2(taxable_total - cost_total)

    # tax rate-wise breakup, as printed on a compliant tax invoice
    breakup: dict[float, dict] = {}
    for l in computed:
        b = breakup.setdefault(l.gst_rate, {"gst_rate": l.gst_rate, "taxable": 0.0,
                                            "cgst": 0.0, "sgst": 0.0, "igst": 0.0})
        b["taxable"] = r2(b["taxable"] + l.taxable)
        b["cgst"] = r2(b["cgst"] + l.cgst)
        b["sgst"] = r2(b["sgst"] + l.sgst)
        b["igst"] = r2(b["igst"] + l.igst)

    # HSN summary (required in GSTR-1 above turnover thresholds)
    hsn: dict[str, dict] = {}
    for l in computed:
        key = l.hsn or "—"
        h = hsn.setdefault(key, {"hsn": key, "description": l.name, "uqc": l.unit,
                                 "qty": 0.0, "taxable": 0.0, "tax": 0.0})
        h["qty"] = r2(h["qty"] + l.qty)
        h["taxable"] = r2(h["taxable"] + l.taxable)
        h["tax"] = r2(h["tax"] + l.tax)

    return {
        "supply_type": "intra" if intra else "inter",
        "place_of_supply": str(place_of_supply or supplier_state).zfill(2),
        "place_of_supply_name": state_name(place_of_supply or supplier_state),
        "items": [asdict(l) for l in computed],
        "subtotal": subtotal,
        "discount_total": discount_total,
        "taxable_total": taxable_total,
        "cgst": cgst, "sgst": sgst, "igst": igst,
        "total_tax": r2(cgst + sgst + igst),
        "round_off": round_off,
        "total": r2(total),
        "cost_total": cost_total,
        "profit": profit,
        "margin_pct": r2(profit / taxable_total * 100) if taxable_total else 0.0,
        "tax_breakup": sorted(breakup.values(), key=lambda x: x["gst_rate"]),
        "hsn_summary": sorted(hsn.values(), key=lambda x: -x["taxable"]),
        "amount_in_words": amount_in_words(total),
    }


# --------------------------------------------------------- number words ---
_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
         "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen",
         "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two(n: int) -> str:
    if n < 20:
        return _ONES[n]
    return (_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else "")).strip()


def _three(n: int) -> str:
    if n < 100:
        return _two(n)
    return (_ONES[n // 100] + " Hundred" + (" " + _two(n % 100) if n % 100 else "")).strip()


def amount_in_words(amount: float) -> str:
    """Indian numbering: crore / lakh / thousand."""
    rupees = int(abs(amount))
    paise = int(round((abs(amount) - rupees) * 100))
    if rupees == 0 and paise == 0:
        return "Zero Rupees Only"
    parts = []
    for div, label in ((10_000_000, "Crore"), (100_000, "Lakh"), (1_000, "Thousand")):
        if rupees >= div:
            parts.append(f"{_three(rupees // div) if div == 1000 else _two(rupees // div) if rupees // div < 100 else _three(rupees // div)} {label}")
            rupees %= div
    if rupees:
        parts.append(_three(rupees))
    words = " ".join(p for p in parts if p.strip())
    out = f"{'Minus ' if amount < 0 else ''}{words} Rupees"
    if paise:
        out += f" and {_two(paise)} Paise"
    return out + " Only"


# --------------------------------------------------------- tax summaries --
def gst_summary(sales: list[dict], purchases: list[dict]) -> dict:
    """Output tax vs input tax (ITC) -> net GST payable for a period."""
    out_cgst = r2(sum(i.get("cgst", 0) for i in sales))
    out_sgst = r2(sum(i.get("sgst", 0) for i in sales))
    out_igst = r2(sum(i.get("igst", 0) for i in sales))
    in_cgst = r2(sum(i.get("cgst", 0) for i in purchases))
    in_sgst = r2(sum(i.get("sgst", 0) for i in purchases))
    in_igst = r2(sum(i.get("igst", 0) for i in purchases))
    output_total = r2(out_cgst + out_sgst + out_igst)
    input_total = r2(in_cgst + in_sgst + in_igst)
    return {
        "taxable_sales": r2(sum(i.get("taxable_total", 0) for i in sales)),
        "taxable_purchases": r2(sum(i.get("taxable_total", 0) for i in purchases)),
        "output_tax": {"cgst": out_cgst, "sgst": out_sgst, "igst": out_igst, "total": output_total},
        "input_tax": {"cgst": in_cgst, "sgst": in_sgst, "igst": in_igst, "total": input_total},
        "net_payable": r2(max(output_total - input_total, 0)),
        "credit_carried_forward": r2(max(input_total - output_total, 0)),
        "invoice_count": {"sales": len(sales), "purchases": len(purchases)},
    }
