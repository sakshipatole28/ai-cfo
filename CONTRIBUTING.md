# Contributing

1. Create a branch from `main`: `feat/<short-name>`, `fix/<short-name>` or `docs/<short-name>`.
2. Write or update tests first.
3. Run `make check`. It must pass locally before you push.
4. Open a pull request using the template and link the issue.
5. If behaviour or architecture changes, add or update an ADR in `docs/adr/` and the status checklist in `docs/plan/03_AI_CFO_V3_B2B.md` (§5).

Commit messages: imperative mood, ≤72-character subject (e.g. `Add envelope encryption for tenant data keys`).

Read [SECURITY.md](SECURITY.md) before touching anything related to data, keys or broker integrations.
