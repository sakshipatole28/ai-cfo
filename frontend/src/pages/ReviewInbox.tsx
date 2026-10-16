import { Link } from "@tanstack/react-router";
import {
  ArrowLeft,
  BadgeCheck,
  BookOpen,
  Check,
  CheckCircle2,
  Clock,
  Eye,
  FileText,
  Keyboard,
  ShieldCheck,
  Sparkles,
  Undo2,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { FindingBody } from "@/components/FindingBody";
import { Logo } from "@/components/shell/Logo";
import { Avatar, Badge, Button, buttonClass, Card, EmptyState, Kbd, SeverityBadge, severityBar, Sheet } from "@/components/ui";
import { firm, TODAY } from "@/data/demo";
import { cn } from "@/lib/cn";
import { type Finding, portfolios } from "@/lib/engine";
import { fmtDate, inrShort } from "@/lib/format";
import { type Decision, useApp, useClientName } from "@/state/app";

const decisionLabel: Record<Decision, { label: string; tone: "good" | "neutral" | "warning"; Icon: typeof Check }> = {
  accepted: { label: "Accepted", tone: "good", Icon: Check },
  dismissed: { label: "Dismissed", tone: "neutral", Icon: X },
  snoozed: { label: "Snoozed 30 days", tone: "warning", Icon: Clock },
};

export function ReviewInbox() {
  const { decisions, decide, approved, approve, explain, aiEnabled } = useApp();
  const displayName = useClientName();
  const queue = useMemo(() => portfolios.filter((p) => p.findings.length > 0 && !approved[p.spec.id]), [approved]);
  const [clientId, setClientId] = useState<string | undefined>(queue[0]?.spec.id);
  const [findingId, setFindingId] = useState<string | undefined>(queue[0]?.findings[0]?.id);
  const [mobileView, setMobileView] = useState<"clients" | "findings" | "detail">("clients");
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState(false);
  const [showKeys, setShowKeys] = useState(false);

  const pf = portfolios.find((p) => p.spec.id === clientId);
  const findings = useMemo(() => pf?.findings ?? [], [pf]);
  const current: Finding | undefined = findings.find((f) => f.id === findingId) ?? findings[0];
  const remaining = findings.filter((f) => !decisions[f.id]).length;
  const name = pf ? displayName(pf.spec.name) : "";

  const selectClient = (id: string) => {
    setClientId(id);
    setFindingId(portfolios.find((p) => p.spec.id === id)?.findings[0]?.id);
    setMobileView("findings");
  };

  const act = useCallback(
    (d: Decision) => {
      if (!current) return;
      decide(current.id, d);
      const idx = findings.findIndex((f) => f.id === current.id);
      const next = findings.slice(idx + 1).find((f) => !decisions[f.id]) ?? findings.find((f) => !decisions[f.id] && f.id !== current.id);
      if (next) setFindingId(next.id);
      toast(decisionLabel[d].label, {
        description: current.title,
        action: { label: "Undo", onClick: () => decide(current.id, null) },
      });
    },
    [current, decide, decisions, findings],
  );

  const doApprove = useCallback(() => {
    if (!pf || remaining > 0) return;
    approve(pf.spec.id);
    setPreview(false);
    toast.success(`Review approved for ${name}`, { description: "Report rendered in your browser and logged to the audit trail." });
    const next = queue.find((p) => p.spec.id !== pf.spec.id);
    if (next) {
      setClientId(next.spec.id);
      setFindingId(next.findings[0]?.id);
    }
    setMobileView("clients");
  }, [pf, remaining, approve, name, queue]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.closest("input, textarea, [contenteditable=true], [role=dialog]")) return;
      if (!current) return;
      const idx = findings.findIndex((f) => f.id === current.id);
      const k = e.key.toLowerCase();
      if (k === "j" && findings[idx + 1]) setFindingId(findings[idx + 1]!.id);
      else if (k === "k" && idx > 0) setFindingId(findings[idx - 1]!.id);
      else if (k === "a") act("accepted");
      else if (k === "d") act("dismissed");
      else if (k === "s") act("snoozed");
      else if (k === "e" && current.evidence[0]) explain(current.evidence[0]);
      else if (k === "?") setShowKeys((v) => !v);
      else if (k === "enter" && (e.ctrlKey || e.metaKey)) doApprove();
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [current, findings, act, explain, doApprove]);

  if (queue.length === 0) {
    return (
      <EmptyState icon={<CheckCircle2 />} title="Inbox zero">
        Every review is approved. New drafts appear after the next weekly run or when you run a review from a client page.
      </EmptyState>
    );
  }

  const clientList = (
    <div className="flex h-full flex-col">
      <div className="flex h-11 items-center justify-between border-b border-line px-4">
        <p className="text-[12px] font-semibold uppercase tracking-wider text-muted">Clients · {queue.length}</p>
      </div>
      <ul className="scrollbar-thin flex-1 overflow-y-auto p-2">
        {queue.map((p) => {
          const open = p.findings.filter((f) => !decisions[f.id]).length;
          const high = p.findings.some((f) => f.severity === "high" && !decisions[f.id]);
          return (
            <li key={p.spec.id}>
              <button
                onClick={() => selectClient(p.spec.id)}
                className={cn(
                  "flex w-full cursor-pointer items-center gap-3 rounded-lg px-2.5 py-2.5 text-left transition-colors",
                  p.spec.id === clientId ? "bg-accent-soft" : "hover:bg-surface-2",
                )}
              >
                <Avatar name={displayName(p.spec.name)} className="size-8" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13.5px] font-medium text-fg">{displayName(p.spec.name)}</span>
                  <span className="block text-[12px] text-muted">
                    {open ? `${open} of ${p.findings.length} to decide` : "Ready to approve"}
                  </span>
                </span>
                {high && <span className="size-2 rounded-full bg-critical" aria-label="Has high severity" />}
                {!open && <BadgeCheck className="size-4 text-good" aria-hidden />}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );

  const findingList = (
    <div className="flex h-full flex-col">
      <div className="flex h-11 items-center gap-2 border-b border-line px-4">
        <button className="cursor-pointer text-muted lg:hidden" onClick={() => setMobileView("clients")} aria-label="Back to clients">
          <ArrowLeft className="size-4" />
        </button>
        <p className="flex-1 truncate text-[13px] font-semibold text-fg">{name}</p>
        {pf && <span className="tabular text-[12px] text-muted">{inrShort(pf.total)}</span>}
      </div>
      <ul className="scrollbar-thin flex-1 space-y-1.5 overflow-y-auto p-2">
        {findings.map((f) => {
          const d = decisions[f.id];
          return (
            <li key={f.id}>
              <button
                onClick={() => {
                  setFindingId(f.id);
                  setMobileView("detail");
                }}
                className={cn(
                  "relative flex w-full cursor-pointer gap-3 overflow-hidden rounded-lg border p-3 pl-4 text-left transition-colors",
                  f.id === current?.id ? "border-accent bg-surface shadow-card" : "border-transparent hover:bg-surface-2",
                  d && "opacity-60",
                )}
              >
                <span className={cn("absolute inset-y-2 left-1.5 w-1 rounded-full", severityBar[f.severity])} aria-hidden />
                <span className="min-w-0 flex-1">
                  <span className="block text-[13px] font-medium text-fg">{f.title}</span>
                  <span className="mt-1 flex flex-wrap items-center gap-1.5">
                    <SeverityBadge severity={f.severity} />
                    {d && (
                      <Badge tone={decisionLabel[d].tone}>
                        {decisionLabel[d].label}
                      </Badge>
                    )}
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      <ApproveBar remaining={remaining} total={findings.length} onPreview={() => setPreview(true)} onApprove={doApprove} />
    </div>
  );

  const detail = current && pf && (
    <div className="flex h-full flex-col">
      <div className="flex h-11 items-center gap-2 border-b border-line px-4 sm:px-6">
        <button className="cursor-pointer text-muted lg:hidden" onClick={() => setMobileView("findings")} aria-label="Back to findings">
          <ArrowLeft className="size-4" />
        </button>
        <Badge tone="ai">
          <Sparkles aria-hidden /> AI draft
        </Badge>
        <span className="flex-1" />
        <button onClick={() => setShowKeys(true)} className="hidden cursor-pointer items-center gap-1.5 text-[12px] text-muted hover:text-fg md:flex">
          <Keyboard className="size-3.5" aria-hidden /> Shortcuts <Kbd>?</Kbd>
        </button>
      </div>
      <div className="scrollbar-thin flex-1 overflow-y-auto">
        <div className="mx-auto max-w-2xl space-y-5 px-4 py-5 sm:px-6">
          <div>
            <SeverityBadge severity={current.severity} />
            <h2 className="mt-2 text-[19px] font-semibold tracking-tight text-fg">{current.title}</h2>
            <p className="mt-2.5 text-[14.5px] leading-[1.7] text-fg-2">
              <FindingBody body={current.body} name={name} />
            </p>
            <p className="mt-2 text-[12px] text-muted">Highlighted numbers are computed. Select one to see the formula, inputs and sources.</p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <Card className="p-3.5">
              <p className="eyebrow flex items-center gap-1.5">
                <BookOpen className="size-3.5" aria-hidden /> Evidence and rules
              </p>
              <ul className="mt-2 space-y-1.5">
                {current.evidence.map((e) => (
                  <li key={e.title}>
                    <button onClick={() => explain(e)} className="flex w-full cursor-pointer items-center gap-2 rounded-md text-left text-[12.5px] text-fg hover:text-accent">
                      <Eye className="size-3.5 shrink-0 text-muted" aria-hidden />
                      <span className="truncate">{e.title}</span>
                    </button>
                  </li>
                ))}
                {current.evidence[0]?.citations.map((c) => (
                  <li key={c.id} className="flex items-start gap-2 text-[12.5px] text-fg-2">
                    <FileText className="mt-0.5 size-3.5 shrink-0 text-muted" aria-hidden />
                    <span>
                      {c.issuer}: {c.section}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
            <Card className="p-3.5">
              <p className="eyebrow flex items-center gap-1.5">
                <ShieldCheck className="size-3.5" aria-hidden /> Compliance checks
              </p>
              <dl className="mt-2 space-y-1.5 text-[12.5px]">
                {[
                  ["Wording rules (RIA profile)", "Passed"],
                  ["Advice classifier", `p = ${current.compliance.classifier.toFixed(2)} · below 0.30`],
                  ["LLM judge", current.compliance.judge === "pass" ? "Passed" : "Not needed"],
                  ["Number verifier", current.compliance.rewrites ? `Passed after ${current.compliance.rewrites} rewrite` : "Passed first time"],
                ].map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between gap-2">
                    <dt className="text-fg-2">{k}</dt>
                    <dd className="flex items-center gap-1 text-right text-fg">
                      <CheckCircle2 className="size-3.5 text-good" aria-hidden /> {v}
                    </dd>
                  </div>
                ))}
              </dl>
            </Card>
          </div>

          <div>
            <label htmlFor={`note-${current.id}`} className="text-[12.5px] font-medium text-fg">
              Your rationale <span className="font-normal text-muted">(kept with the record of advice)</span>
            </label>
            <textarea
              id={`note-${current.id}`}
              value={notes[current.id] ?? ""}
              onChange={(e) => setNotes((n) => ({ ...n, [current.id]: e.target.value }))}
              placeholder="e.g. Discussed on call; client prefers to keep the index fund for low cost."
              rows={2}
              className="mt-1.5 w-full resize-y rounded-lg border border-line bg-surface px-3 py-2 text-[13px] text-fg outline-none placeholder:text-muted focus:border-accent"
            />
          </div>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2 border-t border-line bg-surface px-4 py-3 sm:px-6">
        {decisions[current.id] ? (
          <>
            <Badge tone={decisionLabel[decisions[current.id]!].tone}>{decisionLabel[decisions[current.id]!].label}</Badge>
            <Button size="sm" variant="ghost" onClick={() => decide(current.id, null)}>
              <Undo2 /> Undo
            </Button>
          </>
        ) : (
          <>
            <Button variant="primary" size="sm" onClick={() => act("accepted")} >
              <Check /> Accept <Kbd className="hidden border-white/30 bg-white/10 text-accent-fg md:inline-flex">A</Kbd>
            </Button>
            <Button variant="outline" size="sm" onClick={() => act("dismissed")}>
              <X /> Dismiss <Kbd className="hidden md:inline-flex">D</Kbd>
            </Button>
            <Button variant="ghost" size="sm" onClick={() => act("snoozed")}>
              <Clock /> Snooze <Kbd className="hidden md:inline-flex">S</Kbd>
            </Button>
          </>
        )}
        <span className="flex-1" />
        <Link to="/clients/$clientId" params={{ clientId: pf.spec.id }} className={buttonClass("ghost", "sm")}>
          Open client
        </Link>
      </div>
    </div>
  );

  return (
    <div className="h-[calc(100%-0px)] min-h-[560px]">
      {!aiEnabled && (
        <div className="gutter-x border-b border-critical/30 bg-critical-soft py-2 text-[12.5px] text-critical-text">
          AI drafting is switched off. Existing drafts stay reviewable; no new drafts will be generated.
        </div>
      )}
      <div className="grid h-full lg:grid-cols-[260px_340px_minmax(0,1fr)]">
        <aside className={cn("min-h-0 border-r border-line bg-surface", mobileView === "clients" ? "block" : "hidden", "lg:block")}>{clientList}</aside>
        <section className={cn("min-h-0 border-r border-line bg-bg", mobileView === "findings" ? "block" : "hidden", "lg:block")}>{findingList}</section>
        <section className={cn("min-h-0 bg-surface", mobileView === "detail" ? "block" : "hidden", "lg:block")}>{detail}</section>
      </div>

      <Sheet
        open={preview}
        onOpenChange={setPreview}
        title="Client report preview"
        description="Rendered in your browser; the server never sees the client's name"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setPreview(false)}>
              Keep editing
            </Button>
            <Button variant="primary" onClick={doApprove} disabled={remaining > 0}>
              <BadgeCheck /> Approve and finalise
            </Button>
          </div>
        }
      >
        {pf && (
          <article className="m-4 rounded-xl border border-line bg-surface p-5 sm:m-5">
            <header className="flex items-center justify-between border-b border-line pb-4">
              <div className="flex items-center gap-2.5">
                <Logo size={28} />
                <div>
                  <p className="text-[13px] font-semibold text-fg">{firm.name}</p>
                  <p className="text-[11px] text-muted">SEBI RIA {firm.registration}</p>
                </div>
              </div>
              <p className="text-[11.5px] text-muted">{fmtDate(TODAY)}</p>
            </header>
            <h3 className="mt-4 text-[17px] font-semibold text-fg">Portfolio review for {name}</h3>
            <p className="mt-1 text-[12.5px] text-muted">
              Portfolio {inrShort(pf.total)} · {pf.spec.risk} model · data as of {fmtDate("2026-09-30")} (statements) and {fmtDate("2026-10-16")} (Dhan)
            </p>
            <ol className="mt-4 space-y-3">
              {findings
                .filter((f) => decisions[f.id] === "accepted")
                .map((f, i) => (
                  <li key={f.id} className="text-[13px] leading-relaxed text-fg-2">
                    <p className="font-semibold text-fg">
                      {i + 1}. {f.title}
                    </p>
                    <FindingBody body={f.body} name={name} />
                    {notes[f.id] && <p className="mt-1 text-[12.5px] italic text-muted">Adviser's note: {notes[f.id]}</p>}
                  </li>
                ))}
            </ol>
            {findings.every((f) => decisions[f.id] !== "accepted") && <p className="mt-4 text-[13px] text-muted">No findings accepted yet.</p>}
            <footer className="mt-5 border-t border-line pt-3 text-[11px] leading-relaxed text-muted">
              Figures are computed from the statements listed above; every number can be traced to its source. This review was prepared by your adviser, who approved
              its contents. It is not an offer or solicitation.
            </footer>
          </article>
        )}
      </Sheet>

      <Sheet open={showKeys} onOpenChange={setShowKeys} title="Keyboard shortcuts" side="right">
        <dl className="divide-y divide-line px-5">
          {[
            ["J / K", "Next / previous finding"],
            ["A", "Accept"],
            ["D", "Dismiss"],
            ["S", "Snooze 30 days"],
            ["E", "Explain the first number"],
            ["Ctrl + Enter", "Approve review (when all decided)"],
            ["Ctrl + K", "Command menu"],
          ].map(([k, v]) => (
            <div key={k} className="flex items-center justify-between py-3 text-[13px]">
              <dd className="text-fg-2">{v}</dd>
              <dt>
                <Kbd>{k}</Kbd>
              </dt>
            </div>
          ))}
        </dl>
      </Sheet>
    </div>
  );
}

function ApproveBar({ remaining, total, onPreview, onApprove }: { remaining: number; total: number; onPreview: () => void; onApprove: () => void }) {
  const done = total - remaining;
  return (
    <div className="space-y-2 border-t border-line bg-surface p-3">
      <div className="flex items-center justify-between text-[12px] text-muted">
        <span>
          {done} of {total} decided
        </span>
        {remaining === 0 && <span className="font-medium text-good-text">Ready to approve</span>}
      </div>
      <div className="flex h-1.5 overflow-hidden rounded-full bg-surface-3">
        <div className="h-full rounded-full bg-accent transition-[width]" style={{ width: `${(done / Math.max(total, 1)) * 100}%` }} />
      </div>
      <div className="flex gap-2">
        <Button size="sm" variant="outline" className="flex-1" onClick={onPreview}>
          <Eye /> Preview
        </Button>
        <Button size="sm" variant="primary" className="flex-1" onClick={onApprove} disabled={remaining > 0}>
          <BadgeCheck /> Approve
        </Button>
      </div>
    </div>
  );
}
