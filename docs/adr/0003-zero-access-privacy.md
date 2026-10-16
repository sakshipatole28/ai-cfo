# ADR-0003: Zero-access identity and an encrypted, pseudonymous Portfolio Store

- **Status:** Accepted, 2026-10-16
- **Context:** Requirement: developers, database admins and the host must not be able to see client data unless processing strictly needs it. Regulated buyers are accountable for their vendors (SEBI 2025, CSCRF), and DPDP requires erasure.
- **Decision:**
  1. **Identity Vault (zero-knowledge):** name, PAN, DOB and contacts are encrypted in the browser with a Firm Key the server never sees. The Firm Key is wrapped to each member's key pair (password-derived via Argon2id). A Recovery Kit is shown once.
  2. **Blind index:** the browser sends `HMAC(FirmKey, PAN)` for matching; the server never sees the PAN.
  3. **Portfolio Store:** keyed by random `client_id`, with fields sealed using AES-256-GCM and a per-tenant data key. The data key is wrapped by a KEK in OpenBao Transit (dev: `LocalKeyProvider`). Associated data binds each ciphertext to tenant + row + field. *(Implemented: `aicfo.crypto`.)*
  4. Reports use `{{CLIENT}}` placeholders; the browser fills in names and renders PDFs.
  5. CAS parsing happens in the browser if spike S1 succeeds; otherwise in an in-memory-only worker that strips identity fields immediately.
  6. **Crypto-shredding** for erasure; the hash-chained audit log stores IDs and hashes only.
  7. Operators: no standing production access; break-glass access is time-boxed and audited; split OpenBao unseal keys.
- **Consequences / honest limits:**
  - Pseudonymous data is still personal data under DPDP.
  - Browser end-to-end encryption trusts the served JavaScript (mitigations: CSP, SRI, signed and reviewed releases).
  - Workers see plaintext holdings in memory during computation.
  - Losing every user credential *and* the Recovery Kit makes identities unrecoverable, by design.
