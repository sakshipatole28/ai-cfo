"""Deterministic tools the agents call. They turn a Snapshot into Evidence records.

Agents never compute numbers themselves: they receive these records, and the
verifier later checks that any number in drafted text appears in them.
"""

from __future__ import annotations

from aicfo.core.analytics import Evidence, Snapshot
from aicfo.core.book import ASSET_CLASSES, Book
from aicfo.core.format import day, inr, inr_short, pct, pts


# Evidence for fund-pair overlap: the most overlapping pairs, each with its working.
def overlap_evidence(s: Snapshot, book: Book, max_pairs: int = 3) -> list[Evidence]:
    # Evidence records built so far.
    out = []
    # The top pairs (already sorted, most overlapping first).
    for o in s.overlaps[:max_pairs]:
        # Rupees held in the two funds together.
        combined = o.a.value + o.b.value
        # One Evidence record per pair.
        out.append(
            Evidence(
                # Stable id built from the two fund codes.
                id=f"overlap:{o.a.ref}:{o.b.ref}",
                # Human title.
                title=f"Overlap: {o.a.short_name} × {o.b.short_name}",
                # Headline number: overlap %.
                result=pct(o.pct),
                # The formula explained in words, for non-technical readers.
                formula_words="For every company both funds hold, take the smaller of the two weights, then add them up.",
                # The formula in symbols.
                formula="overlap = Σ min(wₐ, w_b)",
                # The six biggest shared companies, each with the smaller of the two weights.
                inputs=tuple(
                    (
                        name,
                        f"min({wa:.1f}%, {wb:.1f}%) = {min(wa, wb):.1f}%",
                        f"AMC disclosure · {book.disclosure_month}",
                    )
                    for _, name, wa, wb in o.common[:6]
                ),
                # The arithmetic, line by line.
                steps=(
                    f"{len(o.common)} companies appear in both portfolios.",
                    f"Sum of the smaller weights = {pct(o.pct)} (rounded {pct(o.pct, 0)}).",
                    f"Combined value in the two funds = {inr(combined)} ({inr_short(combined)}).",
                ),
                # Raw numbers a finding may quote (checked by the verifier).
                values=(o.pct, combined),
            )
        )
    # Evidence list.
    return out


# Evidence for allocation drift, one per asset class.
def drift_evidence(s: Snapshot) -> list[Evidence]:
    out = []
    # Equity, Debt, Gold, Cash.
    for c in ASSET_CLASSES:
        # Actual minus target, in points.
        d = s.drift[c]
        # Rupee gap: drift × portfolio value.
        gap = d / 100 * s.total
        # One Evidence record per class.
        out.append(
            Evidence(
                id=f"drift:{c.lower()}",
                title=f"{c} drift vs {s.client.risk} model",
                result=pts(d),
                formula_words="Actual share minus the model's target share; the rupee gap is that difference times the portfolio value.",
                formula="drift = actual% − target%;  gap = drift × value",
                # What went in: values, shares and the model target.
                inputs=(
                    (f"{c} value", inr(s.allocation[c]), "Snapshot"),
                    ("Portfolio value", inr(s.total), "Snapshot"),
                    (f"Actual {c.lower()} share", pct(s.allocation_pct[c]), ""),
                    ("Model target", pct(s.target[c], 0), f"IPS v3 · {s.client.risk}"),
                ),
                # Actual share, drift and rupee gap, step by step.
                steps=(
                    f"{inr(s.allocation[c])} ÷ {inr(s.total)} = {pct(s.allocation_pct[c])}.",
                    f"{pct(s.allocation_pct[c])} − {pct(s.target[c], 0)} = {pts(d)}.",
                    f"Gap ≈ {inr(gap)} ({inr_short(abs(gap))}).",
                ),
                # Actual %, target %, drift and rupee gap.
                values=(s.allocation_pct[c], s.target[c], d, gap),
            )
        )
    # Evidence list.
    return out


# Evidence for tax timing and the unused long-term gains exemption.
def tax_evidence(s: Snapshot, book: Book) -> list[Evidence]:
    out = []
    # Lots about to turn long-term, biggest gain first.
    for u in sorted(s.upcoming_lots, key=lambda u: -u.lot.gain):
        # Waiting only matters when there is a gain.
        if u.lot.gain <= 0:
            continue
        # Tax saved by waiting: gain × (short-term rate − long-term rate).
        saving = u.lot.gain * (book.stcg_rate - book.ltcg_rate)
        # One Evidence record per lot.
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
    # Exemption left and long-term gains available to use it.
    if s.exemption_left > 0 and s.lt_gain_unrealised > 10_000:
        # How much of the exemption can actually be used.
        usable = min(s.exemption_left, s.lt_gain_unrealised)
        # Evidence for the exemption headroom.
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
    # Evidence list.
    return out


# Evidence for the biggest look-through exposures (a company hidden inside several funds).
def concentration_evidence(s: Snapshot, book: Book, top: int = 3) -> list[Evidence]:
    out = []
    # Top companies by exposure.
    for e in s.exposures[:top]:
        # One Evidence record per company, listing each fund that holds it.
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
    # Evidence list.
    return out


# All evidence for a snapshot, keyed by id. Analysts and the verifier read from this.
def all_evidence(s: Snapshot, book: Book) -> dict[str, Evidence]:
    # Combine the four kinds.
    items = (
        overlap_evidence(s, book)
        + drift_evidence(s)
        + tax_evidence(s, book)
        + concentration_evidence(s, book)
    )
    # Look-up by id.
    return {e.id: e for e in items}


def evidence_text(e: Evidence) -> str:
    """All human-readable numbers an agent may quote from this evidence."""
    return " ".join([e.result, *(v for _, v, _ in e.inputs), *e.steps])
