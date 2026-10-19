"""Indian number formatting shared by evidence, agents and the verifier."""

from __future__ import annotations

from datetime import date


def _group_indian(n: int) -> str:
    s = str(abs(n))
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts: list[str] = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts) + "," + tail


def inr(value: float) -> str:
    n = round(value)
    return f"{'−' if n < 0 else ''}₹{_group_indian(n)}"


def inr_short(value: float) -> str:
    a = abs(value)
    sign = "−" if value < 0 else ""
    if a >= 1e7:
        return f"{sign}₹{a / 1e7:.2f} Cr"
    if a >= 1e5:
        return f"{sign}₹{a / 1e5:.{1 if a >= 1e6 else 2}f} L"
    return inr(value)


def pct(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}%"


def pts(value: float) -> str:
    sign = "+" if value > 0 else "−" if value < 0 else ""
    return f"{sign}{abs(value):.1f} pts"


def day(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%d %b %Y").lstrip("0")
