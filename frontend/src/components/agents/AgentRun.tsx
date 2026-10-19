import { Bot, Check, CircleDashed, Cpu, FileText, Play, ShieldCheck, Sparkles, Wrench } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge, Button, Sheet, SeverityBadge } from "@/components/ui";
import { cn } from "@/lib/cn";
import { type AgentRun, agentRuns, PIPELINE, type TraceEvent } from "@/lib/agentRuns";
import { portfolioById } from "@/lib/engine";
import { useClientName } from "@/state/app";

const kindStyle = {
  tool: { Icon: Wrench, ring: "border-line-strong", chip: "bg-surface-2 text-fg-2", label: "Deterministic" },
  agent: { Icon: Bot, ring: "border-ai/50", chip: "bg-ai-soft text-ai", label: "Agent" },
  guard: { Icon: ShieldCheck, ring: "border-accent/50", chip: "bg-accent-soft text-accent", label: "Guard" },
} as const;

function NodeCard({ ev, state, onClick, selected }: { ev?: TraceEvent; state: "idle" | "running" | "done"; onClick: () => void; selected: boolean; }) {
  const info = PIPELINE.find((p) => p.node === ev?.node);
  if (!info) return null;
  const k = kindStyle[info.kind];
  return (
    <button
      onClick={onClick}
      className={cn(
        "group relative w-full cursor-pointer rounded-xl border bg-surface p-3 text-left transition-all",
        k.ring,
        state === "idle" && "opacity-45",
        state === "running" && "shadow-pop ring-2 ring-ai/40",
        selected && "ring-2 ring-accent",
      )}
    >
      <div className="flex items-center gap-2">
        <span className={cn("flex size-7 items-center justify-center rounded-lg [&_svg]:size-4", k.chip)}>
          {state === "running" ? <CircleDashed className="animate-spin" /> : state === "done" ? <k.Icon /> : <k.Icon />}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[12.5px] font-semibold text-fg">{info.name}</span>
          <span className="block text-[11px] text-muted">{k.label}</span>
        </span>
        {state === "done" && <Check className="size-4 text-accent" aria-label="Done" />}
      </div>
      {state === "done" && ev && (
        <p className="mt-2 line-clamp-2 text-[12px] leading-snug text-fg-2">
          {ev.summary} <span className="tabular text-muted">· {ev.ms.toFixed(1)} ms</span>
        </p>
      )}
    </button>
  );
}

/** Visual replay of one review run through the LangGraph pipeline. */
export function AgentRunView({ run }: { run: AgentRun }) {
  const displayName = useClientName();
  const name = displayName(portfolioById[run.client_id]?.spec.name ?? run.client_id);
  const order = run.trace;
  const [step, setStep] = useState(order.length);
  const [selected, setSelected] = useState<string>("explainer");

  const replay = () => {
    setStep(0);
    order.forEach((_, i) => setTimeout(() => setStep(i + 1), 380 * (i + 1)));
  };
  useEffect(() => {
    replay();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run.client_id]);

  const stateOf = (node: string) => {
    const i = order.findIndex((t) => t.node === node);
    const analysts = ["overlap_analyst", "allocation_analyst", "tax_analyst"];
    const firstAnalyst = order.findIndex((t) => analysts.includes(t.node));
    const idx = analysts.includes(node) ? firstAnalyst : i;
    if (step > idx + (analysts.includes(node) ? 2 : 0)) return "done" as const;
    if (step === idx || (analysts.includes(node) && step >= firstAnalyst && step <= firstAnalyst + 2)) return "running" as const;
    return "idle" as const;
  };
  const ev = (node: string) => order.find((t) => t.node === node);
  const sel = ev(selected);
  const done = step >= order.length;
  const totalMs = order.reduce((s, t) => s + t.ms, 0);

  return (
    <div className="space-y-5 p-4 sm:p-5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="accent">
          <Cpu aria-hidden /> LangGraph · 9 nodes
        </Badge>
        <Badge tone="outline" className="tabular">
          {totalMs.toFixed(1)} ms total
        </Badge>
        <Badge tone="ai">
          <Sparkles aria-hidden /> no model connected: agents used firm policy
        </Badge>
        <span className="flex-1" />
        <Button size="sm" variant="outline" onClick={replay}>
          <Play /> Replay
        </Button>
      </div>

      {/* Graph */}
      <div className="grid gap-2.5">
        {["load_snapshot", "compute_evidence"].map((n) => (
          <NodeCard key={n} ev={ev(n)} state={stateOf(n)} onClick={() => setSelected(n)} selected={selected === n} />
        ))}
        <div className="relative rounded-2xl border border-dashed border-ai/40 bg-ai-soft/40 p-2.5">
          <p className="mb-2 px-1 text-[11px] font-semibold uppercase tracking-wider text-ai">Run in parallel</p>
          <div className="grid gap-2.5 sm:grid-cols-3">
            {["overlap_analyst", "allocation_analyst", "tax_analyst"].map((n) => (
              <NodeCard key={n} ev={ev(n)} state={stateOf(n)} onClick={() => setSelected(n)} selected={selected === n} />
            ))}
          </div>
        </div>
        <div className="grid gap-2.5 sm:grid-cols-2">
          {["rank", "explainer", "compliance", "verifier"].map((n) => (
            <NodeCard key={n} ev={ev(n)} state={stateOf(n)} onClick={() => setSelected(n)} selected={selected === n} />
          ))}
        </div>
      </div>

      {sel && (
        <div className="rounded-xl border border-line bg-surface-2/60 p-3.5">
          <p className="text-[12px] font-semibold text-fg">{PIPELINE.find((p) => p.node === sel.node)?.name}</p>
          <p className="mt-0.5 text-[12px] text-fg-2">{PIPELINE.find((p) => p.node === sel.node)?.role}</p>
          <pre className="scrollbar-thin mt-2 max-h-40 overflow-auto rounded-lg bg-surface p-2.5 font-mono text-[11px] leading-relaxed text-fg-2">
            {JSON.stringify(sel.detail, null, 1)}
          </pre>
        </div>
      )}

      {/* Drafts */}
      <div className={cn("space-y-2.5 transition-opacity", done ? "opacity-100" : "opacity-40")}>
        <p className="eyebrow">Drafts produced ({run.drafts.filter((d) => d.status === "draft").length})</p>
        {run.drafts.map((d) => (
          <div key={d.id} className="rounded-xl border border-line bg-surface p-3.5">
            <div className="flex flex-wrap items-center gap-1.5">
              <SeverityBadge severity={d.severity} />
              <Badge tone="ai">
                <Bot aria-hidden /> {d.agent.replace("_", " ")}
              </Badge>
              <Badge tone={d.verifier.passed ? "good" : "critical"}>{d.verifier.passed ? "Verified" : "Dropped"}</Badge>
              <Badge tone="outline" className="tabular">
                advice p = {d.compliance.classifier.toFixed(2)}
              </Badge>
            </div>
            <p className="mt-2 text-[13px] leading-relaxed text-fg">{d.text.replaceAll("{client}", name)}</p>
            {d.citations[0] && (
              <p className="mt-2 flex items-start gap-1.5 text-[12px] text-fg-2">
                <FileText className="mt-0.5 size-3.5 shrink-0 text-accent" aria-hidden />
                <span>
                  [1] {d.citations[0].issuer} · {d.citations[0].section}
                </span>
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export function AgentRunSheet({ clientId, open, onOpenChange }: { clientId: string | null; open: boolean; onOpenChange: (o: boolean) => void }) {
  const displayName = useClientName();
  const run = clientId ? agentRuns[clientId] : undefined;
  return (
    <Sheet
      open={open && !!run}
      onOpenChange={onOpenChange}
      title="Agent run"
      description={run ? `${displayName(portfolioById[run.client_id]?.spec.name ?? "")} · snapshot ${run.as_of} · ${run.engine}` : undefined}
      className="sm:w-[640px]"
    >
      {run && <AgentRunView run={run} />}
    </Sheet>
  );
}
