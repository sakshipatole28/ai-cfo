# Retrieval-augmented generation (RAG) in AI CFO

AI CFO answers rule questions ("How is LTCG taxed?", "What records must an adviser keep?") **only from a versioned knowledge base**, and every sentence carries a citation. Portfolio numbers never come from this pipeline. They come from the deterministic engine.

## Pipeline
```
question
  │ 1. redact identifiers (PAN, email, phone)         aicfo.security.redaction
  │ 2. compliance guard: refuse buy/sell/tip requests   aicfo.rag.guard
  ▼
retrieve (k=4)                                         aicfo.rag.retriever
  ├─ BM25 over stemmed tokens (Snowball)               aicfo.rag.bm25
  ├─ dense vectors: bge-small-en-v1.5 (FastEmbed, CPU) or hashing fallback
  └─ Reciprocal Rank Fusion: score = Σ 1/(60 + rank)
  │ 3. relevance gate: IDF-weighted share of question terms found in the top passages ≥ 0.40
  ▼
answer                                                 aicfo.rag.answer
  ├─ LLM (any OpenAI-compatible endpoint, temperature 0), prompt allows only numbered passages
  │     └─ verifier: every [n] must exist; every number must appear in the passages; answer guard
  │        → any failure falls back to the extractive answer, and the issue is recorded
  └─ extractive (default, no model): quote the best-matching sentences, each with [n]
```

## Knowledge base
`data/kb/*.md`: one Markdown file per source, with front matter (`id`, `issuer`, `title`, `source_url`, `version`, `effective`, `kind`). Each `## Section` is split into sentence-aligned chunks of about 700 characters, with one sentence of overlap.

| Document | Issuer |
|---|---|
| Income-tax Act 2025: capital gains | Income Tax Department |
| Income-tax Act 2025: regimes, s.123 (old 80C), ELSS | Income Tax Department |
| Investment Advisers Regulations 2013 | SEBI |
| Mutual fund categorisation | SEBI |
| Portfolio disclosure and riskometer | SEBI |
| AI/ML accountability of regulated entities | SEBI |
| DPDP Act 2023 and Rules 2025 | MeitY |
| Account Aggregator framework | RBI / SEBI |
| Demo firm Investment Policy Statement (fictional) | Firm policy |

The documents are **plain-language summaries with links to the official text, not legal text**. Section numbers under the Income-tax Act 2025 must be verified against the official Act before production use.

## Evaluation
`data/evals/rag_golden.json` holds 28 paraphrased questions, each with the expected source documents. Run:
```bash
cd backend
uv run python -m aicfo.rag eval                                   # hashing embedder (CI)
uv sync --extra models && AICFO_RAG_EMBEDDER=fastembed uv run python -m aicfo.rag eval
```
| Mode | hit@1 | hit@3 | MRR |
|---|---|---|---|
| BM25 | 1.00 | 1.00 | 1.00 |
| Dense (bge-small) | 1.00 | 1.00 | 1.00 |
| Hybrid (RRF) | 1.00 | 1.00 | 1.00 |

These scores are high because the corpus is small (9 documents, 39 passages), so the golden set is easy. The next step is a larger corpus with harder, overlapping topics. The tests also require that:
- all golden questions get cited answers;
- off-topic questions are declined;
- buy/sell requests are refused;
- an LLM answer with an invented number or a bad citation is rejected;
- identifiers are redacted before any model call.

## Use it
```bash
uv run python -m aicfo.rag ask "Is the 1.25 lakh exemption per fund or for the whole year?"
uv run uvicorn aicfo.main:app      # POST /v1/rag/ask · POST /v1/rag/search · GET /v1/kb/documents
# With a local model (data stays on your machine):
AICFO_LLM_BASE_URL=http://localhost:11434/v1 AICFO_LLM_MODEL=llama3.1:8b uv run uvicorn aicfo.main:app
```
The web console runs the same corpus in the browser (BM25 and extractive answers), so the shared demo works without a server. Set `VITE_API_URL` to use the API's hybrid retrieval instead.

## Planned next
- pgvector storage (Postgres) behind the same retriever interface.
- A cross-encoder reranker.
- Per-tenant private documents.
- The ML compliance classifier between the rules layer and the LLM judge.
