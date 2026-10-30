"""CLI: `uv run python -m aicfo.agents {review <client>|copilot <client> <question>|export|eval}`."""

from __future__ import annotations

import argparse
import json
from datetime import datetime

from aicfo.agents.review import serialise
from aicfo.agents.service import get_copilot, get_pipeline
from aicfo.config import REPO_ROOT
from aicfo.core.book import load_book
from aicfo.ml.compliance_classifier import cross_validate

# Where the console's pre-computed agent runs are saved.
EXPORT = REPO_ROOT / "data" / "synthetic" / "agent_runs.json"


# Command-line entry: review, copilot, export or eval.
def main() -> None:
    # Argument parser.
    ap = argparse.ArgumentParser(prog="python -m aicfo.agents")
    # Sub-commands.
    sub = ap.add_subparsers(dest="cmd", required=True)
    # review <client>: run the multi-agent review and print its trace.
    r = sub.add_parser("review")
    # Which client.
    r.add_argument("client")
    # RIA or MFD wording rules.
    r.add_argument("--profile", choices=["RIA", "MFD"], default="RIA")
    # copilot <client> <question>: ask the tool-using Copilot.
    c = sub.add_parser("copilot")
    # Which client.
    c.add_argument("client")
    # The question.
    c.add_argument("question")
    # export: save every client's run for the console.
    sub.add_parser("export")
    # eval: cross-validate the advice classifier.
    sub.add_parser("eval")
    # Read the command line.
    args = ap.parse_args()

    # Run a review.
    if args.cmd == "review":
        # Run the LangGraph agents.
        st = get_pipeline().run(args.client, args.profile)
        # Print each step: node, type, time and what it decided.
        for t in st["trace"]:
            print(f"{t.node:<20} {t.kind:<6} {t.ms:>8.2f} ms  {t.summary}")
        # Blank line.
        print()
        # Print each finding with its status.
        for d in st["drafts"]:
            print(f"[{d.status}] {d.candidate.severity:<6} {d.candidate.kind:<13} {d.text}")
    # Ask the Copilot.
    elif args.cmd == "copilot":
        # Run it.
        a = get_copilot().ask(args.client, args.question)
        # Answer and how it was produced.
        print(f"[{a.mode}] {a.answer}")
        # Which tools it used.
        for call in a.tool_calls:
            print("  tool:", call["tool"])
    # Save runs for the console.
    elif args.cmd == "export":
        # Every client's run as plain JSON.
        runs = {cid: serialise(get_pipeline().run(cid)) for cid in load_book().clients}
        # Write the file.
        EXPORT.write_text(
            json.dumps(
                {"generated": datetime.now().isoformat(timespec="seconds"), "runs": runs},
                ensure_ascii=False,
                indent=1,
            )
            + "\n"
        )
        # Confirm.
        print(f"wrote {EXPORT} ({len(runs)} runs)")
    # Measure the classifier.
    elif args.cmd == "eval":
        # 5-fold cross-validation.
        m = cross_validate()
        print(
            f"compliance classifier 5-fold CV: accuracy {m.accuracy:.2f} precision {m.precision:.2f} recall {m.recall:.2f} F1 {m.f1:.2f}"
        )


# Run when executed as a program.
if __name__ == "__main__":
    # Go.
    main()
