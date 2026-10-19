import { ArrowRight, Bot, BrainCircuit, ChevronRight, Database, GitBranch, ShieldCheck, Wrench } from "lucide-react";
import { useState } from "react";

import { AgentRunSheet } from "@/components/agents/AgentRun";
import { Avatar, Badge, Card, CardHeader } from "@/components/ui";
import { cn } from "@/lib/cn";
import { agentRuns, PIPELINE, runsGenerated } from "@/lib/agentRuns";
import { portfolioById } from "@/lib/engine";
import { useClientName, useVisiblePortfolios } from "@/state/app";

const METRICS = [
  { label: "Retrieval hit@3", value: "1.00", note: "28 golden questions · BM25, bge-small and hybrid", Icon: Database },
  { label: "Advice classifier F1", value: "0.89", note: "5-fold CV · precision 0.94 · recall 0.85", Icon: BrainCircuit },
  { label: "Unsupported numbers", value: "0", note: "across all 12 review runs", Icon: ShieldCheck },
  { label: "Backend tests", value: "101", note: "core, RAG, agents, ML, API", Icon: GitBranch },
];

const kindTone = { tool: "neutral", agent: "ai", guard: "accent" } as const;
const kindIcon = { tool: Wrench, agent: Bot, guard: ShieldCheck } as const;

export function Agents() {
  const visible = useVisiblePortfolios();
  const displayName = useClientName();
  const [open, setOpen] = useState<string | null>(null);
  const runs = visible.map((p) => agentRuns[p.spec.id]).filter((r): r is NonNullable<typeof r> => !!r);

  return (
    <div className="gutter-x mx-auto max-w-[1300px] space-y-5 py-5 sm:py-6">
      <section className="aurora relative overflow-hidden rounded-2xl border border-line p-5 sm:p-7">
        <div className="dot-grid absolute inset-0 opacity-60" aria-hidden />
        <div className="relative grid gap-6 lg:grid-cols-[1.1fr_1fr] lg:items-center">
          <div>
            <p className="eyebrow">Multi-agent review</p>
            <h2 className="mt-1 font-display text-[26px] font-semibold leading-tight text-fg sm:text-[30px]">
              Code computes every number. Agents decide what matters and explain it, with a rule cited for each claim.
            </h2>
            <p className="mt-2 max-w-xl text-[14px] leading-relaxed text-fg-2">
              A LangGraph state graph runs three analyst agents in parallel, then an explainer that retrieves rules (RAG), a compliance judge that combines rules, an ML classifier and an LLM judge, and a verifier that rejects any number not in the evidence.
            </p>
          </div>
          {/* Flow diagram */}
          <div className="rounded-2xl border border-line bg-surface/85 p-4 shadow-card backdrop-blur">
            <div className="grid grid-cols-[1fr_auto_1fr_auto_1fr] items-center gap-1.5 text-center text-[11.5px] font-medium">
              <span className="rounded-lg bg-surface-2 px-2 py-2 text-fg">Snapshot + evidence</span>
              <ArrowRight className="size-4 text-muted" aria-hidden />
              <span className="grid gap-1">
                {["Overlap", "Allocation", "Tax"].map((a) => (
                  <span key={a} className="rounded-lg bg-ai-soft px-2 py-1.5 text-ai">
                    {a} analyst
                  </span>
                ))}
              </span>
              <ArrowRight className="size-4 text-muted" aria-hidden />
              <span className="rounded-lg bg-surface-2 px-2 py-2 text-fg">Rank</span>
            </div>
            <div className="mt-2 grid grid-cols-[1fr_auto_1fr_auto_1fr] items-center gap-1.5 text-center text-[11.5px] font-medium">
              <span className="rounded-lg bg-ai-soft px-2 py-2 text-ai">Explainer + RAG</span>
              <ArrowRight className="size-4 text-muted" aria-hidden />
              <span className="rounded-lg bg-accent-soft px-2 py-2 text-accent">Compliance judge</span>
              <ArrowRight className="size-4 text-muted" aria-hidden />
              <span className="rounded-lg bg-accent-soft px-2 py-2 text-accent">Verifier → drafts</span>
            </div>
            <p className="mt-3 text-center text-[11.5px] text-muted">Sky = agent · Mint = guard · Grey = deterministic code</p>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {METRICS.map(({ label, value, note, Icon }) => (
          <Card key={label} className="p-4">
            <p className="flex items-center gap-1.5 text-[12px] font-medium text-fg-2">
              <Icon className="size-3.5 text-accent" aria-hidden /> {label}
            </p>
            <p className="tabular mt-1 font-display text-[28px] font-semibold text-fg">{value}</p>
            <p className="text-[12px] text-muted">{note}</p>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-12">
        <Card className="lg:col-span-5">
          <CardHeader title="Who does what" description="Every node in the review graph" />
          <ul className="mt-2 divide-y divide-line">
            {PIPELINE.map((a) => {
              const Icon = kindIcon[a.kind];
              return (
                <li key={a.node} className="flex gap-3 px-4 py-3 sm:px-5">
                  <span className={cn("mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg", a.kind === "agent" ? "bg-ai-soft text-ai" : a.kind === "guard" ? "bg-accent-soft text-accent" : "bg-surface-2 text-fg-2")}>
                    <Icon className="size-4" aria-hidden />
                  </span>
                  <div className="min-w-0">
                    <p className="flex flex-wrap items-center gap-1.5 text-[13px] font-semibold text-fg">
                      {a.name} <Badge tone={kindTone[a.kind]}>{a.kind === "tool" ? "code" : a.kind}</Badge>
                    </p>
                    <p className="text-[12.5px] leading-relaxed text-fg-2">{a.role}</p>
                    <p className="text-[11.5px] text-muted">{a.uses}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        </Card>

        <Card className="lg:col-span-7">
          <CardHeader title="Recent review runs" description={`Exported from the Python pipeline · ${runsGenerated.replace("T", " ")}`} />
          <ul className="mt-2 divide-y divide-line">
            {runs.map((r) => {
              const total = r.trace.reduce((s, t) => s + t.ms, 0);
              const kept = r.drafts.filter((d) => d.status === "draft").length;
              const name = displayName(portfolioById[r.client_id]?.spec.name ?? r.client_id);
              return (
                <li key={r.client_id}>
                  <button onClick={() => setOpen(r.client_id)} className="flex w-full cursor-pointer items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-2/60 sm:px-5">
                    <Avatar name={name} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[13.5px] font-medium text-fg">{name}</p>
                      <p className="text-[12px] text-muted">
                        {kept} drafts · {r.drafts.length - kept} dropped · {r.trace.length} nodes · <span className="tabular">{total.toFixed(1)} ms</span>
                      </p>
                    </div>
                    <div className="hidden gap-1 sm:flex">
                      {r.drafts.slice(0, 5).map((d) => (
                        <span key={d.id} className={cn("h-6 w-1.5 rounded-full", d.severity === "high" ? "bg-critical" : d.severity === "medium" ? "bg-warning" : "bg-line-strong")} title={d.title} />
                      ))}
                    </div>
                    <ChevronRight className="size-4 text-muted" aria-hidden />
                  </button>
                </li>
              );
            })}
          </ul>
        </Card>
      </div>

      <AgentRunSheet clientId={open} open={!!open} onOpenChange={(o) => !o && setOpen(null)} />
    </div>
  );
}
