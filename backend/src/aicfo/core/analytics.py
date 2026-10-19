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


def _d(iso: str) -> date:
    return date.fromisoformat(iso)


def _plus_year_and_day(iso: str, years: int = 1) -> str:
    d = _d(iso)
    try:
        d = d.replace(year=d.year + years)
    except ValueError:  # 29 Feb
        d = d.replace(year=d.year + years, day=28)
    return (d + timedelta(days=1)).isoformat()


@dataclass(frozen=True)
class Lot:
    acquired: str
    units: float
    value: float
    cost: float
    long_term_on: str
    days_to_long: int
    locked_until: str | None

    @property
    def gain(self) -> float:
        return self.value - self.cost

    @property
    def is_long(self) -> bool:
        return self.days_to_long <= 0


@dataclass(frozen=True)
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
    def cost(self) -> float:
        return sum(lot.cost for lot in self.lots)


@dataclass(frozen=True)
class Exposure:
    symbol: str
    name: str
    sector: str
    value: float
    pct_of_total: float
    direct: float
    via_funds: tuple[tuple[str, float, float], ...]  # (fund short name, value, weight %)


@dataclass(frozen=True)
class Overlap:
    a: Position
    b: Position
    pct: float
    common: tuple[tuple[str, str, float, float], ...]  # (symbol, name, weight a, weight b)


@dataclass(frozen=True)
class UpcomingLot:
    position: Position
    lot: Lot


@dataclass(frozen=True)
class Snapshot:
    client: ClientSpec
    today: str
    positions: tuple[Position, ...]
    total: float
    allocation: dict[str, float]
    allocation_pct: dict[str, float]
    target: dict[str, float]
    drift: dict[str, float]
    exposures: tuple[Exposure, ...]
    look_through_pct: float
    overlaps: tuple[Overlap, ...]
    lt_gain_unrealised: float
    exemption_left: float
    upcoming_lots: tuple[UpcomingLot, ...]
    engine_version: str = "core-py 0.1.0"


@dataclass(frozen=True)
class Evidence:
    id: str
    title: str
    result: str
    formula_words: str
    formula: str
    inputs: tuple[tuple[str, str, str], ...]  # (label, value, source)
    steps: tuple[str, ...]
    values: tuple[float, ...] = field(default_factory=tuple)  # raw numbers the text may quote


def build_positions(spec: ClientSpec, book: Book) -> tuple[Position, ...]:
    out: list[Position] = []
    for i, h in enumerate(spec.holdings):
        fund = book.funds.get(h.ref) if h.kind == "fund" else None
        stock = book.stocks.get(h.ref) if h.kind == "stock" else None
        if fund is None and stock is None:
            raise KeyError(f"{spec.id}: unknown security {h.ref!r}")
        price = fund.nav if fund else stock.price  # type: ignore[union-attr]
        value = float(h.value or 0) if fund else float(h.qty or 0) * price
        units = value / price if fund else float(h.qty or 0)
        lots: list[Lot] = []
        for spec_lot in h.lots:
            lot_value = value * spec_lot.share
            long_on = _plus_year_and_day(spec_lot.acquired)
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
    return tuple(out)


@dataclass
class _Acc:
    value: float = 0.0
    direct: float = 0.0
    via: list[tuple[str, float, float]] = field(default_factory=list)


def exposures(
    positions: tuple[Position, ...], book: Book, total: float
) -> tuple[tuple[Exposure, ...], float]:
    acc: dict[str, _Acc] = {}
    equity = covered = 0.0
    for p in positions:
        if p.asset_class != "Equity":
            continue
        equity += p.value
        items = [(p.ref, 100.0)] if p.kind == "stock" else list(book.funds[p.ref].weights.items())
        for symbol, w in items:
            if symbol not in book.stocks:
                continue
            v = p.value * w / 100
            e = acc.setdefault(symbol, _Acc())
            e.value += v
            covered += v
            if p.kind == "stock":
                e.direct += v
            else:
                e.via.append((p.short_name, v, w))
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
    return result, (covered / equity * 100 if equity else 0.0)


def overlaps(positions: tuple[Position, ...], book: Book) -> tuple[Overlap, ...]:
    """Pairwise overlap of equity funds: Σ min(wₐ, w_b) over shared holdings (in %)."""
    funds = [p for p in positions if p.kind == "fund" and p.asset_class == "Equity"]
    out: list[Overlap] = []
    for a, b in combinations(funds, 2):
        wa, wb = book.funds[a.ref].weights, book.funds[b.ref].weights
        common = sorted(
            (
                (s, book.stocks[s].name, wa[s], wb[s])
                for s in wa.keys() & wb.keys()
                if s in book.stocks
            ),
            key=lambda c: -min(c[2], c[3]),
        )
        out.append(Overlap(a, b, sum(min(c[2], c[3]) for c in common), tuple(common)))
    return tuple(sorted(out, key=lambda o: -o.pct))


def snapshot(client_id: str, book: Book) -> Snapshot:
    spec = book.client(client_id)
    positions = build_positions(spec, book)
    total = sum(p.value for p in positions)
    allocation: dict[str, float] = {
        c: sum(p.value for p in positions if p.asset_class == c) for c in ASSET_CLASSES
    }
    allocation_pct: dict[str, float] = {c: allocation[c] / total * 100 for c in ASSET_CLASSES}
    target = book.models[spec.risk]
    drift: dict[str, float] = {c: allocation_pct[c] - target[c] for c in ASSET_CLASSES}
    exp, lt_pct = exposures(positions, book, total)
    eq_lots = [(p, lot) for p in positions if p.asset_class == "Equity" for lot in p.lots]
    lt_gain = sum(
        lot.gain
        for _, lot in eq_lots
        if lot.is_long and lot.gain > 0 and not (lot.locked_until and lot.locked_until > book.today)
    )
    upcoming = tuple(
        UpcomingLot(p, lot) for p, lot in eq_lots if not lot.is_long and lot.days_to_long <= 30
    )
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
