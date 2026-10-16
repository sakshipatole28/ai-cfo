/** Hash-chained audit log (demo). Entries hold IDs and actions only, never personal data. */

export interface AuditEntry {
  seq: number;
  at: string; // ISO date-time
  actor: string;
  action: string;
  object: string;
  prevHash: string;
  hash: string;
}

/** 64-bit FNV-1a, hex. Stand-in for SHA-256 used by the backend. */
export function digest(text: string): string {
  let h1 = 0x811c9dc5;
  let h2 = 0x01000193 ^ text.length;
  for (let i = 0; i < text.length; i++) {
    const c = text.charCodeAt(i);
    h1 = Math.imul(h1 ^ c, 0x01000193);
    h2 = Math.imul(h2 ^ c, 0x5bd1e995);
  }
  return (h1 >>> 0).toString(16).padStart(8, "0") + (h2 >>> 0).toString(16).padStart(8, "0");
}

const payload = (e: Omit<AuditEntry, "hash">) => `${e.prevHash}|${e.seq}|${e.at}|${e.actor}|${e.action}|${e.object}`;

export function append(log: AuditEntry[], actor: string, action: string, object: string, at = new Date().toISOString()): AuditEntry[] {
  const prev = log[log.length - 1];
  const entry = { seq: (prev?.seq ?? 0) + 1, at, actor, action, object, prevHash: prev?.hash ?? "0".repeat(16) };
  return [...log, { ...entry, hash: digest(payload(entry)) }];
}

export function verify(log: AuditEntry[]): { ok: boolean; checked: number; brokenAt?: number } {
  let prev = "0".repeat(16);
  for (const e of log) {
    if (e.prevHash !== prev || digest(payload(e)) !== e.hash) return { ok: false, checked: e.seq - 1, brokenAt: e.seq };
    prev = e.hash;
  }
  return { ok: true, checked: log.length };
}

export function seedAudit(): AuditEntry[] {
  const rows: [string, string, string, string][] = [
    ["2026-10-14T09:02:11", "system", "marketdata.amc_disclosures.imported", "disclosures/2026-09 (9 schemes, weights validated)"],
    ["2026-10-14T09:05:40", "system", "marketdata.nav.imported", "nav/2026-10-14"],
    ["2026-10-14T10:12:03", "priya.anand", "client.consent.recorded", "client/kavya-nair consent/c-2210"],
    ["2026-10-14T10:14:57", "arun.k", "ingest.cas.parsed", "client/kavya-nair run/ing-8812 (5/5 checks)"],
    ["2026-10-14T10:15:02", "system", "snapshot.created", "client/kavya-nair snap-20261014"],
    ["2026-10-15T08:30:00", "system", "review.run.completed", "batch/weekly-42 (12 clients, 0 unsupported numbers)"],
    ["2026-10-15T08:30:01", "system", "verifier.finding.dropped", "finding/neha-joshi-harvest (citation unresolved)"],
    ["2026-10-15T11:48:22", "priya.anand", "review.approved", "client/vikram-shetty review/v7"],
    ["2026-10-15T11:49:10", "priya.anand", "report.rendered", "client/vikram-shetty review/v7 (browser)"],
    ["2026-10-16T09:01:15", "arun.k", "connection.dhan.synced", "client/rohan-deshpande conn/dh-31 (11 holdings)"],
    ["2026-10-16T09:01:16", "system", "token.discarded", "conn/dh-31 (session mode)"],
    ["2026-10-16T09:01:40", "system", "reconcile.exception.opened", "client/rohan-deshpande exc/INFY qty"],
    ["2026-10-16T15:22:09", "priya.anand", "settings.ai.provider.changed", "tenant/anand-wealth → India-hosted"],
    ["2026-10-17T07:00:00", "system", "evals.nightly.passed", "suite/l1-l2-l3 (hit@5 0.91, 0 unsupported)"],
  ];
  return rows.reduce<AuditEntry[]>((log, [at, actor, action, object]) => append(log, actor, action, object, `${at}+05:30`), []);
}
