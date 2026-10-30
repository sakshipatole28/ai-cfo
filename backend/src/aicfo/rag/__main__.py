"""CLI: `uv run python -m aicfo.rag {stats|search|ask|eval} [text]`."""

from __future__ import annotations

import argparse
import textwrap

from aicfo.evals.rag_eval import HARD, evaluate, load_golden
from aicfo.rag.retriever import Mode
from aicfo.rag.service import get_rag


# Command-line entry: stats, search, ask or eval.
def main() -> None:
    # Argument parser.
    parser = argparse.ArgumentParser(prog="python -m aicfo.rag")
    # Sub-commands.
    sub = parser.add_subparsers(dest="cmd", required=True)
    # stats: what the knowledge base holds.
    sub.add_parser("stats")
    # search <query>: show retrieved passages and their ranks.
    s = sub.add_parser("search")
    # The query.
    s.add_argument("query")
    # hybrid, bm25 or dense.
    s.add_argument("--mode", choices=["hybrid", "bm25", "dense"], default="hybrid")
    # ask <question>: a cited, guarded answer.
    a = sub.add_parser("ask")
    # The question.
    a.add_argument("question")
    # eval: score retrieval on the golden and hard question sets.
    sub.add_parser("eval")
    # Read the command line.
    args = parser.parse_args()
    # Build the RAG service.
    rag = get_rag()

    # Show corpus size and embedder.
    if args.cmd == "stats":
        print(
            f"{len(rag.documents)} documents, {len(rag.chunks)} chunks, embedder={rag.retriever.embedder.name}"
        )
        # List each document.
        for d in rag.documents:
            print(f"  {d.id:<24} {d.issuer:<22} {d.title}")
    # Show ranked passages.
    elif args.cmd == "search":
        # Each hit with its fused, keyword and meaning ranks.
        for i, h in enumerate(rag.retriever.search(args.query, mode=args.mode), 1):
            print(
                f"{i}. {h.chunk.id:<26} rrf={h.score:.4f} bm25#{h.bm25_rank} dense#{h.dense_rank}  {h.chunk.section}"
            )
    # Answer a question.
    elif args.cmd == "ask":
        # Retrieve, answer and verify.
        ans = rag.answerer.ask(args.question)
        # How it was answered, then the text.
        print(f"[{ans.mode}]\n" + textwrap.fill(ans.text, 100))
        # Each cited source with its link.
        for c in ans.citations:
            print(f"  [{c.n}] {c.issuer} · {c.title} · {c.section}\n      {c.source_url}")
        # Why a model answer was rejected, if it was.
        if ans.issues:
            print("issues:", "; ".join(ans.issues))
    # Score retrieval.
    elif args.cmd == "eval":
        # Column headings.
        print(f"{'mode':<8} {'n':>3} {'hit@1':>6} {'hit@3':>6} {'hit@5':>6} {'MRR':>6}")
        # All three search modes.
        modes: tuple[Mode, ...] = ("bm25", "dense", "hybrid")
        # Plain set and hard (paraphrased) set.
        for label, rows in (("golden", None), ("hard", load_golden(HARD))):
            # Which set.
            print(f"-- {label} set")
            # Each mode.
            for mode in modes:
                # hit@1/3/5 and mean reciprocal rank.
                r = evaluate(rag.retriever, mode, rows)
                print(
                    f"{r.mode:<8} {r.questions:>3} {r.hit_at_1:>6.2f} {r.hit_at_3:>6.2f} {r.hit_at_5:>6.2f} {r.mrr:>6.2f}"
                )


# Run when executed as a program.
if __name__ == "__main__":
    # Go.
    main()
