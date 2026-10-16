# ADR-0004: Data-source ladder behind `DataSourceAdapter`

- **Status:** Accepted, 2026-10-16
- **Context:** Broker APIs don't cover mutual funds or tax lots and restrict multi-user access. Without a licence, Account Aggregator access requires a regulated customer to act as the FIU.
- **Decision:** Every source produces `NormalisedHolding` / `NormalisedTxn` with `source`, `as_of` and `confidence`.

  | Tier | Source |
  |---|---|
  | T0 | Synthetic |
  | T1 | CAS PDF (`casparser`) + email auto-forward |
  | T2 | RTA mailback feeds; broker tradebook exports |
  | T3 | Account Aggregator via TSP (customer is FIU) |
  | T4 | Dhan BYO-key (owner / session-only), broker white-label, Dhan Partner |

  Merge is a reconciliation engine keyed on `(pan_tag, account_ref, ISIN)`. The same account seen twice counts once; different accounts add up; mismatches become exceptions for the advisor.
- **Consequences:** No feature depends on a single provider. Adding a broker means adding one adapter. Unknown tax lots are flagged, never guessed.
