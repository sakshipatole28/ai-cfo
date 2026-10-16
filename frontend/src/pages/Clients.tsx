import { Link } from "@tanstack/react-router";
import { ChevronRight, Lock, Plus, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Avatar, Badge, Button, Card, Meter } from "@/components/ui";
import { TODAY } from "@/data/demo";
import { cn } from "@/lib/cn";
import { type Portfolio, portfolios } from "@/lib/engine";
import { daysBetween, fmtDate, inrShort, signedPts } from "@/lib/format";
import { useApp, useClientName } from "@/state/app";

type Filter = "all" | "review" | "stale" | "drift";

export function Clients() {
  const { decisions, approved, locked } = useApp();
  const displayName = useClientName();
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<Filter>("all");

  const openCount = (p: Portfolio) => (approved[p.spec.id] ? 0 : p.findings.filter((f) => !decisions[f.id]).length);
  const due = (p: Portfolio) => daysBetween(p.spec.lastReview, TODAY) > 90;

  const rows = useMemo(
    () =>
      portfolios
        .filter((p) => (locked ? true : `${p.spec.name} ${p.spec.city}`.toLowerCase().includes(q.toLowerCase())))
        .filter((p) =>
          filter === "review" ? due(p) || openCount(p) > 0 : filter === "stale" ? p.spec.dhan === "expired" : filter === "drift" ? Math.abs(p.drift.Equity) >= 5 : true,
        )
        .sort((a, b) => openCount(b) - openCount(a) || b.total - a.total),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [q, filter, decisions, approved, locked],
  );

  const chips: [Filter, string, number][] = [
    ["all", "All", portfolios.length],
    ["review", "Needs review", portfolios.filter((p) => due(p) || openCount(p) > 0).length],
    ["drift", "Off model", portfolios.filter((p) => Math.abs(p.drift.Equity) >= 5).length],
    ["stale", "Reconnect", portfolios.filter((p) => p.spec.dhan === "expired").length],
  ];

  return (
    <div className="gutter-x mx-auto max-w-[1400px] space-y-4 py-5 sm:py-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Filter clients">
          {chips.map(([key, label, n]) => (
            <button
              key={key}
              role="tab"
              aria-selected={filter === key}
              onClick={() => setFilter(key)}
              className={cn(
                "inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-full border px-3 text-[12.5px] font-medium transition-colors",
                filter === key ? "border-fg bg-fg text-bg" : "border-line bg-surface text-fg-2 hover:border-line-strong",
              )}
            >
              {label}
              <span className={cn("tabular text-[11px]", filter === key ? "opacity-70" : "text-muted")}>{n}</span>
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <label className="flex h-9 flex-1 items-center gap-2 rounded-lg border border-line bg-surface px-3 focus-within:border-accent md:w-64 md:flex-none">
            <Search className="size-4 text-muted" aria-hidden />
            <span className="sr-only">Search clients</span>
            <input
              id="client-search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={locked ? "Unlock vault to search names" : "Search by name or city"}
              disabled={locked}
              className="min-w-0 flex-1 bg-transparent text-[13px] text-fg outline-none placeholder:text-muted"
            />
          </label>
          <Button variant="primary" onClick={() => toast("New client", { description: "Identity is encrypted in your browser before it is saved." })}>
            <Plus /> <span className="hidden sm:inline">Add client</span>
          </Button>
        </div>
      </div>

      <p className="flex items-center gap-1.5 text-[12px] text-muted">
        <Lock className="size-3.5" aria-hidden /> Names are decrypted in this browser only. The server stores pseudonymous IDs.
      </p>

      {/* Table: tablet and desktop */}
      <Card className="hidden overflow-hidden md:block">
        <div className="scrollbar-thin overflow-x-auto">
          <table className="w-full min-w-[860px] text-[13px]">
            <thead className="border-b border-line bg-surface-2/60 text-left text-[11.5px] uppercase tracking-wider text-muted">
              <tr>
                <th className="px-5 py-2.5 font-semibold">Client</th>
                <th className="px-3 py-2.5 font-semibold">Risk profile</th>
                <th className="px-3 py-2.5 text-right font-semibold">Portfolio</th>
                <th className="px-3 py-2.5 text-right font-semibold">Equity drift</th>
                <th className="px-3 py-2.5 font-semibold">Last review</th>
                <th className="px-3 py-2.5 font-semibold">Data</th>
                <th className="px-3 py-2.5 font-semibold">Look-through</th>
                <th className="px-3 py-2.5 text-right font-semibold">Drafts</th>
                <th className="w-8" />
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {rows.map((p) => {
                const n = openCount(p);
                return (
                  <tr key={p.spec.id} className="group relative transition-colors hover:bg-surface-2/60">
                    <td className="px-5 py-3">
                      <Link to="/clients/$clientId" params={{ clientId: p.spec.id }} className="flex items-center gap-3 after:absolute after:inset-0">
                        <Avatar name={displayName(p.spec.name)} />
                        <span className="min-w-0">
                          <span className="block truncate font-medium text-fg">{displayName(p.spec.name)}</span>
                          <span className="block text-[12px] text-muted">
                            {p.spec.city} · {p.spec.age}
                          </span>
                        </span>
                      </Link>
                    </td>
                    <td className="px-3 py-3 text-fg-2">{p.spec.risk}</td>
                    <td className="tabular px-3 py-3 text-right font-medium text-fg">{inrShort(p.total)}</td>
                    <td className={cn("tabular px-3 py-3 text-right", Math.abs(p.drift.Equity) >= 5 ? "font-medium text-critical-text" : "text-muted")}>
                      {signedPts(p.drift.Equity)}
                    </td>
                    <td className="px-3 py-3">
                      <span className="text-fg-2">{fmtDate(p.spec.lastReview)}</span>
                      {due(p) && (
                        <Badge tone="warning" className="ml-2">
                          Due
                        </Badge>
                      )}
                    </td>
                    <td className="px-3 py-3">
                      <span className="flex items-center gap-1.5 text-[12.5px] text-fg-2">
                        <span className={cn("size-2 rounded-full", p.spec.dhan === "expired" ? "bg-warning" : "bg-good")} aria-hidden />
                        {p.spec.dhan === "expired" ? "Reconnect Dhan" : `${p.freshnessDays} days old`}
                      </span>
                    </td>
                    <td className="w-36 px-3 py-3">
                      <div className="flex items-center gap-2">
                        <Meter value={p.lookThroughPct} />
                        <span className="tabular w-9 text-right text-[12px] text-muted">{Math.round(p.lookThroughPct)}%</span>
                      </div>
                    </td>
                    <td className="px-3 py-3 text-right">{n > 0 ? <Badge tone="accent">{n}</Badge> : <span className="text-muted">—</span>}</td>
                    <td className="pr-4 text-muted">
                      <ChevronRight className="size-4 transition-transform group-hover:translate-x-0.5" aria-hidden />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="border-t border-line px-5 py-2.5 text-[12px] text-muted">
          {rows.length} of {portfolios.length} clients
        </div>
      </Card>

      {/* Cards: phones */}
      <ul className="space-y-2.5 md:hidden">
        {rows.map((p) => {
          const n = openCount(p);
          return (
            <li key={p.spec.id}>
              <Link to="/clients/$clientId" params={{ clientId: p.spec.id }} className="block">
                <Card className="p-4 active:bg-surface-2">
                  <div className="flex items-center gap-3">
                    <Avatar name={displayName(p.spec.name)} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium text-fg">{displayName(p.spec.name)}</p>
                      <p className="truncate text-[12px] text-muted">
                        {p.spec.risk} · {p.spec.city}
                      </p>
                    </div>
                    <p className="tabular text-[15px] font-semibold text-fg">{inrShort(p.total)}</p>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {n > 0 && <Badge tone="accent">{n} drafts</Badge>}
                    {Math.abs(p.drift.Equity) >= 5 && <Badge tone="critical">Equity {signedPts(p.drift.Equity)}</Badge>}
                    {due(p) && <Badge tone="warning">Review due</Badge>}
                    {p.spec.dhan === "expired" && <Badge tone="warning">Reconnect Dhan</Badge>}
                  </div>
                </Card>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
