"""Synthetic demo book (data/synthetic/book.json), shared with the web console."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from aicfo.config import REPO_ROOT

BOOK_PATH = REPO_ROOT / "data" / "synthetic" / "book.json"
AssetClass = Literal["Equity", "Debt", "Gold", "Cash"]
ASSET_CLASSES: tuple[AssetClass, ...] = ("Equity", "Debt", "Gold", "Cash")


@dataclass(frozen=True)
class Stock:
    symbol: str
    name: str
    sector: str
    price: float
    isin: str | None = None


@dataclass(frozen=True)
class Fund:
    id: str
    isin: str
    name: str
    short_name: str
    category: str
    asset_class: AssetClass
    nav: float
    weights: dict[str, float]


@dataclass(frozen=True)
class LotSpec:
    acquired: str
    share: float
    cost_ratio: float


@dataclass(frozen=True)
class HoldingSpec:
    ref: str
    kind: Literal["fund", "stock"]
    source: str
    account: str
    lots: tuple[LotSpec, ...]
    value: float | None = None
    qty: float | None = None


@dataclass(frozen=True)
class ClientSpec:
    id: str
    name: str
    city: str
    age: int
    risk: str
    last_review: str
    realised_ltcg: float
    dhan: str
    holdings: tuple[HoldingSpec, ...]


@dataclass(frozen=True)
class Book:
    today: str
    fy_label: str
    ltcg_exemption: float
    ltcg_rate: float
    stcg_rate: float
    disclosure_month: str
    source_as_of: dict[str, str]
    models: dict[str, dict[str, float]]
    stocks: dict[str, Stock]
    funds: dict[str, Fund]
    clients: dict[str, ClientSpec]

    def client(self, client_id: str) -> ClientSpec:
        try:
            return self.clients[client_id]
        except KeyError as exc:
            raise KeyError(f"unknown client {client_id!r}") from exc


def _client(raw: dict[str, Any]) -> ClientSpec:
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


def parse_book(raw: dict[str, Any]) -> Book:
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


@lru_cache
def load_book(path: Path = BOOK_PATH) -> Book:
    return parse_book(json.loads(path.read_text(encoding="utf-8")))
