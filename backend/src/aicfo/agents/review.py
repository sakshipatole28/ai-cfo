"""Review pipeline as a LangGraph state graph.

    load_snapshot → compute_evidence ─┬─ overlap_analyst ────┐
                                      ├─ allocation_analyst ─┼→ rank → explain → compliance → verify → END
                                      └─ tax_analyst ────────┘

* Deterministic nodes: load_snapshot, compute_evidence, rank, verify.
* Agents: three analysts, the explainer (uses RAG for citations) and the compliance
  agent (rules → ML classifier → LLM judge). With no model configured, each agent
  falls back to its deterministic policy so the pipeline always runs (CI, demos).
* Every node appends a trace event (duration, what it decided and why).
"""

from __future__ import annotations

import json
import math
import operator
import re
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Annotated, Any, ClassVar, Literal, TypedDict, cast

from langgraph.graph import END, START, StateGraph

from aicfo.agents.tools import all_evidence, evidence_text
from aicfo.core.analytics import Evidence, Snapshot, snapshot
from aicfo.core.book import Book, load_book
from aicfo.core.format import day, inr, inr_short, pct, pts
from aicfo.llm import LLMError, LLMProvider
from aicfo.ml.compliance_classifier import get_classifier
from aicfo.rag.guard import check_answer
from aicfo.rag.retriever import HybridRetriever
from aicfo.rag.text import numbers

Severity = Literal["high", "medium", "low"]
Profile = Literal["RIA", "MFD"]

# Firm policy thresholds (data/kb/firm-ips.md)
OVERLAP_REVIEW, OVERLAP_HIGH = 60.0, 70.0
DRIFT_BAND, DRIFT_HIGH = 5.0, 10.0
CONCENTRATION = 7.0


@dataclass
class Candidate:
    id: str
    kind: str
    agent: str
    severity: Severity
    title: str
    evidence_ids: list[str]
    impact: float
    rationale: str


@dataclass
class Draft:
    candidate: Candidate
    text: str
    citations: list[dict[str, str]] = field(default_factory=list)
    author: str = "template"
    compliance: dict[str, Any] = field(default_factory=dict)
    verifier: dict[str, Any] = field(default_factory=dict)
    status: Literal["draft", "dropped"] = "draft"


@dataclass
class TraceEvent:
    node: str
    kind: Literal["tool", "agent", "guard"]
    ms: float
    summary: str
    detail: dict[str, Any] = field(default_factory=dict)


class ReviewState(TypedDict, total=False):
    client_id: str
    profile: Profile
    dismissed: list[str]
    snapshot: Snapshot
    evidence: dict[str, Evidence]
    candidates: Annotated[list[Candidate], operator.add]
    ranked: list[Candidate]
    drafts: list[Draft]
    trace: Annotated[list[TraceEvent], operator.add]


def _timed(
    node: str,
    kind: Literal["tool", "agent", "guard"],
    fn: Callable[[ReviewState], tuple[dict[str, Any], str, dict[str, Any]]],
) -> Callable[[ReviewState], dict[str, Any]]:
    def run(state: ReviewState) -> dict[str, Any]:
        t0 = time.perf_counter()
        update, summary, detail = fn(state)
        update["trace"] = [
            TraceEvent(node, kind, round((time.perf_counter() - t0) * 1000, 2), summary, detail)
        ]
        return update

    return run


def _json_block(text: str) -> Any:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in model reply")
    return json.loads(m.group(0))


ANALYST_PROMPT = """You are the {role} for a SEBI-registered adviser.
You receive evidence items computed by tested code. Decide which items matter for this client and how severe they are.
Firm policy: {policy}
Return ONLY JSON: {{"selected": [{{"evidence_id": "...", "severity": "high|medium|low", "title": "short title", "rationale": "one sentence"}}]}}
Use only evidence ids you were given. Never compute or invent numbers."""


class ReviewPipeline:
    def __init__(
        self, retriever: HybridRetriever, llm: LLMProvider | None = None, book: Book | None = None
    ) -> None:
        self.retriever = retriever
        self.llm = llm
        self.book = book or load_book()
        self.classifier = get_classifier()
        self.graph = self._build()

    # ---------- deterministic nodes ----------
    def _load(self, state: ReviewState) -> tuple[dict[str, Any], str, dict[str, Any]]:
        s = snapshot(state["client_id"], self.book)
        return (
            {"snapshot": s},
            f"{len(s.positions)} positions, {inr_short(s.total)}",
            {"engine": s.engine_version, "as_of": s.today},
        )

    def _evidence(self, state: ReviewState) -> tuple[dict[str, Any], str, dict[str, Any]]:
        ev = all_evidence(state["snapshot"], self.book)
        return {"evidence": ev}, f"{len(ev)} evidence records computed", {"ids": list(ev)}

    # ---------- analyst agents ----------
    def _llm_select(
        self, role: str, policy: str, items: list[Evidence]
    ) -> list[dict[str, str]] | None:
        if self.llm is None or not items:
            return None
        listing = "\n".join(f"- {e.id}: {e.title} = {e.result}" for e in items)
        try:
            reply = self.llm.complete(
                ANALYST_PROMPT.format(role=role, policy=policy), f"Evidence:\n{listing}"
            )
            selected = _json_block(reply)["selected"]
            ids = {e.id for e in items}
            valid = [
                s
                for s in selected
                if s.get("evidence_id") in ids and s.get("severity") in ("high", "medium", "low")
            ]
            return valid
        except (LLMError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return None

    def _analyst(
        self,
        name: str,
        role: str,
        policy: str,
        prefixes: tuple[str, ...],
        rule: Callable[[Evidence, Snapshot], Candidate | None],
    ) -> Callable[[ReviewState], tuple[dict[str, Any], str, dict[str, Any]]]:
        def run(state: ReviewState) -> tuple[dict[str, Any], str, dict[str, Any]]:
            s = state["snapshot"]
            items = [e for e in state["evidence"].values() if e.id.startswith(prefixes)]
            by_rule = {c.evidence_ids[0]: c for e in items if (c := rule(e, s))}
            chosen = self._llm_select(role, policy, items)
            mode = "policy"
            if chosen is not None:
                mode = "llm"
                picked = []
                for sel in chosen:
                    base = by_rule.get(sel["evidence_id"]) or rule(
                        state["evidence"][sel["evidence_id"]], s
                    )
                    if base:
                        base.severity = cast(Severity, sel["severity"])
                        base.rationale = sel.get("rationale", base.rationale)
                        picked.append(base)
            else:
                picked = list(by_rule.values())
            summary = f"{len(picked)} of {len(items)} items flagged ({mode})"
            return (
                {"candidates": picked},
                summary,
                {"mode": mode, "flagged": [c.evidence_ids[0] for c in picked]},
            )

        return run

    @staticmethod
    def _overlap_rule(e: Evidence, s: Snapshot) -> Candidate | None:
        if e.id.startswith("overlap:"):
            p = e.values[0]
            if p >= OVERLAP_REVIEW:
                return Candidate(
                    f"{s.client.id}:{e.id}",
                    "overlap",
                    "overlap_analyst",
                    "high" if p >= OVERLAP_HIGH else "medium",
                    "Two funds hold largely the same companies",
                    [e.id],
                    e.values[1],
                    f"Overlap {pct(p)} is above the {OVERLAP_REVIEW:.0f}% review threshold.",
                )
        if e.id.startswith("exposure:") and e.values[0] >= CONCENTRATION:
            return Candidate(
                f"{s.client.id}:{e.id}",
                "concentration",
                "overlap_analyst",
                "medium" if e.values[0] >= 9 else "low",
                f"Hidden concentration in {e.title.split(': ', 1)[1]}",
                [e.id],
                e.values[1],
                f"Single-company exposure {pct(e.values[0])} is above the {CONCENTRATION:.0f}% flag.",
            )
        return None

    @staticmethod
    def _drift_rule(e: Evidence, s: Snapshot) -> Candidate | None:
        d = e.values[2]
        if abs(d) < DRIFT_BAND:
            return None
        cls = e.id.split(":")[1].capitalize()
        return Candidate(
            f"{s.client.id}:{e.id}",
            "drift",
            "allocation_analyst",
            "high" if abs(d) >= DRIFT_HIGH else "medium",
            f"{cls} is {'above' if d > 0 else 'below'} the agreed model",
            [e.id],
            abs(e.values[3]),
            f"Drift {pts(d)} is outside the ±{DRIFT_BAND:.0f} pt band.",
        )

    @staticmethod
    def _tax_rule(e: Evidence, s: Snapshot) -> Candidate | None:
        if e.id.startswith("lot:"):
            return Candidate(
                f"{s.client.id}:{e.id}",
                "tax-timing",
                "tax_analyst",
                "medium",
                "A lot turns long-term soon",
                [e.id],
                e.values[2],
                f"Turns long-term in {e.values[1]:.0f} days with a gain.",
            )
        if e.id == "tax:exemption":
            return Candidate(
                f"{s.client.id}:{e.id}",
                "harvest",
                "tax_analyst",
                "low",
                "Unused long-term gains exemption this year",
                [e.id],
                e.values[2],
                "Exemption headroom and unrealised long-term gains both exist.",
            )
        return None

    # ---------- rank ----------
    def _rank(self, state: ReviewState) -> tuple[dict[str, Any], str, dict[str, Any]]:
        dismissed = set(state.get("dismissed", []))
        weight = {"high": 3, "medium": 2, "low": 1}
        cands = [c for c in state["candidates"] if c.id not in dismissed]
        # Keep only the strongest drift item; one finding per asset-class story.
        drift = sorted((c for c in cands if c.kind == "drift"), key=lambda c: -c.impact)[:1]
        cands = [c for c in cands if c.kind != "drift"] + drift
        tax_timing = sorted((c for c in cands if c.kind == "tax-timing"), key=lambda c: -c.impact)[
            :1
        ]
        cands = [c for c in cands if c.kind != "tax-timing"] + tax_timing
        conc = sorted((c for c in cands if c.kind == "concentration"), key=lambda c: -c.impact)[:1]
        cands = [c for c in cands if c.kind != "concentration"] + conc
        ov = sorted((c for c in cands if c.kind == "overlap"), key=lambda c: -c.impact)[:1]
        cands = [c for c in cands if c.kind != "overlap"] + ov
        ranked = sorted(cands, key=lambda c: (-weight[c.severity], -math.log10(1 + c.impact)))
        return (
            {"ranked": ranked},
            f"{len(ranked)} findings ranked, {len(dismissed)} previously dismissed skipped",
            {"order": [c.id for c in ranked]},
        )

    # ---------- explainer (RAG) ----------
    RAG_QUERY: ClassVar[dict[str, str]] = {
        "overlap": "how overlap between two mutual funds is calculated from monthly portfolio disclosure",
        "concentration": "look-through exposure to a company through mutual fund holdings",
        "drift": "rebalancing review when asset class drifts from model portfolio",
        "tax-timing": "holding period long-term short-term capital gains tax rate listed equity",
        "harvest": "long-term capital gains exemption 1.25 lakh in a year",
    }

    def _template(self, c: Candidate, e: Evidence, s: Snapshot) -> str:
        if c.kind == "overlap":
            a, b = e.title.removeprefix("Overlap: ").split(" × ")
            return (
                f"{{client}}'s {a} and {b} share {pct(e.values[0], 0)} of their portfolios. {inr_short(e.values[1])} is spread across "
                f"two funds that give very similar exposure, so the second fund adds little diversification [1]."
            )
        if c.kind == "concentration":
            name = e.title.split(": ", 1)[1]
            return (
                f"Once fund holdings are looked through, {name} is {pct(e.values[0])} of {{client}}'s total portfolio "
                f"({inr(e.values[1])}), held through {int(e.values[2])} funds{' and directly' if any(lbl == 'Direct shares' for lbl, _, _ in e.inputs) else ''} [1]."
            )
        if c.kind == "drift":
            cls = e.id.split(":")[1].capitalize()
            d, gap = e.values[2], e.values[3]
            return (
                f"{cls} is {pct(e.values[0])} of {{client}}'s portfolio against a {pct(e.values[1], 0)} target for a "
                f"{s.client.risk.lower()} profile: {pts(d)}, about {inr_short(abs(gap))} {'more' if d > 0 else 'less'} than the model allows [1]."
            )
        if c.kind == "tax-timing":
            lt = next(v for lbl, v, _ in e.inputs if lbl == "Long-term from")
            return (
                f"A lot with an unrealised gain of {inr(e.values[0])} becomes long-term on {lt}, in {int(e.values[1])} days. "
                f"If {{client}} plans to sell it, waiting until then lowers the tax by about {inr(e.values[2])} [1]."
            )
        return (
            f"{{client}} has {inr(e.values[0])} of the ₹1.25 lakh long-term gains exemption left in {self.book.fy_label}, and long-term lots hold "
            f"{inr(e.values[1])} of unrealised gains. Booking gains within the exemption could avoid up to {inr(e.values[2])} of future tax [1]."
        )

    def _explain(self, state: ReviewState) -> tuple[dict[str, Any], str, dict[str, Any]]:
        s, drafts, retrievals = state["snapshot"], [], {}
        for c in state["ranked"]:
            e = state["evidence"][c.evidence_ids[0]]
            hits = self.retriever.search(self.RAG_QUERY[c.kind], k=1)
            cites = [
                {
                    "n": "1",
                    "doc_id": h.chunk.doc.id,
                    "chunk_id": h.chunk.id,
                    "title": h.chunk.doc.title,
                    "section": h.chunk.section,
                    "issuer": h.chunk.doc.issuer,
                    "text": h.chunk.text,
                }
                for h in hits
            ]
            retrievals[c.id] = [h.chunk.id for h in hits]
            text, author = self._template(c, e, s), "template"
            if self.llm is not None:
                passage = cites[0]["text"] if cites else ""
                prompt = (
                    "Rewrite the DRAFT for an adviser in plain language, at most 3 sentences. Keep every number exactly as written, "
                    "keep the {client} placeholder and keep the [1] citation. Add no new numbers and no buy/sell instructions."
                )
                try:
                    out = self.llm.complete(
                        prompt, f"DRAFT: {text}\n\nEVIDENCE: {evidence_text(e)}\n\n[1] {passage}"
                    ).strip()
                    if out:
                        text, author = out, "llm"
                except LLMError:
                    pass
            drafts.append(Draft(c, text, cites, author))
        return (
            {"drafts": drafts},
            f"{len(drafts)} drafts written, each with a cited rule",
            {"retrieved": retrievals},
        )

    # ---------- compliance (rules → ML → LLM judge) ----------
    def _compliance(self, state: ReviewState) -> tuple[dict[str, Any], str, dict[str, Any]]:
        profile = state.get("profile", "RIA")
        blocked = 0
        for d in state["drafts"]:
            text = d.text.replace("{client}", "the client")
            rules = check_answer(text)
            p = self.classifier.score(text)
            judge = "skipped"
            if 0.3 <= p < 0.7 and self.llm is not None:
                try:
                    v = _json_block(
                        self.llm.complete(
                            'Does this text tell someone to buy, sell or hold a specific security, or promise returns? Reply JSON {"advice": true|false, "reason": "..."}',
                            text,
                        )
                    )
                    judge = "advice" if v.get("advice") else "pass"
                except (LLMError, ValueError, json.JSONDecodeError):
                    judge = "error"
            advice_like = (not rules.allowed) or p >= 0.5 or judge == "advice"
            d.compliance = {
                "profile": profile,
                "rules": "pass" if rules.allowed else rules.reason,
                "classifier": round(p, 3),
                "judge": judge,
                "advice_like": advice_like,
            }
            if not rules.allowed or (profile == "MFD" and advice_like):
                d.status, blocked = "dropped", blocked + 1
                d.compliance["blocked"] = True
        return (
            {"drafts": state["drafts"]},
            f"{blocked} blocked for profile {profile}",
            {"scores": {d.candidate.id: d.compliance["classifier"] for d in state["drafts"]}},
        )

    # ---------- verifier ----------
    def _allowed_numbers(self, d: Draft, evidence: dict[str, Evidence]) -> set[str]:
        sources = [
            evidence_text(evidence[i]) + " " + evidence[i].title for i in d.candidate.evidence_ids
        ]
        sources += [c["text"] for c in d.citations]
        return set().union(*(numbers(t) for t in sources))

    def check(self, d: Draft, evidence: dict[str, Evidence]) -> list[str]:
        issues = []
        body = re.sub(r"\[\d+\]", "", d.text)
        extra = sorted(numbers(body) - self._allowed_numbers(d, evidence))
        if extra:
            issues.append(f"unsupported numbers: {extra}")
        if any(int(n) > len(d.citations) or int(n) < 1 for n in re.findall(r"\[(\d+)\]", d.text)):
            issues.append("citation out of range")
        if not re.search(r"\[\d+\]", d.text):
            issues.append("no citation")
        if re.search(r"\{(?!client\})[^}]*\}", d.text):
            issues.append("unknown placeholder")
        return issues

    def _verify(self, state: ReviewState) -> tuple[dict[str, Any], str, dict[str, Any]]:
        rewrites = dropped = 0
        for d in state["drafts"]:
            if d.status == "dropped":
                continue
            issues = self.check(d, state["evidence"])
            if (
                issues and d.author == "llm"
            ):  # fall back to the template, which is built from evidence only
                rewrites += 1
                d.text, d.author = (
                    self._template(
                        d.candidate,
                        state["evidence"][d.candidate.evidence_ids[0]],
                        state["snapshot"],
                    ),
                    "template",
                )
                issues = self.check(d, state["evidence"])
            d.verifier = {"passed": not issues, "issues": issues, "rewrites": rewrites}
            if issues:
                d.status, dropped = "dropped", dropped + 1
        kept = sum(d.status == "draft" for d in state["drafts"])
        return (
            {"drafts": state["drafts"]},
            f"{kept} passed, {rewrites} rewritten, {dropped} dropped",
            {},
        )

    # ---------- graph ----------
    def _build(self) -> Any:
        g = StateGraph(ReviewState)

        def node(
            name: str,
            kind: Literal["tool", "agent", "guard"],
            fn: Callable[[ReviewState], tuple[dict[str, Any], str, dict[str, Any]]],
        ) -> None:
            g.add_node(name, cast(Any, _timed(name, kind, fn)))

        node("load_snapshot", "tool", self._load)
        node("compute_evidence", "tool", self._evidence)
        node(
            "overlap_analyst",
            "agent",
            self._analyst(
                "overlap_analyst",
                "Overlap and Concentration Analyst",
                "flag overlap ≥60% (≥70% high) and single-company exposure ≥7%",
                ("overlap:", "exposure:"),
                self._overlap_rule,
            ),
        )
        node(
            "allocation_analyst",
            "agent",
            self._analyst(
                "allocation_analyst",
                "Allocation and Drift Analyst",
                "flag asset-class drift beyond ±5 pts (≥10 pts high)",
                ("drift:",),
                self._drift_rule,
            ),
        )
        node(
            "tax_analyst",
            "agent",
            self._analyst(
                "tax_analyst",
                "Tax Analyst",
                "flag lots turning long-term within 30 days with a gain, and unused LTCG exemption",
                ("lot:", "tax:"),
                self._tax_rule,
            ),
        )
        node("rank", "tool", self._rank)
        node("explainer", "agent", self._explain)
        node("compliance", "guard", self._compliance)
        node("verifier", "guard", self._verify)
        g.add_edge(START, "load_snapshot")
        g.add_edge("load_snapshot", "compute_evidence")
        for analyst in ("overlap_analyst", "allocation_analyst", "tax_analyst"):
            g.add_edge("compute_evidence", analyst)
        g.add_edge(["overlap_analyst", "allocation_analyst", "tax_analyst"], "rank")
        g.add_edge("rank", "explainer")
        g.add_edge("explainer", "compliance")
        g.add_edge("compliance", "verifier")
        g.add_edge("verifier", END)
        return g.compile()

    def run(
        self, client_id: str, profile: Profile = "RIA", dismissed: list[str] | None = None
    ) -> ReviewState:
        result: ReviewState = self.graph.invoke(
            {
                "client_id": client_id,
                "profile": profile,
                "dismissed": dismissed or [],
                "candidates": [],
                "trace": [],
            }
        )
        return result


def serialise(state: ReviewState) -> dict[str, Any]:
    """JSON-friendly view of a run: drafts, evidence and trace (no personal data beyond the synthetic book)."""
    s = state["snapshot"]
    return {
        "client_id": s.client.id,
        "as_of": s.today,
        "engine": s.engine_version,
        "summary": {
            "total": round(s.total),
            "allocation_pct": {k: round(v, 2) for k, v in s.allocation_pct.items()},
        },
        "drafts": [
            {
                **asdict(d.candidate),
                "text": d.text,
                "citations": d.citations,
                "author": d.author,
                "compliance": d.compliance,
                "verifier": d.verifier,
                "status": d.status,
            }
            for d in state["drafts"]
        ],
        "evidence": {
            k: {**asdict(v), "values": list(v.values)}
            for k, v in state["evidence"].items()
            if any(k in d.candidate.evidence_ids for d in state["drafts"])
        },
        "trace": [asdict(t) for t in state["trace"]],
        "_day": day(s.today),
    }
