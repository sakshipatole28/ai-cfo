# AI CFO

**Portfolio intelligence for Indian wealth professionals.** AI CFO ingests every client's holdings from statements and data feeds, computes look-through overlap, allocation drift and capital-gains position deterministically, and drafts cited, compliance-checked review notes that the advisor approves before anything reaches a client.

> Every number computed. Every claim cited. Every action audited. The advisor always in control.

**Status:** working demo on synthetic data; not production-ready for real client data. See [EXPLANATION.md](EXPLANATION.md) for the system diagram and workflow, the [plan](docs/plan/03_AI_CFO_V3_B2B.md) and the [status checklist](docs/plan/03_AI_CFO_V3_B2B.md#5-status-checklist-living-document).

---

## Why
Indian investors hold money across brokers, mutual fund houses and apps. Reviewing one client properly (true exposure, fund overlap, drift from the agreed risk level, tax lots about to turn long-term) takes an advisor hours. AI CFO turns that into minutes, without letting an AI invent numbers.

## How it works
```
Data in                     Exact maths (tested code)      AI (explains, never computes)     Human
────────                    ─────────────────────────      ─────────────────────────────     ─────
CAS (NSDL/CDSL/CAMS/KFin) ┐  look-through exposure          3 analyst agents select findings  advisor
Dhan live (read-only)     ├▶ fund overlap            ────▶  explainer (RAG, cited)    ────▶  reviews,
Distributor feeds         │  allocation drift              compliance (rules→ML→LLM judge)   approves
Tradebook files           ┘  FIFO lots + FY tax rules       verifier: no unsupported numbers  → client
                                    │                                  │
                              Postgres (snapshots, findings, hash-chained audit)   n8n (weekly sweep, notifications)
```
Full diagrams (components, sequence, CI/CD): **[EXPLANATION.md](EXPLANATION.md)**.

## Architecture

![AI CFO system architecture](docs/architecture.png)

Every box is a part of this repository or a service it deploys to. Arrows show the direction of requests and data. Read it top to bottom: people and GitHub at the top, the hosted console (Netlify) and API (Render) in the middle, the database and automation below, and the AI providers at the bottom.

<details>
<summary>Editable source (Mermaid; also in <code>docs/architecture.mmd</code>)</summary>

```mermaid
flowchart TB
  adv(["Advisor, Owner, Admin, Employee<br/>(browser)"])
  cli(["Client portal<br/>(demo)"])

  subgraph gh["GitHub"]
    repo["main and feature branches"]
    ci["CI: lint, types, all tests,<br/>Postgres, browser test, Semgrep, gitleaks"]
    cd["Deploy: API first, then console,<br/>only after CI passes on main"]
  end

  subgraph netlify["Netlify"]
    console["Advisor console<br/>React 19 + Vite, static"]
  end

  subgraph render["Render (Docker)"]
    subgraph api["FastAPI  /v1"]
      auth["Accounts and roles<br/>scrypt password, TOTP, session token"]
      routes["Routes<br/>clients, reviews, approvals,<br/>pipeline, audit, rulebook, copilot"]
      pipe["Data pipeline<br/>book to core to database, idempotent"]
      core["Deterministic core<br/>positions, drift, overlap, tax lots"]
      review["LangGraph review<br/>3 analysts in parallel, rank,<br/>explainer, compliance, verifier"]
      copilot["Copilot agent<br/>tools and rulebook"]
      rag["RAG over the rulebook (data/kb)<br/>BM25 + embeddings + RRF,<br/>cited and verified answers"]
      llm["LLM layer (LangChain)<br/>Groq, with Gemini as fallback"]
      events["Signed events<br/>HMAC-SHA256"]
    end
  end

  subgraph db["Postgres 17 (Supabase, Neon or Docker)"]
    tables[("tenants, users, invites, clients,<br/>snapshots, positions,<br/>review_runs, findings, reviews")]
    audit[("audit_log<br/>hash-chained, append-only")]
  end

  subgraph n8n["n8n"]
    sweep["Weekly sweep<br/>Mon 07:00 IST"]
    notify["Review events<br/>check signature, then notify"]
  end

  groq[("Groq<br/>openai/gpt-oss-120b")]
  gemini[("Gemini<br/>gemini-3-flash-preview")]
  slack[["Slack or Teams<br/>incoming webhook"]]
  book[["data/synthetic/book.json<br/>synthetic clients"]]
  dhan[["Dhan (read-only)<br/>sandbox by default"]]

  adv -- "HTTPS" --> console
  cli -.-> console
  console -- "session token, JSON" --> routes
  routes --> auth
  auth --> tables
  routes --> pipe
  book --> pipe
  pipe --> core
  pipe --> tables
  routes --> review
  routes --> copilot
  routes --> db
  routes --> events
  review --> core
  review --> rag
  review --> llm
  copilot --> core
  copilot --> rag
  rag --> llm
  copilot --> llm
  llm --> groq
  llm -. "if Groq fails" .-> gemini
  events -- "POST, signed" --> notify
  sweep -- "bearer token" --> routes
  notify --> slack
  sweep --> slack
  routes -.-> dhan
  repo --> ci --> cd
  cd -- "deploy hook" --> render
  cd -- "Netlify deploy" --> console
```

</details>

**Who can do what:** the *Owner* creates the firm account and becomes its first Owner. Owners and *Admins* give employees access by inviting them with a role; the employee joins with a one-time code. Admins can grant staff roles only; only an Owner can appoint Owners or Admins; nobody can change their own role; the firm always keeps one active Owner. Details: [EXPLANATION.md](EXPLANATION.md#firm-accounts-and-roles).

## Screenshots
Synthetic demo data: every client, firm and fund name is fictional. Mint marks computed, verified numbers; sky marks AI drafts.

| Agents: the multi-agent review | Agent run, replayed node by node |
|---|---|
| ![Agents](docs/screenshots/agents.png) | ![Agent run](docs/screenshots/agent-run.png) |
| **Ask the rulebook (RAG with citations)** | **Every number explains itself** |
| ![RAG](docs/screenshots/rag.png) | ![Explain drawer](docs/screenshots/explain-drawer.png) |
| **Today** | **Fund overlap** |
| ![Today](docs/screenshots/today.png) | ![Overlap](docs/screenshots/overlap.png) |
| **Review inbox (dark)** | **Team, roles and sessions (dark)** |
| ![Review inbox](docs/screenshots/review-inbox-dark.png) | ![Team](docs/screenshots/team-dark.png) |
| **Sign in (firm or client)** | **Client portal and adviser view on phones** |
| ![Sign in](docs/screenshots/signin.png) | <img src="docs/screenshots/portal-mobile.png" alt="Client portal" width="260"> <img src="docs/screenshots/mobile.png" alt="Phone" width="260"> |

## What works today
| Area | Status |
|---|---|
| **Live broker connection** | Real Dhan connector (official consent sign-in → 24-hour access pass → read-only holdings), only allow-listed read-only endpoints, retries, expiry handling, comparison with the depository statement; sandbox mode runs the whole flow without credentials; API `/v1/connections/dhan/*` |
| **Share without identities** | Anonymiser for firms (command line and in-browser): removes names, PAN, phone, email, address; codes clients and folios with the firm's secret key |
| **Multi-agent review** (backend) | LangGraph graph: 3 parallel analyst agents → rank → explainer (RAG-cited) → compliance (rules → ML classifier → LLM judge) → verifier. Works with any OpenAI-compatible model or falls back to firm policy. Copilot is a tool-using agent. See [docs/AGENTS.md](docs/AGENTS.md) |
| **ML** | Advice-likelihood classifier (logistic regression, numpy), 5-fold CV F1 0.89 |
| **Deterministic core** (Python) | Positions, lots, allocation, drift, look-through, overlap, tax position; every result is an Evidence record |
| **RAG** (backend) | Measured: on 16 paraphrased questions that avoid the documents' own wording, keyword search alone finds the right document first 69% of the time, real bge-small embeddings 100%, hybrid 88% (100% within the top 3); the 28 plain questions are 100% for every method. Enable the real embeddings with `AICFO_RAG_EMBEDDER=fastembed` and `uv sync --extra models`; the offline default is a hashing fallback. Corpus, chunking, BM25 + dense (bge-small or hashing), RRF fusion, relevance gate, cited extractive or LLM answers, citation and number verifier, compliance guard. API, CLI and golden-set eval. See [docs/RAG.md](docs/RAG.md) |
| **RAG** (browser) | Same corpus in the console ("Ask the rulebook" and Copilot), works offline |
| **Access control** (demo) | Firm sign-in with password + authenticator code; roles Owner, Adviser, Analyst, Compliance; adviser-scoped client lists; invites, role changes, suspension, device sessions, sign-out |
| **Client consent** (demo) | Advisers request access; the client approves or declines in their portal with a one-time code and the firm sees it; clients share read-only views (e.g. with their CA) and revoke them |
| **Security core** | Tenant envelope encryption (AES-256-GCM, rotation, crypto-shredding), log redaction, read-only broker guard |
| **Firm accounts and roles** | Owner creates the firm (API + console); employees get access by invite code from an Owner/Admin; five roles with enforced capabilities; password (scrypt) + authenticator code; signed session tokens re-checked against the database each request; suspension takes effect immediately; firms cannot see each other. Verified by tests and a real-browser end-to-end run |
| **LLM providers** | **Groq** and **Gemini Flash** through LangChain, with automatic fallback from one to the other; `make llm-bench` compares them on this app's own guards. Falls back to firm policy with no key |
| **Database pipeline** | SQLAlchemy + Alembic on Postgres 17: idempotent sync of the synthetic book through the core into snapshots and positions; review runs, findings, decisions and approvals stored; hash-chained audit log with verification; tested on SQLite and real Postgres |
| **Automation (n8n)** | Weekly review sweep and signed review-event workflows (`infra/n8n/workflows`), bearer-token API, HMAC-signed webhooks, CI guard for workflow files |
| **CI/CD** | CI: lint, types, tests, Postgres job, container smoke test, frontend build + axe, Semgrep, gitleaks. CD: Render (API) then Netlify (console) after CI passes on `main` |
| **Console** | Agents page with replayable runs from the Python pipeline; accessibility audited with axe (0 WCAG A/AA violations, light and dark) |

## Design commitments
- **Zero-access identity.** Client names and PAN are encrypted in the advisor's browser. The server stores pseudonymous portfolios only. See [ADR-0003](docs/adr/0003-zero-access-privacy.md).
- **Read-only broker access.** The code contains no order-placement calls, and CI fails if any are added.
- **India-resident data.** Real client data runs only on India-region infrastructure.
- **Deterministic core.** Every financial number comes from unit-tested code; LLMs only select and explain.
- **Measured AI.** Faithfulness, citation accuracy and compliance block rate are evaluated continuously.

## Repository layout
| Path | Contents |
|---|---|
| `backend/` | FastAPI service: `core/` maths, `agents/` (LangGraph), `rag/`, `llm/` (Groq/Gemini via LangChain), `auth/` (accounts, roles), `db/` (models, migrations, pipeline), `automation/` (n8n), `api/` (routes) |
| `frontend/` | Advisor console: React 19 + Vite + TypeScript, Tailwind v4, TanStack Router, Radix, Recharts (demo data for now) |
| `infra/` | Docker Compose (Postgres, OpenBao, n8n, API) and n8n workflows |
| `netlify.toml`, `render.yaml` | Console hosting (Netlify) and API hosting (Render) |
| `.github/workflows/` | `ci.yml` (checks) and `deploy.yml` (continuous delivery) |
| `data/` | Dataset scripts and docs (raw data is git-ignored) |
| `docs/plan/` | Project plans (v2 review, v3 B2B plan) |
| `docs/adr/` | Architecture Decision Records |
| `scripts/` | Repository checks (e.g. broker order-API guard) |

## Quick start (development)
Requires [uv](https://docs.astral.sh/uv/), Docker and Node 24.
```bash
cp .env.example backend/.env   # then add your API keys (next section)
make init-env      # fills in the encryption key, session secret and automation token (keeps your keys)
make dev-up        # Postgres + pgvector, OpenBao (dev mode)
make install       # backend dependencies
make check         # lint, types, tests, guards
make db-migrate    # create the tables
make db-seed       # synthetic book → core → Postgres, plus one review per client
make run           # API on http://localhost:8000 (docs at /docs)
make web           # advisor console on http://localhost:5173 (synthetic demo data)
cd backend && uv run python -m aicfo.rag ask "How is LTCG on equity funds taxed?"
cd backend && uv run python -m aicfo.agents review rohan-deshpande
```
Point `AICFO_DATABASE_URL` in `backend/.env` at the Postgres from `make dev-up` (`postgresql+psycopg://aicfo:aicfo@localhost:5432/aicfo`).

**Run the whole thing with real accounts** (console → API → Postgres):
```bash
make dev-up && make db-migrate            # database
make run                                  # API on :8000
echo 'VITE_API_URL=http://localhost:8000' > frontend/.env.local
make web                                  # console on :5173 → "Create a firm account"
```
Without `VITE_API_URL` the console runs as an offline demo with fictional accounts (pick one on the sign-in page).

**Keep `AICFO_LOCAL_KEKS` and `AICFO_JWT_SECRET` stable.** If they change, existing accounts can no longer sign in (`make init-env` sets them once and never overwrites).

**Verify every step.** Each row is one check; run them from the repository root.

| What it proves | Command |
|---|---|
| Backend: lint, strict types, 162 tests, broker read-only guard, n8n workflow files | `make check` |
| Frontend: lint, types, production build | `cd frontend && npm run lint && npm run typecheck && npm run build` |
| Accessibility on 13 screens, light and dark | `cd frontend && npm run build:preview && npm run audit:a11y` |
| Offline demo: create firm, invite, join, role limits | `cd frontend && npm run e2e:demo` |
| Full stack in a real browser (API + database + console) | `make e2e` (API and console must be running) |
| Database on real Postgres, migrations up and down | `cd backend && AICFO_TEST_DATABASE_URL=postgresql+psycopg://aicfo:aicfo@localhost:5432/aicfo_test uv run pytest tests/test_db_pipeline.py tests/test_auth.py` then `make db-migrate` |
| Groq and Gemini keys work, and which one the agents use | `make llm-status` |
| Provider comparison on this app's own checks | `make llm-bench` |
| Agents run for real, with a model choosing findings | `cd backend && uv run python -m aicfo.agents review rohan-deshpande` |
| RAG retrieval on plain and paraphrased questions | `cd backend && uv run python -m aicfo.rag eval` |
| API image builds and starts | `docker build -f backend/Dockerfile -t aicfo-api . ` |
| n8n sweep and signed-webhook workflows | `make automation-up && make n8n-import` |

The database tests drop their tables afterwards, so point them at a separate database (`createdb aicfo_test`), never your development one.

## API keys (Groq and Gemini)
Put them in **`backend/.env`** (git-ignored; copy it from `.env.example`):
```bash
AICFO_LLM_PROVIDER=auto              # Groq first, Gemini as fallback
AICFO_GROQ_API_KEY=gsk_...           # https://console.groq.com/keys
AICFO_GEMINI_API_KEY=...             # https://aistudio.google.com/apikey
```
Then:
```bash
make llm-status    # which provider the agents will use, plus a one-word ping
make llm-bench     # Groq vs Gemini on review runs + RAG (synthetic data), writes docs/llm-benchmark.json
```
**Measured on this app** (4 full agent reviews + 10 RAG questions each, synthetic data; [docs/llm-benchmark.json](docs/llm-benchmark.json)):

| | calls failed | median / slowest call | analyst JSON accepted | rewrites that passed the verifier | RAG answers that passed | score |
|---|---|---|---|---|---|---|
| **Groq** `openai/gpt-oss-120b` | 0 of 31 | 1.6 s / 5.5 s | 100% | 100% | 100% | **1.00** |
| **Gemini** `gemini-3-flash-preview` | 17 of 38 | 3.0 s / 40 s | 75% | 71% | 10% | 0.52 |

Groq is the better primary for this app; Gemini stays as the automatic fallback. Gemini's failures were free-tier quota (429) and timeout (504) responses, not wrong answers, and `gemini-3.6-flash` was out of quota on the tested key, so re-run `make llm-bench` with your own keys before relying on the gap. Use `gemini-3-flash-preview` or `gemini-3.5-flash-lite` if a model is rejected.

`AICFO_LLM_PROVIDER` can be `auto`, `groq`, `gemini`, `openai` (any OpenAI-compatible server such as Ollama) or `none`. Models can be changed with `AICFO_GROQ_MODEL` and `AICFO_GEMINI_MODEL`. In production, set the same variables in the host's dashboard (Render → Environment), never in a file in the repository. Tests and CI ignore these keys and always run without an LLM.

> Free tiers are for **synthetic data only**: Gemini's free tier may use prompts for training, and both services are hosted outside India (plan §1.4).

## Automation (n8n)
```bash
make automation-up   # Postgres + API container (seeded) + n8n on http://localhost:5678
make n8n-import      # load the two workflows from infra/n8n/workflows
```
Open n8n, create the owner account, open **AI CFO · Weekly review sweep** and press *Execute workflow*. Set `AICFO_NOTIFY_URL` (a Slack/Teams incoming-webhook URL) in `infra/.env` to receive messages. Details are in [EXPLANATION.md](EXPLANATION.md#n8n-scheduling-and-notifications).

## Deploy
| Step | Where | What to do |
|---|---|---|
| 1. Database | Supabase (Mumbai) or Neon | Create a project and copy the connection string |
| 2. API | Render → *New → Blueprint* → this repo (`render.yaml`) | Fill `AICFO_DATABASE_URL`, `AICFO_CORS_ORIGINS` (`["https://<site>.netlify.app"]`) and the LLM keys. Copy the **Deploy Hook URL** |
| 3. Console | Netlify → *Add new site* → *Deploy manually* (or link the repo) | Copy the **Site ID**; create a personal access token |
| 4. GitHub | Settings → Secrets and variables → Actions | Secrets `NETLIFY_AUTH_TOKEN`, `NETLIFY_SITE_ID`, `RENDER_DEPLOY_HOOK_URL`; variable `VITE_API_URL` = the Render URL |
| 5. Ship | merge to `main` | CI runs; when it is green, `deploy.yml` deploys the API, waits for `/health`, then deploys the console |

Without `VITE_API_URL`, the Netlify site is a fully offline demo. If you link the repo in Netlify's UI, turn off Netlify's own builds for `main`, or each push will deploy twice.

## Security
See [SECURITY.md](SECURITY.md). Never commit real client data, broker tokens or keys.

## Licence
Proprietary. All rights reserved. See [LICENSE](LICENSE).

*AI CFO is decision-support software for registered professionals. It does not provide investment advice to the public.*
