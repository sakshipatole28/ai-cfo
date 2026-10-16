# Data

**This repository never contains real personal or financial data.** `data/raw/`, `data/private/` and `data/cache/` are git-ignored.

| ID | Dataset | Source | Status |
|---|---|---|---|
| D1 | Scheme master + daily NAV (ISIN) | AMFI `NAVAll.txt`, `api.mfapi.in` | ⬜ loader |
| D2 | Fund constituents (look-through) | AMC monthly portfolio disclosures | ⬜ parsers (top AMCs first) |
| D3 | Equity prices + ISIN master | NSE bhavcopy, `EQUITY_L.csv`, `casparser-isin` | ⬜ loader |
| D4 | Synthetic personas with planted issues + gold labels | Generated from D1–D3 (seeded) | ⬜ generator |
| D5 | Synthetic CAS JSON | Generated from D4, validated against casparser's JSON Schemas | ⬜ |
| D6 | Synthetic Dhan API fixtures | Documented response fields | ⬜ |
| D7 | RAG corpus | SEBI, AMFI, Income-tax Act 2025 + Rules 2026 (public) | ⬜ |
| D8 | Evaluation sets | Gold findings, red-team prompts, RAG golden Q&A | ⬜ |

Public sources must be fetched by scripts (reproducible), not committed by hand. Record each source URL and fetch date.
