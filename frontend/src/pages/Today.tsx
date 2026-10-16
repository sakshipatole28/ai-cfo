import { Link } from "@tanstack/react-router";
import {
  ArrowRight,
  Bot,
  CalendarClock,
  CheckCircle2,
  FileWarning,
  Gauge,
  Inbox,
  Link2Off,
  Play,
  ShieldCheck,
  Upload,
} from "lucide-react";
import type { ReactNode } from "react";
import { toast } from "sonner";

import { Sparkline } from "@/components/charts";
import { usePendingCount } from "@/components/shell/AppShell";
import { Avatar, Badge, Button, buttonClass, Card, CardHeader, Tip } from "@/components/ui";
import { aumHistoryFactors, firm, FY_LABEL, TODAY } from "@/data/demo";
import { cn } from "@/lib/cn";

import { daysBetween, fmtDate, inr, inrShort, signedPts } from "@/lib/format";
import { useApp, useClientName, useVisiblePortfolios } from "@/state/app";

function Kpi({ label, value, sub, children, to }: { label: string; value: ReactNode; sub: ReactNode; children?: ReactNode; to?: string }) {
  const body = (
    <Card className={cn("flex h-full flex-col gap-1 p-4 sm:p-5", to && "transition-colors hover:border-line-strong")}>
      <p className="eyebrow">{label}</p>
      <p className="text-[26px] font-semibold leading-tight tracking-tight text-fg">{value}</p>
      <p className="text-[12.5px] text-muted">{sub}</p>
      {children}
    </Card>
  );
  return to ? (
    <Link to={to} className="block min-w-0 rounded-xl">
      {body}
    </Link>
  ) : (
    body
  );
}

export function Today() {
  const { decisions, approved, openCopilot, me } = useApp();
  const portfolios = useVisiblePortfolios();
  const allFindings = portfolios.flatMap((p) => p.findings);
  const bookAum = portfolios.reduce((s, p) => s + p.total, 0);
  const displayName = useClientName();
  const pending = usePendingCount();
  const open = allFindings.filter((f) => !decisions[f.id] && !approved[f.clientId]);
  const high = open.filter((f) => f.severity === "high").length;
  const due = portfolios.filter((p) => daysBetween(p.spec.lastReview, TODAY) > 90);
  const expired = portfolios.filter((p) => p.spec.dhan === "expired");
  const lots = portfolios
    .flatMap((p) => p.upcomingLots.map((u) => ({ p, ...u })))
    .sort((a, b) => a.lot.daysToLong - b.lot.daysToLong);
  const drifters = [...portfolios].sort((a, b) => Math.abs(b.drift.Equity) - Math.abs(a.drift.Equity)).slice(0, 6);
  const maxDrift = Math.max(...drifters.map((p) => Math.abs(p.drift.Equity)), 10);

  const byClient = new Map<string, number>();
  for (const f of open) byClient.set(f.clientId, (byClient.get(f.clientId) ?? 0) + 1);
  const topReview = [...byClient.entries()]
    .map(([id, n]) => ({ p: portfolios.find((x) => x.spec.id === id)!, n, high: open.filter((f) => f.clientId === id && f.severity === "high").length }))
    .sort((a, b) => b.high - a.high || b.n - a.n)
    .slice(0, 2);

  const actions = [
    ...topReview.map(({ p, n, high: h }) => ({
      icon: <Inbox />,
      tone: "accent" as const,
      title: `Approve review for ${displayName(p.spec.name)}`,
      meta: `${n} drafts${h ? ` · ${h} high severity` : ""}`,
      cta: "Review",
      to: "/review" as const,
      clientId: undefined as string | undefined,
    })),
    ...expired.slice(0, 1).map((p) => ({
      icon: <Link2Off />,
      tone: "warning" as const,
      title: `Reconnect Dhan for ${displayName(p.spec.name)}`,
      meta: "Token expired · holdings shown from last sync",
      cta: "Reconnect",
      to: "/clients/$clientId" as const,
      clientId: p.spec.id as string | undefined,
    })),
    {
      icon: <FileWarning />,
      tone: "warning" as const,
      title: `Resolve Infosys quantity mismatch for ${displayName("Rohan Deshpande")}`,
      meta: "Dhan 80 vs CDSL CAS 75 · opened 16 Oct",
      cta: "Resolve",
      to: "/data" as const,
      clientId: undefined as string | undefined,
    },
  ];

  return (
    <div className="gutter-x mx-auto max-w-[1400px] space-y-5 py-5 sm:py-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-[13px] text-muted">
            {fmtDate(TODAY)} · {FY_LABEL}
          </p>
          <h2 className="mt-0.5 font-display text-[26px] font-semibold text-fg sm:text-[32px]">
            Good afternoon, {(me?.name ?? firm.advisor.name).split(" ")[0]}
          </h2>
          <p className="mt-1 text-[13.5px] text-fg-2">
            {pending} drafts are waiting for you. {due.length} clients are past their 90-day review.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => toast("Upload opens the CAS parser", { description: "In production the PDF is parsed in your browser." })}>
            <Upload /> Upload CAS
          </Button>
          <Button variant="primary" onClick={() => toast.success(`Reviews queued for ${due.length} clients`, { description: "Drafts will appear in the Review inbox." })}>
            <Play /> Run due reviews
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 lg:gap-4">
        <Kpi label={me?.role === "Adviser" ? "Your book" : "Firm book"} value={inrShort(bookAum)} sub={<span className="text-good-text">+{((1 / aumHistoryFactors[0]! - 1) * 100).toFixed(1)}% over 12 months</span>}>
          <Sparkline values={aumHistoryFactors.map((f) => f * bookAum)} label="Book value, last 12 months" />
        </Kpi>
        <Kpi label="Awaiting approval" value={pending} sub={`${high} high severity · ${byClient.size} clients`} to="/review">
          <div className="mt-auto flex gap-1 pt-3">
            {(["high", "medium", "low"] as const).map((s) => {
              const n = open.filter((f) => f.severity === s).length;
              return (
                <Tip key={s} label={`${n} ${s}`}>
                  <div className={cn("h-1.5 rounded-full", s === "high" ? "bg-critical" : s === "medium" ? "bg-warning" : "bg-line-strong")} style={{ flex: Math.max(n, 0.3) }} />
                </Tip>
              );
            })}
          </div>
        </Kpi>
        <Kpi label="Due for review" value={due.length} sub="Last review over 90 days ago" to="/clients">
          <div className="mt-auto flex -space-x-1.5 pt-3">
            {due.slice(0, 5).map((p) => (
              <Avatar key={p.spec.id} name={displayName(p.spec.name)} className="size-7 border-2 border-surface text-[10px]" />
            ))}
          </div>
        </Kpi>
        <Kpi label="Data freshness" value={`${Math.max(...portfolios.map((p) => p.freshnessDays))} days`} sub={`Oldest statement 30 Sep · ${expired.length} Dhan reconnects`} to="/data">
          <div className="mt-auto flex items-center gap-1.5 pt-3 text-[12px] text-muted">
            <CheckCircle2 className="size-3.5 text-good" aria-hidden /> All statements passed totals check
          </div>
        </Kpi>
      </div>

      <div className="grid gap-4 lg:grid-cols-12">
        <Card className="lg:col-span-7">
          <CardHeader title="Next best actions" description="Ranked by severity, money at stake and deadlines" />
          <ul className="mt-3 divide-y divide-line">
            {actions.map((a) => (
              <li key={a.title} className="flex items-center gap-3 px-4 py-3 sm:px-5">
                <span
                  className={cn(
                    "flex size-9 shrink-0 items-center justify-center rounded-lg [&_svg]:size-[18px]",
                    a.tone === "accent" ? "bg-accent-soft text-accent" : "bg-warning-soft text-warning-text",
                  )}
                >
                  {a.icon}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13.5px] font-medium text-fg">{a.title}</p>
                  <p className="truncate text-[12.5px] text-muted">{a.meta}</p>
                </div>
                {a.clientId ? (
                  <Link to="/clients/$clientId" params={{ clientId: a.clientId }} className={buttonClass("outline", "sm")}>
                    {a.cta}
                  </Link>
                ) : (
                  <Link to={a.to as "/review" | "/data"} className={buttonClass(a.tone === "accent" ? "primary" : "outline", "sm")}>
                    {a.cta}
                  </Link>
                )}
              </li>
            ))}
          </ul>
        </Card>

        <Card className="lg:col-span-5">
          <CardHeader title="Tax calendar" description="Lots turning long-term in the next 30 days" action={<CalendarClock className="size-4 text-muted" />} />
          <ul className="mt-3 space-y-1 px-2 pb-3">
            {lots.slice(0, 5).map(({ p, position, lot }) => (
              <li key={lot.id}>
                <Link
                  to="/clients/$clientId"
                  params={{ clientId: p.spec.id }}
                  className="flex items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-surface-2"
                >
                  <div className="flex w-12 shrink-0 flex-col items-center rounded-lg border border-line py-1">
                    <span className="text-[10px] font-semibold uppercase text-muted">{fmtDate(lot.longTermOn).split(" ")[1]}</span>
                    <span className="tabular text-[16px] font-semibold leading-none text-fg">{fmtDate(lot.longTermOn).split(" ")[0]}</span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-medium text-fg">{displayName(p.spec.name)}</p>
                    <p className="truncate text-[12px] text-muted">
                      {position.shortName} · gain {inr(lot.gain)}
                    </p>
                  </div>
                  <Badge tone={lot.daysToLong <= 14 ? "warning" : "neutral"}>{lot.daysToLong} days</Badge>
                </Link>
              </li>
            ))}
          </ul>
        </Card>

        <Card className="lg:col-span-7">
          <CardHeader title="Equity drift across the book" description="Actual equity share minus each client's model" action={<Gauge className="size-4 text-muted" />} />
          <div className="space-y-2.5 px-4 pb-5 pt-4 sm:px-5">
            {drifters.map((p) => {
              const d = p.drift.Equity;
              const w = (Math.abs(d) / maxDrift) * 50;
              return (
                <Link
                  key={p.spec.id}
                  to="/clients/$clientId"
                  params={{ clientId: p.spec.id }}
                  className="grid grid-cols-[minmax(0,140px)_1fr_64px] items-center gap-3 rounded-md text-[12.5px] hover:opacity-90"
                >
                  <span className="truncate text-fg-2">{displayName(p.spec.name)}</span>
                  <span className="relative h-5 rounded bg-surface-2">
                    <span className="absolute inset-y-0.5 left-1/2 w-px bg-line-strong" />
                    <span
                      className="absolute inset-y-1 rounded-[3px]"
                      style={{ left: d < 0 ? `${50 - w}%` : "50%", width: `${w}%`, background: d < 0 ? "var(--div-neg)" : "var(--div-pos)" }}
                    />
                  </span>
                  <span className={cn("tabular text-right font-medium", Math.abs(d) >= 5 ? "text-fg" : "text-muted")}>{signedPts(d)}</span>
                </Link>
              );
            })}
          </div>
        </Card>

        <Card className="lg:col-span-5">
          <CardHeader
            title="AI quality, last night"
            description="Nightly evaluation on synthetic portfolios"
            action={
              <Badge tone="good">
                <ShieldCheck aria-hidden /> Passing
              </Badge>
            }
          />
          <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-b-xl border-t border-line bg-line mt-4">
            {[
              ["Portfolios analysed", "12", "of 12"],
              ["Unsupported numbers", "0", "verifier rejects any"],
              ["Findings dropped", "1", "citation unresolved"],
              ["Retrieval hit@5", "0.91", "golden set, 120 Qs"],
            ].map(([k, v, s]) => (
              <div key={k} className="bg-surface p-4">
                <dt className="text-[12px] text-muted">{k}</dt>
                <dd className="tabular mt-0.5 text-[20px] font-semibold text-fg">{v}</dd>
                <dd className="text-[11.5px] text-muted">{s}</dd>
              </div>
            ))}
          </dl>
        </Card>
      </div>

      <button
        onClick={() => openCopilot()}
        className="flex w-full cursor-pointer items-center gap-3 rounded-xl border border-dashed border-line-strong bg-surface/60 px-4 py-3 text-left text-[13px] text-fg-2 transition-colors hover:border-ai hover:bg-ai-soft/40"
      >
        <Bot className="size-4 text-ai" aria-hidden />
        <span className="flex-1">Ask Copilot about any client. Answers come from the same calculations and cite the rule they rely on.</span>
        <ArrowRight className="size-4 text-muted" aria-hidden />
      </button>
    </div>
  );
}
