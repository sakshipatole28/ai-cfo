import { Link } from "@tanstack/react-router";
import {
  BookOpen,
  CheckCircle2,
  Cpu,
  Download,
  FileCheck2,
  FileText,
  Fingerprint,
  KeyRound,
  Link2Off,
  Loader2,
  Lock,
  Search,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  UploadCloud,
  XCircle,
} from "lucide-react";
import { type ReactNode, useMemo, useState } from "react";
import { toast } from "sonner";

import { Avatar, Badge, Button, Card, CardHeader, Switch } from "@/components/ui";
import { firm, kb } from "@/data/demo";
import { verify } from "@/lib/audit";
import { cn } from "@/lib/cn";
import { portfolios } from "@/lib/engine";
import { fmtDate, inrShort } from "@/lib/format";
import { useApp, useClientName } from "@/state/app";

function Page({ children }: { children: ReactNode }) {
  return <div className="gutter-x mx-auto max-w-[1200px] space-y-4 py-5 sm:py-6">{children}</div>;
}

/* Data inbox */
export function DataInbox() {
  const displayName = useClientName();
  const { log } = useApp();
  const [resolved, setResolved] = useState<"dhan" | "cas" | null>(null);
  const jobs = [
    { client: "Kavya Nair", what: "CAMS CAS · Detailed", status: "done", checks: "5/5 checks", at: "14 Oct, 10:14" },
    { client: "Rohan Deshpande", what: "Dhan holdings sync", status: "done", checks: "11 holdings · token discarded", at: "16 Oct, 09:01" },
    { client: "Neha Joshi", what: "KFintech CAS · Detailed", status: "running", checks: "Parsing… 3/5 checks", at: "Now" },
    { client: "Ishaan Gupta", what: "Dhan holdings sync", status: "blocked", checks: "Token expired 2 days ago", at: "15 Oct, 18:40" },
  ];
  return (
    <Page>
      <Card className="flex flex-col items-center gap-3 border-dashed p-6 text-center sm:flex-row sm:text-left">
        <span className="flex size-11 items-center justify-center rounded-full bg-accent-soft text-accent">
          <UploadCloud className="size-5" aria-hidden />
        </span>
        <div className="flex-1">
          <p className="text-[14px] font-semibold text-fg">Drop CAS statements or tradebooks</p>
          <p className="text-[12.5px] text-muted">CAMS, KFintech, NSDL and CDSL PDFs. Parsed in your browser; only pseudonymised holdings reach the server.</p>
        </div>
        <Button variant="primary" onClick={() => toast("Choose a statement", { description: "Demo: uploads are disabled. No real files are processed." })}>
          Choose files
        </Button>
      </Card>

      <div className="grid gap-4 lg:grid-cols-12">
        <Card className="lg:col-span-7">
          <CardHeader title="Ingestion jobs" description="Every statement is checked before it can affect a portfolio" />
          <ul className="mt-2 divide-y divide-line">
            {jobs.map((j) => (
              <li key={j.client + j.what} className="flex items-center gap-3 px-4 py-3 sm:px-5">
                {j.status === "done" && <CheckCircle2 className="size-5 shrink-0 text-good" aria-label="Done" />}
                {j.status === "running" && <Loader2 className="size-5 shrink-0 animate-spin text-accent" aria-label="Running" />}
                {j.status === "blocked" && <Link2Off className="size-5 shrink-0 text-warning-text" aria-label="Blocked" />}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13px] font-medium text-fg">
                    {displayName(j.client)} · <span className="font-normal text-fg-2">{j.what}</span>
                  </p>
                  <p className="text-[12px] text-muted">{j.checks}</p>
                </div>
                <span className="shrink-0 text-[12px] text-muted">{j.at}</span>
              </li>
            ))}
          </ul>
        </Card>

        <Card className="lg:col-span-5">
          <CardHeader title="Reconciliation exception" description={`${displayName("Rohan Deshpande")} · Infosys · demat ••7731`} action={resolved ? <Badge tone="good">Resolved</Badge> : <Badge tone="warning">Open</Badge>} />
          <div className="space-y-3 p-4 sm:p-5">
            <p className="text-[12.5px] text-fg-2">The same demat account reports different quantities. The newer source is not assumed to be right; choose one and the reason is logged.</p>
            {(
              [
                ["dhan", "Dhan API", "16 Oct 2026", "80 shares", "Includes 5 shares bought on 7 Oct"],
                ["cas", "CDSL CAS", "30 Sep 2026", "75 shares", "Statement closes before the purchase"],
              ] as const
            ).map(([key, src, date, qty, hint]) => (
              <button
                key={key}
                onClick={() => {
                  setResolved(key);
                  log("reconcile.exception.resolved", `exc/INFY → ${key}`);
                  toast.success("Exception resolved", { description: `${src} kept · decision logged` });
                }}
                className={cn(
                  "flex w-full cursor-pointer items-center gap-3 rounded-lg border p-3 text-left transition-colors",
                  resolved === key ? "border-accent bg-accent-soft" : "border-line hover:border-line-strong",
                )}
              >
                <div className="flex-1">
                  <p className="text-[12px] text-muted">
                    {src} · {date}
                  </p>
                  <p className="tabular text-[16px] font-semibold text-fg">{qty}</p>
                  <p className="text-[12px] text-muted">{hint}</p>
                </div>
                {resolved === key && <CheckCircle2 className="size-5 text-accent" aria-hidden />}
              </button>
            ))}
          </div>
        </Card>
      </div>
    </Page>
  );
}

/* Reports */
export function Reports() {
  const { approved } = useApp();
  const displayName = useClientName();
  const rows = portfolios.filter((p) => approved[p.spec.id]);
  return (
    <Page>
      <Card>
        <CardHeader title="Approved reviews" description="Reports are rendered in your browser so client names never reach the server" />
        <ul className="mt-2 divide-y divide-line">
          {rows.length === 0 && <li className="px-5 py-8 text-center text-[13px] text-muted">Approve a review in the inbox to create a report.</li>}
          {rows.map((p) => (
            <li key={p.spec.id} className="flex items-center gap-3 px-4 py-3 sm:px-5">
              <Avatar name={displayName(p.spec.name)} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13.5px] font-medium text-fg">{displayName(p.spec.name)}</p>
                <p className="text-[12px] text-muted">
                  Approved {fmtDate(approved[p.spec.id]!)} · {inrShort(p.total)} · {p.findings.length} findings
                </p>
              </div>
              <Badge tone="good">
                <FileCheck2 aria-hidden /> Final
              </Badge>
              <Button size="sm" variant="outline" onClick={() => toast("PDF generated in the browser", { description: "Demo: downloads are disabled in the preview." })}>
                <Download /> <span className="hidden sm:inline">PDF</span>
              </Button>
            </li>
          ))}
        </ul>
      </Card>
    </Page>
  );
}

/* Knowledge */
export function Knowledge() {
  const [q, setQ] = useState("");
  const docs = Object.values(kb).filter((d) => `${d.title} ${d.summary} ${d.section}`.toLowerCase().includes(q.toLowerCase()));
  return (
    <Page>
      <label className="flex h-10 items-center gap-2 rounded-lg border border-line bg-surface px-3 focus-within:border-accent">
        <Search className="size-4 text-muted" aria-hidden />
        <span className="sr-only">Search rules</span>
        <input id="kb-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search SEBI, AMFI and Income-tax sources" className="flex-1 bg-transparent text-[13.5px] text-fg outline-none placeholder:text-muted" />
      </label>
      <p className="text-[12px] text-muted">The explainer and Copilot may only cite documents in this library. Each is versioned with its effective date.</p>
      <div className="grid gap-3 md:grid-cols-2">
        {docs.map((d) => (
          <Card key={d.id} className="p-4 sm:p-5">
            <div className="flex flex-wrap gap-1.5">
              <Badge tone="accent">{d.issuer}</Badge>
              <Badge tone="outline">{d.version}</Badge>
              <Badge tone="outline">{d.effective}</Badge>
            </div>
            <p className="mt-2.5 text-[14px] font-semibold text-fg">{d.title}</p>
            <p className="text-[12.5px] text-muted">{d.section}</p>
            <p className="mt-2 text-[13px] leading-relaxed text-fg-2">{d.summary}</p>
          </Card>
        ))}
      </div>
      {docs.length === 0 && (
        <p className="py-8 text-center text-[13px] text-muted">
          <BookOpen className="mx-auto mb-2 size-5" aria-hidden /> No documents match “{q}”.
        </p>
      )}
    </Page>
  );
}

/* Audit */
export function Audit() {
  const { audit } = useApp();
  const [state, setState] = useState<"idle" | "running" | "ok" | "fail">("idle");
  const result = useMemo(() => verify(audit), [audit]);
  return (
    <Page>
      <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:p-5">
        <span className={cn("flex size-11 shrink-0 items-center justify-center rounded-full", state === "fail" ? "bg-critical-soft text-critical-text" : "bg-accent-soft text-accent")}>
          {state === "fail" ? <XCircle className="size-5" /> : <Fingerprint className="size-5" />}
        </span>
        <div className="flex-1">
          <p className="text-[14px] font-semibold text-fg">Tamper-evident log</p>
          <p className="text-[12.5px] text-muted">
            Each entry stores the hash of the one before it. Editing or deleting any entry breaks every hash after it. No personal data is stored here.
          </p>
        </div>
        <Button
          variant="primary"
          onClick={() => {
            setState("running");
            setTimeout(() => setState(result.ok ? "ok" : "fail"), 900);
          }}
          disabled={state === "running"}
        >
          {state === "running" ? <Loader2 className="animate-spin" /> : <ShieldCheck />}
          {state === "running" ? "Verifying…" : "Verify chain"}
        </Button>
      </Card>
      {state === "ok" && (
        <div className="flex items-center gap-2 rounded-lg border border-good/40 bg-good-soft px-4 py-2.5 text-[13px] text-good-text">
          <CheckCircle2 className="size-4" aria-hidden /> Chain intact: {result.checked} entries verified from #1 to #{audit.length}.
        </div>
      )}
      <Card className="overflow-hidden">
        <div className="scrollbar-thin overflow-x-auto">
          <table className="w-full min-w-[760px] text-[12.5px]">
            <thead className="border-b border-line bg-surface-2/60 text-left text-[11px] uppercase tracking-wider text-muted">
              <tr>
                <th className="px-5 py-2.5 font-semibold">#</th>
                <th className="px-3 py-2.5 font-semibold">Time (IST)</th>
                <th className="px-3 py-2.5 font-semibold">Actor</th>
                <th className="px-3 py-2.5 font-semibold">Action</th>
                <th className="px-3 py-2.5 font-semibold">Object</th>
                <th className="px-3 py-2.5 font-semibold">Hash</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {[...audit].reverse().map((e) => (
                <tr key={e.seq}>
                  <td className="tabular px-5 py-2 text-muted">{e.seq}</td>
                  <td className="tabular whitespace-nowrap px-3 py-2 text-fg-2">{new Date(e.at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kolkata" })}</td>
                  <td className="px-3 py-2 text-fg">{e.actor}</td>
                  <td className="px-3 py-2 font-mono text-[11.5px] text-fg">{e.action}</td>
                  <td className="px-3 py-2 text-fg-2">{e.object}</td>
                  <td className="px-3 py-2 font-mono text-[11px] text-muted" title={`prev ${e.prevHash}`}>
                    {e.hash.slice(0, 10)}…
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </Page>
  );
}

/* Settings */
function SettingRow({ title, desc, children }: { title: string; desc: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:px-5">
      <div className="flex-1">
        <p className="text-[13.5px] font-medium text-fg">{title}</p>
        <p className="text-[12.5px] text-muted">{desc}</p>
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

export function Settings() {
  const { aiEnabled, setAiEnabled, setLocked } = useApp();
  const [mode, setMode] = useState("india");
  return (
    <Page>
      <Card>
        <CardHeader title="AI controls" description="You stay in control of every model call" action={<Cpu className="size-4 text-muted" />} />
        <div className="mt-2 divide-y divide-line">
          <SettingRow title="AI kill switch" desc="Turn off all drafting and Copilot for the whole firm immediately. Calculations and reports keep working.">
            <div className="flex items-center gap-2">
              <span className={cn("text-[12.5px] font-medium", aiEnabled ? "text-good-text" : "text-critical-text")}>{aiEnabled ? "AI on" : "AI off"}</span>
              <Switch id="ai-switch" label="AI enabled" checked={aiEnabled} onChange={(v) => {
                setAiEnabled(v);
                toast(v ? "AI drafting resumed" : "AI switched off", { description: "Logged to the audit trail." });
              }} />
            </div>
          </SettingRow>
          <SettingRow title="Model provider" desc="Where model calls run. Prompts never contain names, PAN or account numbers.">
            <div className="inline-flex rounded-lg border border-line bg-surface-2 p-0.5" role="radiogroup" aria-label="Model provider">
              {[
                ["india", "India-hosted"],
                ["own", "Our own key"],
                ["local", "Local only"],
              ].map(([v, l]) => (
                <button
                  key={v}
                  role="radio"
                  aria-checked={mode === v}
                  onClick={() => setMode(v!)}
                  className={cn("h-8 cursor-pointer rounded-md px-3 text-[12.5px] font-medium", mode === v ? "bg-surface text-fg shadow-card" : "text-muted hover:text-fg")}
                >
                  {l}
                </button>
              ))}
            </div>
          </SettingRow>
          <SettingRow title="Compliance profile" desc="Controls which wording the guard allows in drafts.">
            <Badge tone="accent">SEBI RIA · {firm.registration}</Badge>
          </SettingRow>
        </div>
      </Card>

      <Card>
        <CardHeader title="Security and privacy" action={<Lock className="size-4 text-muted" />} />
        <div className="mt-2 divide-y divide-line">
          <SettingRow title="Two-factor sign-in" desc="Authenticator app codes are required for every user.">
            <Badge tone="good">
              <ShieldCheck aria-hidden /> Enforced
            </Badge>
          </SettingRow>
          <SettingRow title="Identity vault" desc="Client names and PAN are encrypted in the browser with the firm key. Lock it when you step away.">
            <Button size="sm" variant="outline" onClick={() => setLocked(true)}>
              <Lock /> Lock now
            </Button>
          </SettingRow>
          <SettingRow title="Recovery kit" desc="The only way to recover client identities if every user loses access. Generated once at signup.">
            <Button size="sm" variant="outline" onClick={() => toast("Recovery kit rotation", { description: "Demo: requires the owner's passphrase." })}>
              <KeyRound /> Rotate
            </Button>
          </SettingRow>
          <SettingRow title="Data region" desc="Database, files, keys and model calls for real client data stay in India.">
            <Badge tone="outline">Mumbai (ap-south-1)</Badge>
          </SettingRow>
          <SettingRow title="Erase a client" desc="Destroys the client's identity record and portfolio rows. The audit trail keeps only IDs.">
            <Button size="sm" variant="danger" onClick={() => toast.error("Type the client's name to confirm", { description: "Demo: erasure is disabled." })}>
              <Trash2 /> Erase…
            </Button>
          </SettingRow>
        </div>
      </Card>
      <p className="flex items-center gap-1.5 text-[12px] text-muted">
        <ShieldAlert className="size-3.5" aria-hidden /> AI CFO is decision-support software for registered professionals. It does not give investment advice to the public.
      </p>
    </Page>
  );
}

/* Client-facing consent page (no login, mobile-first) */
export function Consent() {
  const [step, setStep] = useState<"read" | "otp" | "done">("read");
  const [otp, setOtp] = useState("");
  return (
    <div className="gutter-x min-h-full bg-bg py-8">
      <div className="mx-auto max-w-md">
        <div className="flex items-center gap-2.5">
          <Avatar name={firm.name} className="size-9" />
          <div>
            <p className="text-[14px] font-semibold text-fg">{firm.name}</p>
            <p className="text-[12px] text-muted">SEBI-registered investment adviser · {firm.registration}</p>
          </div>
        </div>
        <Card className="mt-5 p-5">
          {step === "done" ? (
            <div className="py-6 text-center">
              <CheckCircle2 className="mx-auto size-10 text-good" aria-hidden />
              <p className="mt-3 text-[17px] font-semibold text-fg">Thank you, consent recorded</p>
              <p className="mt-1 text-[13px] text-muted">You can withdraw it any time from the link in your email or by telling your adviser.</p>
            </div>
          ) : (
            <>
              <h1 className="text-[18px] font-semibold tracking-tight text-fg">Share your portfolio with Priya Anand</h1>
              <p className="mt-1 text-[13px] text-muted">Please read what will be shared and why.</p>
              <dl className="mt-4 space-y-3 text-[13.5px]">
                {[
                  ["What", "Your mutual fund and share holdings, and their transaction history."],
                  ["From", "Statements you or your adviser upload (CAS), and your Dhan account if you connect it."],
                  ["Why", "So your adviser can review your portfolio and prepare recommendations for you."],
                  ["How long", "12 months, or until you withdraw."],
                  ["Your rights", "Withdraw any time; ask for your data to be erased."],
                ].map(([k, v]) => (
                  <div key={k} className="grid grid-cols-[88px_1fr] gap-3">
                    <dt className="font-medium text-fg">{k}</dt>
                    <dd className="text-fg-2">{v}</dd>
                  </div>
                ))}
              </dl>
              {step === "read" ? (
                <Button variant="primary" className="mt-5 h-11 w-full text-[14px]" onClick={() => setStep("otp")}>
                  I agree, send me a code
                </Button>
              ) : (
                <form
                  className="mt-5 space-y-3"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (otp.length === 6) setStep("done");
                  }}
                >
                  <label htmlFor="otp" className="text-[13px] font-medium text-fg">
                    Enter the 6-digit code sent to your phone
                  </label>
                  <input
                    id="otp"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={6}
                    value={otp}
                    onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
                    placeholder="••••••"
                    className="tabular h-12 w-full rounded-lg border border-line bg-surface-2 px-3 text-center text-[20px] tracking-[0.5em] text-fg outline-none focus:border-accent"
                  />
                  <Button type="submit" variant="primary" className="h-11 w-full text-[14px]" disabled={otp.length !== 6}>
                    Confirm consent
                  </Button>
                  <p className="text-center text-[12px] text-muted">Demo: any 6 digits work.</p>
                </form>
              )}
            </>
          )}
        </Card>
        <p className="mt-4 flex items-center justify-center gap-1.5 text-[12px] text-muted">
          <FileText className="size-3.5" aria-hidden /> Recorded under the Digital Personal Data Protection Act, 2023
        </p>
        <p className="mt-6 text-center text-[12.5px]">
          <Link to="/" className="text-accent hover:underline">
            ← Back to the adviser console (demo)
          </Link>
        </p>
      </div>
    </div>
  );
}
