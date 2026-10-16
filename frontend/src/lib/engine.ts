/**
 * Demo copy of the deterministic core (backend `core/` is the source of truth).
 * Every number the UI shows is computed here from the synthetic book, and each
 * finding carries an Explanation listing its formula, inputs and sources.
 */
import {
  ASSET_CLASSES,
  type AssetClass,
  type ClientSpec,
  clientSpecs,
  DISCLOSURE_MONTH,
  ENGINE_VERSION,
  FY_LABEL,
  funds,
  type KbDoc,
  kb,
  LTCG_EXEMPTION,
  LTCG_RATE,
  models,
  RULESET_VERSION,
  type RiskCategory,
  type SourceName,
  STCG_RATE,
  sourceAsOf,
  stocks,
  TODAY,
} from "@/data/demo";
import { daysBetween, fmtDate, inr, inrShort, pct, signedPts } from "@/lib/format";

export interface Lot {
  id: string;
  acquired: string;
  units: number;
  value: number;
  cost: number;
  gain: number;
  longTermOn: string;
  isLong: boolean;
  daysToLong: number;
  lockedUntil?: string;
}

export interface Position {
  id: string;
  kind: "fund" | "stock";
  ref: string;
  name: string;
  shortName: string;
  isin?: string;
  category: string;
  assetClass: AssetClass;
  units: number;
  price: number;
  value: number;
  cost: number;
  source: SourceName;
  account: string;
  asOf: string;
  lots: Lot[];
}

export interface ExplainInput {
  label: string;
  value: string;
  source?: string;
}

export interface Explanation {
  title: string;
  result: string;
  formulaWords: string;
  formula?: string;
  inputs: ExplainInput[];
  steps: string[];
  citations: KbDoc[];
  versions: { label: string; value: string }[];
}

export type Seg = string | { n: string; e: Explanation };
export type Severity = "high" | "medium" | "low";
export type FindingKind = "overlap" | "drift" | "tax-timing" | "harvest" | "concentration";

export interface Finding {
  id: string;
  clientId: string;
  kind: FindingKind;
  severity: Severity;
  title: string;
  body: Seg[];
  impact: number;
  evidence: Explanation[];
  compliance: { rules: "pass"; classifier: number; judge: "skipped" | "pass"; rewrites: number };
}

const versions = (extra: { label: string; value: string }[] = []) => [
  { label: "Engine", value: ENGINE_VERSION },
  { label: "Snapshot", value: `snap-${TODAY.replaceAll("-", "")}` },
  ...extra,
];

function addYearsPlusDay(iso: string, years: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCFullYear(d.getUTCFullYear() + years);
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}

function buildPositions(spec: ClientSpec): Position[] {
  return spec.holdings.map((h, i) => {
    const isFund = h.kind === "fund";
    const fundRef = isFund ? funds[h.ref] : undefined;
    const stockRef = isFund ? undefined : stocks[h.ref];
    const price = fundRef?.nav ?? stockRef?.price ?? 0;
    const value = isFund ? (h.value ?? 0) : (h.qty ?? 0) * price;
    const units = isFund ? value / price : (h.qty ?? 0);
    const lots: Lot[] = h.lots.map((l, j) => {
      const lotValue = value * l.share;
      const cost = lotValue * l.costRatio;
      const longTermOn = addYearsPlusDay(l.acquired, 1);
      const daysToLong = daysBetween(TODAY, longTermOn);
      return {
        id: `${spec.id}-${i}-${j}`,
        acquired: l.acquired,
        units: units * l.share,
        value: lotValue,
        cost,
        gain: lotValue - cost,
        longTermOn,
        isLong: daysToLong <= 0,
        daysToLong,
        lockedUntil: fundRef?.category === "ELSS" ? addYearsPlusDay(l.acquired, 3) : undefined,
      };
    });
    return {
      id: `${spec.id}-${i}`,
      kind: h.kind,
      ref: h.ref,
      name: fundRef?.name ?? stockRef?.name ?? h.ref,
      shortName: fundRef?.shortName ?? stockRef?.name ?? h.ref,
      isin: fundRef?.isin ?? stockRef?.isin,
      category: fundRef?.category ?? "Direct equity",
      assetClass: fundRef?.assetClass ?? "Equity",
      units,
      price,
      value,
      cost: lots.reduce((s, l) => s + l.cost, 0),
      source: h.source,
      account: h.account,
      asOf: sourceAsOf[h.source],
      lots,
    };
  });
}

export interface Exposure {
  symbol: string;
  name: string;
  sector: string;
  value: number;
  pctOfTotal: number;
  direct: number;
  viaFunds: { fund: string; value: number; weight: number }[];
}

export interface OverlapPair {
  a: Position;
  b: Position;
  pct: number;
  common: { symbol: string; name: string; wa: number; wb: number }[];
}

export interface Portfolio {
  spec: ClientSpec;
  positions: Position[];
  total: number;
  allocation: Record<AssetClass, number>;
  allocationPct: Record<AssetClass, number>;
  target: Record<AssetClass, number>;
  drift: Record<AssetClass, number>;
  exposures: Exposure[];
  lookThroughPct: number;
  overlaps: OverlapPair[];
  ltGainUnrealised: number;
  exemptionLeft: number;
  upcomingLots: { position: Position; lot: Lot }[];
  sourceMix: { source: SourceName; value: number; asOf: string }[];
  freshnessDays: number;
  findings: Finding[];
}

function computeExposures(positions: Position[], total: number) {
  const map = new Map<string, Exposure>();
  let equityValue = 0;
  let covered = 0;
  const touch = (symbol: string) => {
    const s = stocks[symbol];
    if (!s) return undefined;
    let e = map.get(symbol);
    if (!e) {
      e = { symbol, name: s.name, sector: s.sector, value: 0, pctOfTotal: 0, direct: 0, viaFunds: [] };
      map.set(symbol, e);
    }
    return e;
  };
  for (const p of positions) {
    if (p.assetClass !== "Equity") continue;
    equityValue += p.value;
    if (p.kind === "stock") {
      const e = touch(p.ref);
      if (e) {
        e.value += p.value;
        e.direct += p.value;
        covered += p.value;
      }
      continue;
    }
    const weights = funds[p.ref]?.weights ?? {};
    for (const [symbol, w] of Object.entries(weights)) {
      const e = touch(symbol);
      if (!e) continue;
      const v = (p.value * w) / 100;
      e.value += v;
      e.viaFunds.push({ fund: p.shortName, value: v, weight: w });
      covered += v;
    }
  }
  const exposures = [...map.values()]
    .map((e) => ({ ...e, pctOfTotal: (e.value / total) * 100 }))
    .sort((x, y) => y.value - x.value);
  return { exposures, lookThroughPct: equityValue ? (covered / equityValue) * 100 : 0 };
}

function computeOverlaps(positions: Position[]): OverlapPair[] {
  const eq = positions.filter((p) => p.kind === "fund" && p.assetClass === "Equity");
  const pairs: OverlapPair[] = [];
  for (let i = 0; i < eq.length; i++) {
    for (let j = i + 1; j < eq.length; j++) {
      const a = eq[i]!;
      const b = eq[j]!;
      const wa = funds[a.ref]!.weights;
      const wb = funds[b.ref]!.weights;
      const common = Object.keys(wa)
        .filter((s) => s in wb)
        .map((s) => ({ symbol: s, name: stocks[s]?.name ?? s, wa: wa[s]!, wb: wb[s]! }))
        .sort((x, y) => Math.min(y.wa, y.wb) - Math.min(x.wa, x.wb));
      const overlap = common.reduce((s, c) => s + Math.min(c.wa, c.wb), 0);
      pairs.push({ a, b, pct: overlap, common });
    }
  }
  return pairs.sort((x, y) => y.pct - x.pct);
}

const hashUnit = (s: string) => {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return ((h >>> 0) % 1000) / 1000;
};

function compliance(id: string, rewrites = 0): Finding["compliance"] {
  const p = 0.01 + hashUnit(id) * 0.07;
  return { rules: "pass", classifier: Number(p.toFixed(2)), judge: p > 0.06 ? "pass" : "skipped", rewrites };
}

function buildFindings(pf: Omit<Portfolio, "findings">): Finding[] {
  const out: Finding[] = [];
  const { spec, total } = pf;
  const cas = (src: string) => `${src} · ${fmtDate(sourceAsOf["CAMS CAS"])}`;

  // Overlap
  const top = pf.overlaps[0];
  if (top && top.pct >= 60) {
    const combined = top.a.value + top.b.value;
    const exp: Explanation = {
      title: `Overlap: ${top.a.shortName} × ${top.b.shortName}`,
      result: pct(top.pct),
      formulaWords: "For every company both funds hold, take the smaller of the two weights, then add them up.",
      formula: "overlap = Σ min(wₐ, w_b) over common holdings",
      inputs: top.common.slice(0, 6).map((c) => ({
        label: c.name,
        value: `min(${c.wa.toFixed(1)}%, ${c.wb.toFixed(1)}%) = ${Math.min(c.wa, c.wb).toFixed(1)}%`,
        source: `AMC disclosure · ${DISCLOSURE_MONTH}`,
      })),
      steps: [
        `${top.common.length} companies appear in both funds' disclosed portfolios.`,
        `Sum of the smaller weights = ${pct(top.pct)}.`,
        `Combined value in the two funds = ${inr(combined)} (${inr(top.a.value)} + ${inr(top.b.value)}).`,
      ],
      citations: [kb.disclosure!],
      versions: versions([{ label: "Disclosures", value: DISCLOSURE_MONTH }]),
    };
    out.push({
      id: `${spec.id}-overlap`,
      clientId: spec.id,
      kind: "overlap",
      severity: top.pct >= 70 ? "high" : "medium",
      title: "Two funds hold largely the same companies",
      body: [
        "{client}'s ",
        top.a.shortName,
        " and ",
        top.b.shortName,
        " share ",
        { n: pct(top.pct, 0), e: exp },
        " of their portfolios. ",
        { n: inrShort(combined), e: exp },
        " is spread across two funds that give very similar exposure, so the second fund adds little diversification.",
      ],
      impact: combined,
      evidence: [exp],
      compliance: compliance(`${spec.id}-overlap`),
    });
  }

  // Drift
  const worst = ASSET_CLASSES.map((c) => ({ c, d: pf.drift[c] })).sort((x, y) => Math.abs(y.d) - Math.abs(x.d))[0]!;
  if (Math.abs(worst.d) >= 5) {
    const amount = (worst.d / 100) * total;
    const exp: Explanation = {
      title: `${worst.c} drift vs ${spec.risk} model`,
      result: signedPts(worst.d),
      formulaWords: "Actual share of the portfolio minus the model's target share; the rupee gap is that difference times the portfolio value.",
      formula: "drift = actual% − target%;  gap = drift × portfolio value",
      inputs: [
        { label: `${worst.c} value`, value: inr(pf.allocation[worst.c]), source: "Snapshot (CAS + Dhan)" },
        { label: "Portfolio value", value: inr(total), source: "Snapshot (CAS + Dhan)" },
        { label: `Actual ${worst.c.toLowerCase()} share`, value: pct(pf.allocationPct[worst.c]) },
        { label: "Model target", value: pct(pf.target[worst.c], 0), source: `IPS v3 · ${spec.risk}` },
      ],
      steps: [
        `${inr(pf.allocation[worst.c])} ÷ ${inr(total)} = ${pct(pf.allocationPct[worst.c])}.`,
        `${pct(pf.allocationPct[worst.c])} − ${pct(pf.target[worst.c], 0)} = ${signedPts(worst.d)}.`,
        `${signedPts(worst.d)} × ${inr(total)} = ${inr(amount)}.`,
      ],
      citations: [kb.ips!, kb.ia!],
      versions: versions(),
    };
    out.push({
      id: `${spec.id}-drift`,
      clientId: spec.id,
      kind: "drift",
      severity: Math.abs(worst.d) >= 10 ? "high" : "medium",
      title: `${worst.c} is ${worst.d > 0 ? "above" : "below"} the agreed model`,
      body: [
        `${worst.c} is `,
        { n: pct(pf.allocationPct[worst.c]), e: exp },
        ` of {client}'s portfolio against a ${pct(pf.target[worst.c], 0)} target for a ${spec.risk.toLowerCase()} profile: `,
        { n: signedPts(worst.d), e: exp },
        `, about `,
        { n: inrShort(Math.abs(amount)), e: exp },
        worst.d > 0 ? " more than the model allows." : " less than the model calls for.",
      ],
      impact: Math.abs(amount),
      evidence: [exp],
      compliance: compliance(`${spec.id}-drift`),
    });
  }

  // Tax timing: lots turning long-term within 30 days with a gain
  const soon = pf.upcomingLots.filter(({ lot }) => lot.gain > 0).sort((a, b) => b.lot.gain - a.lot.gain)[0];
  if (soon) {
    const saving = soon.lot.gain * (STCG_RATE - LTCG_RATE);
    const exp: Explanation = {
      title: `Holding period: ${soon.position.shortName} lot`,
      result: `${soon.lot.daysToLong} days to long-term`,
      formulaWords: "A lot becomes long-term the day after 12 months of holding. The saving is the gain times the difference between the short- and long-term rates.",
      formula: "saving = gain × (20% − 12.5%)",
      inputs: [
        { label: "Acquired", value: fmtDate(soon.lot.acquired), source: cas(soon.position.source) },
        { label: "Long-term from", value: fmtDate(soon.lot.longTermOn) },
        { label: "Lot value", value: inr(soon.lot.value), source: `NAV/price · ${fmtDate(soon.position.asOf)}` },
        { label: "Cost", value: inr(soon.lot.cost), source: "Transaction history" },
        { label: "Unrealised gain", value: inr(soon.lot.gain) },
      ],
      steps: [
        `${fmtDate(soon.lot.acquired)} + 12 months → long-term from ${fmtDate(soon.lot.longTermOn)} (${soon.lot.daysToLong} days from today).`,
        `Gain = ${inr(soon.lot.value)} − ${inr(soon.lot.cost)} = ${inr(soon.lot.gain)}.`,
        `${inr(soon.lot.gain)} × 7.5% = ${inr(saving)} lower tax if sold after that date (before any exemption).`,
      ],
      citations: [kb.stcg!, kb.ltcg!],
      versions: versions([{ label: "Ruleset", value: RULESET_VERSION }]),
    };
    out.push({
      id: `${spec.id}-tax-timing`,
      clientId: spec.id,
      kind: "tax-timing",
      severity: "medium",
      title: "A lot turns long-term soon",
      body: [
        `A ${soon.position.shortName} lot with an unrealised gain of `,
        { n: inr(soon.lot.gain), e: exp },
        ` becomes long-term on ${fmtDate(soon.lot.longTermOn)}, in `,
        { n: `${soon.lot.daysToLong} days`, e: exp },
        `. If {client} plans to sell it, waiting until then lowers the tax by about `,
        { n: inr(saving), e: exp },
        ".",
      ],
      impact: saving,
      evidence: [exp],
      compliance: compliance(`${spec.id}-tax-timing`, 1),
    });
  }

  // LTCG exemption headroom
  if (pf.exemptionLeft > 0 && pf.ltGainUnrealised > 10_000) {
    const usable = Math.min(pf.exemptionLeft, pf.ltGainUnrealised);
    const exp: Explanation = {
      title: `LTCG exemption headroom · ${FY_LABEL}`,
      result: inr(pf.exemptionLeft),
      formulaWords: "The yearly exemption minus long-term gains already realised this financial year.",
      formula: "headroom = ₹1,25,000 − realised LTCG (FY)",
      inputs: [
        { label: "Annual exemption", value: inr(LTCG_EXEMPTION), source: kb.ltcg!.version },
        { label: "Realised LTCG this FY", value: inr(spec.realisedLtcg), source: "Transaction history" },
        { label: "Unrealised long-term gains", value: inr(pf.ltGainUnrealised), source: "Lots held > 12 months" },
      ],
      steps: [
        `${inr(LTCG_EXEMPTION)} − ${inr(spec.realisedLtcg)} = ${inr(pf.exemptionLeft)} headroom.`,
        `Usable now = min(headroom, unrealised LT gains) = ${inr(usable)}.`,
        `At 12.5%, using it this year avoids up to ${inr(usable * LTCG_RATE)} of future tax.`,
      ],
      citations: [kb.ltcg!],
      versions: versions([{ label: "Ruleset", value: RULESET_VERSION }]),
    };
    out.push({
      id: `${spec.id}-harvest`,
      clientId: spec.id,
      kind: "harvest",
      severity: "low",
      title: "Unused long-term gains exemption this year",
      body: [
        "{client} has ",
        { n: inr(pf.exemptionLeft), e: exp },
        ` of the ₹1.25 lakh long-term gains exemption left in ${FY_LABEL}, and long-term lots hold `,
        { n: inrShort(pf.ltGainUnrealised), e: exp },
        " of unrealised gains. Booking gains within the exemption could avoid up to ",
        { n: inr(usable * LTCG_RATE), e: exp },
        " of future tax.",
      ],
      impact: usable * LTCG_RATE,
      evidence: [exp],
      compliance: compliance(`${spec.id}-harvest`),
    });
  }

  // Concentration via look-through
  const big = pf.exposures[0];
  if (big && big.pctOfTotal >= 7) {
    const exp: Explanation = {
      title: `Look-through exposure: ${big.name}`,
      result: pct(big.pctOfTotal),
      formulaWords: "Direct holding plus each fund's value times that fund's weight in the company, divided by the total portfolio.",
      formula: "exposure = (direct + Σ fund value × weight) ÷ portfolio value",
      inputs: [
        ...(big.direct ? [{ label: "Direct shares", value: inr(big.direct), source: `Dhan · ${fmtDate(sourceAsOf.Dhan)}` }] : []),
        ...big.viaFunds.map((v) => ({
          label: `via ${v.fund} (${v.weight.toFixed(1)}%)`,
          value: inr(v.value),
          source: `AMC disclosure · ${DISCLOSURE_MONTH}`,
        })),
        { label: "Portfolio value", value: inr(total) },
      ],
      steps: [`Total exposure = ${inr(big.value)}.`, `${inr(big.value)} ÷ ${inr(total)} = ${pct(big.pctOfTotal)}.`],
      citations: [kb.disclosure!],
      versions: versions([{ label: "Disclosures", value: DISCLOSURE_MONTH }]),
    };
    out.push({
      id: `${spec.id}-concentration`,
      clientId: spec.id,
      kind: "concentration",
      severity: big.pctOfTotal >= 9 ? "medium" : "low",
      title: `Hidden concentration in ${big.name}`,
      body: [
        `Once fund holdings are looked through, ${big.name} is `,
        { n: pct(big.pctOfTotal), e: exp },
        ` of {client}'s total portfolio (`,
        { n: inrShort(big.value), e: exp },
        `), held ${big.direct ? "directly and " : ""}through ${big.viaFunds.length} fund${big.viaFunds.length === 1 ? "" : "s"}.`,
      ],
      impact: big.value,
      evidence: [exp],
      compliance: compliance(`${spec.id}-concentration`),
    });
  }

  const rank: Record<Severity, number> = { high: 0, medium: 1, low: 2 };
  return out.sort((a, b) => rank[a.severity] - rank[b.severity] || b.impact - a.impact);
}

export function buildPortfolio(spec: ClientSpec): Portfolio {
  const positions = buildPositions(spec);
  const total = positions.reduce((s, p) => s + p.value, 0);
  const allocation = Object.fromEntries(ASSET_CLASSES.map((c) => [c, 0])) as Record<AssetClass, number>;
  for (const p of positions) allocation[p.assetClass] += p.value;
  const allocationPct = Object.fromEntries(
    ASSET_CLASSES.map((c) => [c, (allocation[c] / total) * 100]),
  ) as Record<AssetClass, number>;
  const target = models[spec.risk as RiskCategory];
  const drift = Object.fromEntries(ASSET_CLASSES.map((c) => [c, allocationPct[c] - target[c]])) as Record<AssetClass, number>;
  const { exposures, lookThroughPct } = computeExposures(positions, total);
  const overlaps = computeOverlaps(positions);
  const equityLots = positions.filter((p) => p.assetClass === "Equity").flatMap((p) => p.lots.map((lot) => ({ position: p, lot })));
  const ltGainUnrealised = equityLots
    .filter(({ lot }) => lot.isLong && lot.gain > 0 && !(lot.lockedUntil && lot.lockedUntil > TODAY))
    .reduce((s, { lot }) => s + lot.gain, 0);
  const upcomingLots = equityLots.filter(({ lot }) => !lot.isLong && lot.daysToLong <= 30);
  const bySource = new Map<SourceName, number>();
  for (const p of positions) bySource.set(p.source, (bySource.get(p.source) ?? 0) + p.value);
  const sourceMix = [...bySource.entries()].map(([source, value]) => ({ source, value, asOf: sourceAsOf[source] }));
  const freshnessDays = Math.max(...sourceMix.map((s) => daysBetween(s.asOf, TODAY)));
  const base = {
    spec, positions, total, allocation, allocationPct, target, drift, exposures, lookThroughPct, overlaps,
    ltGainUnrealised, exemptionLeft: Math.max(0, LTCG_EXEMPTION - spec.realisedLtcg), upcomingLots, sourceMix, freshnessDays,
  };
  return { ...base, findings: buildFindings(base) };
}

export const portfolios: Portfolio[] = clientSpecs.map(buildPortfolio);
export const portfolioById: Record<string, Portfolio> = Object.fromEntries(portfolios.map((p) => [p.spec.id, p]));
export const allFindings: Finding[] = portfolios.flatMap((p) => p.findings);
export const bookAum = portfolios.reduce((s, p) => s + p.total, 0);
