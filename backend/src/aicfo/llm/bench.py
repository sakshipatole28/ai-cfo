"""Compare LLM providers on the tasks this product actually gives them (synthetic data only).

A provider is better here when more of its output survives the guards, not when it writes
more. For each provider we run:

* review runs: analyst JSON accepted (valid ids and severities), explainer rewrites that
  pass the number/citation verifier;
* RAG answers on the golden questions: answers that pass the citation verifier (mode "llm")
  instead of falling back to extractive;
* reliability and speed: failed calls, p50/p95 latency.
"""

from __future__ import annotations

import statistics
import time
from dataclasses import asdict, dataclass, field

from aicfo.agents.review import ReviewPipeline
from aicfo.core.book import load_book
from aicfo.evals.rag_eval import load_golden
from aicfo.llm import LLMError, LLMProvider
from aicfo.rag.answer import Answerer
from aicfo.rag.retriever import HybridRetriever


@dataclass
# Wraps a provider to time every call and count failures; can pause between calls for free-tier limits.
class Recorder:
    """Wraps a provider to time every call and count failures; pauses to respect rate limits."""

    # The real provider being measured.
    inner: LLMProvider
    # Seconds to wait before each call.
    pause: float = 0.0
    # Milliseconds per call.
    latencies: list[float] = field(default_factory=list)
    # Calls that raised LLMError.
    errors: int = 0
    # Copied from the provider.
    name: str = field(init=False)

    # Runs after the fields are set.
    def __post_init__(self) -> None:
        # Report under the provider's name.
        self.name = self.inner.name

    # Forward the call, measuring it.
    def complete(self, system: str, user: str) -> str:
        # Space calls out to stay within rate limits.
        if self.pause:
            # Wait.
            time.sleep(self.pause)
        # Start the clock.
        t0 = time.perf_counter()
        # Run the real call.
        try:
            # Pass the reply through unchanged.
            return self.inner.complete(system, user)
        # A failed call…
        except LLMError:
            # …is counted…
            self.errors += 1
            # …and re-raised so the agents behave exactly as in production.
            raise
        # Always record the time.
        finally:
            # Milliseconds taken.
            self.latencies.append((time.perf_counter() - t0) * 1000)


@dataclass(frozen=True)
# One provider's results.
class BenchReport:
    # Which provider.
    provider: str
    # Number of model calls made.
    calls: int
    # How many failed.
    errors: int
    # Median latency.
    p50_ms: float
    # Slow-case latency (95th percentile).
    p95_ms: float
    # Share of analyst answers that were valid JSON with known evidence ids.
    analyst_json_ok: float
    # Share of model-written findings that passed the number/citation verifier.
    rewrites_verified: float
    # Share of RAG answers that passed the citation verifier (instead of falling back).
    rag_verified: float
    # Weighted summary: quality first, reliability second.
    score: float


# A ratio rounded to 3 places, safe when the denominator is zero.
def _share(ok: int, total: int) -> float:
    # ok ÷ total, or 0.
    return round(ok / total, 3) if total else 0.0


# Benchmark one provider on this app's real tasks (synthetic data only).
def run(
    provider: LLMProvider,
    retriever: HybridRetriever,
    clients: int = 4,
    questions: int = 10,
    pause: float = 0.0,
) -> BenchReport:
    # Wrap the provider to measure it.
    rec = Recorder(provider, pause)
    # The real LangGraph review pipeline, using the measured provider.
    pipeline = ReviewPipeline(retriever, rec)
    # Counters for analyst answers and rewrites.
    analysts = analysts_ok = drafts = drafts_ok = 0
    # The first few clients of the synthetic book.
    for cid in list(load_book().clients)[:clients]:
        # A full review: analysts, explainer, compliance, verifier.
        state = pipeline.run(cid)
        # Look at each step.
        for t in state["trace"]:
            # Analyst steps only.
            if t.node.endswith("_analyst"):
                # Count it.
                analysts += 1
                # Did the model's JSON get accepted (mode "llm") rather than falling back to policy?
                analysts_ok += t.detail.get("mode") == "llm"
        # Each finding.
        for d in state["drafts"]:
            # Count it.
            drafts += 1
            # Written by the model AND kept after the verifier?
            drafts_ok += d.author == "llm" and d.status == "draft"

    # The real RAG answerer, using the measured provider.
    answerer = Answerer(retriever, rec)
    # Counters for RAG answers.
    asked = verified = 0
    # Questions from the golden set.
    for row in load_golden()[:questions]:
        # Ask and let the verifier judge.
        a = answerer.ask(str(row["q"]))
        # Count only answerable questions.
        if a.mode in ("llm", "extractive"):  # answerable questions only
            # Count it.
            asked += 1
            # "llm" means the model's answer passed verification.
            verified += a.mode == "llm"

    # Latencies sorted for percentiles.
    lat = sorted(rec.latencies) or [0.0]
    # The three quality ratios.
    analyst, rewrites, rag = (
        _share(analysts_ok, analysts),
        _share(drafts_ok, drafts),
        _share(verified, asked),
    )
    # 1 minus the share of failed calls.
    reliability = 1 - _share(rec.errors, len(rec.latencies))
    # Assemble the report.
    return BenchReport(
        provider=provider.name,
        calls=len(rec.latencies),
        errors=rec.errors,
        p50_ms=round(statistics.median(lat)),
        p95_ms=round(lat[min(len(lat) - 1, int(0.95 * len(lat)))]),
        analyst_json_ok=analyst,
        rewrites_verified=rewrites,
        rag_verified=rag,
        # Quality first; speed only breaks ties.
        score=round(0.3 * analyst + 0.3 * rewrites + 0.3 * rag + 0.1 * reliability, 3),
    )


# Render reports as a Markdown table, best first.
def table(reports: list[BenchReport]) -> str:
    # Column names.
    cols = list(asdict(reports[0])) if reports else []
    # Header and separator rows.
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    # Best score first; faster wins ties.
    for r in sorted(reports, key=lambda r: (-r.score, r.p50_ms)):
        # One row per provider.
        lines.append("| " + " | ".join(str(v) for v in asdict(r).values()) + " |")
    # The finished table.
    return "\n".join(lines)
