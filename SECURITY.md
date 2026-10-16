# Security Policy

## Reporting a vulnerability
Please **do not open a public issue**. Email **sakshipatole28@gmail.com** with the subject `[AI CFO security]`, a description, and steps to reproduce. You will get an acknowledgement within 72 hours.

## Rules for contributors (enforced in CI where possible)
1. **No secrets in git.** Keys, tokens and `.env` files are git-ignored and scanned by gitleaks on every push.
2. **No real personal or financial data** in the repository, tests, fixtures, issues or logs. Use the synthetic datasets (`data/`).
3. **Read-only broker access.** No order-placement, modification or cancellation endpoints may appear in the code (`scripts/check_no_order_apis.py`).
4. **Never log** tokens, PAN, names, emails or phone numbers. The logging redaction filter is a safety net, not a licence to log.
5. **Never store** broker passwords, PINs or TOTP secrets.
6. **Encryption** uses `cryptography` (AES-256-GCM) and libsodium only. No custom primitives.

## Data protection model (summary)
- **Identity Vault:** client identity is encrypted in the advisor's browser with a firm key the server never sees.
- **Portfolio Store:** pseudonymous and encrypted at rest with per-tenant data keys wrapped by a key-management service.
- **Crypto-shredding** for erasure; a hash-chained audit log that contains no personal data.

Full design: [docs/adr/0003-zero-access-privacy.md](docs/adr/0003-zero-access-privacy.md).
