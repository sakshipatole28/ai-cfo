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

EXPORT = REPO_ROOT / "data" / "synthetic" / "agent_runs.json"


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m aicfo.agents")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("review")
    r.add_argument("client")
    r.add_argument("--profile", choices=["RIA", "MFD"], default="RIA")
    c = sub.add_parser("copilot")
    c.add_argument("client")
    c.add_argument("question")
    sub.add_parser("export")
    sub.add_parser("eval")
    args = ap.parse_args()

    if args.cmd == "review":
        st = get_pipeline().run(args.client, args.profile)
        for t in st["trace"]:
            print(f"{t.node:<20} {t.kind:<6} {t.ms:>8.2f} ms  {t.summary}")
        print()
        for d in st["drafts"]:
            print(f"[{d.status}] {d.candidate.severity:<6} {d.candidate.kind:<13} {d.text}")
    elif args.cmd == "copilot":
        a = get_copilot().ask(args.client, args.question)
        print(f"[{a.mode}] {a.answer}")
        for call in a.tool_calls:
            print("  tool:", call["tool"])
    elif args.cmd == "export":
        runs = {cid: serialise(get_pipeline().run(cid)) for cid in load_book().clients}
        EXPORT.write_text(
            json.dumps(
                {"generated": datetime.now().isoformat(timespec="seconds"), "runs": runs},
                ensure_ascii=False,
                indent=1,
            )
            + "\n"
        )
        print(f"wrote {EXPORT} ({len(runs)} runs)")
    elif args.cmd == "eval":
        m = cross_validate()
        print(
            f"compliance classifier 5-fold CV: accuracy {m.accuracy:.2f} precision {m.precision:.2f} recall {m.recall:.2f} F1 {m.f1:.2f}"
        )


if __name__ == "__main__":
    main()
