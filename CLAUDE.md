# CLAUDE.md: working rules for this repository

Read `docs/plan/03_AI_CFO_V3_B2B.md` (plan and status checklist) and `docs/adr/` before starting work.

## Product
B2B portfolio-intelligence platform for Indian advisors (RIAs, MFDs, wealth firms). Deterministic core does all maths; LLM agents only select and explain; an advisor approves before anything reaches a client.

## Non-negotiable rules
- **Broker access is read-only.** Never add order placement, modification or cancellation calls. Never store broker passwords, PINs or TOTP secrets. `scripts/check_no_order_apis.py` must pass.
- **No real personal data** anywhere in the repo. Use synthetic data from `data/`.
- **Never log** tokens, PAN, names, emails or phones. Use `aicfo.security.redaction`.
- **Agents never compute numbers.** Numbers come from `core/`; every claim carries `evidence_ids`; the verifier rejects unsupported numbers.
- **CI never calls real broker or LLM APIs.** Use recorded fixtures (respx) and the fake LLM.
- **Every external service sits behind an interface** (`KeyProvider`, `VectorStore`, `LLMProvider`, `JobQueue`, `DataSourceAdapter`).

## Workflow
Feature branch → tests first → `make check` green → PR using the template → update the status checklist (§5) in the plan.

## Commands
`make install` · `make check` · `make test` · `make run` · `make dev-up` / `make dev-down`
