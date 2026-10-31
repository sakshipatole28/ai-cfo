"""Review pipeline as a LangGraph state graph.

    load_snapshot → compute_evidence ─┬─ overlap_analyst ────┐
                                      ├─ allocation_analyst ─┼→ rank → explain → compliance → verify → END
                                      └─ tax_analyst ────────┘

* Tools (plain code): load_snapshot, compute_evidence, rank.
* Agents (a model makes a choice): three analysts and the explainer (uses RAG for citations).
  With no model configured, each agent falls back to its deterministic policy so the
  pipeline always runs (CI, demos).
* Guards (checks that can block): compliance (rules → ML classifier → LLM judge for
  borderline wording) and the verifier (plain code).
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
from aicfo.rag.text import normalise_citations, numbers

# How serious a finding is.
Severity = Literal["high", "medium", "low"]
# Kind of firm: RIA may advise; MFD (distributor) is information-only, so advice-like text is blocked.
Profile = Literal["RIA", "MFD"]

# Firm policy thresholds (data/kb/firm-ips.md)
# Fund overlap % at which a pair is worth reviewing / is serious.
OVERLAP_REVIEW, OVERLAP_HIGH = 60.0, 70.0
# Allocation drift (percentage points) that is flagged / serious.
DRIFT_BAND, DRIFT_HIGH = 5.0, 10.0
# Look-through exposure to one company (% of the portfolio) that gets flagged.
CONCENTRATION = 7.0


# A possible finding picked by an analyst, before any text is written.
@dataclass
class Candidate:
    # Unique id, e.g. "<client>:overlap:NSB:HN50".
    id: str
    # Topic: overlap, concentration, drift, tax-timing or harvest.
    kind: str
    # Which analyst agent raised it.
    agent: str
    # high / medium / low.
    severity: Severity
    # Short headline.
    title: str
    # Ids of the computed Evidence records that back it.
    evidence_ids: list[str]
    # Rupee size, used to rank findings of equal severity.
    impact: float
    # One sentence on why it was flagged.
    rationale: str


# A written finding together with the checks it has passed.
@dataclass
class Draft:
    # The finding this text explains.
    candidate: Candidate
    # The wording; "{client}" is filled in by the browser so the server never holds names.
    text: str
    # Rule passages (from RAG) the text cites as [1].
    citations: list[dict[str, str]] = field(default_factory=list)
    # "template" (built from evidence) or "llm" (rewritten by a model).
    author: str = "template"
    # Result of the compliance checks (rules, classifier score, judge).
    compliance: dict[str, Any] = field(default_factory=dict)
    # Result of the number/citation verifier.
    verifier: dict[str, Any] = field(default_factory=dict)
    # "draft" (shown to the adviser) or "dropped" (a guard blocked it).
    status: Literal["draft", "dropped"] = "draft"


# One step of the run, recorded so the console can replay it.
@dataclass
class TraceEvent:
    # Name of the graph node.
    node: str
    # tool = code, agent = AI decision, guard = safety check.
    kind: Literal["tool", "agent", "guard"]
    # How long the node took, in milliseconds.
    ms: float
    # One-line outcome.
    summary: str
    # Extra facts (what was flagged, what was retrieved…).
    detail: dict[str, Any] = field(default_factory=dict)


# The shared state passed between graph nodes (LangGraph merges each node's output into it).
class ReviewState(TypedDict, total=False):
    # Which client is being reviewed (a pseudonymous id).
    client_id: str
    # RIA or MFD wording rules.
    profile: Profile
    # Finding ids the adviser dismissed before; they are not raised again.
    dismissed: list[str]
    # Positions, allocation and drift, computed by code.
    snapshot: Snapshot
    # Every computed number with its formula, by id.
    evidence: dict[str, Evidence]
    # Findings picked by the three analysts; operator.add merges the parallel branches.
    candidates: Annotated[list[Candidate], operator.add]
    # Candidates after de-duplication and ordering.
    ranked: list[Candidate]
    # Written findings.
    drafts: list[Draft]
    # Step-by-step record, appended to by every node.
    trace: Annotated[list[TraceEvent], operator.add]


# Wrap a node so it is timed and leaves a trace event.
def _timed(
    node: str,
    kind: Literal["tool", "agent", "guard"],
    fn: Callable[[ReviewState], tuple[dict[str, Any], str, dict[str, Any]]],
) -> Callable[[ReviewState], dict[str, Any]]:
    # The wrapped node that LangGraph calls.
    def run(state: ReviewState) -> dict[str, Any]:
        # Start the clock.
        t0 = time.perf_counter()
        # Run the real node; it returns its state update, a summary and details.
        update, summary, detail = fn(state)
        # Add this step to the trace.
        update["trace"] = [
            TraceEvent(node, kind, round((time.perf_counter() - t0) * 1000, 2), summary, detail)
        ]
        # Hand the update back to LangGraph.
        return update

    # Give LangGraph the wrapped node.
    return run


# Pull the JSON object out of a model reply (models often add chatter around it).
def _json_block(text: str) -> Any:
    # Find the first {...} block, across lines.
    m = re.search(r"\{.*\}", text, re.S)
    # No JSON at all: treat as a failed reply.
    if not m:
        raise ValueError("no JSON object in model reply")
    # Parse it; invalid JSON raises and the caller falls back to policy.
    return json.loads(m.group(0))


# Instruction for an analyst agent: choose from the given evidence; never invent numbers.
ANALYST_PROMPT = """You are the {role} for a SEBI-registered adviser.
You receive evidence items computed by tested code. Decide which items matter for this client and how severe they are.
Firm policy: {policy}
Return ONLY JSON: {{"selected": [{{"evidence_id": "...", "severity": "high|medium|low", "title": "short title", "rationale": "one sentence"}}]}}
Use only evidence ids you were given. Never compute or invent numbers."""


# Builds and runs the multi-agent review as a LangGraph state graph.
class ReviewPipeline:
    # Wire the pipeline: retriever for citations, optional LLM, the synthetic book.
    def __init__(
        self, retriever: HybridRetriever, llm: LLMProvider | None = None, book: Book | None = None
    ) -> None:
        # RAG search used by the explainer to cite the governing rule.
        self.retriever = retriever
        # Groq/Gemini (or None: every agent then follows firm policy).
        self.llm = llm
        # The synthetic client book.
        self.book = book or load_book()
        # ML model scoring how advice-like a sentence is.
        self.classifier = get_classifier()
        # Compile the graph once; it is reused for every run.
        self.graph = self._build()

    # ---------- deterministic nodes ----------
    # Node 1 (code): compute the client's snapshot.
    def _load(self, state: ReviewState) -> tuple[dict[str, Any], str, dict[str, Any]]:
        # Positions, allocation, drift, overlap, tax lots, all from tested code.
        s = snapshot(state["client_id"], self.book)
        # State update, summary line, details for the trace.
        return (
            {"snapshot": s},
            f"{len(s.positions)} positions, {inr_short(s.total)}",
            {"engine": s.engine_version, "as_of": s.today},
        )

    # Node 2 (code): turn the snapshot into Evidence records.
    def _evidence(self, state: ReviewState) -> tuple[dict[str, Any], str, dict[str, Any]]:
        # Each Evidence holds its formula, inputs, steps and result.
        ev = all_evidence(state["snapshot"], self.book)
        # Store the evidence; analysts read only from here.
        return {"evidence": ev}, f"{len(ev)} evidence records computed", {"ids": list(ev)}

    # ---------- analyst agents ----------
    # Ask the model which evidence items matter and how severe they are.
    def _llm_select(
        self, role: str, policy: str, items: list[Evidence]
    ) -> list[dict[str, str]] | None:
        # No model configured (or nothing to judge): the caller uses firm policy.
        if self.llm is None or not items:
            return None
        # Show the model one line per evidence item: id, title and result.
        listing = "\n".join(f"- {e.id}: {e.title} = {e.result}" for e in items)
        # Any model or parsing failure falls back to policy instead of breaking the review.
        try:
            # One model call per analyst.
            reply = self.llm.complete(
                ANALYST_PROMPT.format(role=role, policy=policy), f"Evidence:\n{listing}"
            )
            # Parse the model's JSON answer.
            selected = _json_block(reply)["selected"]
            # The only ids the model may choose.
            ids = {e.id for e in items}
            # Keep only picks with a known evidence id and a valid severity.
            valid = [
                s
                for s in selected
                if s.get("evidence_id") in ids and s.get("severity") in ("high", "medium", "low")
            ]
            # Validated picks.
            return valid
        # Provider error, bad JSON or missing keys: report "no answer".
        except (LLMError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            # None means: use the deterministic firm policy.
            return None

    # Build one analyst node (overlap, allocation or tax) from a role, a policy and a rule.
    def _analyst(
        self,
        name: str,
        role: str,
        policy: str,
        prefixes: tuple[str, ...],
        rule: Callable[[Evidence, Snapshot], Candidate | None],
    ) -> Callable[[ReviewState], tuple[dict[str, Any], str, dict[str, Any]]]:
        # The node LangGraph runs; the three analysts run in parallel.
        def run(state: ReviewState) -> tuple[dict[str, Any], str, dict[str, Any]]:
            # The client's computed snapshot.
            s = state["snapshot"]
            # Only the evidence kinds this analyst is responsible for.
            items = [e for e in state["evidence"].values() if e.id.startswith(prefixes)]
            # What firm policy would flag, by evidence id.
            by_rule = {c.evidence_ids[0]: c for e in items if (c := rule(e, s))}
            # What the model chooses (or None).
            chosen = self._llm_select(role, policy, items)
            # Assume policy until the model answers.
            mode = "policy"
            # The model answered: use its picks.
            if chosen is not None:
                # Record that the model decided.
                mode = "llm"
                # Findings to raise.
                picked = []
                # Each pick the model made.
                for sel in chosen:
                    # Reuse the policy candidate, or build one from the evidence.
                    base = by_rule.get(sel["evidence_id"]) or rule(
                        state["evidence"][sel["evidence_id"]], s
                    )
                    # Skip evidence that cannot become a finding.
                    if base:
                        # The model decides severity…
                        base.severity = cast(Severity, sel["severity"])
                        # …and gives the reason.
                        base.rationale = sel.get("rationale", base.rationale)
                        # Keep it.
                        picked.append(base)
            # No model answer: follow firm policy.
            else:
                # All policy-flagged items.
                picked = list(by_rule.values())
            # Trace line, e.g. "2 of 6 items flagged (llm)".
            summary = f"{len(picked)} of {len(items)} items flagged ({mode})"
            # Candidates to merge, the summary and the flagged ids.
            return (
                {"candidates": picked},
                summary,
                {"mode": mode, "flagged": [c.evidence_ids[0] for c in picked]},
            )

        # The analyst node.
        return run

    # Policy rule: when does overlap or concentration evidence become a finding?
    @staticmethod
    # Overlap and single-company concentration rules.
    def _overlap_rule(e: Evidence, s: Snapshot) -> Candidate | None:
        # Fund-pair overlap evidence.
        if e.id.startswith("overlap:"):
            # The overlap percentage.
            p = e.values[0]
            # Only flag overlap above the review threshold.
            if p >= OVERLAP_REVIEW:
                # Build the finding; severity is high above the serious threshold.
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
        # Look-through exposure to one company.
        if e.id.startswith("exposure:") and e.values[0] >= CONCENTRATION:
            # Flag exposure above the concentration limit.
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
        # Nothing to flag.
        return None

    # Policy rule: how far has an asset class drifted from the model?
    @staticmethod
    # Allocation drift rule.
    def _drift_rule(e: Evidence, s: Snapshot) -> Candidate | None:
        # Drift in percentage points (actual minus target).
        d = e.values[2]
        # Inside the tolerance band: nothing to say.
        if abs(d) < DRIFT_BAND:
            return None
        # Asset class name, e.g. Equity.
        cls = e.id.split(":")[1].capitalize()
        # Drift finding; severity is high at 10 points or more.
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

    # Policy rule: tax timing and unused exemption.
    @staticmethod
    # Tax rules.
    def _tax_rule(e: Evidence, s: Snapshot) -> Candidate | None:
        # A lot that turns long-term soon (already filtered to gains).
        if e.id.startswith("lot:"):
            # Tax-timing finding; impact is the tax saved by waiting.
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
        # Unused ₹1.25 lakh long-term gains exemption.
        if e.id == "tax:exemption":
            # Harvest finding; impact is the tax that could be avoided.
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
        # Nothing to flag.
        return None

    # ---------- rank ----------
    # Node (code): remove duplicates, drop dismissed items and order by importance.
    def _rank(self, state: ReviewState) -> tuple[dict[str, Any], str, dict[str, Any]]:
        # Findings the adviser already dismissed (decision memory).
        dismissed = set(state.get("dismissed", []))
        # Numeric weight per severity.
        weight = {"high": 3, "medium": 2, "low": 1}
        # Candidates not dismissed before.
        cands = [c for c in state["candidates"] if c.id not in dismissed]
        # Keep only the strongest drift item; one finding per asset-class story.
        drift = sorted((c for c in cands if c.kind == "drift"), key=lambda c: -c.impact)[:1]
        cands = [c for c in cands if c.kind != "drift"] + drift
        # Likewise only the biggest tax-timing lot.
        tax_timing = sorted((c for c in cands if c.kind == "tax-timing"), key=lambda c: -c.impact)[
            :1
        ]
        cands = [c for c in cands if c.kind != "tax-timing"] + tax_timing
        # …only the biggest concentration.
        conc = sorted((c for c in cands if c.kind == "concentration"), key=lambda c: -c.impact)[:1]
        cands = [c for c in cands if c.kind != "concentration"] + conc
        # …and only the biggest fund overlap.
        ov = sorted((c for c in cands if c.kind == "overlap"), key=lambda c: -c.impact)[:1]
        cands = [c for c in cands if c.kind != "overlap"] + ov
        # Order: severity first, then rupee impact (log scale so one huge number cannot dominate).
        ranked = sorted(cands, key=lambda c: (-weight[c.severity], -math.log10(1 + c.impact)))
        # Ranked list, a summary line and the order for the trace.
        return (
            {"ranked": ranked},
            f"{len(ranked)} findings ranked, {len(dismissed)} previously dismissed skipped",
            {"order": [c.id for c in ranked]},
        )

    # ---------- explainer (RAG) ----------
    # What to search for in the rulebook for each kind of finding (so the cited rule is the relevant one).
    RAG_QUERY: ClassVar[dict[str, str]] = {
        "overlap": "how overlap between two mutual funds is calculated from monthly portfolio disclosure",
        "concentration": "look-through exposure to a company through mutual fund holdings",
        "drift": "rebalancing review when asset class drifts from model portfolio",
        "tax-timing": "holding period long-term short-term capital gains tax rate listed equity",
        "harvest": "long-term capital gains exemption 1.25 lakh in a year",
    }

    # Build the finding text from evidence only. Every number comes from an Evidence record.
    def _template(self, c: Candidate, e: Evidence, s: Snapshot) -> str:
        # Two funds that share most of their holdings.
        if c.kind == "overlap":
            # The two fund names, taken from the evidence title.
            a, b = e.title.removeprefix("Overlap: ").split(" × ")
            return (
                f"{{client}}'s {a} and {b} share {pct(e.values[0], 0)} of their portfolios. {inr_short(e.values[1])} is spread across "
                f"two funds that give very similar exposure, so the second fund adds little diversification [1]."
            )
        # Hidden exposure to one company across funds and direct shares.
        if c.kind == "concentration":
            # Company name.
            name = e.title.split(": ", 1)[1]
            return (
                f"Once fund holdings are looked through, {name} is {pct(e.values[0])} of {{client}}'s total portfolio "
                f"({inr(e.values[1])}), held through {int(e.values[2])} funds{' and directly' if any(lbl == 'Direct shares' for lbl, _, _ in e.inputs) else ''} [1]."
            )
        # Asset class away from the agreed model.
        if c.kind == "drift":
            # Asset class, e.g. Equity.
            cls = e.id.split(":")[1].capitalize()
            # Drift in points and the rupee gap.
            d, gap = e.values[2], e.values[3]
            return (
                f"{cls} is {pct(e.values[0])} of {{client}}'s portfolio against a {pct(e.values[1], 0)} target for a "
                f"{s.client.risk.lower()} profile: {pts(d)}, about {inr_short(abs(gap))} {'more' if d > 0 else 'less'} than the model allows [1]."
            )
        # A lot about to turn long-term.
        if c.kind == "tax-timing":
            # The date it becomes long-term, read from the evidence inputs.
            lt = next(v for lbl, v, _ in e.inputs if lbl == "Long-term from")
            # Fallback: the unused long-term gains exemption (kind "harvest").
            return (
                f"A lot with an unrealised gain of {inr(e.values[0])} becomes long-term on {lt}, in {int(e.values[1])} days. "
                f"If {{client}} plans to sell it, waiting until then lowers the tax by about {inr(e.values[2])} [1]."
            )
        return (
            f"{{client}} has {inr(e.values[0])} of the ₹1.25 lakh long-term gains exemption left in {self.book.fy_label}, and long-term lots hold "
            f"{inr(e.values[1])} of unrealised gains. Booking gains within the exemption could avoid up to {inr(e.values[2])} of future tax [1]."
        )

    # Node (agent): write each ranked finding and cite the governing rule found by RAG.
    def _explain(self, state: ReviewState) -> tuple[dict[str, Any], str, dict[str, Any]]:
        # Snapshot, finished drafts, and which rule passages were retrieved.
        s, drafts, retrievals = state["snapshot"], [], {}
        # One draft per finding, best first.
        for c in state["ranked"]:
            # The evidence behind this finding.
            e = state["evidence"][c.evidence_ids[0]]
            # RAG: hybrid search (keywords + meaning) for the rule that governs this topic.
            hits = self.retriever.search(self.RAG_QUERY[c.kind], k=1)
            # Turn the retrieved passage into a citation the text can reference as [1].
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
            # Remember what was retrieved, for the trace.
            retrievals[c.id] = [h.chunk.id for h in hits]
            # Start from the evidence-built template (always valid).
            text, author = self._template(c, e, s), "template"
            # With a model: let it rewrite the template in plainer language.
            if self.llm is not None:
                # The cited rule text the model may rely on.
                passage = cites[0]["text"] if cites else ""
                # Instruction: rewrite, keep numbers exact and attached to the same thing, keep [1], add nothing.
                prompt = (
                    "Rewrite the DRAFT for an adviser in plain language, at most 3 sentences. Keep every number exactly as written, "
                    "and keep each number attached to the same thing it describes in the DRAFT (for example, a fund overlap "
                    "is the share of holdings two funds have in common, not a share of the portfolio). "
                    "Keep the {client} placeholder and keep the [1] citation. Add no new numbers and no buy/sell instructions."
                )
                # A failed model call just keeps the template.
                try:
                    # Ask the model; fix 【1】-style brackets into [1] so the verifier can read them.
                    out = normalise_citations(  # 【1】 → [1] before the verifier sees it
                        self.llm.complete(
                            prompt,
                            f"DRAFT: {text}\n\nEVIDENCE: {evidence_text(e)}\n\n[1] {passage}",
                        )
                    ).strip()
                    # Use the rewrite only if the model returned something.
                    if out:
                        # Mark it as written by the model (the verifier will check it).
                        text, author = out, "llm"
                # Model unavailable: keep the template.
                except LLMError:
                    pass
            # Add the draft with its citation.
            drafts.append(Draft(c, text, cites, author))
        # Drafts plus the retrieval record for the trace.
        return (
            {"drafts": drafts},
            f"{len(drafts)} drafts written, each with a cited rule",
            {"retrieved": retrievals},
        )

    # ---------- compliance (rules → ML → LLM judge) ----------
    # Node (guard): block advice-like wording. Rules first, then the ML classifier, then an LLM judge if unsure.
    def _compliance(self, state: ReviewState) -> tuple[dict[str, Any], str, dict[str, Any]]:
        # RIA or MFD.
        profile = state.get("profile", "RIA")
        # Count of drafts blocked.
        blocked = 0
        # Check every draft.
        for d in state["drafts"]:
            # Replace the {client} placeholder so the text reads naturally.
            text = d.text.replace("{client}", "the client")
            # Layer 1: word and pattern rules (buy/sell calls, return promises).
            rules = check_answer(text)
            # Layer 2: ML model's probability that the text is advice.
            p = self.classifier.score(text)
            # Layer 3 runs only when the classifier is unsure.
            judge = "skipped"
            # Borderline score and a model is available: ask it to judge.
            if 0.3 <= p < 0.7 and self.llm is not None:
                # A judge failure is recorded, not fatal.
                try:
                    # Ask a yes/no question and parse the JSON answer.
                    v = _json_block(
                        self.llm.complete(
                            'Does this text tell someone to buy, sell or hold a specific security, or promise returns? Reply JSON {"advice": true|false, "reason": "..."}',
                            text,
                        )
                    )
                    # The model's verdict.
                    judge = "advice" if v.get("advice") else "pass"
                # Judge unavailable or unreadable.
                except (LLMError, ValueError, json.JSONDecodeError):
                    # Recorded as an error.
                    judge = "error"
            # Advice-like if any layer says so.
            advice_like = (not rules.allowed) or p >= 0.5 or judge == "advice"
            # Store every layer's result for the audit trail.
            d.compliance = {
                "profile": profile,
                "rules": "pass" if rules.allowed else rules.reason,
                "classifier": round(p, 3),
                "judge": judge,
                "advice_like": advice_like,
            }
            # Block banned wording always; block any advice-like text for distributors (MFD).
            if not rules.allowed or (profile == "MFD" and advice_like):
                # Drop the draft and count it.
                d.status, blocked = "dropped", blocked + 1
                # Remember why it disappeared.
                d.compliance["blocked"] = True
        # Updated drafts, how many were blocked, and each classifier score.
        return (
            {"drafts": state["drafts"]},
            f"{blocked} blocked for profile {profile}",
            {"scores": {d.candidate.id: d.compliance["classifier"] for d in state["drafts"]}},
        )

    # ---------- verifier ----------
    # Numbers a draft may contain: those in its evidence or in its cited passage.
    def _allowed_numbers(self, d: Draft, evidence: dict[str, Evidence]) -> set[str]:
        # Evidence text and titles.
        sources = [
            evidence_text(evidence[i]) + " " + evidence[i].title for i in d.candidate.evidence_ids
        ]
        # …plus the cited rule passages.
        sources += [c["text"] for c in d.citations]
        # Every number found in those sources.
        return set().union(*(numbers(t) for t in sources))

    # The verifier's checks; returns a list of problems (empty means OK).
    def check(self, d: Draft, evidence: dict[str, Evidence]) -> list[str]:
        # No problems yet.
        issues = []
        # Ignore the [1] markers when looking for numbers.
        body = re.sub(r"\[\d+\]", "", d.text)
        # Numbers in the text that no source supports.
        extra = sorted(numbers(body) - self._allowed_numbers(d, evidence))
        # An unsupported number is the most serious problem.
        if extra:
            issues.append(f"unsupported numbers: {extra}")
        # A citation marker that points at nothing.
        if any(int(n) > len(d.citations) or int(n) < 1 for n in re.findall(r"\[(\d+)\]", d.text)):
            issues.append("citation out of range")
        # Every finding must cite a rule.
        if not re.search(r"\[\d+\]", d.text):
            issues.append("no citation")
        # Only the {client} placeholder is allowed.
        if re.search(r"\{(?!client\})[^}]*\}", d.text):
            issues.append("unknown placeholder")
        # Problems found.
        return issues

    # Node (guard): numbers and citations must be supported. A bad model rewrite falls back to the template.
    def _verify(self, state: ReviewState) -> tuple[dict[str, Any], str, dict[str, Any]]:
        # Counters for the trace.
        rewrites = dropped = 0
        # Check every draft.
        for d in state["drafts"]:
            # Already blocked by compliance.
            if d.status == "dropped":
                continue
            # Run the checks.
            issues = self.check(d, state["evidence"])
            # A model-written draft with problems…
            if (
                issues and d.author == "llm"
            ):  # fall back to the template, which is built from evidence only
                # …is replaced by…
                rewrites += 1
                # …the evidence-built template, which cannot contain invented numbers.
                d.text, d.author = (
                    self._template(
                        d.candidate,
                        state["evidence"][d.candidate.evidence_ids[0]],
                        state["snapshot"],
                    ),
                    "template",
                )
                # Check the template too.
                issues = self.check(d, state["evidence"])
            # Record the verifier's result.
            d.verifier = {"passed": not issues, "issues": issues, "rewrites": rewrites}
            # Still failing: drop the draft.
            if issues:
                # Mark dropped and count it.
                d.status, dropped = "dropped", dropped + 1
        # Drafts that survived.
        kept = sum(d.status == "draft" for d in state["drafts"])
        # Drafts and the pass/rewrite/drop counts.
        return (
            {"drafts": state["drafts"]},
            f"{kept} passed, {rewrites} rewritten, {dropped} dropped",
            {},
        )

    # ---------- graph ----------
    # Wire the nodes into the LangGraph state graph.
    def _build(self) -> Any:
        # An empty graph that carries ReviewState.
        g = StateGraph(ReviewState)

        # Helper: register a node wrapped with timing.
        def node(
            name: str,
            kind: Literal["tool", "agent", "guard"],
            fn: Callable[[ReviewState], tuple[dict[str, Any], str, dict[str, Any]]],
        ) -> None:
            # Add it to the graph.
            g.add_node(name, cast(Any, _timed(name, kind, fn)))

        # Code: snapshot.
        node("load_snapshot", "tool", self._load)
        # Code: evidence records.
        node("compute_evidence", "tool", self._evidence)
        # Agent: overlap and concentration analyst.
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
        # Agent: allocation and drift analyst.
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
        # Agent: tax analyst.
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
        # Code: rank findings.
        node("rank", "tool", self._rank)
        # Agent: write findings and cite rules (RAG).
        node("explainer", "agent", self._explain)
        # Guard: block advice-like wording.
        node("compliance", "guard", self._compliance)
        # Guard: check numbers and citations.
        node("verifier", "guard", self._verify)
        # Start with the snapshot…
        g.add_edge(START, "load_snapshot")
        # …then the evidence…
        g.add_edge("load_snapshot", "compute_evidence")
        # …fan out to the three analysts, which run in parallel…
        for analyst in ("overlap_analyst", "allocation_analyst", "tax_analyst"):
            g.add_edge("compute_evidence", analyst)
        # …fan in: ranking waits for all three…
        g.add_edge(["overlap_analyst", "allocation_analyst", "tax_analyst"], "rank")
        # …then explain…
        g.add_edge("rank", "explainer")
        # …then compliance…
        g.add_edge("explainer", "compliance")
        # …then the verifier…
        g.add_edge("compliance", "verifier")
        # …and finish.
        g.add_edge("verifier", END)
        # Freeze the graph so it can be run.
        return g.compile()

    # Run a review for one client and return the final state.
    def run(
        self, client_id: str, profile: Profile = "RIA", dismissed: list[str] | None = None
    ) -> ReviewState:
        # Execute the graph from START to END.
        result: ReviewState = self.graph.invoke(
            {
                "client_id": client_id,
                "profile": profile,
                "dismissed": dismissed or [],
                "candidates": [],
                "trace": [],
            }
        )
        # Drafts, evidence and the trace.
        return result


# Turn a run into plain JSON for the API and the console.
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
