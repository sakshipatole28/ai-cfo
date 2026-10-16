# AI CFO v2 — Full Project Report

**Owner:** Sakshi Patole · **Type:** Product + GenAI / Agentic AI / RAG · **Standard:** `05_ENGINEERING_STANDARD.md`
**Release target:** `v2.0.0` — deployed, real users, fully automated CI/CD. Cost: ₹0.

---

## 1. Summary

AI CFO is an agentic portfolio-intelligence system for Indian retail investors. Its core is **live, read-only broker linking** (Dhan primary, Upstox secondary) through a provider-adapter layer, so investors never type in their holdings. A **CAS statement upload** fills in mutual funds held outside those brokers, and a **merge layer** combines both into one verified portfolio.

On that portfolio, tested deterministic code computes true look-through fund overlap, allocation drift and FY-correct tax headroom. A team of LLM agents, grounded by a RAG knowledge base of official SEBI / AMFI / Income-tax documents, selects what matters, explains it in plain language with citations, and passes every sentence through a compliance guard. Every finding is traceable and audited.

**One-line pitch:** *"Connect your broker once — your whole portfolio, explained. Every number computed, every claim cited, never a buy/sell tip."*

---

## 2. Brutal rating

| Criterion | Now | After v2.0 | Why |
|---|---|---|---|
| Novelty | 4 | 5.5 | Live broker data + agentic reasoning + auditability together is uncommon; individual parts exist |
| Research | 2 | 3 | Product, not paper |
| Engineering | 6 | **9** | OAuth broker integrations, token vault, adapters, merge, agents, RAG, evals, CI/CD |
| GenAI / Agentic depth | 4 (fake RAG) | **8** | Real hybrid RAG, graph agents, tool calling, evals |
| Hiring value | 6 | **8.5** | Fintech integrations + GenAI = strong product-company signal |
| Overall | **5/10** | **8/10** | If every fault below is fixed |

### Faults in the current repo (all must be fixed)
1. Real-looking encryption key in public git history (`backend/.env.docker`).
2. Tax logic cites the repealed Income-tax Act 1961 for FY 2026-27 (2025 Act applies from 1 Apr 2026; 80C → s.123 per mapping guides — **verify with CBDT before coding**).
3. "Overlap" compares the `sector` field, not real holdings.
4. "RAG" uses SHA-256 word hashes, not embeddings.
5. Broker data alone misses funds held elsewhere → CAS complement + merge needed.
6. Broker token expiry not handled (see §4).
7. Docs contradict code (agent count, KNOWN_ISSUES, test count).
8. Celery + Redis + paid LLM API → not free to run. Replaced below.

---

## 3. Features (v2.0 scope)

| # | Feature | Type |
|---|---|---|
| **F1** | **Connect Dhan (primary) via OAuth/consent — read-only, encrypted token, revocable** | **Core integration** |
| **F2** | **Connect Upstox (secondary) via OAuth — read-only, encrypted token, revocable** | **Core integration** |
| **F3** | **Provider-adapter layer: one normalised holdings model for every broker** | **Core architecture** |
| **F4** | **Sync: holdings, MF/equity positions, transactions → weekly snapshots** | **Data** |
| F5 | CAS PDF upload (CAMS / KFintech / NSDL) for funds outside linked brokers | Data |
| F6 | Merge layer: de-duplicate by ISIN across brokers + CAS; source badge per holding | Data |
| F7 | Connection health: token status, last sync time, one-click reconnect | Product |
| F8 | Look-through exposure: underlying stocks across all funds | Deterministic |
| F9 | True pairwise fund overlap (weighted common holdings) | Deterministic |
| F10 | Allocation drift vs target in % and ₹ | Deterministic |
| F11 | FY-aware tax headroom + LTCG/STCG holding-period alerts | Deterministic |
| F12 | Weekly agentic report: ranked findings, plain language, citations | Agentic AI |
| F13 | "Ask about my portfolio" chat, grounded in your data + cited rules | RAG + agent |
| F14 | Explainability drawer: inputs, formula, data source, rule citations | Trust |
| F15 | Compliance guard: blocks buy/sell/named-security instructions | Safety |
| F16 | Accept / dismiss / snooze findings; decision memory | Product |
| F17 | Hash-chained audit log | Trust |
| F18 | Disconnect broker + delete-my-data | Privacy |
| F19 | Demo mode (synthetic portfolio, no login, no broker) | Product |
| F20 | MCP server exposing read-only portfolio tools | Agentic |

**Never in scope:** placing orders, trading, recommendations. The app requests read-only data only; it never stores broker passwords, PINs or TOTP secrets.

---

## 4. Broker integration design (the core)

### 4.1 Verified constraints (October 2026)
| Broker | Token lifetime | Refresh? | Access to *other users'* accounts | Cost |
|---|---|---|---|---|
| **Dhan** | 24 hours (web/endpoint tokens; can be renewed while still active) | Renew only while valid | Requires **Dhan Partner** credentials (apply via DhanHQ form); individuals can use their own API key + consent flow | Trading APIs (incl. holdings) free; data APIs charged |
| **Upstox** | Expires **3:30 AM daily** | **No refresh tokens** (Upstox policy) | Standard OAuth app flow | Check developer terms on Day 1 |

### 4.2 Design consequences
1. **Sync-on-open, not sync-in-background.** Fresh tokens exist only when the user has logged in recently. When the user opens AI CFO, the app checks each connection; if expired → "Reconnect Dhan/Upstox" (one click, broker login page) → immediate sync.
2. **Snapshots make the weekly report work without live tokens.** The weekly agent run uses the latest snapshot and states its date ("Based on holdings synced on 14 Oct").
3. **Dhan access mode — two paths, built behind one adapter:**
   - **Partner mode (target):** apply for Dhan Partner credentials on Day 1; users log in via Dhan's consent flow.
   - **Bring-your-own-key mode (works immediately):** the user creates their own DhanHQ API key/secret (valid 12 months), AI CFO stores them encrypted and runs the official consent flow. Used for you and test users until partner approval.
4. **Encrypted token vault:** tokens and API secrets encrypted at rest (AES-GCM via `cryptography`, key only in env vars, key-rotation supported); never logged; deleted on disconnect.
5. **Adapters are swappable:** adding Zerodha/Groww later = one new adapter class, no other code changes.

### 4.3 Adapter interface
```
class BrokerAdapter(Protocol):
    name: str
    def auth_url(user_id) -> str                       # start login/consent
    def exchange(callback_params) -> TokenBundle        # get access token
    def token_status(bundle) -> Valid | Expired | Revoked
    def fetch_holdings(bundle) -> list[RawHolding]
    def fetch_transactions(bundle, since) -> list[RawTxn]
    def normalise(raw) -> list[Holding]                 # ISIN, units, avg cost, asset class, source
```
Each adapter has: typed response models (Pydantic), retries with backoff, rate-limit handling, timeouts, and **recorded-response contract tests**.

### 4.4 Merge layer rules
- Key = ISIN (+ folio for MFs). Same ISIN in two sources → keep the more recent, flag conflicts above a tolerance.
- Every holding carries `source` (dhan / upstox / cas) and `as_of`.
- Coverage meter on dashboard: "% of portfolio from verified broker data vs CAS".

---

## 5. Tech stack (all free; nothing heavy installed)

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.12 (backend), TypeScript (frontend) | |
| Package mgmt | `uv` | |
| API | **FastAPI** + Pydantic v2 | |
| Broker SDKs | **`dhanhq`** (official Python SDK) and **`upstox-python-sdk`** — or plain `httpx` behind the adapter | Official clients; adapter hides them |
| HTTP | `httpx` (async) + `tenacity` (retries) | |
| Token encryption | `cryptography` (AES-GCM, envelope key in env) | Never roll your own crypto |
| DB | **Supabase Postgres** (hosted) | No installation |
| ORM / migrations | SQLAlchemy 2.0 (async) + **Alembic** | |
| Vectors | **pgvector** in Supabase | |
| App auth | **Supabase Auth** (JWT verified in FastAPI) | |
| File storage | Supabase Storage (CAS deleted after parsing) | |
| CAS parsing | **`casparser`** | |
| AMC holdings | AMC monthly portfolio disclosures → `pandas` + `openpyxl` | |
| Embeddings | **FastEmbed** (`bge-small-en-v1.5`, ONNX CPU) | |
| Retrieval | Hybrid: pgvector + Postgres full-text → Reciprocal Rank Fusion | |
| Agents | **LangGraph** | |
| LLM | Adapter: **Gemini (free) → Groq (free) fallback** | |
| Compliance | Rules + LLM-judge second pass | |
| LLM observability | **Langfuse** free | |
| Evals | pytest + DeepEval/Ragas, cached in CI | |
| Scheduling | **GitHub Actions cron** → protected job endpoints | Replaces Celery/Redis |
| MCP | Official Python MCP SDK | |
| Frontend | React + Vite + TS + Tailwind + shadcn/ui + TanStack Query + Recharts | |
| Hosting | Backend **Render** free (Docker; sleeps after 15 min); frontend **Vercel** | |
| Tests | pytest, hypothesis, **respx** (mock broker HTTP), Playwright, vitest | |

**OAuth note:** broker redirect URLs must point to your deployed backend (`https://<app>.onrender.com/brokers/<name>/callback`). Register a second redirect URL for local development (`http://localhost:8000/...`).

---

## 6. Architecture

```
                     ┌─────────── Vercel ───────────┐
User browser ──────▶ │ React: connect brokers,      │
   │                 │ dashboard, report, chat,     │
   │                 │ explain drawer, CAS upload   │
   │                 └──────────────┬───────────────┘
   │ broker login (redirect)        │ HTTPS + Supabase JWT
   ▼                                ▼
┌────────────┐      ┌──────────────────────── Render (Docker) ────────────────────────┐
│ Dhan /     │◀────▶│ FastAPI                                                          │
│ Upstox     │ API  │  brokers/   adapters (dhan, upstox) · OAuth callbacks · vault     │
│ (read-only)│      │  ingestion/ CAS parser · merge layer (ISIN) · snapshots           │
└────────────┘      │  core/      lookthrough · overlap · drift · tax(FY) — pure, tested│
                    │  rag/       FastEmbed → pgvector + FTS → RRF                      │
                    │  agents/    LangGraph ── LLM adapter (Gemini → Groq)              │
                    │  compliance/ rules + LLM judge                                    │
                    │  audit/     hash-chained log + traces                             │
                    │  mcp/       read-only tools                                       │
                    └──────────┬───────────────────────────────┬──────────────────────┘
                               ▼                               ▼
                 Supabase: Postgres + pgvector + Auth + Storage      Langfuse
GitHub Actions: CI · CD on tags · weekly agent run (snapshots) · monthly AMC ingest · nightly evals
```

### Agent graph (LangGraph)
```
START → load_latest_snapshot → ┬─ drift_agent ─┐
                               ├─ overlap_agent ┼→ aggregator → ranker (decision memory)
                               └─ tax_agent ────┘    → explainer (RAG, cited)
                                                     → compliance_guard ─fail→ rewrite (≤2) ─fail→ drop+log
                                                     → persist (report, traces, audit) → END
```
Agents receive numbers from `core`, never compute them; outputs are Pydantic schemas; every claim lists `evidence_ids`; numbers not present in evidence → rejected.

### Chat agent tools
`get_holdings`, `get_connection_status`, `get_overlap(a,b)`, `get_drift`, `get_tax_headroom(fy)`, `search_rules(query)`. Compliance guard on every answer.

---

## 7. Data model (Supabase Postgres, Row-Level Security on all user tables)

| Table | Key columns |
|---|---|
| `profiles` | user_id, target_allocation, created_at |
| **`broker_connections`** | id, user_id, broker, mode (partner/byo_key), status, encrypted_token, encrypted_api_secret (byo), token_expires_at, last_sync_at, revoked_at |
| `sync_runs` | id, connection_id, started_at, finished_at, status, error_code, records |
| `cas_uploads` | id, user_id, uploaded_at, status, parser_version |
| `holdings_snapshots` | id, user_id, as_of, coverage_pct |
| `holdings` | snapshot_id, isin, folio, name, units, avg_cost, value, asset_class, **source**, source_as_of |
| `transactions` | user_id, isin, date, type, units, amount, source |
| `amc_disclosures` | scheme_isin, month, security_isin, weight |
| `findings`, `traces`, `decisions` | as before |
| `audit_log` | append-only, hash-chained (includes broker connect/disconnect events) |
| `kb_documents`, `kb_chunks` | RAG store (vector(384) + tsvector) |
| `agent_runs` | tokens, cost, langfuse_trace_id |

---

## 8. Workflows

**8.1 Onboarding:** sign up → "Connect Dhan" / "Connect Upstox" → broker login → callback → token encrypted → first sync → dashboard. Optional: upload CAS for outside funds.

**8.2 Returning user:** open app → connection check → if expired, one-click reconnect → sync → fresh snapshot.

**8.3 Weekly report:** GitHub Actions cron → `/jobs/weekly-run` → agents run on latest snapshot per user → report shows snapshot date → user notified to reconnect if snapshot older than 7 days.

**8.4 Monthly:** AMC disclosure ingest (top 5 AMCs first) with weight-sum validation.

**8.5 Developer:** issue → branch → Claude Code (tests first) → PR → CI → review → merge → tag → CD.

---

## 9. Testing strategy

| Level | What | Tool |
|---|---|---|
| **Broker contract tests** | Recorded (sanitised) Dhan/Upstox responses → adapter → normalised holdings | pytest + respx |
| **Token lifecycle** | expired / revoked / renewed / partial failure → correct status + UI state | pytest |
| **Merge** | duplicate ISINs, conflicts, CAS-only, broker-only | pytest + hypothesis |
| **Vault** | encrypt/decrypt round-trip, key rotation, tokens never in logs | pytest |
| Core | hand-computed formulas; tax both sides of 1 Apr 2026 | pytest, hypothesis |
| Integration | API + Postgres/pgvector service container | pytest, httpx |
| Agents | fake deterministic LLM | pytest |
| LLM evals | faithfulness, citations, compliance (cached) | DeepEval/Ragas |
| E2E | connect broker (mocked OAuth server) → sync → report → explain | Playwright |
| Live smoke (manual, your own account) | real Dhan/Upstox read-only sync | checklist in `docs/` |

**CI never calls real broker APIs.** Real-account checks are manual and documented.

---

## 10. CI/CD
- **ci.yml:** ruff → mypy → pytest (Postgres+pgvector service) → evals (cached) → frontend lint/test/build → Playwright → gitleaks, pip-audit, npm audit, CodeQL.
- **cd.yml (tag):** Docker → GHCR → Alembic migrate → Render deploy hook → Vercel → smoke test → GitHub Release.
- **cron:** weekly run, monthly AMC ingest, nightly live evals (small).

---

## 11. Security & compliance
- Read-only scopes only; no order endpoints imported anywhere (CI check greps for order APIs).
- Tokens/secrets AES-GCM encrypted; master key only in Render env; rotation script; redaction filter in logging.
- Never store broker passwords, PINs or TOTP.
- RLS, JWT verification, rate limiting, CORS allowlist, CSRF `state` parameter in OAuth flows.
- Disconnect = revoke + delete tokens + audit event. Delete-my-data endpoint.
- Wording: *"decision support, not investment advice."* No legal claims.
- Check each broker's API terms for showing data to third-party users before public launch.

---

## 12. Build plan (7 full days + buffer)

| Day | Deliverable (PR merged, CI green) |
|---|---|
| **0 (today)** | Apply for **Dhan Partner** access; create Dhan API key (your account) and Upstox developer app; Supabase, Google AI Studio, Groq accounts |
| 1 | Purge leaked key + rotate; uv/pre-commit/CI/branch protection; Supabase + Alembic baseline; token vault; doc fixes; ADR-001 (free stack), ADR-002 (broker design) |
| 2 | **Adapter interface + Dhan adapter** (BYO-key consent flow), OAuth callback, contract tests, connection status API |
| 3 | **Upstox adapter** (OAuth), sync service + snapshots + reconnect flow; CAS upload + `casparser`; **merge layer** with tests |
| 4 | AMC disclosures (5 AMCs); look-through, true overlap, drift; FY-aware tax engine |
| 5 | RAG (ingest, hybrid search, golden-set eval); LangGraph agents + LLM adapter + compliance guard + Langfuse |
| 6 | Frontend: connect-broker screens, connection health, dashboard, report, explain drawer, chat; Playwright with mocked OAuth; MCP server |
| 7 | CD to Render + Vercel; cron jobs; README/docs/GIF; `v2.0.0`; live smoke test on your own Dhan/Upstox accounts; onboard 3–5 users |
| +2–3 buffer | Partner-mode switch when approved; fixes from real users |

---

## 13. Definition of done
- [ ] Standard §9 complete
- [ ] Dhan + Upstox connect, sync and reconnect work on real accounts (read-only)
- [ ] CAS + merge produce one portfolio with source badges and coverage %
- [ ] Token expiry handled gracefully everywhere
- [ ] RAG eval + compliance metrics published
- [ ] Live URL + demo mode; 3+ real users
- [ ] College synopsis updated (tax law, merge layer, free stack, token handling)

## 14. Resume line (fill numbers after measuring)
> **AI CFO** — deployed agentic portfolio analyser for Indian investors: read-only Dhan & Upstox integrations via a provider-adapter layer with encrypted token vault, CAS ingestion and ISIN-level merge; LangGraph multi-agent pipeline with hybrid RAG (hit@5 = X%) over SEBI/Income-tax sources; deterministic look-through overlap and FY-correct tax engine; compliance guard (Y% block rate); full CI/CD with LLM evals; N real users.

## 15. Claude Code kickoff
> Read PROJECT_PLAN.md and ENGINEERING_STANDARD.md. We are on Day 1. Broker integrations are read-only: never import order-placement APIs, never store PINs/TOTP, never log tokens. CI must never call real broker APIs — use recorded fixtures. Feature branch, tests first, PR, then show me CI results.

## Sources (broker constraints)
- Dhan authentication docs: https://dhanhq.co/docs/v2/authentication/
- Upstox community answer on token expiry: https://community.upstox.com/t/do-upstox-provides-api-with-refresh-token-as-daily-i-need-to-generate-the-access-token-please-guide/13077
