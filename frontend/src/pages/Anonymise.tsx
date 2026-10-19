import { ArrowDown, Check, ClipboardCopy, EyeOff, FileSpreadsheet, KeyRound, ShieldCheck, Upload } from "lucide-react";
import { type ChangeEvent, useMemo, useState } from "react";
import { toast } from "sonner";

import { Badge, Button, Card, CardHeader, Term } from "@/components/ui";
import { cn } from "@/lib/cn";
import sample from "../../../data/synthetic/ca_firm_sample.csv?raw";

type Kind = "name" | "pan" | "phone" | "email" | "address" | "dob" | "account" | null;

const IDENTITY: [Exclude<Kind, null | "account">, RegExp][] = [
  ["name", /^(client|investor|holder|customer|full)?\s*_?name$|^name$/i],
  ["pan", /\bpan\b/i],
  ["phone", /phone|mobile|contact/i],
  ["email", /e-?mail/i],
  ["address", /address|city|pin\s*code|pincode/i],
  ["dob", /birth|\bdob\b/i],
];
const ACCOUNT = /folio|account|demat|dp\s*id|client\s*id|bo\s*id/i;
const PAN_RX = /\b[A-Z]{5}[0-9]{4}[A-Z]\b/g;
const EMAIL_RX = /\b[\w.+-]+@[\w-]+\.[\w.-]+\b/g;
const PHONE_RX = /(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)/g;

function classify(h: string): Kind {
  if (ACCOUNT.test(h)) return "account";
  for (const [k, rx] of IDENTITY) if (rx.test(h)) return k;
  return null;
}

function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i]!;
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') {
        cell += '"';
        i++;
      } else if (c === '"') quoted = false;
      else cell += c;
    } else if (c === '"') quoted = true;
    else if (c === ",") {
      row.push(cell);
      cell = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(cell);
      if (row.some((x) => x.trim())) rows.push(row);
      row = [];
      cell = "";
    } else cell += c;
  }
  row.push(cell);
  if (row.some((x) => x.trim())) rows.push(row);
  return rows;
}

const toCsv = (rows: string[][]) => rows.map((r) => r.map((c) => (/[",\n]/.test(c) ? `"${c.replaceAll('"', '""')}"` : c)).join(",")).join("\n");

async function hmacCode(key: string, prefix: string, value: string): Promise<string> {
  const enc = new TextEncoder();
  const k = await crypto.subtle.importKey("raw", enc.encode(key), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = new Uint8Array(await crypto.subtle.sign("HMAC", k, enc.encode(value.trim().toUpperCase())));
  return `${prefix}-${[...sig.slice(0, 4)].map((b) => b.toString(16).padStart(2, "0")).join("").toUpperCase()}`;
}

const kindLabel: Record<Exclude<Kind, null>, string> = { name: "Name", pan: "PAN", phone: "Phone", email: "Email", address: "Address", dob: "Date of birth", account: "Account number" };

export function Anonymise() {
  const [text, setText] = useState(sample.trim());
  const [key, setKey] = useState("our-firm-secret-2026");
  const [result, setResult] = useState<{ rows: string[][]; scrubbed: number; clients: number } | null>(null);
  const table = useMemo(() => parseCsv(text), [text]);
  const header = table[0] ?? [];
  const kinds = header.map(classify);

  const run = async () => {
    if (!key.trim()) return toast.error("Enter a secret key first");
    const pan = kinds.indexOf("pan");
    const name = kinds.indexOf("name");
    const outHeader = ["client_code", ...header.flatMap((h, i) => (kinds[i] === "account" ? [`${h} (code)`] : kinds[i] ? [] : [h]))];
    const out: string[][] = [outHeader];
    let scrubbed = 0;
    const clients = new Set<string>();
    for (const row of table.slice(1)) {
      const ident = (row[pan] || row[name] || "").trim();
      const code = ident ? await hmacCode(key, "C", ident) : "C-UNKNOWN";
      clients.add(code);
      const cells = [code];
      for (let i = 0; i < header.length; i++) {
        const v = row[i] ?? "";
        if (kinds[i] === "account") cells.push(v.trim() ? await hmacCode(key, "A", v) : "");
        else if (kinds[i]) continue;
        else {
          const clean = v.replace(PAN_RX, "").replace(EMAIL_RX, "").replace(PHONE_RX, "").trim();
          if (clean !== v.trim()) scrubbed++;
          cells.push(clean);
        }
      }
      out.push(cells);
    }
    setResult({ rows: out, scrubbed, clients: clients.size });
  };

  const onFile = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => {
      setText(String(reader.result ?? ""));
      setResult(null);
    };
    reader.readAsText(f);
  };

  const removed = header.filter((_, i) => kinds[i] && kinds[i] !== "account");
  const coded = header.filter((_, i) => kinds[i] === "account");

  return (
    <div className="gutter-x mx-auto max-w-[1300px] space-y-5 py-5 sm:py-6">
      <section className="aurora relative overflow-hidden rounded-2xl border border-line p-5 sm:p-7">
        <div className="dot-grid absolute inset-0 opacity-60" aria-hidden />
        <div className="relative max-w-3xl">
          <p className="eyebrow">Share data without identities</p>
          <h2 className="mt-1 font-display text-[26px] font-semibold leading-tight text-fg">Remove who the clients are. Keep what they hold.</h2>
          <p className="mt-2 text-[14px] leading-relaxed text-fg-2">
            This runs entirely in this browser; nothing is uploaded. Names, <Term k="PAN" />, phone numbers, emails and addresses are removed. Each client and each <Term k="Folio" /> number becomes a{" "}
            <Term k="Pseudonymous code">code</Term> made with your firm's secret key, so the same client always gets the same code, but nobody can turn it back into a name without your key.
          </p>
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-12">
        <Card className="lg:col-span-8">
          <CardHeader
            title="1. Your spreadsheet"
            description="Example rows from a fictional CA firm. Replace with your own file (CSV)."
            action={
              <label className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-lg border border-line bg-surface px-3 text-[12.5px] font-medium text-fg hover:bg-surface-2">
                <Upload className="size-3.5" aria-hidden /> Choose CSV
                <input type="file" accept=".csv,text/csv" onChange={onFile} className="sr-only" />
              </label>
            }
          />
          <div className="scrollbar-thin mt-3 overflow-x-auto px-4 pb-4 sm:px-5">
            <table className="w-full min-w-[900px] text-[12px]">
              <thead>
                <tr>
                  {header.map((h, i) => (
                    <th key={h} className={cn("border-b border-line px-2 py-2 text-left font-semibold", kinds[i] && kinds[i] !== "account" ? "bg-critical-soft text-critical-text" : kinds[i] === "account" ? "bg-warning-soft text-warning-text" : "text-fg")}>
                      {h}
                      {kinds[i] && <span className="block text-[10.5px] font-medium">{kinds[i] === "account" ? "→ code" : "→ removed"}</span>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {table.slice(1).map((r, ri) => (
                  <tr key={ri}>
                    {header.map((h, i) => (
                      <td key={h} className={cn("px-2 py-1.5", kinds[i] && kinds[i] !== "account" ? "text-critical-text" : "text-fg-2")}>
                        {r[i]}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card className="p-4 sm:p-5 lg:col-span-4">
          <p className="text-[14px] font-semibold text-fg">2. What happens</p>
          <ul className="mt-3 space-y-2 text-[13px]">
            <li className="flex gap-2">
              <EyeOff className="mt-0.5 size-4 shrink-0 text-critical-text" aria-hidden />
              <span className="text-fg-2">
                <b className="text-fg">Removed:</b> {removed.map((h) => `${h} (${kindLabel[kinds[header.indexOf(h)]!]})`).join(", ") || "nothing detected"}
              </span>
            </li>
            <li className="flex gap-2">
              <KeyRound className="mt-0.5 size-4 shrink-0 text-warning-text" aria-hidden />
              <span className="text-fg-2">
                <b className="text-fg">Replaced with codes:</b> client (from PAN) {coded.length ? `and ${coded.join(", ")}` : ""}
              </span>
            </li>
            <li className="flex gap-2">
              <ShieldCheck className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
              <span className="text-fg-2">
                <b className="text-fg">Also checked:</b> every other cell for anything that looks like a PAN, email or phone number.
              </span>
            </li>
            <li className="flex gap-2">
              <Check className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
              <span className="text-fg-2">
                <b className="text-fg">Kept:</b> scheme or share, <Term k="ISIN" />, units, purchase dates and amounts, which are needed for overlap and tax calculations.
              </span>
            </li>
          </ul>
          <label htmlFor="anon-key" className="mt-4 block text-[12.5px] font-medium text-fg">
            Your firm's secret key <span className="font-normal text-fg-2">(stays with you)</span>
          </label>
          <input id="anon-key" value={key} onChange={(e) => setKey(e.target.value)} className="mt-1.5 h-10 w-full rounded-lg border border-line bg-surface px-3 font-mono text-[13px] text-fg outline-none focus:border-accent" />
          <Button variant="primary" className="mt-3 h-10 w-full" onClick={() => void run()}>
            <FileSpreadsheet /> Remove identities
          </Button>
        </Card>
      </div>

      {result && (
        <Card>
          <CardHeader
            title="3. What would be shared"
            description={`${result.rows.length - 1} rows · ${result.clients} clients · ${result.scrubbed} other cell${result.scrubbed === 1 ? "" : "s"} cleaned`}
            action={
              <Button
                size="sm"
                variant="outline"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(toCsv(result.rows));
                    toast.success("Copied as CSV");
                  } catch {
                    toast.error("Copy was blocked by the browser");
                  }
                }}
              >
                <ClipboardCopy /> Copy CSV
              </Button>
            }
          />
          <div className="flex justify-center py-1 text-fg-2">
            <ArrowDown className="size-4" aria-hidden />
          </div>
          <div className="scrollbar-thin overflow-x-auto px-4 pb-5 sm:px-5">
            <table className="w-full min-w-[820px] text-[12px]">
              <thead>
                <tr>
                  {result.rows[0]!.map((h) => (
                    <th key={h} className={cn("border-b border-line px-2 py-2 text-left font-semibold", h === "client_code" || h.endsWith("(code)") ? "bg-accent-soft text-accent" : "text-fg")}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {result.rows.slice(1).map((r, ri) => (
                  <tr key={ri}>
                    {r.map((c, ci) => (
                      <td key={ci} className={cn("px-2 py-1.5", ci === 0 || result.rows[0]![ci]!.endsWith("(code)") ? "font-mono text-accent" : "text-fg-2")}>
                        {c}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="border-t border-line px-5 py-3 text-[12px] text-fg-2">
            The same tool exists as a command for the firm's own computer: <code className="font-mono text-fg">python -m aicfo.ingest.anonymise holdings.csv shared.csv --key "…"</code>
          </p>
        </Card>
      )}
      <Badge tone="outline">Demo data: the names, PAN and phone numbers above are invented.</Badge>
    </div>
  );
}
