"""CLI: `uv run python -m aicfo.rag {stats|search|ask|eval} [text]`."""

from __future__ import annotations

import argparse
import textwrap

from aicfo.evals.rag_eval import evaluate
from aicfo.rag.retriever import Mode
from aicfo.rag.service import get_rag


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m aicfo.rag")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stats")
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--mode", choices=["hybrid", "bm25", "dense"], default="hybrid")
    a = sub.add_parser("ask")
    a.add_argument("question")
    sub.add_parser("eval")
    args = parser.parse_args()
    rag = get_rag()

    if args.cmd == "stats":
        print(
            f"{len(rag.documents)} documents, {len(rag.chunks)} chunks, embedder={rag.retriever.embedder.name}"
        )
        for d in rag.documents:
            print(f"  {d.id:<24} {d.issuer:<22} {d.title}")
    elif args.cmd == "search":
        for i, h in enumerate(rag.retriever.search(args.query, mode=args.mode), 1):
            print(
                f"{i}. {h.chunk.id:<26} rrf={h.score:.4f} bm25#{h.bm25_rank} dense#{h.dense_rank}  {h.chunk.section}"
            )
    elif args.cmd == "ask":
        ans = rag.answerer.ask(args.question)
        print(f"[{ans.mode}]\n" + textwrap.fill(ans.text, 100))
        for c in ans.citations:
            print(f"  [{c.n}] {c.issuer} · {c.title} · {c.section}\n      {c.source_url}")
        if ans.issues:
            print("issues:", "; ".join(ans.issues))
    elif args.cmd == "eval":
        print(f"{'mode':<8} {'n':>3} {'hit@1':>6} {'hit@3':>6} {'hit@5':>6} {'MRR':>6}")
        modes: tuple[Mode, ...] = ("bm25", "dense", "hybrid")
        for mode in modes:
            r = evaluate(rag.retriever, mode)
            print(
                f"{r.mode:<8} {r.questions:>3} {r.hit_at_1:>6.2f} {r.hit_at_3:>6.2f} {r.hit_at_5:>6.2f} {r.mrr:>6.2f}"
            )


if __name__ == "__main__":
    main()
