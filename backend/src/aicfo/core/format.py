"""Indian number formatting shared by evidence, agents and the verifier."""

from __future__ import annotations

from datetime import date


# Group digits the Indian way: 12,34,567 (last three, then pairs).
def _group_indian(n: int) -> str:
    # Digits without a sign.
    s = str(abs(n))
    # Short numbers need no commas.
    if len(s) <= 3:
        # As is.
        return s
    # Last three digits, and the rest.
    head, tail = s[:-3], s[-3:]
    # Pairs of digits, built from the right.
    parts: list[str] = []
    # Peel off two digits at a time.
    while len(head) > 2:
        # Take the last pair.
        parts.insert(0, head[-2:])
        # Remove it.
        head = head[:-2]
    # Anything left over (one or two digits).
    if head:
        # Put it in front.
        parts.insert(0, head)
    # Join with commas.
    return ",".join(parts) + "," + tail


# Rupees in full: ₹29,05,000.
def inr(value: float) -> str:
    # Whole rupees.
    n = round(value)
    # Minus sign for losses.
    return f"{'−' if n < 0 else ''}₹{_group_indian(n)}"


# Rupees in lakh/crore form: ₹29.1 L, ₹1.2 Cr.
def inr_short(value: float) -> str:
    # Magnitude.
    a = abs(value)
    # Minus sign if negative.
    sign = "−" if value < 0 else ""
    # A crore or more.
    if a >= 1e7:
        # In crore.
        return f"{sign}₹{a / 1e7:.2f} Cr"
    # A lakh or more.
    if a >= 1e5:
        # In lakh.
        return f"{sign}₹{a / 1e5:.{1 if a >= 1e6 else 2}f} L"
    # Smaller amounts in full.
    return inr(value)


# A percentage with fixed decimals.
def pct(value: float, digits: int = 1) -> str:
    # e.g. 84.2%.
    return f"{value:.{digits}f}%"


# Percentage points with a sign: +14.2 pts.
def pts(value: float) -> str:
    # Plus, minus or nothing.
    sign = "+" if value > 0 else "−" if value < 0 else ""
    # Signed points.
    return f"{sign}{abs(value):.1f} pts"


# A date for people: 29 Oct 2026.
def day(iso: str) -> str:
    # Format and drop a leading zero.
    return date.fromisoformat(iso).strftime("%d %b %Y").lstrip("0")
