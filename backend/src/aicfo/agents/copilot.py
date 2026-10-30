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
from aicfo.rag.text import normalise_citations, numbers
from aicfo.security.redaction import redact

# The instruction the model sees: which tools exist and the exact JSON format to reply in.
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
# What the Copilot returns to the console.
class CopilotAnswer:
    # The (identifier-redacted) question.
    question: str
    # The reply.
    answer: str
    # tools, rules, llm, refused or not_found: how the answer was produced.
    mode: str
    # Every tool the agent called, with its result (shown in the UI).
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    # Rule passages cited.
    citations: list[dict[str, str]] = field(default_factory=list)
    # Problems the safety checks found.
    issues: list[str] = field(default_factory=list)


# A tool-using agent: answers questions about one client from tool results and the rulebook.
class Copilot:
    # Wire the Copilot: RAG for rules, an optional model, the synthetic book.
    def __init__(
        self, rag: Answerer, llm: LLMProvider | None = None, book: Book | None = None
    ) -> None:
        # Rulebook search with citations.
        self.rag = rag
        # Groq/Gemini, or None to use the keyword router.
        self.llm = llm
        # The synthetic client book.
        self.book = book or load_book()

    # Build this client's tools. Each returns text made only from computed Evidence.
    def _tools(self, client_id: str) -> dict[str, Any]:
        # Compute the client's numbers once.
        s = snapshot(client_id, self.book)
        # All Evidence records for the client.
        ev = all_evidence(s, self.book)

        # Tool: portfolio value and allocation against the model.
        def summary(**_: Any) -> str:
            # e.g. "Equity 84.2% (model 70%), Debt …".
            alloc = ", ".join(
                f"{c} {pct(s.allocation_pct[c])} (model {pct(s.target[c], 0)})"
                for c in ASSET_CLASSES
            )
            # One sentence with the totals.
            return (
                f"Portfolio {inr(s.total)} ({inr_short(s.total)}), {s.client.risk} model. {alloc}."
            )

        # Tool: drift per asset class.
        def drift(**_: Any) -> str:
            # Each class's drift, written from its Evidence.
            return " ".join(evidence_text(ev[f"drift:{c.lower()}"]) for c in ASSET_CLASSES)

        # Tool: overlap between equity funds.
        def overlap(**_: Any) -> str:
            # The overlap Evidence records.
            items = [e for k, e in ev.items() if k.startswith("overlap:")]
            # Their results, or a note when there are fewer than two equity funds.
            return (
                " ".join(f"{e.title}: {e.result}." for e in items) or "Fewer than two equity funds."
            )

        # Tool: LTCG exemption left and lots turning long-term.
        def tax(**_: Any) -> str:
            # Start with the exemption and unrealised long-term gains.
            parts = [
                f"LTCG exemption left in {self.book.fy_label}: {inr(s.exemption_left)} of {inr(self.book.ltcg_exemption)};"
                f" unrealised long-term gains {inr(s.lt_gain_unrealised)}."
            ]
            # Add each upcoming lot, soonest first.
            for u in sorted(s.upcoming_lots, key=lambda u: u.lot.days_to_long):
                # Lot, date it turns long-term, days left and gain.
                parts.append(
                    f"{u.position.short_name} lot turns long-term on {day(u.lot.long_term_on)} ({u.lot.days_to_long} days), gain {inr(u.lot.gain)}."
                )
            # Join into one answer.
            return " ".join(parts)

        # Tool: largest look-through company exposures.
        def exposures(**_: Any) -> str:
            # Top five companies with % of portfolio and rupees.
            return " ".join(
                f"{e.name} {pct(e.pct_of_total)} ({inr_short(e.value)})." for e in s.exposures[:5]
            )

        # Tool name → function. The model may call only these.
        return {
            "get_summary": summary,
            "get_drift": drift,
            "get_overlap": overlap,
            "get_tax_position": tax,
            "get_exposures": exposures,
        }

    # Without a model: pick a tool from keywords in the question.
    def _route(self, q: str) -> str | None:
        # Case-insensitive matching.
        ql = q.lower()
        # Each tool with the words that suggest it.
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
            # First tool whose keyword appears.
            if any(w in ql for w in words):
                # Chosen tool.
                return tool
        # No keyword matched.
        return None

    # Answer a question about a client.
    def ask(self, client_id: str, question: str) -> CopilotAnswer:
        # Mask PAN, phone, email, tokens before anything else sees the question.
        q = redact(question.strip())
        # Refuse requests for buy/sell calls.
        guard = check_question(q)
        # Return a polite refusal and record why.
        if not guard.allowed:
            return CopilotAnswer(
                q,
                "I can't recommend buying or selling a specific security. I can show the client's exposure, drift or tax position to support your decision.",
                "refused",
                [{"tool": "compliance.rules", "result": f"blocked: {guard.reason}"}],
            )
        # Prepare this client's tools.
        tools = self._tools(client_id)
        # Model available: let it choose tools in a loop.
        if self.llm is not None:
            # Run the tool-calling loop.
            return self._loop(client_id, q, tools)
        # No model: choose a tool by keywords.
        tool = self._route(q)
        # Questions about rules (or with no matching tool) go to the rulebook.
        if (
            tool is None
            or "rule" in q.lower()
            or "sebi" in q.lower()
            or q.lower().startswith(("what is", "how is", "how are", "can ", "does ", "is the"))
        ):
            # RAG: retrieve passages and build a cited answer.
            a = self.rag.ask(q)
            # Got an answer from the rulebook.
            if a.mode in ("extractive", "llm"):
                # Answer with its citations.
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
            # Nothing in the data or the rulebook matches.
            if tool is None:
                # Say so honestly.
                return CopilotAnswer(
                    q, "I couldn't find that in this client's data or the rulebook.", "not_found"
                )
        # Run the chosen tool.
        result = tools[tool]()
        # Answer straight from the tool.
        return CopilotAnswer(q, result, "tools", [{"tool": tool, "args": {}, "result": result}])

    # With a model: up to four steps of "call a tool, read the result, decide".
    def _loop(self, client_id: str, q: str, tools: dict[str, Any]) -> CopilotAnswer:
        # Tool calls so far.
        calls: list[dict[str, Any]] = []
        # Rule citations collected.
        citations: list[dict[str, str]] = []
        # Running conversation shown to the model.
        transcript = f"Client: {client_id}\nQuestion: {q}"
        # At most four steps, so a confused model cannot loop forever.
        for _ in range(4):
            # Ask the model for its next step.
            try:
                # The model replies with JSON: a tool call or a final answer.
                reply = self.llm.complete(TOOLS_SPEC, transcript)  # type: ignore[union-attr]
                # Parse the JSON block in the reply.
                msg = json.loads(re.search(r"\{.*\}", reply, re.S).group(0))  # type: ignore[union-attr]
            # Model failed or replied with junk: stop and use the tool results so far.
            except (LLMError, AttributeError, json.JSONDecodeError):
                # Leave the loop.
                break
            # The model says it is done.
            if "answer" in msg:
                # Fix 【1】-style citation brackets into [1].
                answer = normalise_citations(str(msg["answer"]))
                # Everything the answer may quote: tool results and the question.
                observed = " ".join(str(c.get("result", "")) for c in calls) + " " + q
                # Numbers in the answer that no tool returned.
                extra = sorted(numbers(re.sub(r"\[\d+\]", "", answer)) - numbers(observed))
                # An unsupported number is a problem…
                issues = [f"unsupported numbers: {extra}"] if extra else []
                # …and so is advice-like wording.
                if not check_answer(answer).allowed:
                    # Record it.
                    issues.append("compliance")
                # Clean answer: return it.
                if not issues:
                    # Model answer, verified.
                    return CopilotAnswer(q, answer, "llm", calls, citations)
                # Otherwise show the last tool result instead of unverified text.
                fallback = calls[-1]["result"] if calls else "I couldn't produce a verified answer."
                # Verified fallback with the issues listed.
                return CopilotAnswer(q, str(fallback), "tools", calls, citations, issues)
            # The tool the model wants to call, and its arguments.
            name, args = msg.get("tool"), msg.get("args") or {}
            # Rulebook search via RAG.
            if name == "search_rules":
                # Search with the model's query.
                a = self.rag.ask(str(args.get("query", q)))
                # The cited passage text.
                result = a.text
                # Remember the citations.
                citations = [
                    {"n": str(c.n), "doc_id": c.doc_id, "section": c.section, "issuer": c.issuer}
                    for c in a.citations
                ]
            # One of the client tools.
            elif name in tools:
                # Run it.
                result = tools[name]()
            # The model asked for a tool that does not exist.
            else:
                # Tell it so; it can try again.
                result = f"unknown tool {name}"
            # Record the call and its result.
            calls.append({"tool": name, "args": args, "result": result})
            # Show the result to the model on the next step.
            transcript += f"\nTool {name} → {result}"
        # Out of steps: return the last tool result.
        return CopilotAnswer(
            q,
            calls[-1]["result"] if calls else "No answer.",
            "tools",
            calls,
            citations,
            ["loop ended without an answer"],
        )
