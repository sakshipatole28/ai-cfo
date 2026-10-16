import { useState } from "react";
import { Area, AreaChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, Treemap } from "recharts";

import { Tip } from "@/components/ui";
import { ASSET_CLASSES, type AssetClass } from "@/data/demo";
import { cn } from "@/lib/cn";
import type { Exposure, OverlapPair, Portfolio } from "@/lib/engine";
import { inr, inrShort, pct, signedPts } from "@/lib/format";

export const assetColor: Record<AssetClass, string> = {
  Equity: "var(--series-1)",
  Debt: "var(--series-2)",
  Gold: "var(--series-4)",
  Cash: "var(--series-3)",
};

const tooltipBox = "rounded-lg border border-line bg-surface px-3 py-2 text-[12px] shadow-pop";

/* Allocation donut with a legend table (actual vs target), so values never rely on colour */
export function AllocationDonut({ pf }: { pf: Portfolio }) {
  const data = ASSET_CLASSES.map((c) => ({ name: c, value: pf.allocation[c] })).filter((d) => d.value > 0);
  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center">
      <div className="relative size-[168px] shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} dataKey="value" innerRadius={56} outerRadius={80} paddingAngle={1.5} stroke="var(--surface)" strokeWidth={2} isAnimationActive={false}>
              {data.map((d) => (
                <Cell key={d.name} fill={assetColor[d.name as AssetClass]} />
              ))}
            </Pie>
            <Tooltip
              content={({ active, payload }) =>
                active && payload?.[0] ? (
                  <div className={tooltipBox}>
                    <p className="font-medium text-fg">{payload[0].name}</p>
                    <p className="tabular text-fg-2">
                      {inr(Number(payload[0].value))} · {pct((Number(payload[0].value) / pf.total) * 100)}
                    </p>
                  </div>
                ) : null
              }
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="eyebrow">Total</span>
          <span className="tabular text-[17px] font-semibold text-fg">{inrShort(pf.total)}</span>
        </div>
      </div>
      <table className="w-full text-[12.5px]">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wider text-muted">
            <th className="pb-1.5 font-semibold">Asset</th>
            <th className="pb-1.5 text-right font-semibold">Actual</th>
            <th className="pb-1.5 text-right font-semibold">Target</th>
            <th className="pb-1.5 text-right font-semibold">Drift</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {ASSET_CLASSES.map((c) => (
            <tr key={c}>
              <td className="py-1.5">
                <span className="flex items-center gap-2 text-fg">
                  <span className="size-2.5 rounded-[3px]" style={{ background: assetColor[c] }} aria-hidden />
                  {c}
                </span>
              </td>
              <td className="tabular py-1.5 text-right text-fg">{pct(pf.allocationPct[c])}</td>
              <td className="tabular py-1.5 text-right text-muted">{pct(pf.target[c], 0)}</td>
              <td className={cn("tabular py-1.5 text-right font-medium", Math.abs(pf.drift[c]) >= 5 ? "text-critical-text" : "text-fg-2")}>
                {signedPts(pf.drift[c])}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* Diverging drift bars: blue below target, red above, neutral midline */
export function DriftBars({ pf }: { pf: Portfolio }) {
  const max = Math.max(10, ...ASSET_CLASSES.map((c) => Math.abs(pf.drift[c])));
  return (
    <div className="space-y-3">
      {ASSET_CLASSES.map((c) => {
        const d = pf.drift[c];
        const w = (Math.abs(d) / max) * 50;
        const amount = (d / 100) * pf.total;
        return (
          <div key={c} className="grid grid-cols-[64px_1fr_92px] items-center gap-3 text-[12.5px]">
            <span className="text-fg-2">{c}</span>
            <Tip label={`${c}: ${pct(pf.allocationPct[c])} vs ${pf.target[c]}% target → ${signedPts(d)} (${inr(amount)})`}>
              <div className="relative h-6 cursor-default rounded-md bg-surface-2">
                <div className="absolute inset-y-1 left-1/2 w-px bg-line-strong" aria-hidden />
                <div
                  className="absolute inset-y-1.5 rounded-[4px]"
                  style={{
                    left: d < 0 ? `${50 - w}%` : "50%",
                    width: `${w}%`,
                    background: d < 0 ? "var(--div-neg)" : "var(--div-pos)",
                  }}
                />
              </div>
            </Tip>
            <span className={cn("tabular text-right font-medium", Math.abs(d) >= 5 ? "text-fg" : "text-muted")}>
              {signedPts(d)}
              <span className="block text-[11px] font-normal text-muted">{inrShort(amount)}</span>
            </span>
          </div>
        );
      })}
      <div className="grid grid-cols-[64px_1fr_92px] gap-3 text-[11px] text-muted">
        <span />
        <div className="flex justify-between">
          <span>◀ Below model</span>
          <span>Above model ▶</span>
        </div>
        <span />
      </div>
    </div>
  );
}

/* Overlap heatmap: one hue, stronger = more overlap. Click a cell for shared holdings. */
const heat = (v: number) => `color-mix(in oklab, var(--series-1) ${Math.round(8 + (v / 100) * 92)}%, var(--surface))`;

export function OverlapHeatmap({ pf, onSelect, selected }: { pf: Portfolio; onSelect: (p: OverlapPair) => void; selected?: OverlapPair }) {
  const fundsHeld = pf.positions.filter((p) => p.kind === "fund" && p.assetClass === "Equity");
  if (fundsHeld.length < 2) return <p className="text-[13px] text-muted">Overlap needs at least two equity funds.</p>;
  const find = (a: string, b: string) => pf.overlaps.find((o) => (o.a.id === a && o.b.id === b) || (o.a.id === b && o.b.id === a));
  return (
    <div className="scrollbar-thin overflow-x-auto">
      <table className="border-separate border-spacing-1 text-[12px]">
        <thead>
          <tr>
            <th />
            {fundsHeld.map((f) => (
              <th key={f.id} className="w-[88px] px-1 pb-1 text-left align-bottom font-medium text-fg-2">
                {f.shortName}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {fundsHeld.map((row) => (
            <tr key={row.id}>
              <th className="whitespace-nowrap pr-2 text-left font-medium text-fg-2">{row.shortName}</th>
              {fundsHeld.map((col) => {
                if (row.id === col.id)
                  return (
                    <td key={col.id} className="h-12 rounded-md bg-surface-2 text-center text-muted" aria-label="Same fund">
                      —
                    </td>
                  );
                const pair = find(row.id, col.id)!;
                const isSel = selected && pair === selected;
                return (
                  <td key={col.id} className="p-0">
                    <Tip label={`${row.shortName} × ${col.shortName}: ${pct(pair.pct)} overlap · ${pair.common.length} shared companies`}>
                      <button
                        onClick={() => onSelect(pair)}
                        className={cn(
                          "tabular h-12 w-[88px] cursor-pointer rounded-md text-[13px] font-semibold transition-shadow",
                          isSel && "ring-2 ring-fg ring-offset-2 ring-offset-surface",
                        )}
                        style={{ background: heat(pair.pct), color: pair.pct > 52 ? "#fff" : "var(--fg)" }}
                      >
                        {pct(pair.pct, 0)}
                      </button>
                    </Tip>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-3 flex items-center gap-2 text-[11px] text-muted">
        <span>0%</span>
        <span className="h-2 w-40 rounded-full" style={{ background: `linear-gradient(90deg, ${heat(0)}, ${heat(100)})` }} aria-hidden />
        <span>100% overlap</span>
      </div>
    </div>
  );
}

/* Look-through treemap: area = exposure; one hue, labels on every tile */
interface TreeNodeProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  name?: string;
  pctOfTotal?: number;
}
function TreeTile({ x = 0, y = 0, width = 0, height = 0, name = "", pctOfTotal = 0 }: TreeNodeProps) {
  const strong = pctOfTotal >= 4;
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} rx={6} fill={heat(Math.min(100, 18 + pctOfTotal * 7))} stroke="var(--surface)" strokeWidth={2} />
      {width > 64 && height > 30 && (
        <>
          <text x={x + 8} y={y + 18} fontSize={12} fontWeight={600} fill={strong ? "#fff" : "var(--fg)"}>
            {name.length * 6.6 > width - 12 ? `${name.slice(0, Math.max(3, Math.floor((width - 16) / 6.6)))}…` : name}
          </text>
          {height > 44 && (
            <text x={x + 8} y={y + 34} fontSize={11.5} fill={strong ? "#fff" : "var(--fg-2)"} style={{ fontVariantNumeric: "tabular-nums" }}>
              {pct(pctOfTotal)}
            </text>
          )}
        </>
      )}
    </g>
  );
}

export function ExposureTreemap({ exposures }: { exposures: Exposure[] }) {
  const data = exposures.slice(0, 18).map((e) => ({ name: e.name, size: e.value, pctOfTotal: e.pctOfTotal, sector: e.sector }));
  return (
    <div className="h-[340px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <Treemap data={data} dataKey="size" content={<TreeTile />} isAnimationActive={false}>
          <Tooltip
            content={({ active, payload }) => {
              const p = payload?.[0]?.payload as { name: string; size: number; pctOfTotal: number; sector: string } | undefined;
              return active && p ? (
                <div className={tooltipBox}>
                  <p className="font-medium text-fg">{p.name}</p>
                  <p className="text-muted">{p.sector}</p>
                  <p className="tabular text-fg-2">
                    {inr(p.size)} · {pct(p.pctOfTotal)} of portfolio
                  </p>
                </div>
              ) : null;
            }}
          />
        </Treemap>
      </ResponsiveContainer>
    </div>
  );
}

/* Sparkline for KPI tiles */
export function Sparkline({ values, label }: { values: number[]; label: string }) {
  const data = values.map((v, i) => ({ i, v }));
  return (
    <div className="h-12 w-full" aria-label={label} role="img">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="spark" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.22} />
              <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area type="monotone" dataKey="v" stroke="var(--accent)" strokeWidth={2} fill="url(#spark)" isAnimationActive={false} dot={false}
            activeDot={{ r: 4, fill: "var(--accent)", stroke: "var(--surface)", strokeWidth: 2 }} />
          <Tooltip
            cursor={{ stroke: "var(--line-strong)" }}
            content={({ active, payload }) => (active && payload?.[0] ? <div className={tooltipBox}>{inrShort(Number(payload[0].value))}</div> : null)}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/* LTCG exemption: used vs remaining, as a labelled bar */
export function ExemptionBar({ used, total }: { used: number; total: number }) {
  const u = Math.min(100, (used / total) * 100);
  return (
    <div>
      <div className="flex h-3 overflow-hidden rounded-full bg-surface-3">
        <div className="h-full bg-series-2" style={{ width: `${u}%` }} />
      </div>
      <div className="mt-2 flex justify-between text-[12px]">
        <span className="flex items-center gap-1.5 text-fg-2">
          <span className="size-2 rounded-[2px] bg-series-2" aria-hidden /> Used <b className="tabular font-semibold text-fg">{inr(used)}</b>
        </span>
        <span className="flex items-center gap-1.5 text-fg-2">
          <span className="size-2 rounded-[2px] bg-surface-3 ring-1 ring-line-strong" aria-hidden /> Left <b className="tabular font-semibold text-fg">{inr(Math.max(0, total - used))}</b>
        </span>
      </div>
    </div>
  );
}

export function useOverlapSelection(pf: Portfolio) {
  return useState<OverlapPair | undefined>(pf.overlaps[0]);
}
