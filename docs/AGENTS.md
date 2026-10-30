# Multi-agent review pipeline

The review is a **LangGraph state graph**. Tested code computes every number. Agents decide what matters, explain it with a cited rule, and pass compliance and verification before an adviser sees a draft.

```
load_snapshot → compute_evidence ─┬─ overlap_analyst ────┐
   (code)          (code)         ├─ allocation_analyst ─┼→ rank → explainer → compliance → verifier → drafts
                                  └─ tax_analyst ────────┘  (code)  (agent+RAG)  (guard)      (guard)
```

| Node | Type | What it does | Uses |
|---|---|---|---|
| `load_snapshot` | code | Builds positions, lots and valuations for one client | `aicfo.core.analytics` |
| `compute_evidence` | code | Overlap, drift, look-through exposure and tax lots, each as an **Evidence** record (formula, inputs, steps, raw values) | `aicfo.agents.tools` |
| `overlap_analyst` | agent | Selects overlap and concentration items and sets severity | LLM (JSON, validated) or firm policy |
| `allocation_analyst` | agent | Judges drift against the client's model | LLM or firm policy |
| `tax_analyst` | agent | Lots turning long-term within 30 days; unused LTCG exemption | LLM or firm policy |
| `rank` | code | Orders by severity and rupee impact; skips findings the adviser dismissed before (decision memory) | — |
| `explainer` | agent | Writes each finding; retrieves the governing rule via **RAG** and cites it `[1]` | Hybrid retriever; LLM rewrite optional |
| `compliance` | guard | Rules, then the **ML advice classifier**, then an **LLM judge** for borderline scores (0.3–0.7). The MFD profile blocks advice-like text | `aicfo.rag.guard`, `aicfo.ml` |
| `verifier` | guard | Every number must appear in the evidence or the cited passage; citations must resolve; only the `{client}` placeholder is allowed. LLM text that fails is replaced by the evidence-built template | — |

The three analysts run **in parallel** (fan-out from `compute_evidence`, fan-in at `rank`). Every node records a trace event: duration, a summary, and details such as which evidence it flagged and which passages it retrieved.

## Without a model
If no LLM is configured, each agent falls back to its deterministic **firm policy** (thresholds from `data/kb/firm-ips.md`). The pipeline therefore always runs, in CI and in the demo, and the trace says which mode was used. Connect a model to let agents decide and write. Groq and Gemini go through LangChain (`aicfo/llm/providers.py`), with automatic fallback from one to the other; any OpenAI-compatible endpoint also works:
```bash
AICFO_GROQ_API_KEY=gsk_... AICFO_GEMINI_API_KEY=... uv run python -m aicfo.agents review rohan-deshpande
AICFO_LLM_PROVIDER=openai AICFO_LLM_BASE_URL=http://localhost:11434/v1 uv run python -m aicfo.agents review rohan-deshpande
uv run python -m aicfo.llm bench    # compare Groq and Gemini on this pipeline's guards
```
Model output never adds numbers. Analyst JSON is schema-checked against known evidence IDs, and rewritten text goes back through the verifier.

## Copilot (tool-using agent)
`aicfo.agents.copilot`.
- **Tools:** `get_summary`, `get_drift`, `get_overlap`, `get_tax_position`, `get_exposures`, `search_rules`.
- **With a model:** a JSON tool-calling loop of up to 4 steps. The final answer is rejected if it contains a number that no tool returned.
- **Without a model:** an intent router calls the same tools.
- **Always:** requests for buy/sell calls are refused, and identifiers are redacted first.

## ML: advice-likelihood classifier
`aicfo.ml.compliance_classifier`: L2-regularised logistic regression (numpy).
- **Features:** hashed words and word pairs, plus cue features (imperative start, second person, modal verbs).
- **Training data:** `data/ml/compliance_sentences.jsonl` (80 labelled synthetic sentences).
- **5-fold cross-validation:** accuracy 0.90 · precision 0.94 · recall 0.85 · **F1 0.89**.

The dataset is small; growing it with reviewed real drafts is the next step.

## Run it
```bash
cd backend
uv run python -m aicfo.agents review rohan-deshpande            # trace + drafts
uv run python -m aicfo.agents review neha-joshi --profile MFD
uv run python -m aicfo.agents copilot rohan-deshpande "How much LTCG exemption is left?"
uv run python -m aicfo.agents eval                              # classifier CV
uv run python -m aicfo.agents export                            # data/synthetic/agent_runs.json for the console
uv run uvicorn aicfo.main:app   # POST /v1/clients/{id}/review · POST /v1/clients/{id}/copilot · GET /v1/clients
```

## Tests (`backend/tests/test_core_and_agents.py`)
- **Core numbers:** hand-checked values, plus invariants for all 12 clients (allocation sums to 100%, drift sums to 0, overlap stays between 0 and 100).
- **Graph:** node order and parallel fan-out; findings follow firm policy.
- **Safety, for every client:** every draft is cited, verified and number-safe; invented numbers are rejected; dismissed findings are skipped.
- **LLM paths with a fake model:** analyst JSON is validated, unknown IDs are dropped, a rewrite with a new number falls back to the template, and the MFD profile blocks advice-like text.
- **Classifier:** a quality gate on its cross-validated scores.
- **Copilot and API:** both have their own tests.
