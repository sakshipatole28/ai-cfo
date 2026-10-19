# AI CFO v3 — B2B Plan (supersedes v2 where they differ)

**Owner:** Sakshi Patole · **Status:** In progress, built step by step · **Research date:** 16 Oct 2026
**Base document:** `02_AI_CFO_V2.md` (kept for history)

| Step | Section | State |
|---|---|---|
| 1 | §0 Direction, §1 Blockers → solutions | ✅ Done |
| 2 | §2 Stack, §2A Zero-access privacy, §2B Development data | ✅ Done |
| 3 | §3 Architecture + multi-tenant data model | ✅ Done |
| 4 | §4 UI/UX structure | ✅ Done |
| 5 | §5 Status checklist + roadmap | ✅ Done (living document) |

---

## 0. Direction change: B2C → B2B

### 0.1 New positioning
> **AI CFO is a portfolio-intelligence workspace for Indian wealth professionals.** It ingests every client's holdings from statements and data feeds, computes look-through overlap, drift and capital-gains position deterministically, and drafts cited, compliance-checked review notes. The advisor approves them before anything reaches a client.

One-line pitch for buyers: *"Client portfolio reviews in minutes, not hours. Every number computed, every claim cited, every action audited, with the advisor always in the loop."*

### 0.2 Who buys (ideal customer profile, in order)
| # | Segment | Why they buy | Regulatory fit |
|---|---|---|---|
| 1 | **SEBI RIAs** (small and mid firms) | Manual portfolio reviews; IA Regulations require records of risk profile, suitability and the rationale for advice | They are allowed to advise, so AI drafts plus advisor approval is legal. They can be AA FIUs |
| 2 | **Mutual fund distributors (ARN holders)** | Large market; need overlap and review reports to retain clients | Cannot give advice beyond incidental advice, so the platform must run in "information only" compliance mode |
| 3 | **PMS / wealth firms / family offices** | Consolidated multi-source reporting | Regulated, so they can be AA FIUs; strict vendor due diligence (CSCRF) |
| 4 | **Brokers (white-label)** | Portfolio-insight module inside their own app | Deploying **inside the broker's infrastructure** is the access route Upstox described for third-party apps (§1.1) |

Competitive context: Wealthy.in (raised ₹130 Cr in late 2025, serves 6,000+ MFDs with AI tools), Valuefy, and MFD back-office software such as Investwell and Wealth Elite. **Differentiation:** look-through accuracy, citation-backed explanations, a compliance and audit trail designed for SEBI's 2025 AI-accountability rules, and an API/MCP-first design.

### 0.3 What B2B fixes automatically
- **Investment-advice risk** moves to the registered customer. AI CFO is a technology provider with a human-in-the-loop workflow.
- **Data access** becomes possible through the customer's regulated status (Account Aggregator FIU route) and through feeds they already receive (RTA mailback files for ARN holders).
- **Willingness to pay** is real: per-advisor seats or per client.

### 0.4 What B2B makes stricter
- **SEBI Intermediaries (Amendment) Regulations, Feb 2025:** a regulated entity is fully responsible for AI tools it uses, **including tools bought from third parties**: data privacy, outputs and legal compliance. Buyers will audit us.
- **SEBI CSCRF:** processing and storage of regulated entities' data should be in India, and encryption keys should be managed in India. The exact localisation scope is still under consultation, so design India-resident from day one.
- **DPDP Act and Rules (notified Nov 2025):** our customer is the data fiduciary and AI CFO is the data processor. A Data Processing Agreement is needed. Most obligations apply from **13 May 2027**.

---

## 1. Every blocker → a concrete solution (nothing dropped)

Legend: 🟢 works now · 🟡 needs a partner or customer, but we build it now behind an adapter · 🔵 later phase, interface designed now

### 1.1 Broker access for other users (Upstox paused multi-client onboarding; Dhan needs partner approval)
**Root cause:** exchange rules now require third-party platforms using broker APIs to be exchange-empanelled and hosted inside broker infrastructure. Empanelment needs a company with significant net worth; NCDEX, for example, now requires ₹1 crore for vendors.

**Solution: a data-source ladder.** Brokers become one adapter among many, not the foundation.
| Tier | Source | Who it serves | Status |
|---|---|---|---|
| T0 | Synthetic demo data | Sales demos, CI | 🟢 |
| T1 | **CAS PDF** (NSDL/CDSL demat CAS + CAMS/KFintech MF CAS) via `casparser` (MIT, v1.4.1, Aug 2026) | Every client of every customer | 🟢 |
| T1+ | **CAS auto-ingest by email**: each tenant gets an inbound address; the client or advisor sets a forwarding filter, so the monthly NSDL/CDSL CAS arrives automatically | Keeps data fresh without any broker | 🟢 (avoids Gmail's restricted-scope security assessment) |
| T2 | **RTA distributor feeds**: CAMS/KFintech mailback reports (folio, AUM and transaction reports per ARN) | MFD and RIA customers; covers all clients at once | 🟢 file import (one parser per report format) |
| T2 | **Broker tradebook / tax P&L exports** (CSV/XLSX) | Equity tax lots (see 1.2) | 🟢 |
| T3 | **Account Aggregator** (CDSL, NSDL, CAMS, KFintech are live FIPs) via an AA/TSP such as Finvu, OneMoney or Setu, **with the customer as the FIU** | RIAs, PMS firms, brokers | 🟡 build against the Finvu/OneMoney sandbox now. Production needs Sahamati certification and an IS audit; vendor estimate ₹5–25 L in year one, paid with the first enterprise deal |
| T4a | Dhan / Upstox **bring-your-own-key** | Owner's own account, live-sync demo | 🟢 |
| T4b | **Broker white-label**: deployed inside a broker's infrastructure | Broker customers | 🔵 Helm chart / Docker bundle ready |
| T4c | Dhan Partner application | Direct multi-user | 🟡 apply now; no dependency on it |

**Design rule:** `DataSourceAdapter` replaces `BrokerAdapter`. Every source returns `NormalisedHolding` / `NormalisedTxn` with `source`, `as_of` and `confidence`. Adding a source never touches the core.

### 1.2 Broker data has no MF holdings and no tax lots
**Solution:**
- MF holdings and full MF transaction history come from CAMS/KFintech CAS and RTA feeds (T1/T2).
- Equity lots: a **FIFO lot engine** fed by tradebook imports (T2) plus NSDL/CDSL CAS monthly transactions. AA depository history is capped at 2 years, so tradebooks fill the gap.
- When lots are unknown, the holding is marked **"holding period unverified"**. It is excluded from LTCG/STCG alerts and never guessed.

### 1.3 Merge-layer bug (v2 "keep the more recent")
**Solution: a reconciliation engine, not a de-duplicator.**
- Identity key: `(holder_PAN_hash, account_ref, ISIN)`. `account_ref` is a demat BO ID (DP ID + client ID) or an MF folio.
- The same `account_ref` from two sources counts as **one position**. Precedence is by `as_of`, then source reliability: AA > RTA feed > CAS > broker API > manual.
- A **different** `account_ref` with the same ISIN is **additive** (two demat accounts, two folios).
- Any quantity mismatch above tolerance creates a **reconciliation exception** shown to the advisor. Nothing is silently dropped.
- Property-based tests (hypothesis): totals are conserved; merge is idempotent and does not depend on source order.

### 1.4 Free LLM tier trains on prompts (Gemini free) and data leaves India
**Solution: three layers.**
1. **Pseudonymisation gateway.** The LLM never sees PAN, names, folios or account numbers, only `CLIENT_A`-style tokens, computed findings and evidence IDs. The gateway re-identifies after generation. This is a tested module.
2. **Provider policy by environment:**
   - dev/demo: Gemini free or Groq, **synthetic data only**;
   - production: **Vertex AI Gemini in `asia-south1` (Mumbai)**, which keeps ML processing in-region and is paid but low cost for Flash models;
   - optional: Groq with Zero Data Retention (US-hosted, so only for tenants who accept that).
3. **Tenant bring-your-own model key** (their own Vertex or Azure account). Enterprise buyers often require this, and it moves the LLM cost to them.

> Honest note: **"₹0" holds for development, demo and pilots.** Production with real regulated client data needs a small paid LLM bill (or the tenant's own key), because the free tiers can't meet privacy and residency requirements.

### 1.5 Investment-advice exposure
**Solution: tenant compliance profiles, plus human-in-the-loop by default.**
- `RIA` profile: AI drafts recommendations. **The advisor must approve.** Suitability and risk profile are attached, and the rationale is stored, which matches IA record-keeping duties.
- `MFD` profile: information-only language. The guard blocks advice wording and allows facts such as overlap, drift and tax status.
- `BROKER_WL` profile: information-only, with the broker's disclaimers.
- Nothing AI-generated reaches an end client without an approved state. There is a **per-tenant AI kill switch**, matching SEBI's direction on human oversight and kill switches.

### 1.6 DPDP Act compliance, and audit-log vs right-to-erasure
**Solution:**
- **Consent ledger** per end client: purpose, scope, source, timestamp, expiry, and the advisor who captured it.
- **Crypto-shredding.** Each end client's PII is encrypted with its own data key (envelope encryption). Erasure destroys that key, so the data becomes unreadable while the **hash-chained audit log stays intact**, because chain entries hold only IDs and hashes, never PII.
- Retention policy engine, a 72-hour breach runbook, and a DPA template for customers.

### 1.7 Data localisation and vendor due diligence (CSCRF, SEBI AI rules)
**Solution:**
- India-region hosting for all client data: database, storage, compute and LLM (details in §2).
- Keys managed in India.
- A ready-made **"Trust Pack"** for sales:
  - architecture diagram;
  - data-flow map;
  - encryption and key policy;
  - audit-log design;
  - model card;
  - evaluation results (faithfulness, citation accuracy, compliance block rate);
  - incident process;
  - kill switch and human-oversight evidence.

### 1.8 AMC portfolio disclosures are messy and late
**Solution:**
- **Per-AMC parser plugins**: a registry of mappings from each AMC's layout to a canonical schema.
- Validation gates:
  - weights sum to about 100%;
  - valid ISIN checksum;
  - month continuity;
  - outlier detection.
- Rollout order: AMCs ranked by AUM *in the customer's book* (the top 10 AMCs cover most AUM).
- The UI shows **look-through coverage %** and the **disclosure month**. Funds without data show "not yet looked-through"; nothing is estimated.

### 1.9 Tax law transition (Income-tax Act 1961 → 2025, from 1 Apr 2026)
**Solution:**
- A versioned **rule-set per financial year**, with a citation table mapping each rule to both the old and new section numbers.
- Scope: capital gains first:
  - equity LTCG 12.5% above ₹1.25 L;
  - STCG 20%;
  - 31 Jan 2018 grandfathering;
  - post-Apr-2023 debt-fund slab treatment.
- Old-regime deductions (80C → s.123, ELSS) are an optional module.
- **Gate:** the mapping table is verified against official CBDT/incometaxindia.gov.in text before release (task in §5). Tests cover both sides of 1 Apr 2026.

### 1.10 Live Dhan connection + validation harness (academic commitment)
**Commitment kept:** the Dhan connection ships as the **T4a live connector**, used for live demos and as a real-data validation source.

**Correction to the "demo vs real accuracy" idea:** synthetic and real data measure *different* things.
- **Synthetic data** has known ground truth because we plant the problems. It measures whether the system *finds* them (recall and precision).
- **Real data** measures robustness: odd ISINs, ETFs, SGBs, corporate actions, partial data. Its ground truth must come from a **second independent source**.

**Three-layer validation**
| Layer | Question | Ground truth | Target |
|---|---|---|---|
| L1 Ingestion | Did we read holdings correctly? | Dhan API vs the same person's **CDSL CAS** for the same date (Dhan demat accounts sit at a depository, so they appear in the CAS); `casparser` output vs the PDF | **100% exact** quantities and ISINs; every mismatch explained |
| L2 Computation | Are overlap, drift and tax numbers right? | Hand-computed spreadsheets plus an independent reference implementation; public overlap tools as a sanity check | **100% exact** (these are unit tests, not accuracy %) |
| L3 Agents (LLM) | Are findings faithful, cited, compliant and useful? | Planted scenarios (synthetic); expert labels from a CA, RIA or faculty member on real cases | Numbers not in evidence = **0**; citation accuracy ≥95%; compliance block rate on a red-team set ≥99%; finding precision/recall reported |

**Datasets**
- **D1 Synthetic personas** (generator, seeded): about 10 personas with planted issues. Examples: 5 large-cap funds overlapping 70%+, equity drift +18%, ₹1.1 L unrealised LTCG available for tax harvesting, a lot crossing 12 months next week, missing ISIN, duplicate folio. Built from **real public market data**:
  - AMFI `NAVAll.txt` (NAVs and ISINs);
  - AMC monthly portfolio disclosures (fund constituents);
  - NSE bhavcopy and equity list (prices and ISINs).
- **D2 Recorded API fixtures:** the Dhan response schema, captured from the owner's account and sanitised, plus DhanHQ Sandbox for request/response flow (the sandbox is not a data source).
- **D3 Owner's real account:** live Dhan plus own CDSL/CAMS CAS → L1 reconciliation.
- **D4 Consenting volunteers (3–5):** written consent, session-only tokens, anonymised results only.

**Volunteer security model**
- Dhan tokens are **not read-only scoped**, as far as public docs show. Read-only is enforced by our code: an allow-listed client exposes only holdings, positions and profile, and CI fails if any order endpoint is referenced.
- The volunteer generates a 24-hour token on web.dhan.co. It is used **in memory for one sync and then discarded**, never written to disk. Owner mode uses the encrypted vault.
- Defence in depth: since 2026, Dhan order placement requires the account holder's registered static IP, so a leaked token can't place orders from an unregistered IP. We **never rely on this**.
- Pseudonymised before any LLM call; crypto-shredding of each volunteer's data after the demo; consent and deletion logged in the audit chain.

**Sponsorship routes (ranked):** (1) a pilot RIA or MFD firm as design partner, which matches the B2B plan; (2) a Dhan Partner application supported by a college letter; (3) faculty or industry mentor review for L3 expert labels.

### 1.11 Other v2 items moved to later steps
| Item | Solution location |
|---|---|
| Celery + Redis not free | §2: Postgres-native job queue |
| Render free tier sleeps and isn't India-hosted | §2: India-region free compute |
| Vector database choice (Chroma etc.) | §2: compared with pgvector |
| GitHub Actions cron delays and 60-day auto-disable | §2: database-native scheduler, with Actions only as backup |
| 7-day timeline unrealistic | §5: phased roadmap |
| Existing repo faults (leaked key, fake RAG, sector "overlap") | §5: status chart |

### Sources for §0–§1
- Upstox multi-client pause: https://community.upstox.com/t/request-for-multi-user-api-access/15433
- Dhan auth/partner: https://dhanhq.co/docs/v2/authentication/
- Empanelment net worth (NCDEX): https://teamleaseregtech.com/updates/article/50395/ncdex-issued-the-revised-eligibility-criteria-for-ctcl-ats-empanelment-vendors-algo-providers/
- AA FIPs (CDSL): https://www.cdslindia.com/Investors/FIP.html · NSDL: https://nsdl.co.in/value/Financial_Information_Provider.php · Sahamati: https://sahamati.org.in/signatories-of-aa-participation-terms/
- AA state 2026 (vendor-authored): https://casparser.in/blog/state-of-account-aggregator-2026/
- Finvu sandbox: https://finvu.github.io/sandbox/get_started.html · Setu AA: https://docs.setu.co/data/account-aggregator/quickstart
- CAMS mailback (PPFAS): https://amc.ppfas.com/distributors/cams-wbr-mail-back-services/ · KFintech distributor manual: https://mfs.kfintech.com/mfs/Distributor/Downloads/DistributorManual.pdf
- SEBI AI accountability: https://foxmandal.in/news/regulated-entities-responsible-for-output-of-ai-usage-sebi/
- CSCRF localisation: https://www.medianama.com/2025/01/223-sebi-holds-off-on-data-localisation-cscrf-framework/ · https://seconize.co/blog/faqs-on-cybersecurity-and-cyber-resilience-framework/
- Vertex AI data residency: https://cloud.google.com/vertex-ai/generative-ai/docs/learn/data-residency
- Groq data controls: https://console.groq.com/docs/your-data
- DPDP Rules: https://www.barandbench.com/view-point/meity-notifies-final-digital-personal-data-protection-rules-2025
- Wealthy.in: https://fintech.global/2025/11/24/wealthy-launches-new-ai-tools-after-rs-130-cr-14-5m-raise/

---

## 2. Technology stack (free tier, India-resident, under our control)

**Principles**
1. **Postgres is the platform.** One database provides relational data, vectors (pgvector), full-text search, the job queue and the scheduler. Fewer services means fewer places for data to leak or go out of sync.
2. **Every external service sits behind an interface** (`KeyProvider`, `VectorStore`, `LLMProvider`, `JobQueue`, `DataSourceAdapter`), so any piece can be swapped without rewrites.
3. **Real client data only on India-region infrastructure.** Overseas free tiers are used only with synthetic data.

| Layer | Decision | Why | Free-tier facts (Oct 2026) | Alternatives kept behind the interface |
|---|---|---|---|---|
| Local dev | **Docker Compose**: Postgres 17 + pgvector, OpenBao (dev mode) | Unlimited, offline, identical to production | Free | — |
| Database (hosted) | **Supabase Postgres, Mumbai region** (verify region on day 1) | Postgres + pgvector + Auth (TOTP MFA) + Storage in one | 500 MB DB, 2 active projects, **pauses after 7 days idle**, **no automatic backups on free** → nightly encrypted `pg_dump` job | Self-hosted Postgres on Oracle VM; Neon (0.5 GB, 100 CU-h; India region unconfirmed) |
| Vector search | **pgvector (HNSW) + Postgres full-text → Reciprocal Rank Fusion** | Corpus is thousands of chunks, not millions. Same database means the same RLS, backups and India residency | Included | Qdrant Cloud free (1 GB), Chroma Cloud (Starter + credits), Pinecone Starter (2 GB). **Not chosen:** a separate store adds sync, tenancy and residency problems. Qdrant is kept as a benchmark baseline in the research ablations |
| Job queue (replaces Celery + Redis) | **Procrastinate** (Python, async, Postgres-backed: retries, locks, periodic tasks) | No Redis to run; jobs are transactional with data | Free (library) | DBOS Transact (durable workflows), Supabase Queues (pgmq) + pg_cron, Hatchet (self-host free; cloud 1k runs/month). Risk: Procrastinate is seeking extra maintainers, which is why it sits behind `JobQueue` |
| Scheduler | **Procrastinate periodic tasks**; GitHub Actions only for CI-side jobs (evals, dataset refresh) | Actions cron can be delayed and is auto-disabled after 60 days of inactivity | Free | pg_cron |
| Cache / rate limit | In-process cache + Postgres-backed limits | No Redis needed at this scale | Free | Valkey container; Upstash Redis free |
| Compute (India) | **Oracle Cloud Always Free VM** (Mumbai/Hyderabad): Docker Compose + Caddy (automatic HTTPS) | Only meaningful always-free compute in an India region | **Reduced to 2 OCPU / 12 GB on 15 Jun 2026**; idle instances reclaimed (7-day low-use rule); capacity can be scarce | Render free (Singapore, sleeps after 15 min) **for synthetic demo only** |
| Frontend hosting | **Cloudflare Pages or Vercel** (static files only) | Holds no data; the browser calls the India API directly | Free | — |
| Key management | **OpenBao** (open-source Vault fork) Transit engine on the India VM; `LocalKeyProvider` in dev | Keys never sit in the app database; we hold the root | Free (self-host) | Google Cloud KMS (asia-south1, paid per key) |
| Client-side crypto | **libsodium** (`libsodium-wrappers`) in the browser | Audited, misuse-resistant primitives | Free | WebCrypto API |
| CAS parsing | **`casparser` 1.4.x** (MIT, built on pypdfium2, ships JSON Schemas) | Official schemas let us generate schema-valid synthetic data | Free | Browser-side parsing (spike S1, §2A) |
| Embeddings / reranking | **FastEmbed**: `bge-small-en-v1.5` (384-dim) + cross-encoder reranker | CPU-only, local, no data leaves the server | Free | — |
| LLM | `LLMProvider` adapter: **Ollama (local) for dev and evals** → Gemini free / Groq free (**synthetic only**) → **Vertex AI Gemini asia-south1** for production, or the tenant's own key | Development fully offline; production India-resident | Ollama free; Gemini/Groq free tiers rate-limited and change often | Groq ZDR (US) for tenants who accept it |
| Agents | **LangGraph** | Explicit graph, checkpoints in Postgres | Free | — |
| ML | (1) **Compliance classifier** (embeddings + logistic regression) as a fast first-pass guard; (2) cross-encoder reranker for RAG; (3) later: learning-to-rank from advisor accept/dismiss decisions | Measurable, cheap, explainable | Free | — |
| LLM tracing | **OpenTelemetry → Arize Phoenix (self-hosted)** | Traces include prompts, so we keep them on our own server | Free self-host | Langfuse cloud Hobby (50k units) **for synthetic data only** |
| Backend | Python 3.12, **uv**, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic, httpx + tenacity | Same as v2 | Free | — |
| Frontend | React + Vite + TypeScript, TanStack Router/Query/Table, Tailwind + shadcn/ui, Recharts, react-hook-form + zod | Detailed in §4 | Free | — |
| Quality gates | ruff, mypy, pytest, hypothesis, respx, Playwright, vitest, gitleaks, pip-audit, Semgrep, import-linter, Dependabot | — | Free on GitHub | — |

> **Cost honesty:** ₹0 covers development, CI, demos and synthetic-data pilots. A production pilot with a real firm's client data needs India-resident compute and LLM. The Oracle free VM covers compute; the LLM needs Vertex (low cost for Flash) or the tenant's own key. Cloud startup-credit programmes can cover this.

---

## 2A. Zero-access privacy architecture ("even we can't see it")

**Goal:** developers, database administrators and the hosting provider **cannot read who a client is**, and cannot read financial data at rest. Plaintext exists only where it is needed (the advisor's browser, or a worker's memory during a computation), and never in logs.

### Two vaults
| Vault | Contains | Encrypted with | Who can decrypt |
|---|---|---|---|
| **Identity Vault** (zero-knowledge) | Client name, PAN, DOB, email, phone, notes | **Firm Key**, generated **in the advisor's browser** at firm signup | **Only firm users' browsers.** The server never has the key |
| **Portfolio Store** (pseudonymous) | Holdings, transactions and snapshots, keyed by a random `client_id` (e.g. `c_7f3a…`) | **Per-tenant data key** (envelope encryption: data key wrapped by a key held in OpenBao) | Workers, in memory only, during a job |

### How the Firm Key works (same model as password managers)
1. At signup the browser creates the **Firm Key** and the user's **key pair**. The user's private key is encrypted with a key derived from their password (Argon2id).
2. The Firm Key is "wrapped" (encrypted) to each team member's public key. Adding a teammate means wrapping it to their key too. Removing them means rotating the Firm Key.
3. A **Recovery Kit** (printable recovery key) is shown once. If every user loses access *and* the kit is lost, the identities are unrecoverable. That is the price of zero-knowledge, and it is stated clearly in onboarding.

### Matching without seeing (blind index)
The browser computes `HMAC(Firm Key, PAN)` and sends only that tag. The server matches statements to clients by tag and never sees the PAN.

### Where each piece of data is processed
| Flow | Design |
|---|---|
| **CAS upload** | **Target (spike S1):** parse in the browser (casparser-web / Pyodide / pdf.js), send only pseudonymised holdings plus the PAN tag. **Fallback:** server parses in an isolated worker, **in memory only, never written to disk**; name/PAN/address stripped immediately; the PDF bytes are discarded after parsing |
| **Dhan sync** | Server-side call (broker APIs don't allow browser calls). Holdings contain no identity (ISIN, quantity, price). We **never call the profile endpoint** |
| **LLM** | Receives only `client_id`-level, already pseudonymous findings. The server has no names to leak |
| **Reports and PDFs** | Server returns findings with `{{CLIENT}}` placeholders. The **browser fills in names and renders the PDF** |
| **Client search by name** | Done in the browser on the decrypted list |
| **Consent links** | Generated by the server; the **advisor sends them** (copy link / WhatsApp / email client), so the server never needs the client's contact details |

### Operator controls ("max control stays with us")
- We hold the **root of trust**: OpenBao root and unseal keys are split between the owner and a sealed offline backup.
- **No standing production access.** Break-glass access is time-limited, requires a stated reason, and is written to the audit chain.
- Logging redaction filter, plus tests asserting that no PAN-like or token-like strings appear in logs.
- **Crypto-shredding:** deleting a tenant's data key erases the tenant; deleting a client's records and identity entry erases the client.

### Honest limits (stated in the Trust Pack)
- **Pseudonymous is not anonymous.** A unique portfolio could in theory re-identify someone, so the Portfolio Store is still treated as personal data under DPDP.
- **Web end-to-end encryption trusts the JavaScript we serve.** A malicious deploy could steal keys. Mitigations: content security policy, Subresource Integrity, signed and reviewed releases, two-person deploy approval.
- **Workers see plaintext holdings in memory while computing.** Hardware enclaves (confidential computing) are a paid, later option.

---

## 2B. Development data: no real person needed

| ID | Dataset | Source | Use |
|---|---|---|---|
| D1 | Scheme master + daily NAV (with ISIN) | AMFI `NAVAll.txt`; `api.mfapi.in` (full history); Kaggle "India Mutual Fund 2006–2026" (AMFI-derived) | Valuation, persona generation |
| D2 | Fund constituents (look-through) | AMC monthly portfolio Excel files, top AMCs first (captn3m0/mf-portfolio as reference; check its licence) | Look-through and overlap ground truth |
| D3 | Equity prices + ISIN master | NSE bhavcopy + `EQUITY_L.csv`; `casparser-isin` database | Direct-equity personas |
| D4 | **Synthetic personas** (our generator, seeded, about 10 to start, 200+ for the benchmark) | Built on D1–D3, with **planted issues + gold labels** | L3 agent evaluation (recall and precision) |
| D5 | **Synthetic CAS JSON** | Generated from personas, **validated against casparser's published JSON Schemas** | Ingestion and merge tests without PDFs |
| D6 | **Synthetic Dhan API fixtures** | Built from documented response fields (`isin`, `totalQty`, `avgCostPrice`, …) | Adapter contract tests (respx) |
| D7 | RAG corpus | SEBI MF Master Circular, SEBI IA Regulations + FAQs (Aug 2025), AMFI investor material, **Income-tax Act 2025 + Income-tax Rules 2026** (incometaxindia.gov.in) | Retrieval and citations |
| D8 | Eval sets | RAG golden Q→passage set; compliance red-team prompts (hand-written + LLM-generated, human-reviewed); gold findings from D4 | Nightly evals, paper |
| D9 | Owner's own data (optional, later) | Own Dhan account + own CAS | L1 live reconciliation demo |

---

## 3. Architecture and multi-tenant data model

### 3.1 Runtime components
```
┌──────────────────────── Advisor's browser (trusted for identity) ────────────────────────┐
│ React SPA · Crypto worker (libsodium: Firm Key, Identity Vault, PAN blind index)         │
│ CAS parser (spike S1: Pyodide/pdf.js) · Report renderer (fills {{CLIENT}}, builds PDF)    │
└───────────────┬──────────────────────────────────────────────────────────────────────────┘
                │ HTTPS · JWT (Supabase Auth, TOTP MFA) · only pseudonymous data + ciphertext
┌───────────────▼───────────────── India region ───────────────────────────────────────────┐
│ API (FastAPI)            Worker (Procrastinate)                 OpenBao (Transit KEKs)     │
│  auth · RBAC · tenancy    ingest · reconcile · compute ·          ▲ wrap/unwrap tenant keys │
│  REST /v1 · MCP (r/o)     agents · marketdata · rag · evals ──────┘                         │
│        │                         │                                                         │
│        └──────────┬──────────────┘                                                         │
│                   ▼                                                                         │
│   Postgres 17: tenant data (RLS) · market data · KB + pgvector + FTS · job queue · audit   │
│   Phoenix (OpenTelemetry traces, self-hosted)                                               │
└──────────┬─────────────────────────────┬──────────────────────────────────────────────────┘
           ▼                             ▼
   Broker APIs (Dhan, read-only)   LLM provider (Ollama dev · Vertex asia-south1 prod · tenant key)
```

### 3.2 Backend package layout and dependency rules
```
aicfo/
  api/          thin HTTP routers (/v1): validation → service call → response
  auth/         JWT verification, roles (owner/advisor/analyst/viewer), permission checks
  tenancy/      request/job tenant context; sets Postgres `app.tenant_id` per transaction
  crypto/       ✅ envelope encryption (TenantCipher, KeyProvider, rotation)
  security/     ✅ log redaction; rate limits; CSP/SRI helpers
  domain/       Pydantic contracts: NormalisedHolding, NormalisedTxn, Lot, Snapshot, Finding, Evidence
  sources/      DataSourceAdapter + cas · dhan · tradebook · rta · synthetic
  reconcile/    merge engine → snapshots + exceptions
  marketdata/   amfi_nav · mfapi · nse · amc_disclosures (one parser plugin per AMC)
  core/         PURE functions: lookthrough · overlap · drift · lots(FIFO) · tax/rulesets/fy2026_27
  rag/          ingest · chunk · embed · hybrid search (pgvector + FTS → RRF) · rerank
  agents/       LangGraph graphs · analysts · explainer · compliance · verifier · copilot · tools
  llm/          LLMProvider adapters (ollama, gemini, groq, vertex, fake) · pseudonymisation gateway
  ml/           compliance classifier (train/infer) · later: learning-to-rank
  audit/        hash-chained, append-only log (IDs and hashes only)
  jobs/         Procrastinate tasks and schedules
  db/           SQLAlchemy models, sessions, Alembic migrations
  evals/        L1 ingestion · L2 maths · L3 agents (datasets D4–D8)
  mcp/          read-only MCP tools over the same services
```
**Rules (checked in CI with import-linter):**
- `core` imports nothing from I/O layers. It is pure and deterministic.
- `agents` get numbers only through tools that call `core`.
- `api` never touches `db` models directly; it goes through services.
- Only `llm/` talks to model providers, and only through the pseudonymisation gateway.

### 3.3 Tenant isolation: request and job lifecycle
1. The browser sends `Authorization: Bearer <JWT>`. The API verifies its signature, expiry and MFA claim, then loads `user_id`, `tenant_id` and `role`.
2. Each request runs in one database transaction that begins with `SET LOCAL app.tenant_id = '<uuid>'`.
3. Every tenant table has an **RLS policy**: `tenant_id = current_setting('app.tenant_id')::uuid`. The application's database role is **not** the table owner and has **no BYPASSRLS**.
4. Workers set the same variable from the job payload. A job with no tenant can only touch global tables (market data, knowledge base).
5. A test suite runs every repository query as tenant A against tenant B's rows and **must get zero rows**.

### 3.4 Data model
Column protection: **P** plain · **E** envelope-encrypted by the server (tenant data key) · **Z** zero-knowledge, encrypted in the browser with the Firm Key · **H** keyed hash or blind index (no plaintext)

**Tenancy and people**
| Table | Key columns (protection) |
|---|---|
| `tenants` | id, display_name P, firm_type P (RIA/MFD/BROKER_WL), compliance_profile P, data_region P, `wrapped_data_key` P (ciphertext), ai_enabled P, llm_mode P, created_at |
| `users` | id (= auth uid), tenant_id, role P, status P, public_key P, `wrapped_private_key` Z, `wrapped_firm_key` Z, mfa_enrolled P |
| `clients` | id (random), tenant_id, advisor_id, **`pan_tag` H**, **`identity_blob` Z** (name, PAN, DOB, contacts, notes), risk_category P, model_portfolio_id, status |
| `consents` | id, tenant_id, client_id, purpose P, scopes P, sources P, granted_at, expires_at, withdrawn_at, captured_by, evidence_hash H |
| `model_portfolios` | id, tenant_id, name P, targets P (asset-class weights) |

**Ingestion and portfolio** (financial amounts are E; identifiers are H; ISIN and dates stay P because they are needed for joins with public market data)
| Table | Key columns (protection) |
|---|---|
| `data_connections` | id, tenant_id, client_id, source P, mode P (owner_vault/session), status P, `token` E (owner mode only), token_expires_at, last_sync_at |
| `ingestion_runs` | id, tenant_id, client_id, source P, parser_version P, status P, checks P (totals matched?), records P, error_code P |
| `accounts` | id, tenant_id, client_id, **`account_ref_tag` H** (BO ID or folio), kind P (demat/folio), institution P |
| `snapshots` | id, tenant_id, client_id, as_of P, coverage P (by source, freshness, look-through %), engine_version P |
| `positions` | id, tenant_id, snapshot_id, account_id, isin P, asset_class P, units E, avg_cost E, value E, source P, source_as_of P, confidence P |
| `lots` | id, tenant_id, account_id, isin P, acquired_on P, units E, cost E, verified P |
| `transactions` | id, tenant_id, account_id, isin P, txn_date P, type P, units E, amount E, source P, dedupe_hash H |
| `recon_exceptions` | id, tenant_id, client_id, snapshot_id, kind P, details E, status P, resolved_by |

**Analytics, AI and review**
| Table | Key columns (protection) |
|---|---|
| `computations` | id, tenant_id, snapshot_id, kind P (lookthrough/overlap/drift/tax), inputs_hash H, result E, engine_version P, ruleset_version P |
| `evidence` | id, tenant_id, computation_id, path P (e.g. `overlap.pairs[2].pct`), value E, formula_ref P |
| `findings` | id, tenant_id, client_id, run_id, kind P, severity P, impact_inr E, text_template E (with `{{CLIENT}}`), evidence_ids P, citations P (kb_chunk ids), compliance P (rule/classifier/judge results), status P |
| `reviews` | id, tenant_id, client_id, version, status P (draft/approved/sent), approved_by, approved_at |
| `decisions` | id, tenant_id, finding_id, user_id, action P (accept/dismiss/snooze/edit), reason E, snooze_until |
| `agent_runs` | id, tenant_id, graph P, model P, tokens P, latency_ms P, cost P, trace_id P, outcome P |
| `chat_messages` | id, tenant_id, thread_id, role P, content E, tool_calls E |

**Global (public data, no tenant, no RLS)**
| Table | Key columns |
|---|---|
| `securities` | isin PK, name, kind (equity/MF/ETF/bond/SGB), amfi_code, sector, active |
| `nav_history` / `price_history` | isin, date, nav or close, source |
| `fund_portfolios` | scheme_isin, month, security_isin, weight, source_url, fetched_at, validation_status |
| `kb_documents` | id, issuer (SEBI/AMFI/CBDT), title, url, version, effective_from/to, sha256, fetched_at |
| `kb_chunks` | id, document_id, ord, section_ref, text, `embedding vector(384)` (HNSW), `tsv tsvector` (GIN) |

**Audit** (append-only; UPDATE/DELETE revoked for the application role)
`audit_log`: seq, tenant_id, at, actor_id, action, object_type, object_id, details_hash, prev_hash, hash. **No personal data ever.**

**Erasure:**
- **Client erasure:** delete `identity_blob` and every row keyed by `client_id`, then write an audit entry.
- **Tenant erasure:** destroy `wrapped_data_key` (crypto-shredding), then purge rows.

### 3.5 Main flows
**A. CAS ingestion**
1. Consent check.
2. Browser parses the PDF (S1), or uploads it to the fallback worker (memory only).
3. Identity fields are dropped. The PAN becomes `pan_tag`; folio and BO IDs become `account_ref_tag`.
4. Normalised records go to `ingestion_runs`.
5. Checks run: parsed total equals the statement total, and `pan_tag` matches the client.
6. Reconcile, write a `snapshot`, and log to audit.

**B. Dhan sync**
1. Consent flow, then a token.
2. Allow-listed client: holdings and positions only.
3. Normalise, then reconcile.
4. The token is discarded (session mode) or stored E (owner mode). Expired tokens show a "Reconnect" state; there is never an automated re-login.

**C. Review run** (weekly schedule or on demand)
1. Load the latest snapshot.
2. `core` computations, saved as `computations` + `evidence`.
3. LangGraph runs: three analysts → rank → explainer (RAG) → rules → classifier → LLM judge → verifier.
4. Draft `findings` → advisor's review inbox.

**D. Approval and report**
1. The advisor edits, accepts or dismisses findings (`decisions`).
2. Approve creates a `reviews` version.
3. The browser decrypts identity, fills in `{{CLIENT}}`, renders the branded PDF, and the advisor sends it.

**E. Erasure:** as in §3.4. The audit chain stays verifiable.

### 3.6 Agent contracts (from the 6-agent design)
- **Analyst input:** `computations` for one snapshot plus the client's risk category and targets. No identity.
- **Analyst output (Pydantic):** `[{kind, claim_template, evidence_ids[], severity_hint, rationale}]`
- **Explainer output:** `[{finding_id, text_template, citations[kb_chunk_id]}]`
- **Verifier** (deterministic) rejects text when:
  - any number in it is not one of the referenced evidence values (after formatting rules);
  - any citation does not resolve to a chunk;
  - `{{CLIENT}}` placeholders are malformed.

  It allows up to 2 rewrites, then drops the finding and logs it.
- **Compliance:** rules (regex/lexicon per profile) → ML classifier (probability of advice) → LLM judge (only if uncertain).
- **Copilot tools** (read-only, tenant-scoped): `get_snapshot_summary`, `get_holdings`, `get_overlap(a,b)`, `get_drift`, `get_tax_position(fy)`, `search_rules(q)`, `get_connection_status`.

### 3.7 API surface (`/v1`, all tenant-scoped; roles in brackets)
- **auth/session:** `GET /me`
- **tenant:** `GET|PATCH /tenant`, `POST /tenant/ai-kill-switch` [owner]
- **team:** `GET|POST /users`, `PATCH /users/{id}` [owner]
- **clients:** `GET|POST /clients`, `GET|PATCH /clients/{id}`, `DELETE /clients/{id}` (erasure) [advisor]
- **consents:** `POST /clients/{id}/consent-requests`, `POST /consents/{token}/accept` (public, OTP)
- **ingest:** `POST /clients/{id}/ingest/cas` (pseudonymised records or fallback file), `POST /clients/{id}/ingest/tradebook`
- **connections:** `POST /clients/{id}/connections/dhan/start`, `GET /connections/dhan/callback`, `DELETE /connections/{id}`
- **portfolio:** `GET /clients/{id}/snapshots/latest`, `GET /clients/{id}/exceptions`
- **analysis:** `POST /clients/{id}/reviews/run`, `GET /reviews/{id}`, `GET /findings/{id}/explain`
- **decisions:** `POST /findings/{id}/decision`, `POST /reviews/{id}/approve` [advisor; analysts cannot approve]
- **chat:** `POST /clients/{id}/chat`
- **audit:** `GET /audit?from&to`, `GET /audit/verify` [owner/viewer]

### 3.8 Background jobs
| Job | Trigger |
|---|---|
| `ingest.parse_cas`, `ingest.sync_dhan`, `ingest.parse_tradebook` | On upload or connect |
| `reconcile.build_snapshot` → `compute.run_core` | After ingestion |
| `agents.review_run` | Weekly per client, or on demand |
| `marketdata.amfi_nav` | Daily |
| `marketdata.amc_disclosures` | Monthly (around the 12th) |
| `rag.ingest_corpus` | Manual or monthly; versioned |
| `evals.nightly` | Daily (synthetic data only) |
| `ops.backup` | Nightly encrypted dump |
| `ops.retention` | Daily: expire consents, purge per policy |

### 3.9 Reproducibility and quality attributes
- **Reproducibility:** every snapshot, computation and finding stores `engine_version`, `ruleset_version`, `parser_version`, model ID and prompt version, so any number shown can be regenerated exactly.
- **Performance targets:** snapshot + core compute < 2 s for 50 holdings; review run < 60 s; API p95 < 300 ms (excluding LLM).
- **Failure handling:** idempotent jobs (dedupe keys), retries with backoff, and a dead-letter state shown in an ops view.

---

## 4. UI/UX structure

### 4.1 Design principles
1. **Trust is visible.** Every number shows its source and as-of date, and **every number is clickable** to open the explanation drawer (formula, inputs, rule cited, versions).
2. **Calm, dense, professional.** This is a working tool for advisors, like a modern banking or analytics console: information-rich tables, restrained colour, no decoration.
3. **The advisor stays in control.** AI output is always labelled *Draft*. Nothing goes out without an explicit **Approve**.
4. **Never wait on AI.** Data and maths render first; AI drafts stream in with skeletons; jobs show live progress.
5. **Keyboard-first, mobile-capable.** Power users fly with `Ctrl+K` and shortcuts; approvals and the inbox work comfortably on a phone.
6. **Indian conventions.** ₹ with lakh/crore grouping (`Intl.NumberFormat('en-IN')`), FY April–March, DD MMM YYYY dates.
7. **Accessible by default:** WCAG 2.2 AA.

### 4.2 Users and their main jobs
| Persona | Main jobs | Main screens |
|---|---|---|
| **Advisor** | Review and approve findings, talk to clients, ask the copilot | Today, Review inbox, Client 360, Copilot |
| **Analyst / assistant** | Upload statements, resolve data exceptions, prepare drafts (cannot approve) | Data inbox, Clients |
| **Owner** | Team, branding, compliance profile, AI kill switch, model portfolios | Settings, Audit |
| **Auditor / compliance** | Read-only audit trail and decisions | Audit, Reports |
| **Client (no login)** | Give consent, receive the report | Consent page (mobile-first), report PDF |

### 4.3 Navigation (information architecture)
```
Top bar:  [Firm logo]  [Ctrl+K search / command]   [AI: On ● ]  [Jobs ⟳ 2]  [🔔]  [User ▾ · Lock vault]
Sidebar:  Today · Clients · Review inbox (badge) · Data inbox (badge) · Reports · Copilot · Knowledge · Audit · Settings
```
- **Command palette (`Ctrl+K`):** jump to any client (names are searched *in the browser* after decryption), run actions ("Run review for…", "Upload CAS for…"), open settings.
- **AI status pill:** shows On/Off (kill switch) and the provider mode (Local / India-hosted / Tenant key).
- **Lock vault:** clears decrypted identities from memory. Auto-locks after idle time.

### 4.4 Screens
**Access**
| Screen | Contents |
|---|---|
| Sign in → MFA | Email + password, then a 6-digit TOTP code; "trust this device" is *not* offered |
| Unlock vault | Shown after sign-in on a new session. Derives the key from the password; explains in one line why ("only your browser can read client names") |
| Onboarding wizard | 1 Firm profile + registration no. → 2 Compliance profile → 3 **Recovery Kit** (download/print, confirm saved) → 4 Invite team → 5 Model portfolios → 6 Start with demo data or the first client |

**Work**
| Screen | Layout and key components |
|---|---|
| **Today** (home) | KPI tiles: pending approvals, clients due for review, data freshness, open exceptions. Queues: "Ready to review", "Needs data", "Lots turning long-term in 30 days", "Reconnect Dhan" |
| **Clients** | Virtualised data table: name (decrypted locally), risk, portfolio band, last review, freshness, open findings, coverage %. Filters, saved views, bulk "Run review". Cards on mobile |
| **Client 360** | Header: name, risk, target model, **coverage meter**, source badges with as-of dates, Run review. Tabs listed below |
| ↳ Overview | Allocation vs target (donut + diverging drift bars in % and ₹), top 10 underlying exposures, open findings |
| ↳ Holdings | Grouped by account and source; source badge per row; row opens a lot drawer (acquired date, units, cost, "unverified" flags) |
| ↳ Look-through | Treemap of true company/sector exposure across all funds + direct shares; disclosure month and look-through % shown |
| ↳ Overlap | Heatmap matrix of fund pairs; click a cell to list the common holdings with both weights |
| ↳ Tax | FY timeline of lots crossing 12 months; ₹1.25 L LTCG exemption gauge (used/remaining); realised vs unrealised; ruleset version shown |
| ↳ Findings | Finding cards (draft/approved/dismissed history) |
| ↳ Data | Connections (Dhan status, expiry, Reconnect), uploads, reconciliation exceptions |
| ↳ Timeline | Client-scoped audit and activity feed |
| **Review inbox** | Three-pane: client list → findings for that client → finding detail. Finding card: plain-language text with **numbers highlighted (click → explain)**, citation chips, compliance badge (passed rules/classifier/judge), actions **Accept · Edit · Dismiss (reason) · Snooze**. Sticky footer: "3 accepted · 1 edited · Preview report · **Approve**" |
| **Explain drawer** (everywhere) | Result → formula in words and symbols → inputs table (value, source, as-of) → step-by-step calculation → rule citation (excerpt + link + version) → versions (engine, ruleset, parser, model, prompt) → "Copy as audit note" |
| **Data inbox** | Live ingestion jobs; **exception resolver**: side-by-side values from each source, pick or annotate, everything logged; connection health |
| **Copilot** | Right-side panel opened on any screen, aware of the current client. Shows which tools it used ("used get_overlap"), cites rules, displays the compliance notice; answers can be pinned to a review as a draft finding |
| **Reports** | Approved reviews; branded preview; PDF rendered in the browser; send log |
| **Knowledge** | Searchable SEBI/AMFI/Income-tax library with document versions and effective dates |
| **Audit** | Filterable log; **Verify chain** button with result and checked range; export |
| **Settings** | Firm & branding · Team & roles · Model portfolios · Compliance profile · AI (kill switch, provider mode, own key) · Security (MFA, sessions, recovery kit rotation) · Data & privacy (retention, export, erasure with type-to-confirm) · Connections |

**Client-facing**
| Screen | Contents |
|---|---|
| Consent page | Mobile-first, plain language: what, from where, why, how long, how to withdraw → OTP → done |
| Report | Firm-branded PDF/web view: summary, findings, charts, sources, disclaimer |

**Demo mode:** a permanent "Demo data, not real people" banner; a guided tour of 6 steps; reset button.

### 4.5 Interaction patterns
- **Shortcuts in the review inbox:** `J`/`K` next/previous, `A` accept, `E` explain, `D` dismiss, `S` snooze, `Ctrl+Enter` approve. `?` shows all shortcuts.
- **Optimistic updates with undo:** "Dismissed · Undo" toast instead of confirmation dialogs. Destructive actions (erasure, disconnect) use type-to-confirm.
- **Live progress:** server-sent events for jobs ("Parsing CAS… 3/5 checks passed").
- **Empty states always offer the next action** ("No data yet: Upload CAS · Connect Dhan · Use demo data").
- **Skeletons, not spinners;** charts reserve their space so pages don't jump.
- **Inline validation** with zod schemas shared with the API types.

### 4.6 Data visualisation rules
- One colour-blind-safe palette with semantic meaning (over target / under target / neutral), identical in light and dark themes.
- Every chart shows its unit, as-of date and source, and has a **table view toggle** for accessibility and exact values.
- Chart types:
  - **diverging bars** for drift;
  - **heatmap** for overlap;
  - **treemap** for look-through;
  - **timeline** for lots;
  - **gauge** for the exemption;
  - **donut** only for allocation.
- Tabular numerals (`font-variant-numeric: tabular-nums`) everywhere numbers align.

### 4.7 Responsive behaviour
| Width | Layout |
|---|---|
| ≥ 1280 px | Sidebar + list + detail (three panes); copilot as a side panel |
| 768–1279 px | Collapsible sidebar; two panes; copilot as an overlay sheet |
| < 768 px | Single pane; bottom nav (Today · Inbox · Clients · Copilot); tables become cards; review actions as large buttons |

### 4.8 Design system
- **Components:** shadcn/ui (Radix primitives) + Tailwind CSS v4 design tokens; lucide icons.
- **Tokens:**
  - neutral slate base + one brand accent (overridable per tenant for branding);
  - semantic success/warning/danger/info;
  - 4-px spacing scale, 8-px radius, two elevation levels.
- **Type:** Inter (UI) with tabular numerals; JetBrains Mono for IDs and audit hashes.
- **Motion:** subtle (150–200 ms), respects `prefers-reduced-motion`.
- **Themes:** light and dark, system default.

### 4.9 Frontend architecture
- **Build and language:** Vite + React + TypeScript (strict).
- **Routing and data:**
  - **TanStack Router:** type-safe routes, loaders;
  - **TanStack Query:** server cache, optimistic updates;
  - **TanStack Table + Virtual:** large tables.
- **State and forms:** Zustand for UI state; react-hook-form + zod.
- **Charts:** Recharts for standard charts; visx for the heatmap and treemap.
- **Crypto:** libsodium in a **Web Worker**. Decrypted identities live only in that worker's memory and are wiped on lock or idle.
- **API types:** generated from the FastAPI OpenAPI schema (no hand-written drift).
- **Security on the page:**
  - strict CSP (no inline scripts);
  - Subresource Integrity;
  - Trusted Types;
  - **no third-party scripts or analytics on authenticated pages**.
- **Testing:**
  - Vitest + Testing Library;
  - Playwright end-to-end with **axe accessibility checks**;
  - Playwright screenshot tests for key screens;
  - component catalogue (Ladle or Storybook).

### 4.10 Budgets
- **Bundle:** app shell < 250 KB gzipped; route-level code splitting.
- **Speed:** LCP < 2.5 s on 4G; interactions < 100 ms.
- **Accessibility:** 0 axe violations (serious or critical) in CI.

---

## 5. Status checklist (living document)

Legend: ✅ done · 🔄 in progress · ⬜ to do · ♻️ needs update (exists, but must change) · Priority **P0** (blocking) → **P3** (later)

### 5.1 Planning and research
| Item | State | Pri |
|---|---|---|
| v2 feasibility review with sources | ✅ | — |
| B2B pivot and blocker → solution map (§0–§1) | ✅ | — |
| Validation framework L1/L2/L3 (§1.10) | ✅ | — |
| Stack, zero-access design, data plan (§2, §2A, §2B) | ✅ | — |
| §3 Architecture + data model | ✅ | — |
| §4 UI/UX structure | ✅ | — |
| Clickable UI prototype (to validate §4 before coding the frontend) | ✅ built as the real frontend + shareable preview | — |
| Verify the 80C→s.123 and capital-gains section mapping against the official Act text | ⬜ | P0 (before tax engine) |
| Verify Supabase Mumbai region, pgmq/cron on free tier, Oracle India capacity | ⬜ | P0 (day 1) |

### 5.2 Old v1 repo (`AI-CFO-India`: public repo **deleted 16 Oct 2026**; local mirror backup at `~/AI-CFO-India-backup.git`)
| Item | State | Pri |
|---|---|---|
| Rotate the leaked encryption key and purge it from git history | ♻️ | **P0** — do it even if v1 is abandoned |
| Fake RAG (SHA-256 word hashes) | ♻️ → replaced by §2 RAG | — |
| Sector-field "overlap" | ♻️ → replaced by look-through overlap | — |
| Docs contradict code | ♻️ → new repo has a docs-match-code check | — |

### 5.3 Build phases (new repo)
| Phase | Deliverables | State | Pri |
|---|---|---|---|
| **0 Foundation** | ✅ repo, licence, CI (lint, type, test, pip-audit, gitleaks, Semgrep, Dependabot), CLAUDE.md, ADR-0001…0004, Docker Compose (Postgres+pgvector, OpenBao), config, `/health`, **envelope crypto + log redaction + read-only guard (28 tests)** · ⬜ push to GitHub, branch protection, Alembic baseline | 🔄 | P0 |
| **1 Data** | AMFI/mfapi loaders, ISIN master, 2–3 AMC disclosure parsers + validation, persona generator (D4), synthetic CAS JSON (D5), Dhan fixtures (D6), normalised model, **reconciliation engine** (property tests) | ⬜ | P0 |
| **2 Core maths** | ✅ Python core: positions, lots, allocation, drift, look-through, overlap, tax position, Evidence records; hand-checked + invariant tests · ⬜ FIFO from real transaction history, FY rule-set module, grandfathering | 🔄 | P0 |
| **3 Privacy** | Identity Vault (browser), blind index, OpenBao provider, crypto-shredding, log-redaction tests, spike S1 (browser CAS parse) | ⬜ | P0 |
| **4 RAG** | ✅ 9-document KB (summaries + official links), sentence-aware chunking, BM25 (Snowball) + dense (bge-small via FastEmbed or hashing fallback) + RRF, IDF relevance gate, extractive + LLM answers with citation/number verifier, compliance guard, PII redaction, API `/v1/rag/*`, CLI, 28-question golden eval (hit@3 = 1.00 in all modes), RAG tests; browser port in console · ⬜ pgvector store, reranker, larger and harder corpus, per-tenant documents | 🔄 | P1 |
| **5 Agents + ML** | ✅ LangGraph review graph (3 parallel analysts, rank, RAG explainer, compliance rules→ML→LLM judge, verifier), trace per node, decision memory, RIA/MFD profiles, LLM paths validated + fallback to firm policy; Copilot tool-using agent; ML advice classifier (CV F1 0.89); Python deterministic core; API + CLI + export; 101 backend tests · ⬜ pseudonymisation gateway for real data, LLM eval suite with a live model, larger labelled set | 🔄 | P1 |
| **6 Live connector** | Dhan adapter (owner vault mode + session-only mode), read-only allow-list + CI guard | ⬜ | P1 |
| **7 Frontend** | ✅ console (mint/sky design language), sign-in with TOTP step, roles + adviser-scoped data, Team (invite, roles, suspend, sessions), Client access (requests, consents, client shares), client portal (approve/decline with OTP, share with CA, revoke, activity), Ask the rulebook (RAG), Copilot with RAG · ⬜ real auth (Supabase) + API wiring, route code-splitting, Playwright e2e + axe in CI | 🔄 | P1 |
| **8 Deploy** | Oracle India VM + Supabase Mumbai, Caddy, backups, Phoenix tracing, Trust Pack | ⬜ | P2 |
| **9 Research** | 200+ persona benchmark, ablations (single vs multi-agent, ±verifier, ±RAG, several LLMs), expert labels, paper draft | ⬜ | P2 |
| **10 B2B growth** | Email ingest, RTA feed parsers, AA sandbox adapter, Dhan Partner application, pilot firm | ⬜ | P3 |

**Realistic timeline (solo + Claude Code):** phases 0–2 ≈ 2–3 weeks · 3–6 ≈ 3–4 weeks · 7–8 ≈ 2–3 weeks · research track runs in parallel from phase 5. **About 8–12 weeks total.**

### Sources for §2–§2B
- Oracle free-tier cut: https://infoq.com/news/2026/07/oracle-cloud-free-tier-limits/ · Oracle Always Free docs: https://docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm
- Supabase free limits: https://automationatlas.io/answers/supabase-free-tier-limits-2026/ · Neon pricing: https://neon.com/pricing
- Vector DB pricing: https://agentdeals.dev/vector-database-pricing
- Procrastinate: https://procrastinate.readthedocs.io · Hatchet review: https://automationatlas.io/answers/hatchet-review-2026/
- casparser: https://github.com/codereverser/casparser · Kaggle India MF 2006–2026: https://www.kaggle.com/datasets/darshshah1010/india-mutual-fund-20062026 · mf-portfolio: https://git.captnemo.in/github.com/captn3m0/mf-portfolio.git/commit · AMFI NAV: https://www.amfiindia.com/net-asset-value/nav-download
- Income-tax Act 2025: https://www.incometaxindia.gov.in/income-tax-act-2025 · Rules 2026: https://www.incometaxindia.gov.in/w/rule-1-104
- Envelope encryption / tenant keys: https://workos.com/blog/envelope-encryption-explained · https://workos.com/blog/cryptographic-key-isolation-multi-tenant-saas
