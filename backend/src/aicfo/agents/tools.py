"""Deterministic tools the agents call. They turn a Snapshot into Evidence records.

Agents never compute numbers themselves: they receive these records, and the
verifier later checks that any number in drafted text appears in them.
"""

from __future__ import annotations

from aicfo.core.analytics import Evidence, Snapshot
from aicfo.core.book import ASSET_CLASSES, Book
from aicfo.core.format import day, inr, inr_short, pct, pts


def overlap_evidence(s: Snapshot, book: Book, max_pairs: int = 3) -> list[Evidence]:
    out = []
    for o in s.overlaps[:max_pairs]:
        combined = o.a.value + o.b.value
        out.append(
            Evidence(
                id=f"overlap:{o.a.ref}:{o.b.ref}",
                title=f"Overlap: {o.a.short_name} × {o.b.short_name}",
                result=pct(o.pct),
                formula_words="For every company both funds hold, take the smaller of the two weights, then add them up.",
                formula="overlap = Σ min(wₐ, w_b)",
                inputs=tuple(
                    (
                        name,
                        f"min({wa:.1f}%, {wb:.1f}%) = {min(wa, wb):.1f}%",
                        f"AMC disclosure · {book.disclosure_month}",
                    )
                    for _, name, wa, wb in o.common[:6]
                ),
                steps=(
                    f"{len(o.common)} companies appear in both portfolios.",
                    f"Sum of the smaller weights = {pct(o.pct)} (rounded {pct(o.pct, 0)}).",
                    f"Combined value in the two funds = {inr(combined)} ({inr_short(combined)}).",
                ),
                values=(o.pct, combined),
            )
        )
    return out


def drift_evidence(s: Snapshot) -> list[Evidence]:
    out = []
    for c in ASSET_CLASSES:
        d = s.drift[c]
        gap = d / 100 * s.total
        out.append(
            Evidence(
                id=f"drift:{c.lower()}",
                title=f"{c} drift vs {s.client.risk} model",
                result=pts(d),
                formula_words="Actual share minus the model's target share; the rupee gap is that difference times the portfolio value.",
                formula="drift = actual% − target%;  gap = drift × value",
                inputs=(
                    (f"{c} value", inr(s.allocation[c]), "Snapshot"),
                    ("Portfolio value", inr(s.total), "Snapshot"),
                    (f"Actual {c.lower()} share", pct(s.allocation_pct[c]), ""),
                    ("Model target", pct(s.target[c], 0), f"IPS v3 · {s.client.risk}"),
                ),
                steps=(
                    f"{inr(s.allocation[c])} ÷ {inr(s.total)} = {pct(s.allocation_pct[c])}.",
                    f"{pct(s.allocation_pct[c])} − {pct(s.target[c], 0)} = {pts(d)}.",
                    f"Gap ≈ {inr(gap)} ({inr_short(abs(gap))}).",
                ),
                values=(s.allocation_pct[c], s.target[c], d, gap),
            )
        )
    return out


def tax_evidence(s: Snapshot, book: Book) -> list[Evidence]:
    out = []
    for u in sorted(s.upcoming_lots, key=lambda u: -u.lot.gain):
        if u.lot.gain <= 0:
            continue
        saving = u.lot.gain * (book.stcg_rate - book.ltcg_rate)
        out.append(
            Evidence(
                id=f"lot:{u.position.ref}:{u.lot.acquired}",
                title=f"Holding period: {u.position.short_name} lot",
                result=f"{u.lot.days_to_long} days to long-term",
                formula_words="A lot becomes long-term after 12 months; the saving is the gain times the difference between the 20% and 12.5% rates.",
                formula="saving = gain × (20% − 12.5%)",
                inputs=(
                    ("Acquired", day(u.lot.acquired), u.position.source),
                    ("Long-term from", day(u.lot.long_term_on), ""),
                    ("Unrealised gain", inr(u.lot.gain), ""),
                ),
                steps=(
                    f"Long-term from {day(u.lot.long_term_on)}, {u.lot.days_to_long} days away.",
                    f"Saving ≈ {inr(u.lot.gain)} × 7.5% = {inr(saving)}.",
                ),
                values=(u.lot.gain, float(u.lot.days_to_long), saving),
            )
        )
    if s.exemption_left > 0 and s.lt_gain_unrealised > 10_000:
        usable = min(s.exemption_left, s.lt_gain_unrealised)
        out.append(
            Evidence(
                id="tax:exemption",
                title=f"LTCG exemption headroom · {book.fy_label}",
                result=inr(s.exemption_left),
                formula_words="The yearly exemption minus long-term gains already realised this financial year.",
                formula="headroom = ₹1,25,000 − realised LTCG",
                inputs=(
                    ("Annual exemption", inr(book.ltcg_exemption), "Income-tax Act, 2025"),
                    ("Realised LTCG this FY", inr(s.client.realised_ltcg), "Transactions"),
                    (
                        "Unrealised long-term gains",
                        inr(s.lt_gain_unrealised),
                        "Lots held > 12 months",
                    ),
                ),
                steps=(
                    f"{inr(book.ltcg_exemption)} − {inr(s.client.realised_ltcg)} = {inr(s.exemption_left)}.",
                    f"Usable = {inr(usable)}; at 12.5% that avoids up to {inr(usable * book.ltcg_rate)} of future tax.",
                ),
                values=(s.exemption_left, s.lt_gain_unrealised, usable * book.ltcg_rate),
            )
        )
    return out


def concentration_evidence(s: Snapshot, book: Book, top: int = 3) -> list[Evidence]:
    out = []
    for e in s.exposures[:top]:
        out.append(
            Evidence(
                id=f"exposure:{e.symbol}",
                title=f"Look-through exposure: {e.name}",
                result=pct(e.pct_of_total),
                formula_words="Direct shares plus each fund's value times its weight in the company, divided by the portfolio value.",
                formula="exposure = (direct + Σ value × weight) ÷ portfolio",
                inputs=(
                    *((("Direct shares", inr(e.direct), "Dhan"),) if e.direct else ()),
                    *(
                        (f"via {f} ({w:.1f}%)", inr(v), f"AMC disclosure · {book.disclosure_month}")
                        for f, v, w in e.via_funds
                    ),
                ),
                steps=(
                    f"{inr(e.value)} ÷ {inr(s.total)} = {pct(e.pct_of_total)}.",
                    f"Held through {len(e.via_funds)} funds{' plus direct shares' if e.direct else ''}.",
                ),
                values=(e.pct_of_total, e.value, float(len(e.via_funds))),
            )
        )
    return out


def all_evidence(s: Snapshot, book: Book) -> dict[str, Evidence]:
    items = (
        overlap_evidence(s, book)
        + drift_evidence(s)
        + tax_evidence(s, book)
        + concentration_evidence(s, book)
    )
    return {e.id: e for e in items}


def evidence_text(e: Evidence) -> str:
    """All human-readable numbers an agent may quote from this evidence."""
    return " ".join([e.result, *(v for _, v, _ in e.inputs), *e.steps])
