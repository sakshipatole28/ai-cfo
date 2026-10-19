import { Link, useParams } from "@tanstack/react-router";
import {
  ArrowLeft,
  Bot,
  CheckCircle2,
  ChevronRight,
  FileWarning,
  Layers,
  Link2,
  Link2Off,
  PieChart,
  Play,
  Receipt,
  ScanSearch,
  Sparkles,
  Wallet,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { AllocationDonut, assetColor, DriftBars, ExemptionBar, ExposureTreemap, OverlapHeatmap } from "@/components/charts";
import { AgentRunSheet } from "@/components/agents/AgentRun";
import { FindingBody } from "@/components/FindingBody";
import {
  Avatar,
  Badge,
  Button,
  buttonClass,
  Card,
  CardHeader,
  EmptyState,
  Meter,
  SeverityBadge,
  Sheet,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui";
import { DISCLOSURE_MONTH, FY_LABEL, LTCG_EXEMPTION, sourceAsOf, TODAY } from "@/data/demo";
import { cn } from "@/lib/cn";
import { type OverlapPair, portfolioById, type Position } from "@/lib/engine";
import { daysBetween, fmtDate, inr, inrShort, pct } from "@/lib/format";
import { useApp, useClientName } from "@/state/app";

const sourceTone: Record<string, string> = {
  Dhan: "var(--series-1)",
  "CDSL CAS": "var(--series-3)",
  "CAMS CAS": "var(--series-2)",
  "KFintech CAS": "var(--series-4)",
};

export function Client360() {
  const { clientId } = useParams({ from: "/clients/$clientId" });
  const pf = portfolioById[clientId];
  const { openCopilot, decisions, approved, log } = useApp();
  const displayName = useClientName();
  const [lotsFor, setLotsFor] = useState<Position | null>(null);
  const [pair, setPair] = useState<OverlapPair | undefined>(pf?.overlaps[0]);
  const [runOpen, setRunOpen] = useState(false);

  if (!pf) {
    return (
      <EmptyState icon={<ScanSearch />} title="Client not found">
        <Link to="/clients" className="text-accent">
          Back to clients
        </Link>
      </EmptyState>
    );
  }

  const name = displayName(pf.spec.name);
  const open = approved[pf.spec.id] ? [] : pf.findings.filter((f) => !decisions[f.id]);
  const equityLots = pf.positions.filter((p) => p.assetClass === "Equity").flatMap((p) => p.lots.map((lot) => ({ p, lot })));
  const stGain = equityLots.filter(({ lot }) => !lot.isLong).reduce((s, { lot }) => s + lot.gain, 0);

  return (
    <div className="gutter-x mx-auto max-w-[1400px] space-y-4 py-5 sm:py-6">
      <Link to="/clients" className="inline-flex items-center gap-1.5 text-[12.5px] font-medium text-muted hover:text-fg">
        <ArrowLeft className="size-3.5" aria-hidden /> Clients
      </Link>

      {/* Header */}
      <Card className="p-4 sm:p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center">
          <div className="flex min-w-0 flex-1 items-center gap-3.5">
            <Avatar name={name} className="size-12 text-[15px]" />
            <div className="min-w-0">
              <h2 className="truncate text-[20px] font-semibold tracking-tight text-fg">{name}</h2>
              <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[12.5px] text-muted">
                <Badge tone="accent">{pf.spec.risk}</Badge>
                <span>
                  {pf.spec.city} · {pf.spec.age} yrs · last review {fmtDate(pf.spec.lastReview)}
                </span>
                {daysBetween(pf.spec.lastReview, TODAY) > 90 && <Badge tone="warning">Review due</Badge>}
              </div>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4 sm:flex sm:items-center sm:gap-6">
            <div>
              <p className="eyebrow">Portfolio</p>
              <p className="tabular text-[22px] font-semibold tracking-tight text-fg">{inrShort(pf.total)}</p>
            </div>
            <div className="min-w-0 sm:w-56">
              <p className="eyebrow">Data coverage by source</p>
              <div className="mt-1.5 flex h-2 overflow-hidden rounded-full bg-surface-3">
                {pf.sourceMix.map((s) => (
                  <div key={s.source} style={{ width: `${(s.value / pf.total) * 100}%`, background: sourceTone[s.source] }} className="h-full border-r-2 border-surface last:border-r-0" />
                ))}
              </div>
              <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[11.5px] text-muted">
                {pf.sourceMix.map((s) => (
                  <span key={s.source} className="flex items-center gap-1">
                    <span className="size-2 rounded-[2px]" style={{ background: sourceTone[s.source] }} aria-hidden />
                    {s.source} · {fmtDate(s.asOf).slice(0, 6)}
                  </span>
                ))}
              </div>
            </div>
            <div className="col-span-2 flex gap-2 sm:col-span-1">
              <Button variant="outline" onClick={() => openCopilot(pf.spec.id)} className="flex-1 sm:flex-none">
                <Bot /> Ask
              </Button>
              <Button
                variant="primary"
                className="flex-1 sm:flex-none"
                onClick={() => {
                  log("review.run.requested", `client/${pf.spec.id}`);
                  setRunOpen(true);
                }}
              >
                <Play /> Run review
              </Button>
            </div>
          </div>
        </div>
        {pf.spec.dhan === "expired" && (
          <div className="mt-4 flex flex-col gap-2 rounded-lg border border-warning/40 bg-warning-soft px-3.5 py-2.5 text-[13px] sm:flex-row sm:items-center">
            <Link2Off className="size-4 shrink-0 text-warning-text" aria-hidden />
            <p className="flex-1 text-fg-2">
              Dhan access expired. Direct shares are shown from the last sync on {fmtDate(sourceAsOf.Dhan)}. Dhan tokens last 24 hours and are never refreshed automatically.
            </p>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                log("connection.dhan.reconnect.requested", `client/${pf.spec.id}`);
                toast("Reconnect link ready", { description: "Send it to the client; they sign in on Dhan's own page." });
              }}
            >
              <Link2 /> Send reconnect link
            </Button>
          </div>
        )}
      </Card>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">
            <PieChart /> Overview
          </TabsTrigger>
          <TabsTrigger value="holdings">
            <Wallet /> Holdings
          </TabsTrigger>
          <TabsTrigger value="lookthrough">
            <ScanSearch /> Look-through
          </TabsTrigger>
          <TabsTrigger value="overlap">
            <Layers /> Overlap
          </TabsTrigger>
          <TabsTrigger value="tax">
            <Receipt /> Tax
          </TabsTrigger>
          <TabsTrigger value="findings">
            <Sparkles /> Findings
            {open.length > 0 && <Badge tone="accent">{open.length}</Badge>}
          </TabsTrigger>
          <TabsTrigger value="data">
            <FileWarning /> Data
          </TabsTrigger>
        </TabsList>

        {/* Overview */}
        <TabsContent value="overview" className="mt-4 grid gap-4 lg:grid-cols-12">
          <Card className="lg:col-span-6">
            <CardHeader title="Allocation vs model" description={`${pf.spec.risk} model · Investment Policy Statement v3`} />
            <div className="p-4 sm:p-5">
              <AllocationDonut pf={pf} />
            </div>
          </Card>
          <Card className="lg:col-span-6">
            <CardHeader title="Drift from model" description="Percentage points and rupees; review band is ±5 pts" />
            <div className="p-4 sm:p-5">
              <DriftBars pf={pf} />
            </div>
          </Card>
          <Card className="lg:col-span-5">
            <CardHeader title="Largest true exposures" description={`Direct shares plus fund holdings · disclosures ${DISCLOSURE_MONTH}`} />
            <ul className="space-y-2.5 p-4 sm:p-5">
              {pf.exposures.slice(0, 7).map((e) => (
                <li key={e.symbol} className="grid grid-cols-[minmax(0,1fr)_96px_48px] items-center gap-3 text-[12.5px]">
                  <span className="truncate text-fg">{e.name}</span>
                  <Meter value={(e.pctOfTotal / (pf.exposures[0]?.pctOfTotal ?? 1)) * 100} label={`${e.name} exposure`} />
                  <span className="tabular text-right font-medium text-fg">{pct(e.pctOfTotal)}</span>
                </li>
              ))}
            </ul>
          </Card>
          <Card className="lg:col-span-7">
            <CardHeader
              title="Draft findings"
              description="Written by AI from computed numbers · awaiting your approval"
              action={
                open.length > 0 && (
                  <Link to="/review" className={buttonClass("ghost", "sm")}>
                    Open inbox <ChevronRight />
                  </Link>
                )
              }
            />
            <ul className="mt-2 divide-y divide-line">
              {open.length === 0 && (
                <li className="flex items-center gap-2 px-5 py-6 text-[13px] text-muted">
                  <CheckCircle2 className="size-4 text-good" aria-hidden /> Nothing waiting. Last review approved.
                </li>
              )}
              {open.slice(0, 4).map((f) => (
                <li key={f.id} className="flex gap-3 px-4 py-3 sm:px-5">
                  <SeverityBadge severity={f.severity} />
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-medium text-fg">{f.title}</p>
                    <p className="mt-0.5 text-[12.5px] leading-relaxed text-fg-2">
                      <FindingBody body={f.body} name={name} />
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        </TabsContent>

        {/* Holdings */}
        <TabsContent value="holdings" className="mt-4">
          <Card className="overflow-hidden">
            <div className="scrollbar-thin overflow-x-auto">
              <table className="w-full min-w-[820px] text-[13px]">
                <thead className="border-b border-line bg-surface-2/60 text-left text-[11.5px] uppercase tracking-wider text-muted">
                  <tr>
                    <th className="px-5 py-2.5 font-semibold">Holding</th>
                    <th className="px-3 py-2.5 font-semibold">Asset</th>
                    <th className="px-3 py-2.5 text-right font-semibold">Units</th>
                    <th className="px-3 py-2.5 text-right font-semibold">NAV / price</th>
                    <th className="px-3 py-2.5 text-right font-semibold">Value</th>
                    <th className="px-3 py-2.5 text-right font-semibold">Gain</th>
                    <th className="px-3 py-2.5 font-semibold">Source</th>
                    <th className="w-8" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {pf.positions.map((p) => {
                    const gain = p.value - p.cost;
                    return (
                      <tr key={p.id} className="cursor-pointer hover:bg-surface-2/60" onClick={() => setLotsFor(p)}>
                        <td className="px-5 py-3">
                          <p className="font-medium text-fg">{p.name}</p>
                          <p className="font-mono text-[11.5px] text-muted">
                            {p.isin ?? "ISIN on file"} · {p.account}
                          </p>
                        </td>
                        <td className="px-3 py-3">
                          <span className="flex items-center gap-1.5 text-fg-2">
                            <span className="size-2 rounded-[2px]" style={{ background: assetColor[p.assetClass] }} aria-hidden />
                            {p.category}
                          </span>
                        </td>
                        <td className="tabular px-3 py-3 text-right text-fg-2">{p.units.toLocaleString("en-IN", { maximumFractionDigits: p.kind === "fund" ? 3 : 0 })}</td>
                        <td className="tabular px-3 py-3 text-right text-fg-2">{inr(p.price)}</td>
                        <td className="tabular px-3 py-3 text-right font-medium text-fg">{inr(p.value)}</td>
                        <td className={cn("tabular px-3 py-3 text-right", gain >= 0 ? "text-good-text" : "text-critical-text")}>{inr(gain)}</td>
                        <td className="px-3 py-3">
                          <Badge tone="outline">{p.source}</Badge>
                          <span className="ml-1.5 text-[11.5px] text-muted">{fmtDate(p.asOf).slice(0, 6)}</span>
                        </td>
                        <td className="pr-4 text-muted">
                          <ChevronRight className="size-4" aria-hidden />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
                <tfoot className="border-t border-line bg-surface-2/40 text-[13px]">
                  <tr>
                    <td className="px-5 py-2.5 font-semibold text-fg" colSpan={4}>
                      Total · {pf.positions.length} holdings
                    </td>
                    <td className="tabular px-3 py-2.5 text-right font-semibold text-fg">{inr(pf.total)}</td>
                    <td colSpan={3} />
                  </tr>
                </tfoot>
              </table>
            </div>
          </Card>
          <p className="mt-2 text-[12px] text-muted">Select a holding to see its tax lots.</p>
        </TabsContent>

        {/* Look-through */}
        <TabsContent value="lookthrough" className="mt-4 grid gap-4 lg:grid-cols-12">
          <Card className="lg:col-span-8">
            <CardHeader
              title="True company exposure"
              description="Tile size = rupees exposed, through funds and direct shares"
              action={<Badge tone="outline">{Math.round(pf.lookThroughPct)}% of equity looked through</Badge>}
            />
            <div className="p-3 sm:p-4">
              <ExposureTreemap exposures={pf.exposures} />
            </div>
          </Card>
          <Card className="lg:col-span-4">
            <CardHeader title="Where it comes from" description="Top 5 companies, broken down by route" />
            <ul className="divide-y divide-line">
              {pf.exposures.slice(0, 5).map((e) => (
                <li key={e.symbol} className="px-4 py-3 sm:px-5">
                  <div className="flex items-baseline justify-between gap-2">
                    <p className="truncate text-[13px] font-medium text-fg">{e.name}</p>
                    <p className="tabular text-[13px] font-semibold text-fg">{inrShort(e.value)}</p>
                  </div>
                  <p className="mt-0.5 text-[12px] leading-relaxed text-muted">
                    {[e.direct ? `Direct ${inrShort(e.direct)}` : null, ...e.viaFunds.map((v) => `${v.fund} ${inrShort(v.value)}`)].filter(Boolean).join(" · ")}
                  </p>
                </li>
              ))}
            </ul>
          </Card>
        </TabsContent>

        {/* Overlap */}
        <TabsContent value="overlap" className="mt-4 grid gap-4 lg:grid-cols-12">
          <Card className="lg:col-span-7">
            <CardHeader title="Fund overlap" description={`Σ min(weightₐ, weight_b) over shared companies · ${DISCLOSURE_MONTH} disclosures`} />
            <div className="p-4 sm:p-5">
              <OverlapHeatmap pf={pf} selected={pair} onSelect={setPair} />
            </div>
          </Card>
          <Card className="lg:col-span-5">
            <CardHeader
              title={pair ? `${pair.a.shortName} × ${pair.b.shortName}` : "Select a pair"}
              description={pair ? `${pair.common.length} shared companies · ${pct(pair.pct)} overlap` : "Click a cell in the matrix"}
            />
            {pair && (
              <div className="scrollbar-thin max-h-[360px] overflow-y-auto p-4 sm:p-5">
                <table className="w-full text-[12.5px]">
                  <thead className="text-left text-[11px] uppercase tracking-wider text-muted">
                    <tr>
                      <th className="pb-2 font-semibold">Company</th>
                      <th className="pb-2 text-right font-semibold">A</th>
                      <th className="pb-2 text-right font-semibold">B</th>
                      <th className="pb-2 text-right font-semibold">Shared</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {pair.common.map((c) => (
                      <tr key={c.symbol}>
                        <td className="py-1.5 text-fg">{c.name}</td>
                        <td className="tabular py-1.5 text-right text-muted">{c.wa.toFixed(1)}%</td>
                        <td className="tabular py-1.5 text-right text-muted">{c.wb.toFixed(1)}%</td>
                        <td className="tabular py-1.5 text-right font-medium text-fg">{Math.min(c.wa, c.wb).toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </TabsContent>

        {/* Tax */}
        <TabsContent value="tax" className="mt-4 grid gap-4 lg:grid-cols-12">
          <Card className="p-4 sm:p-5 lg:col-span-5">
            <p className="eyebrow">LTCG exemption · {FY_LABEL}</p>
            <p className="tabular mt-1 text-[24px] font-semibold tracking-tight text-fg">{inr(pf.exemptionLeft)} left</p>
            <p className="mb-3 text-[12.5px] text-muted">of {inr(LTCG_EXEMPTION)} per financial year · equity and equity-oriented funds</p>
            <ExemptionBar used={pf.spec.realisedLtcg} total={LTCG_EXEMPTION} />
            <dl className="mt-5 grid grid-cols-2 gap-3 border-t border-line pt-4 text-[12.5px]">
              <div>
                <dt className="text-muted">Unrealised long-term gains</dt>
                <dd className="tabular text-[15px] font-semibold text-fg">{inr(pf.ltGainUnrealised)}</dd>
              </div>
              <div>
                <dt className="text-muted">Unrealised short-term gains</dt>
                <dd className="tabular text-[15px] font-semibold text-fg">{inr(stGain)}</dd>
              </div>
            </dl>
          </Card>
          <Card className="lg:col-span-7">
            <CardHeader title="Equity lots and holding period" description="Long-term after 12 months · ELSS locked for 3 years · ruleset FY 2026-27" />
            <div className="scrollbar-thin overflow-x-auto">
              <table className="mt-2 w-full min-w-[560px] text-[12.5px]">
                <thead className="text-left text-[11px] uppercase tracking-wider text-muted">
                  <tr className="border-b border-line">
                    <th className="px-5 py-2 font-semibold">Holding</th>
                    <th className="px-3 py-2 font-semibold">Acquired</th>
                    <th className="px-3 py-2 text-right font-semibold">Gain</th>
                    <th className="px-3 py-2 font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {equityLots
                    .sort((a, b) => (a.lot.isLong === b.lot.isLong ? a.lot.daysToLong - b.lot.daysToLong : a.lot.isLong ? 1 : -1))
                    .map(({ p, lot }) => (
                      <tr key={lot.id}>
                        <td className="px-5 py-2 text-fg">{p.shortName}</td>
                        <td className="tabular px-3 py-2 text-fg-2">{fmtDate(lot.acquired)}</td>
                        <td className={cn("tabular px-3 py-2 text-right", lot.gain >= 0 ? "text-good-text" : "text-critical-text")}>{inr(lot.gain)}</td>
                        <td className="px-3 py-2">
                          {lot.lockedUntil && lot.lockedUntil > TODAY ? (
                            <Badge tone="neutral">ELSS lock until {fmtDate(lot.lockedUntil)}</Badge>
                          ) : lot.isLong ? (
                            <Badge tone="good">Long-term</Badge>
                          ) : (
                            <Badge tone={lot.daysToLong <= 30 ? "warning" : "outline"}>Long-term in {lot.daysToLong} days</Badge>
                          )}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </Card>
        </TabsContent>

        {/* Findings */}
        <TabsContent value="findings" className="mt-4 space-y-3">
          {pf.findings.map((f) => (
            <Card key={f.id} className="p-4 sm:p-5">
              <div className="flex flex-wrap items-center gap-2">
                <SeverityBadge severity={f.severity} />
                <Badge tone="ai">
                  <Sparkles aria-hidden /> AI draft
                </Badge>
                {decisions[f.id] && <Badge tone="outline">{decisions[f.id]}</Badge>}
                {approved[pf.spec.id] && <Badge tone="good">Approved</Badge>}
              </div>
              <p className="mt-2 text-[14px] font-semibold text-fg">{f.title}</p>
              <p className="mt-1 text-[13.5px] leading-relaxed text-fg-2">
                <FindingBody body={f.body} name={name} />
              </p>
            </Card>
          ))}
          <Link to="/review" className={buttonClass("primary")}>
            Review and approve in the inbox <ChevronRight />
          </Link>
        </TabsContent>

        {/* Data */}
        <TabsContent value="data" className="mt-4 grid gap-4 md:grid-cols-2">
          {pf.sourceMix.map((s) => (
            <Card key={s.source} className="p-4 sm:p-5">
              <div className="flex items-center justify-between">
                <p className="text-[14px] font-semibold text-fg">{s.source}</p>
                {s.source === "Dhan" && pf.spec.dhan === "expired" ? <Badge tone="warning">Token expired</Badge> : <Badge tone="good">Verified</Badge>}
              </div>
              <p className="mt-1 text-[12.5px] text-muted">
                {inrShort(s.value)} · {pct((s.value / pf.total) * 100)} of portfolio · as of {fmtDate(s.asOf)}
              </p>
              <ul className="mt-3 space-y-1.5 text-[12.5px] text-fg-2">
                {(s.source === "Dhan"
                  ? ["Read-only holdings call only", "Token discarded after sync (session mode)", "Reconciled with CDSL CAS"]
                  : ["Parsed totals match statement totals", "PAN tag matches client", "PDF deleted after parsing"]
                ).map((c) => (
                  <li key={c} className="flex items-center gap-2">
                    <CheckCircle2 className="size-3.5 text-good" aria-hidden /> {c}
                  </li>
                ))}
              </ul>
            </Card>
          ))}
          {pf.spec.id === "rohan-deshpande" && (
            <Card className="border-warning/50 p-4 sm:p-5 md:col-span-2">
              <div className="flex items-center gap-2">
                <FileWarning className="size-4 text-warning-text" aria-hidden />
                <p className="text-[14px] font-semibold text-fg">Reconciliation exception: Infosys quantity</p>
              </div>
              <p className="mt-1 text-[12.5px] text-muted">Same demat account, two sources disagree. Nothing was merged silently.</p>
              <div className="mt-3 grid grid-cols-2 gap-3 text-[13px]">
                <div className="rounded-lg border border-line p-3">
                  <p className="text-muted">Dhan · 16 Oct</p>
                  <p className="tabular text-[18px] font-semibold text-fg">80 shares</p>
                </div>
                <div className="rounded-lg border border-line p-3">
                  <p className="text-muted">CDSL CAS · 30 Sep</p>
                  <p className="tabular text-[18px] font-semibold text-fg">75 shares</p>
                </div>
              </div>
              <Link to="/data" className={cn(buttonClass("outline", "sm"), "mt-3")}>
                Resolve in Data inbox
              </Link>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      <AgentRunSheet clientId={pf.spec.id} open={runOpen} onOpenChange={setRunOpen} />

      {/* Lots drawer */}
      <Sheet open={!!lotsFor} onOpenChange={(o) => !o && setLotsFor(null)} title={lotsFor?.name ?? ""} description={lotsFor ? `${lotsFor.account} · ${lotsFor.source}` : undefined}>
        {lotsFor && (
          <div className="space-y-4 p-5">
            <div className="grid grid-cols-3 gap-3 text-[12.5px]">
              {[
                ["Value", inr(lotsFor.value)],
                ["Cost", inr(lotsFor.cost)],
                ["Gain", inr(lotsFor.value - lotsFor.cost)],
              ].map(([k, v]) => (
                <div key={k} className="rounded-lg bg-surface-2 p-3">
                  <p className="text-muted">{k}</p>
                  <p className="tabular text-[14px] font-semibold text-fg">{v}</p>
                </div>
              ))}
            </div>
            <ul className="space-y-2">
              {lotsFor.lots.map((l) => (
                <li key={l.id} className="rounded-lg border border-line p-3 text-[12.5px]">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-fg">Bought {fmtDate(l.acquired)}</span>
                    {l.lockedUntil && l.lockedUntil > TODAY ? (
                      <Badge tone="neutral">Locked until {fmtDate(l.lockedUntil)}</Badge>
                    ) : l.isLong ? (
                      <Badge tone="good">Long-term</Badge>
                    ) : (
                      <Badge tone="warning">Long-term on {fmtDate(l.longTermOn)}</Badge>
                    )}
                  </div>
                  <p className="tabular mt-1 text-muted">
                    {l.units.toLocaleString("en-IN", { maximumFractionDigits: 3 })} units · cost {inr(l.cost)} · value {inr(l.value)} · gain {inr(l.gain)}
                  </p>
                </li>
              ))}
            </ul>
            <p className="text-[12px] text-muted">Lots come from CAS transaction history and broker tradebooks. If a purchase date is unknown, the lot is flagged and left out of tax alerts.</p>
          </div>
        )}
      </Sheet>
    </div>
  );
}
