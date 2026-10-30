"""CLI: `uv run python -m aicfo.llm {status|bench}`.

`bench` calls the real Groq and Gemini APIs with synthetic data. Never run it in CI.
"""

from __future__ import annotations

import argparse
import json

from aicfo.config import get_settings
from aicfo.llm import LLMError
from aicfo.llm.bench import run, table
from aicfo.llm.providers import build_llm, configured_vendors, single
from aicfo.rag.service import get_rag


# Command-line entry: `status` checks keys, `bench` compares providers.
def main() -> None:
    # Argument parser.
    ap = argparse.ArgumentParser(prog="python -m aicfo.llm")
    # Sub-commands.
    sub = ap.add_subparsers(dest="cmd", required=True)
    # status: show which provider the agents will use and ping it.
    sub.add_parser("status")
    # bench: compare providers on this app's tasks.
    b = sub.add_parser("bench")
    # Limit to some providers.
    b.add_argument("--providers", nargs="+", choices=["groq", "gemini"])
    # How many clients to review.
    b.add_argument("--clients", type=int, default=4)
    # How many RAG questions to ask.
    b.add_argument("--questions", type=int, default=10)
    # Seconds between calls (free tiers have rate limits).
    b.add_argument("--pause", type=float, default=2.0, help="seconds between calls (free tiers)")
    # Also save the results as JSON.
    b.add_argument("--json", dest="out", help="also write the reports to this file")
    # Read the command line.
    args = ap.parse_args()
    # Keys and models from backend/.env.
    settings = get_settings()

    # Status command.
    if args.cmd == "status":
        # The provider the app would use now.
        llm = build_llm(settings)
        # Show the setting…
        print(f"provider setting: {settings.llm_provider}")
        # …which keys exist (names only, never values)…
        print(f"keys found for:   {', '.join(configured_vendors(settings)) or 'none'}")
        # …and what will actually be used.
        print(f"agents will use:  {llm.name if llm else 'deterministic firm policy (no LLM)'}")
        # Try one tiny call.
        if llm:
            # A failure is information, not a crash.
            try:
                # A reply means the key and model work.
                print(f"ping:             {llm.complete('Reply with the word OK.', 'ping')!r}")
            # Report the failure.
            except LLMError as exc:
                # Why it failed.
                print(f"ping failed:      {exc}")
        # Done.
        return

    # Vendors to benchmark: the ones asked for, or all with keys.
    vendors = args.providers or configured_vendors(settings)
    # Nothing to test.
    if not vendors:
        # Say which keys to set.
        raise SystemExit("No API keys found. Set AICFO_GROQ_API_KEY and/or AICFO_GEMINI_API_KEY.")
    # Shared RAG index.
    retriever = get_rag().retriever
    # Results per provider.
    reports = []
    # Each provider on its own, with no fallback.
    for v in vendors:
        # Progress.
        print(f"benchmarking {v} …", flush=True)
        # Run and store the report.
        reports.append(
            run(single(v, settings), retriever, args.clients, args.questions, args.pause)
        )
    # Show the comparison.
    print(table(reports))
    # Save as JSON if asked.
    if args.out:
        # Write the file.
        with open(args.out, "w", encoding="utf-8") as f:
            # Plain JSON.
            json.dump([r.__dict__ for r in reports], f, indent=1)


# Run when executed as a program.
if __name__ == "__main__":
    # Go.
    main()
