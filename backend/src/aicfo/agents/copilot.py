"""Adviser Copilot: a tool-using agent over one client's snapshot and the rulebook.

With a model: a JSON tool-calling loop (at most 4 steps). Without a model: an
intent router calls the same tools. Either way the answer is guarded, and any
number must come from a tool result.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from aicfo.agents.tools import all_evidence, evidence_text
from aicfo.core.analytics import snapshot
from aicfo.core.book import ASSET_CLASSES, Book, load_book
from aicfo.core.format import day, inr, inr_short, pct
from aicfo.llm import LLMError, LLMProvider
from aicfo.rag.answer import Answerer
from aicfo.rag.guard import check_answer, check_question
from aicfo.rag.text import numbers
from aicfo.security.redaction import redact

TOOLS_SPEC = """Tools (call one at a time):
- get_summary(): portfolio value and allocation vs model
- get_drift(): drift per asset class
- get_overlap(): pairwise overlap of equity funds
- get_tax_position(): LTCG exemption headroom and lots turning long-term
- get_exposures(): largest look-through company exposures
- search_rules(query): cited passages from SEBI, Income-tax, DPDP and firm policy
Reply with JSON only: {"tool": "<name>", "args": {...}} to call a tool, or {"answer": "<text with [n] citations when rules are used>"} when done.
Use only numbers that appear in tool results. Never recommend buying or selling a specific security."""


@dataclass
class CopilotAnswer:
    question: str
    answer: str
    mode: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    citations: list[dict[str, str]] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


class Copilot:
    def __init__(
        self, rag: Answerer, llm: LLMProvider | None = None, book: Book | None = None
    ) -> None:
        self.rag = rag
        self.llm = llm
        self.book = book or load_book()

    def _tools(self, client_id: str) -> dict[str, Any]:
        s = snapshot(client_id, self.book)
        ev = all_evidence(s, self.book)

        def summary(**_: Any) -> str:
            alloc = ", ".join(
                f"{c} {pct(s.allocation_pct[c])} (model {pct(s.target[c], 0)})"
                for c in ASSET_CLASSES
            )
            return (
                f"Portfolio {inr(s.total)} ({inr_short(s.total)}), {s.client.risk} model. {alloc}."
            )

        def drift(**_: Any) -> str:
            return " ".join(evidence_text(ev[f"drift:{c.lower()}"]) for c in ASSET_CLASSES)

        def overlap(**_: Any) -> str:
            items = [e for k, e in ev.items() if k.startswith("overlap:")]
            return (
                " ".join(f"{e.title}: {e.result}." for e in items) or "Fewer than two equity funds."
            )

        def tax(**_: Any) -> str:
            parts = [
                f"LTCG exemption left in {self.book.fy_label}: {inr(s.exemption_left)} of {inr(self.book.ltcg_exemption)};"
                f" unrealised long-term gains {inr(s.lt_gain_unrealised)}."
            ]
            for u in sorted(s.upcoming_lots, key=lambda u: u.lot.days_to_long):
                parts.append(
                    f"{u.position.short_name} lot turns long-term on {day(u.lot.long_term_on)} ({u.lot.days_to_long} days), gain {inr(u.lot.gain)}."
                )
            return " ".join(parts)

        def exposures(**_: Any) -> str:
            return " ".join(
                f"{e.name} {pct(e.pct_of_total)} ({inr_short(e.value)})." for e in s.exposures[:5]
            )

        return {
            "get_summary": summary,
            "get_drift": drift,
            "get_overlap": overlap,
            "get_tax_position": tax,
            "get_exposures": exposures,
        }

    def _route(self, q: str) -> str | None:
        ql = q.lower()
        for tool, words in (
            ("get_overlap", ("overlap", "similar", "same companies", "duplicate")),
            ("get_drift", ("drift", "equity", "allocation", "target", "model", "rebalanc")),
            (
                "get_tax_position",
                ("ltcg", "stcg", "exemption", "lot", "harvest", "long-term", "tax position"),
            ),
            ("get_exposures", ("exposure", "concentrat", "bank", "company", "stock")),
            ("get_summary", ("worth", "value", "summary", "portfolio")),
        ):
            if any(w in ql for w in words):
                return tool
        return None

    def ask(self, client_id: str, question: str) -> CopilotAnswer:
        q = redact(question.strip())
        guard = check_question(q)
        if not guard.allowed:
            return CopilotAnswer(
                q,
                "I can't recommend buying or selling a specific security. I can show the client's exposure, drift or tax position to support your decision.",
                "refused",
                [{"tool": "compliance.rules", "result": f"blocked: {guard.reason}"}],
            )
        tools = self._tools(client_id)
        if self.llm is not None:
            return self._loop(client_id, q, tools)
        tool = self._route(q)
        if (
            tool is None
            or "rule" in q.lower()
            or "sebi" in q.lower()
            or q.lower().startswith(("what is", "how is", "how are", "can ", "does ", "is the"))
        ):
            a = self.rag.ask(q)
            if a.mode in ("extractive", "llm"):
                return CopilotAnswer(
                    q,
                    a.text,
                    "rules",
                    [{"tool": "search_rules", "args": {"query": q}}],
                    [
                        {
                            "n": str(c.n),
                            "doc_id": c.doc_id,
                            "section": c.section,
                            "issuer": c.issuer,
                        }
                        for c in a.citations
                    ],
                )
            if tool is None:
                return CopilotAnswer(
                    q, "I couldn't find that in this client's data or the rulebook.", "not_found"
                )
        result = tools[tool]()
        return CopilotAnswer(q, result, "tools", [{"tool": tool, "args": {}, "result": result}])

    def _loop(self, client_id: str, q: str, tools: dict[str, Any]) -> CopilotAnswer:
        calls: list[dict[str, Any]] = []
        citations: list[dict[str, str]] = []
        transcript = f"Client: {client_id}\nQuestion: {q}"
        for _ in range(4):
            try:
                reply = self.llm.complete(TOOLS_SPEC, transcript)  # type: ignore[union-attr]
                msg = json.loads(re.search(r"\{.*\}", reply, re.S).group(0))  # type: ignore[union-attr]
            except (LLMError, AttributeError, json.JSONDecodeError):
                break
            if "answer" in msg:
                answer = str(msg["answer"])
                observed = " ".join(str(c.get("result", "")) for c in calls) + " " + q
                extra = sorted(numbers(re.sub(r"\[\d+\]", "", answer)) - numbers(observed))
                issues = [f"unsupported numbers: {extra}"] if extra else []
                if not check_answer(answer).allowed:
                    issues.append("compliance")
                if not issues:
                    return CopilotAnswer(q, answer, "llm", calls, citations)
                fallback = calls[-1]["result"] if calls else "I couldn't produce a verified answer."
                return CopilotAnswer(q, str(fallback), "tools", calls, citations, issues)
            name, args = msg.get("tool"), msg.get("args") or {}
            if name == "search_rules":
                a = self.rag.ask(str(args.get("query", q)))
                result = a.text
                citations = [
                    {"n": str(c.n), "doc_id": c.doc_id, "section": c.section, "issuer": c.issuer}
                    for c in a.citations
                ]
            elif name in tools:
                result = tools[name]()
            else:
                result = f"unknown tool {name}"
            calls.append({"tool": name, "args": args, "result": result})
            transcript += f"\nTool {name} → {result}"
        return CopilotAnswer(
            q,
            calls[-1]["result"] if calls else "No answer.",
            "tools",
            calls,
            citations,
            ["loop ended without an answer"],
        )
