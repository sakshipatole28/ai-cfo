"""Synthetic demo book (data/synthetic/book.json), shared with the web console."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from aicfo.config import REPO_ROOT

# The synthetic book shared with the console (data/synthetic/book.json).
BOOK_PATH = REPO_ROOT / "data" / "synthetic" / "book.json"
# The four asset classes.
AssetClass = Literal["Equity", "Debt", "Gold", "Cash"]
# Same, as a tuple for looping.
ASSET_CLASSES: tuple[AssetClass, ...] = ("Equity", "Debt", "Gold", "Cash")


# A directly held share.
@dataclass(frozen=True)
class Stock:
    # Ticker.
    symbol: str
    # Company name.
    name: str
    # Sector.
    sector: str
    # Last price.
    price: float
    # ISIN code, if known.
    isin: str | None = None


# A mutual fund.
@dataclass(frozen=True)
class Fund:
    # Short code, e.g. NSB.
    id: str
    # ISIN code.
    isin: str
    # Full name.
    name: str
    # Name used in sentences.
    short_name: str
    # SEBI category (Flexi Cap, ELSS…).
    category: str
    # Equity, Debt, Gold or Cash.
    asset_class: AssetClass
    # Net asset value per unit.
    nav: float
    # Top holdings: company symbol → weight in %.
    weights: dict[str, float]


# A purchase lot as a share of a holding.
@dataclass(frozen=True)
class LotSpec:
    # Purchase date.
    acquired: str
    # Share of the holding's value.
    share: float
    # Cost ÷ current value (below 1 means a gain).
    cost_ratio: float


# One holding in a client's portfolio.
@dataclass(frozen=True)
class HoldingSpec:
    # Fund code or share symbol.
    ref: str
    # fund or stock.
    kind: Literal["fund", "stock"]
    # Where the data came from (CDSL statement, Dhan…).
    source: str
    # Pseudonymous account reference.
    account: str
    # Purchase lots.
    lots: tuple[LotSpec, ...]
    # Value in rupees (funds).
    value: float | None = None
    # Quantity (shares).
    qty: float | None = None


# A client of the synthetic firm.
@dataclass(frozen=True)
class ClientSpec:
    # Pseudonymous id used everywhere on the server.
    id: str
    # Fictional name (kept only in the browser in production).
    name: str
    # City.
    city: str
    # Age.
    age: int
    # Risk profile that selects the model portfolio.
    risk: str
    # Date of the last review.
    last_review: str
    # Long-term gains already realised this year.
    realised_ltcg: float
    # Dhan connection status.
    dhan: str
    # All holdings.
    holdings: tuple[HoldingSpec, ...]


# The whole synthetic book.
@dataclass(frozen=True)
class Book:
    # The 'as of' date for every calculation.
    today: str
    # Financial year label.
    fy_label: str
    # Yearly long-term gains exemption (₹).
    ltcg_exemption: float
    # Long-term rate.
    ltcg_rate: float
    # Short-term rate.
    stcg_rate: float
    # Month of the fund holdings disclosures.
    disclosure_month: str
    # As-of date per data source.
    source_as_of: dict[str, str]
    # Target allocation per risk profile.
    models: dict[str, dict[str, float]]
    # Shares by symbol.
    stocks: dict[str, Stock]
    # Funds by code.
    funds: dict[str, Fund]
    # Clients by id.
    clients: dict[str, ClientSpec]

    # Look a client up by id.
    def client(self, client_id: str) -> ClientSpec:
        # Find them.
        try:
            # The client.
            return self.clients[client_id]
        # Unknown id…
        except KeyError as exc:
            # …says which.
            raise KeyError(f"unknown client {client_id!r}") from exc


# Build a client from the JSON.
def _client(raw: dict[str, Any]) -> ClientSpec:
    # Each holding with its lots.
    holdings = tuple(
        HoldingSpec(
            ref=h["ref"],
            kind=h["kind"],
            source=h["source"],
            account=h["account"],
            value=h.get("value"),
            qty=h.get("qty"),
            lots=tuple(LotSpec(lt["acquired"], lt["share"], lt["costRatio"]) for lt in h["lots"]),
        )
        for h in raw["holdings"]
    )
    # Assemble the client.
    return ClientSpec(
        id=raw["id"],
        name=raw["name"],
        city=raw["city"],
        age=raw["age"],
        risk=raw["risk"],
        last_review=raw["lastReview"],
        realised_ltcg=raw["realisedLtcg"],
        dhan=raw["dhan"],
        holdings=holdings,
    )


# Build the whole book from parsed JSON.
def parse_book(raw: dict[str, Any]) -> Book:
    # Stocks, funds and clients become typed objects.
    return Book(
        today=raw["today"],
        fy_label=raw["fy_label"],
        ltcg_exemption=raw["ltcg_exemption"],
        ltcg_rate=raw["ltcg_rate"],
        stcg_rate=raw["stcg_rate"],
        disclosure_month=raw["disclosure_month"],
        source_as_of=raw["source_as_of"],
        models=raw["models"],
        stocks={
            k: Stock(v["symbol"], v["name"], v["sector"], v["price"], v.get("isin"))
            for k, v in raw["stocks"].items()
        },
        funds={
            k: Fund(
                v["id"],
                v["isin"],
                v["name"],
                v["shortName"],
                v["category"],
                v["assetClass"],
                v["nav"],
                v["weights"],
            )
            for k, v in raw["funds"].items()
        },
        clients={c["id"]: _client(c) for c in raw["clients"]},
    )


# Read the file once.
@lru_cache
# Load the synthetic book from disk.
def load_book(path: Path = BOOK_PATH) -> Book:
    # Parse the JSON file.
    return parse_book(json.loads(path.read_text(encoding="utf-8")))
