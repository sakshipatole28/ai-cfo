"""Deterministic portfolio analytics. Pure functions: no I/O, no randomness, no LLM.

Every agent number comes from here, and every result is wrapped in an
`Evidence` record (formula, inputs, steps) so the UI can explain it and the
verifier can check that drafted text only uses these numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from itertools import combinations

from aicfo.core.book import ASSET_CLASSES, Book, ClientSpec


# Parse an ISO date string (YYYY-MM-DD).
def _d(iso: str) -> date:
    # Standard-library parser; raises on a bad date.
    return date.fromisoformat(iso)


# Date after which a holding counts as long-term: more than `years` years, i.e. +1 day.
def _plus_year_and_day(iso: str, years: int = 1) -> str:
    # Acquisition date.
    d = _d(iso)
    # Move forward by whole years.
    try:
        # Same day and month, later year.
        d = d.replace(year=d.year + years)
    # 29 February does not exist in the target year.
    except ValueError:  # 29 Feb
        # Use 28 February instead.
        d = d.replace(year=d.year + years, day=28)
    # Long-term only after the anniversary, so add one day.
    return (d + timedelta(days=1)).isoformat()


# One purchase lot of a holding (frozen = cannot be changed after creation).
@dataclass(frozen=True)
# A lot: units bought on one date at one cost.
class Lot:
    acquired: str
    units: float
    value: float
    cost: float
    long_term_on: str
    days_to_long: int
    locked_until: str | None

    @property
    # Unrealised gain = current value - cost.
    def gain(self) -> float:
        # Positive when in profit.
        return self.value - self.cost

    @property
    # True once the lot is past its one-year long-term date.
    def is_long(self) -> bool:
        # Zero or negative days left means long-term.
        return self.days_to_long <= 0


@dataclass(frozen=True)
# One holding (a fund or a share) valued today, with its lots.
class Position:
    id: str
    kind: str
    ref: str
    name: str
    short_name: str
    category: str
    asset_class: str
    units: float
    price: float
    value: float
    source: str
    account: str
    as_of: str
    lots: tuple[Lot, ...]

    @property
    # Total cost of the position = sum of its lots' cost.
    def cost(self) -> float:
        # Add the lots up.
        return sum(lot.cost for lot in self.lots)


@dataclass(frozen=True)
# Look-through exposure to one company: direct shares plus the part held inside funds.
class Exposure:
    symbol: str
    name: str
    sector: str
    value: float
    pct_of_total: float
    direct: float
    # Which funds hold it: (fund name, rupee value, weight %).
    via_funds: tuple[tuple[str, float, float], ...]  # (fund short name, value, weight %)


@dataclass(frozen=True)
# How much two equity funds have in common.
class Overlap:
    a: Position
    b: Position
    pct: float
    # The shared companies: (symbol, name, weight in fund A, weight in fund B).
    common: tuple[tuple[str, str, float, float], ...]  # (symbol, name, weight a, weight b)


@dataclass(frozen=True)
# A lot about to turn long-term (used for tax-timing findings).
class UpcomingLot:
    position: Position
    lot: Lot


@dataclass(frozen=True)
# Everything computed for one client on one day. The agents read only this.
class Snapshot:
    client: ClientSpec
    today: str
    positions: tuple[Position, ...]
    total: float
    # Rupees per asset class.
    allocation: dict[str, float]
    # Share of the portfolio per asset class, in %.
    allocation_pct: dict[str, float]
    # The agreed model's target % per asset class.
    target: dict[str, float]
    # Actual minus target, in percentage points.
    drift: dict[str, float]
    # Look-through exposures, biggest first.
    exposures: tuple[Exposure, ...]
    # How much of the equity could be looked through to company level.
    look_through_pct: float
    # Fund pairs, most overlapping first.
    overlaps: tuple[Overlap, ...]
    # Unrealised long-term gains that could be booked now.
    lt_gain_unrealised: float
    # Unused part of the yearly long-term gains exemption (₹).
    exemption_left: float
    # Lots turning long-term within 30 days.
    upcoming_lots: tuple[UpcomingLot, ...]
    # Stored with every snapshot so any number can be reproduced exactly.
    engine_version: str = "core-py 0.1.0"


@dataclass(frozen=True)
# A computed number with its working: the unit of proof the verifier and the UI use.
class Evidence:
    # Stable id, e.g. "overlap:NSB:HN50".
    id: str
    # What it is.
    title: str
    # The answer, formatted for people.
    result: str
    # The formula in plain words.
    formula_words: str
    # The formula as symbols.
    formula: str
    # What went in: (label, value, where it came from).
    inputs: tuple[tuple[str, str, str], ...]  # (label, value, source)
    # The arithmetic, step by step.
    steps: tuple[str, ...]
    # The raw numbers a written finding is allowed to quote.
    values: tuple[float, ...] = field(default_factory=tuple)  # raw numbers the text may quote


# Turn a client's holdings into positions with lots, prices and values.
def build_positions(spec: ClientSpec, book: Book) -> tuple[Position, ...]:
    # Positions built so far.
    out: list[Position] = []
    # Each holding of the client.
    for i, h in enumerate(spec.holdings):
        # A mutual fund, if this holding is one…
        fund = book.funds.get(h.ref) if h.kind == "fund" else None
        # …or a direct share.
        stock = book.stocks.get(h.ref) if h.kind == "stock" else None
        # Unknown security: fail loudly rather than guess.
        if fund is None and stock is None:
            raise KeyError(f"{spec.id}: unknown security {h.ref!r}")
        # NAV for a fund, last price for a share.
        price = fund.nav if fund else stock.price  # type: ignore[union-attr]
        # Funds are held by value; shares by quantity × price.
        value = float(h.value or 0) if fund else float(h.qty or 0) * price
        # Units held.
        units = value / price if fund else float(h.qty or 0)
        # Purchase lots of this holding.
        lots: list[Lot] = []
        # Each lot is a share of the holding with its own date and cost.
        for spec_lot in h.lots:
            # This lot's current value.
            lot_value = value * spec_lot.share
            # Date it turns long-term.
            long_on = _plus_year_and_day(spec_lot.acquired)
            # Build the lot: cost = value × cost ratio; ELSS funds are locked for 3 years.
            lots.append(
                Lot(
                    acquired=spec_lot.acquired,
                    units=units * spec_lot.share,
                    value=lot_value,
                    cost=lot_value * spec_lot.cost_ratio,
                    long_term_on=long_on,
                    days_to_long=(_d(long_on) - _d(book.today)).days,
                    locked_until=_plus_year_and_day(spec_lot.acquired, 3)
                    if fund and fund.category == "ELSS"
                    else None,
                )
            )
        # Build the position with names, class, source and as-of date.
        out.append(
            Position(
                id=f"{spec.id}-{i}",
                kind=h.kind,
                ref=h.ref,
                name=fund.name if fund else stock.name,  # type: ignore[union-attr]
                short_name=fund.short_name if fund else stock.name,  # type: ignore[union-attr]
                category=fund.category if fund else "Direct equity",
                asset_class=fund.asset_class if fund else "Equity",
                units=units,
                price=price,
                value=value,
                source=h.source,
                account=h.account,
                as_of=book.source_as_of[h.source],
                lots=tuple(lots),
            )
        )
    # Immutable result.
    return tuple(out)


@dataclass
# Running total while adding up one company's exposure.
class _Acc:
    # Rupees in total.
    value: float = 0.0
    # Of which held as direct shares.
    direct: float = 0.0
    # Of which held through funds.
    via: list[tuple[str, float, float]] = field(default_factory=list)


# Look-through: add up what the client really owns in each company, directly and via funds.
def exposures(
    positions: tuple[Position, ...], book: Book, total: float
) -> tuple[tuple[Exposure, ...], float]:
    # Totals per company symbol.
    acc: dict[str, _Acc] = {}
    # Equity value, and how much of it we could see through.
    equity = covered = 0.0
    # Each holding.
    for p in positions:
        # Only equity has company exposure.
        if p.asset_class != "Equity":
            continue
        # Count this holding's equity.
        equity += p.value
        # A share is 100% one company; a fund contributes its published weights.
        items = [(p.ref, 100.0)] if p.kind == "stock" else list(book.funds[p.ref].weights.items())
        # Each company in the holding.
        for symbol, w in items:
            # Skip companies we have no data for.
            if symbol not in book.stocks:
                continue
            # Rupees in that company = holding value × weight.
            v = p.value * w / 100
            # Running total for the company.
            e = acc.setdefault(symbol, _Acc())
            # Add to its total…
            e.value += v
            # …and to the part we could see through.
            covered += v
            # Direct share…
            if p.kind == "stock":
                # …counted as direct.
                e.direct += v
            # Fund…
            else:
                # …remember which fund and how much.
                e.via.append((p.short_name, v, w))
    # Build Exposure records, biggest company first.
    result = tuple(
        sorted(
            (
                Exposure(
                    sym,
                    book.stocks[sym].name,
                    book.stocks[sym].sector,
                    e.value,
                    e.value / total * 100,
                    e.direct,
                    tuple(e.via),
                )
                for sym, e in acc.items()
            ),
            key=lambda x: -x.value,
        )
    )
    # Exposures, and the share of equity we could look through.
    return result, (covered / equity * 100 if equity else 0.0)


# Pairwise overlap of equity funds.
def overlaps(positions: tuple[Position, ...], book: Book) -> tuple[Overlap, ...]:
    """Pairwise overlap of equity funds: Σ min(wₐ, w_b) over shared holdings (in %)."""
    # Only equity funds.
    funds = [p for p in positions if p.kind == "fund" and p.asset_class == "Equity"]
    # One record per pair.
    out: list[Overlap] = []
    # Every pair of funds once.
    for a, b in combinations(funds, 2):
        # Each fund's weights by company.
        wa, wb = book.funds[a.ref].weights, book.funds[b.ref].weights
        # Companies both funds hold, with both weights, biggest overlap first.
        common = sorted(
            (
                (s, book.stocks[s].name, wa[s], wb[s])
                for s in wa.keys() & wb.keys()
                if s in book.stocks
            ),
            key=lambda c: -min(c[2], c[3]),
        )
        # Overlap % = sum over shared companies of the smaller weight.
        out.append(Overlap(a, b, sum(min(c[2], c[3]) for c in common), tuple(common)))
    # Most overlapping pair first.
    return tuple(sorted(out, key=lambda o: -o.pct))


# The main entry point: compute everything for one client.
def snapshot(client_id: str, book: Book) -> Snapshot:
    # The client's holdings and risk profile.
    spec = book.client(client_id)
    # Value every holding.
    positions = build_positions(spec, book)
    # Portfolio value.
    total = sum(p.value for p in positions)
    # Rupees per asset class.
    allocation: dict[str, float] = {
        c: sum(p.value for p in positions if p.asset_class == c) for c in ASSET_CLASSES
    }
    # As a percentage of the total.
    allocation_pct: dict[str, float] = {c: allocation[c] / total * 100 for c in ASSET_CLASSES}
    # The model portfolio for the client's risk profile.
    target = book.models[spec.risk]
    # Actual minus target, per class.
    drift: dict[str, float] = {c: allocation_pct[c] - target[c] for c in ASSET_CLASSES}
    # Company-level exposures.
    exp, lt_pct = exposures(positions, book, total)
    # All lots of equity holdings.
    eq_lots = [(p, lot) for p in positions if p.asset_class == "Equity" for lot in p.lots]
    # Long-term gains available now: in profit, past the long-term date, not locked (ELSS).
    lt_gain = sum(
        lot.gain
        for _, lot in eq_lots
        if lot.is_long and lot.gain > 0 and not (lot.locked_until and lot.locked_until > book.today)
    )
    # Not-yet-long-term lots that turn long-term within 30 days.
    upcoming = tuple(
        UpcomingLot(p, lot) for p, lot in eq_lots if not lot.is_long and lot.days_to_long <= 30
    )
    # Bundle it all; exemption left = yearly allowance minus gains already realised.
    return Snapshot(
        client=spec,
        today=book.today,
        positions=positions,
        total=total,
        allocation=allocation,
        allocation_pct=allocation_pct,
        target=target,
        drift=drift,
        exposures=exp,
        look_through_pct=lt_pct,
        overlaps=overlaps(positions, book),
        lt_gain_unrealised=lt_gain,
        exemption_left=max(0.0, book.ltcg_exemption - spec.realised_ltcg),
        upcoming_lots=upcoming,
    )
