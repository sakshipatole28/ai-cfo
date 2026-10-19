import { ArrowRight, Check, CircleDashed, ExternalLink, Eye, KeyRound, Lock, RefreshCw, ShieldCheck, Smartphone, Unplug } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Badge, Button, Sheet, Term } from "@/components/ui";
import { cn } from "@/lib/cn";
import { portfolioById } from "@/lib/engine";
import { inr } from "@/lib/format";
import { useApp, useClientName } from "@/state/app";

type Step = "explain" | "dhan" | "sync" | "done";

interface LogLine {
  at: string;
  text: string;
  tone?: "ok" | "warn" | "info";
}

/** Statement quantities (synthetic CDSL statement, 30 Sep) used to reconcile the live data. */
const STATEMENT: Record<string, Record<string, number>> = {
  "rohan-deshpande": { HDFCBANK: 120, INFY: 75, RELIANCE: 60, ITC: 300 },
};

function clock() {
  return new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
}

export function LiveConnectSheet({ clientId, open, onOpenChange, audience }: { clientId: string; open: boolean; onOpenChange: (o: boolean) => void; audience: "client" | "adviser" }) {
  const { markSynced } = useApp();
  const displayName = useClientName();
  const pf = portfolioById[clientId];
  const [step, setStep] = useState<Step>("explain");
  const [code, setCode] = useState("");
  const [log, setLog] = useState<LogLine[]>([]);
  const timers = useRef<number[]>([]);

  useEffect(() => {
    const pending = timers.current;
    if (open) {
      setStep("explain");
      setCode("");
      setLog([]);
    }
    return () => pending.forEach(clearTimeout);
  }, [open]);

  if (!pf) return null;
  const dhanHoldings = pf.positions.filter((p) => p.source === "Dhan");
  const statement = STATEMENT[clientId] ?? {};
  const diffs = dhanHoldings.filter((h) => statement[h.ref] !== undefined && statement[h.ref] !== h.units);
  const first = displayName(pf.spec.name).split(" ")[0];

  const runSync = () => {
    setStep("sync");
    const lines: LogLine[] = [
      { at: "", text: "Dhan confirmed the client's approval and returned a one-time code", tone: "info" },
      { at: "", text: "Exchanged the code for an access pass · valid 24 hours · kept in memory only", tone: "ok" },
      { at: "", text: "Requested holdings (read-only): GET /v2/holdings", tone: "info" },
      { at: "", text: `Received ${dhanHoldings.length} holdings: ${dhanHoldings.map((h) => h.ref).join(", ") || "none"}`, tone: "ok" },
      { at: "", text: "Compared each holding with the 30 Sep depository statement (by ISIN)", tone: "info" },
      diffs.length
        ? { at: "", text: `${diffs.length} difference found: ${diffs.map((d) => `${d.shortName} ${d.units} live vs ${statement[d.ref]} on statement`).join("; ")} → sent to the adviser to check`, tone: "warn" }
        : { at: "", text: "Every holding matches the statement", tone: "ok" },
      { at: "", text: "Snapshot updated · findings will refresh on the next review", tone: "ok" },
      { at: "", text: "Access pass discarded. Nothing that can open the account is stored.", tone: "ok" },
    ];
    lines.forEach((l, i) => {
      timers.current.push(
        window.setTimeout(() => {
          setLog((cur) => [...cur, { ...l, at: clock() }]);
          if (i === lines.length - 1) {
            markSynced(clientId);
            timers.current.push(window.setTimeout(() => setStep("done"), 500));
          }
        }, 550 * (i + 1)),
      );
    });
  };


  return (
    <Sheet
      open={open}
      onOpenChange={onOpenChange}
      title="Live connection to Dhan"
      description={audience === "client" ? "You stay in control: read-only, 24 hours, revocable" : `${displayName(pf.spec.name)} · how the client connects`}
      className="sm:w-[560px]"
    >
      <div className="space-y-5 p-5">
        {/* progress */}
        <ol className="grid grid-cols-4 gap-1.5" aria-label="Steps">
          {(["explain", "dhan", "sync", "done"] as Step[]).map((s, i) => {
            const idx = ["explain", "dhan", "sync", "done"].indexOf(step);
            return (
              <li key={s} className="space-y-1">
                <div className={cn("h-1.5 rounded-full", i <= idx ? "bg-accent" : "bg-surface-3")} />
                <p className={cn("text-[11px] font-medium", i <= idx ? "text-fg" : "text-fg-2")}>{["Why", "Approve on Dhan", "Live sync", "Done"][i]}</p>
              </li>
            );
          })}
        </ol>

        {step === "explain" && (
          <div className="space-y-4">
            <p className="text-[14px] leading-relaxed text-fg">
              {audience === "client" ? "Connect your Dhan account so your adviser sees your shares as they are today, not as they were on last month's statement." : `${first} connects their Dhan account once; the adviser then sees current shares without waiting for the monthly statement.`}
            </p>
            <ul className="space-y-2.5">
              {[
                [ExternalLink, "You sign in on Dhan's own page", "AI CFO never sees the password or the 6-digit code."],
                [Eye, "Read-only", "It can look at holdings. It has no way to buy, sell or move money."],
                [KeyRound, "A 24-hour access pass", "Dhan gives a temporary pass. AI CFO uses it once and throws it away."],
                [Unplug, "Revocable", "Disconnect any time from the client portal or from Dhan."],
              ].map(([Icon, title, text]) => {
                const I = Icon as typeof Eye;
                return (
                  <li key={title as string} className="flex gap-3 rounded-xl border border-line p-3">
                    <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent">
                      <I className="size-4" aria-hidden />
                    </span>
                    <span>
                      <span className="block text-[13.5px] font-semibold text-fg">{title as string}</span>
                      <span className="block text-[12.5px] text-fg-2">{text as string}</span>
                    </span>
                  </li>
                );
              })}
            </ul>
            <p className="text-[12px] text-fg-2">
              Technical note: this is Dhan's <Term k="Consent flow" /> through their <Term k="API" />. The real app opens dhan.co; this demo simulates that page.
            </p>
            <Button variant="primary" className="h-11 w-full" onClick={() => setStep("dhan")}>
              Continue to Dhan <ArrowRight />
            </Button>
          </div>
        )}

        {step === "dhan" && (
          <div className="space-y-3">
            <p className="rounded-lg bg-warning-soft px-3 py-2 text-[12px] font-medium text-warning-text">Simulated Dhan page for the demo. In the real app this is dhan.co in your browser.</p>
            <div className="overflow-hidden rounded-2xl border border-line-strong bg-surface shadow-card">
              <div className="flex items-center gap-2 border-b border-line bg-surface-2 px-4 py-2.5 text-[12px] text-fg-2">
                <Lock className="size-3.5" aria-hidden /> auth.dhan.co/login/consentApp-login
              </div>
              <div className="space-y-4 p-5">
                <p className="text-[16px] font-semibold text-fg">AI CFO is asking to view your account</p>
                <ul className="space-y-1.5 text-[13px] text-fg-2">
                  <li className="flex items-center gap-2">
                    <Check className="size-4 text-accent" aria-hidden /> View holdings and positions
                  </li>
                  <li className="flex items-center gap-2">
                    <Lock className="size-4 text-fg-2" aria-hidden /> Cannot place, change or cancel orders
                  </li>
                </ul>
                <label className="block text-[12.5px] font-medium text-fg">
                  Enter the 6-digit code from your authenticator app
                  <span className="mt-1.5 flex h-11 items-center gap-2 rounded-xl border border-line bg-surface px-3 focus-within:border-accent">
                    <Smartphone className="size-4 text-fg-2" aria-hidden />
                    <input id="dhan-code" inputMode="numeric" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} placeholder="Any 6 digits in the demo" className="tabular flex-1 bg-transparent text-[15px] tracking-[0.3em] text-fg outline-none placeholder:tracking-normal placeholder:text-fg-2" />
                  </span>
                </label>
                <div className="flex gap-2">
                  <Button variant="outline" className="flex-1" onClick={() => setStep("explain")}>
                    Cancel
                  </Button>
                  <Button variant="primary" className="flex-1" disabled={code.length !== 6} onClick={runSync}>
                    <ShieldCheck /> Approve read-only access
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {(step === "sync" || step === "done") && (
          <div className="space-y-4">
            <div className="rounded-xl border border-line bg-surface-2/60 p-3 font-mono text-[12px]" role="log" aria-live="polite">
              {log.map((l, i) => (
                <p key={i} className="flex gap-2 py-0.5">
                  <span className="text-fg-2">{l.at}</span>
                  <span className={cn(l.tone === "warn" ? "text-warning-text" : l.tone === "ok" ? "text-fg" : "text-fg-2")}>{l.text}</span>
                </p>
              ))}
              {step === "sync" && (
                <p className="flex items-center gap-2 py-0.5 text-fg-2">
                  <CircleDashed className="size-3.5 animate-spin" aria-hidden /> working…
                </p>
              )}
            </div>

            {step === "done" && (
              <>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="good">
                    <span className="size-1.5 rounded-full bg-good" aria-hidden /> Live · synced just now
                  </Badge>
                </div>
                <p className="text-[12.5px] leading-relaxed text-fg-2">The next sync asks the client to approve again. Dhan's access passes last up to 24 hours, and AI CFO keeps none of them.</p>
                <div className="scrollbar-thin overflow-x-auto rounded-xl border border-line">
                  <table className="w-full min-w-[440px] text-[12.5px]">
                    <thead className="bg-surface-2/60 text-left text-[11px] uppercase tracking-wider text-fg-2">
                      <tr>
                        <th className="px-3 py-2 font-semibold">Share</th>
                        <th className="px-3 py-2 text-right font-semibold">Live quantity</th>
                        <th className="px-3 py-2 text-right font-semibold">Statement</th>
                        <th className="px-3 py-2 text-right font-semibold">Value</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line">
                      {dhanHoldings.map((h) => {
                        const st = statement[h.ref];
                        const differs = st !== undefined && st !== h.units;
                        return (
                          <tr key={h.id} className={differs ? "bg-warning-soft/60" : undefined}>
                            <td className="px-3 py-2 text-fg">
                              {h.shortName}
                              <span className="block font-mono text-[11px] text-fg-2">{h.isin}</span>
                            </td>
                            <td className="tabular px-3 py-2 text-right text-fg">{h.units}</td>
                            <td className={cn("tabular px-3 py-2 text-right", differs ? "font-semibold text-warning-text" : "text-fg-2")}>{st ?? "—"}</td>
                            <td className="tabular px-3 py-2 text-right text-fg">{inr(h.value)}</td>
                          </tr>
                        );
                      })}
                      {dhanHoldings.length === 0 && (
                        <tr>
                          <td colSpan={4} className="px-3 py-4 text-center text-fg-2">
                            No shares held at Dhan for this client.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" className="flex-1" onClick={() => { setCode(""); setLog([]); setStep("dhan"); }}>
                    <RefreshCw /> Sync again
                  </Button>
                  <Button variant="primary" className="flex-1" onClick={() => onOpenChange(false)}>
                    Done
                  </Button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </Sheet>
  );
}
