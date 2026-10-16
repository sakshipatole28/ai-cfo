# ADR-0001: Build for wealth professionals (B2B), not retail investors (B2C)

- **Status:** Accepted, 2026-10-16
- **Context:** The v2 plan relied on retail users linking their own broker accounts. In 2026, brokers restricted multi-user API access: Upstox paused multi-client onboarding, citing exchange empanelment and broker-hosting requirements, and Dhan requires Partner approval. Personalised suggestions to retail users also sit close to regulated investment advice.
- **Decision:** Customers are SEBI RIAs, mutual fund distributors, wealth/PMS firms and, later, brokers via white-label. AI drafts; the advisor approves. Tenant compliance profiles (RIA / MFD / BROKER_WL) control what language is allowed.
- **Consequences:**
  - Multi-tenancy, role-based access and audit are core requirements from day one.
  - Data access uses a source ladder (ADR-0004) instead of depending on brokers.
  - Buyers will run vendor due diligence (SEBI 2025 AI accountability, CSCRF), so a Trust Pack is a deliverable.
  - A live Dhan connection is still built (owner and consenting-volunteer modes) for demos and real-data validation.
