import type { Role } from "@/lib/roles";

/**
 * Synthetic demo book. Every person, firm and fund name here is fictional.
 * Company names are real listed companies; all weights, prices and positions are invented.
 */

export const TODAY = "2026-10-17";
export const FY_LABEL = "FY 2026-27";
export const LTCG_EXEMPTION = 125_000;
export const LTCG_RATE = 0.125;
export const STCG_RATE = 0.2;
export const ENGINE_VERSION = "core 0.4.0";
export const RULESET_VERSION = "tax-in FY2026-27 r3";
export const DISCLOSURE_MONTH = "Sep 2026";

export const firm = {
  name: "Anand Wealth Partners",
  registration: "INA-DEMO-0042",
  type: "RIA" as const,
  advisor: { name: "Priya Anand", role: "Owner · Advisor" },
};

export type AssetClass = "Equity" | "Debt" | "Gold" | "Cash";
export const ASSET_CLASSES: AssetClass[] = ["Equity", "Debt", "Gold", "Cash"];

export interface Stock {
  symbol: string;
  name: string;
  sector: string;
  isin?: string;
  price: number;
}

export const stocks: Record<string, Stock> = Object.fromEntries(
  (
    [
      ["HDFCBANK", "HDFC Bank", "Financials", "INE040A01034", 1782],
      ["ICICIBANK", "ICICI Bank", "Financials", "INE090A01021", 1388],
      ["RELIANCE", "Reliance Industries", "Energy", "INE002A01018", 1412],
      ["INFY", "Infosys", "IT", "INE009A01021", 1638],
      ["TCS", "Tata Consultancy Services", "IT", "INE467B01029", 3346],
      ["BHARTIARTL", "Bharti Airtel", "Telecom", "INE397D01024", 1915],
      ["LT", "Larsen & Toubro", "Industrials", "INE018A01030", 3620],
      ["ITC", "ITC", "Consumer staples", "INE154A01025", 418],
      ["SBIN", "State Bank of India", "Financials", "INE062A01020", 842],
      ["AXISBANK", "Axis Bank", "Financials", "INE238A01034", 1176],
      ["HINDUNILVR", "Hindustan Unilever", "Consumer staples", "INE030A01027", 2510],
      ["KOTAKBANK", "Kotak Mahindra Bank", "Financials", undefined, 2140],
      ["BAJFINANCE", "Bajaj Finance", "Financials", undefined, 1012],
      ["MARUTI", "Maruti Suzuki", "Auto", undefined, 15880],
      ["SUNPHARMA", "Sun Pharmaceutical", "Healthcare", undefined, 1745],
      ["TITAN", "Titan Company", "Consumer discretionary", undefined, 3710],
      ["M&M", "Mahindra & Mahindra", "Auto", undefined, 3480],
      ["NTPC", "NTPC", "Utilities", undefined, 352],
      ["ULTRACEMCO", "UltraTech Cement", "Materials", undefined, 12450],
      ["HCLTECH", "HCL Technologies", "IT", undefined, 1588],
      ["TRENT", "Trent", "Consumer discretionary", undefined, 5410],
      ["PERSISTENT", "Persistent Systems", "IT", undefined, 6120],
      ["DIXON", "Dixon Technologies", "Industrials", undefined, 16200],
      ["POLYCAB", "Polycab India", "Industrials", undefined, 7380],
      ["MAXHEALTH", "Max Healthcare", "Healthcare", undefined, 1190],
      ["COFORGE", "Coforge", "IT", undefined, 1810],
      ["INDHOTEL", "Indian Hotels", "Consumer discretionary", undefined, 768],
      ["KPITTECH", "KPIT Technologies", "IT", undefined, 1342],
      ["CDSL", "Central Depository Services", "Financials", undefined, 1620],
    ] as const
  ).map(([symbol, name, sector, isin, price]) => [symbol, { symbol, name, sector, isin, price }]),
);

export interface Fund {
  id: string;
  isin: string;
  name: string;
  shortName: string;
  category: string;
  assetClass: AssetClass;
  nav: number;
  /** Disclosed portfolio weights in %, by stock symbol (equity funds only). */
  weights: Record<string, number>;
}

const f = (
  id: string,
  n: number,
  name: string,
  shortName: string,
  category: string,
  assetClass: AssetClass,
  nav: number,
  weights: Record<string, number> = {},
): Fund => ({ id, isin: `INF0DEMO${String(n).padStart(4, "0")}`, name, shortName, category, assetClass, nav, weights });

export const funds: Record<string, Fund> = Object.fromEntries(
  [
    f("NSB", 1, "Northstar Bluechip Fund", "Northstar Bluechip", "Large Cap", "Equity", 92.41, {
      HDFCBANK: 9.6, ICICIBANK: 8.1, RELIANCE: 8.4, INFY: 6.2, TCS: 4.3, BHARTIARTL: 4.8, LT: 4.1,
      ITC: 3.6, SBIN: 3.2, AXISBANK: 3.0, HINDUNILVR: 2.5, KOTAKBANK: 2.9, BAJFINANCE: 2.2,
      MARUTI: 1.8, SUNPHARMA: 1.9, TITAN: 1.5, "M&M": 1.9, NTPC: 1.6, ULTRACEMCO: 1.3, HCLTECH: 1.7,
    }),
    f("HN50", 2, "Harbor Nifty 50 Index Fund", "Harbor Nifty 50", "Index", "Equity", 41.73, {
      HDFCBANK: 12.9, ICICIBANK: 8.9, RELIANCE: 8.6, INFY: 5.0, BHARTIARTL: 4.6, LT: 3.9, ITC: 3.4,
      TCS: 3.0, SBIN: 2.9, AXISBANK: 3.0, KOTAKBANK: 2.7, "M&M": 2.6, BAJFINANCE: 2.3, HINDUNILVR: 2.0,
      SUNPHARMA: 1.6, HCLTECH: 1.6, MARUTI: 1.6, NTPC: 1.4, TITAN: 1.3, ULTRACEMCO: 1.2,
    }),
    f("MFC", 3, "Meridian Flexi Cap Fund", "Meridian Flexi Cap", "Flexi Cap", "Equity", 68.05, {
      HDFCBANK: 7.8, ICICIBANK: 6.0, BAJFINANCE: 4.1, ITC: 3.9, HCLTECH: 3.5, INFY: 3.2, BHARTIARTL: 3.6,
      MARUTI: 3.0, TRENT: 2.8, PERSISTENT: 2.6, MAXHEALTH: 2.5, COFORGE: 2.4, INDHOTEL: 2.2, DIXON: 2.0,
      POLYCAB: 1.9, KOTAKBANK: 2.1, SUNPHARMA: 2.3,
    }),
    f("ILM", 4, "Indus Large & Midcap Fund", "Indus Large & Mid", "Large & Mid Cap", "Equity", 54.88, {
      ICICIBANK: 6.1, HDFCBANK: 6.8, RELIANCE: 4.2, TRENT: 3.4, PERSISTENT: 3.1, MAXHEALTH: 3.0,
      INDHOTEL: 2.7, COFORGE: 2.5, POLYCAB: 2.6, DIXON: 2.4, BHARTIARTL: 3.3, LT: 2.9, SBIN: 2.2,
      KPITTECH: 2.0, CDSL: 1.6,
    }),
    f("SEL", 5, "Sapphire ELSS Tax Saver Fund", "Sapphire ELSS", "ELSS", "Equity", 118.6, {
      HDFCBANK: 8.9, ICICIBANK: 7.7, RELIANCE: 7.1, INFY: 5.8, TCS: 3.9, BHARTIARTL: 4.4, LT: 4.0,
      ITC: 3.8, AXISBANK: 3.4, SBIN: 3.1, KOTAKBANK: 2.5, HCLTECH: 2.0, "M&M": 2.2, SUNPHARMA: 1.8,
    }),
    f("CSC", 6, "Coastal Small Cap Fund", "Coastal Small Cap", "Small Cap", "Equity", 37.12, {
      KPITTECH: 3.1, CDSL: 3.4, POLYCAB: 2.8, DIXON: 2.6, COFORGE: 2.2, INDHOTEL: 1.9,
    }),
    f("BSD", 7, "Banyan Short Duration Fund", "Banyan Short Duration", "Short Duration Debt", "Debt", 31.44),
    f("KGF", 8, "Kaveri Gold ETF Fund of Fund", "Kaveri Gold FoF", "Gold FoF", "Gold", 27.9),
    f("LLQ", 9, "Lakeview Liquid Fund", "Lakeview Liquid", "Liquid", "Cash", 3120.5),
  ].map((fund) => [fund.id, fund]),
);

export type RiskCategory = "Conservative" | "Moderate" | "Moderately aggressive" | "Aggressive";

export const models: Record<RiskCategory, Record<AssetClass, number>> = {
  Conservative: { Equity: 30, Debt: 55, Gold: 10, Cash: 5 },
  Moderate: { Equity: 50, Debt: 35, Gold: 10, Cash: 5 },
  "Moderately aggressive": { Equity: 70, Debt: 20, Gold: 5, Cash: 5 },
  Aggressive: { Equity: 80, Debt: 12, Gold: 5, Cash: 3 },
};

export type SourceName = "Dhan" | "CDSL CAS" | "CAMS CAS" | "KFintech CAS";

export interface LotSpec {
  acquired: string;
  /** Share of the holding's current value in this lot (0–1). */
  share: number;
  /** Cost as a fraction of this lot's current value. */
  costRatio: number;
}

export interface HoldingSpec {
  ref: string; // fund id or stock symbol
  kind: "fund" | "stock";
  value?: number; // funds
  qty?: number; // stocks
  source: SourceName;
  account: string;
  lots: LotSpec[];
}

export interface ClientSpec {
  id: string;
  name: string;
  city: string;
  age: number;
  risk: RiskCategory;
  lastReview: string;
  realisedLtcg: number;
  dhan: "connected" | "expired" | "none";
  holdings: HoldingSpec[];
}

const cams = (acct: string) => ({ source: "CAMS CAS" as const, account: `Folio ••${acct}` });
const kfin = (acct: string) => ({ source: "KFintech CAS" as const, account: `Folio ••${acct}` });
const dhan = { source: "Dhan" as const, account: "Dhan demat ••7731" };
const lot = (acquired: string, share: number, costRatio: number): LotSpec => ({ acquired, share, costRatio });
const fund = (ref: string, value: number, src: { source: SourceName; account: string }, lots: LotSpec[]): HoldingSpec => ({
  ref, kind: "fund", value, ...src, lots,
});

export const clientSpecs: ClientSpec[] = [
  {
    id: "rohan-deshpande", name: "Rohan Deshpande", city: "Pune", age: 41, risk: "Moderately aggressive",
    lastReview: "2026-04-11", realisedLtcg: 38_000, dhan: "expired",
    holdings: [
      fund("NSB", 620_000, cams("4821"), [lot("2023-06-05", 1, 0.66)]),
      fund("HN50", 550_000, kfin("1907"), [lot("2024-08-19", 1, 0.78)]),
      fund("MFC", 480_000, cams("5530"), [lot("2024-02-12", 0.254, 0.755), lot("2025-10-28", 0.746, 0.8655)]),
      fund("SEL", 240_000, kfin("6612"), [lot("2024-01-15", 1, 0.75)]),
      fund("BSD", 310_000, cams("4821"), [lot("2023-03-01", 1, 0.84)]),
      fund("KGF", 90_000, cams("4821"), [lot("2024-11-20", 1, 0.8)]),
      fund("LLQ", 60_000, cams("4821"), [lot("2026-09-02", 1, 0.995)]),
      { ref: "HDFCBANK", kind: "stock", qty: 120, ...dhan, lots: [lot("2022-03-10", 1, 0.69)] },
      { ref: "INFY", kind: "stock", qty: 80, ...dhan, lots: [lot("2023-01-18", 1, 0.92)] },
      { ref: "RELIANCE", kind: "stock", qty: 60, ...dhan, lots: [lot("2024-07-08", 1, 1.12)] },
      { ref: "ITC", kind: "stock", qty: 300, ...dhan, lots: [lot("2025-11-04", 1, 0.93)] },
    ],
  },
  {
    id: "meera-iyer", name: "Meera Iyer", city: "Chennai", age: 58, risk: "Moderate",
    lastReview: "2026-07-02", realisedLtcg: 110_000, dhan: "none",
    holdings: [
      fund("HN50", 900_000, kfin("3310"), [lot("2021-04-12", 1, 0.58)]),
      fund("SEL", 300_000, kfin("3311"), [lot("2023-02-01", 1, 0.7)]),
      fund("BSD", 1_100_000, cams("8120"), [lot("2022-07-01", 1, 0.83)]),
      fund("KGF", 240_000, cams("8120"), [lot("2023-09-01", 1, 0.74)]),
      fund("LLQ", 150_000, cams("8120"), [lot("2026-08-14", 1, 0.996)]),
    ],
  },
  {
    id: "kavya-nair", name: "Kavya Nair", city: "Kochi", age: 33, risk: "Aggressive",
    lastReview: "2026-05-20", realisedLtcg: 0, dhan: "connected",
    holdings: [
      fund("MFC", 420_000, cams("2207"), [lot("2025-11-10", 1, 0.88)]),
      fund("CSC", 380_000, cams("2207"), [lot("2024-05-01", 1, 0.76)]),
      fund("ILM", 310_000, kfin("9902"), [lot("2025-03-15", 1, 0.84)]),
      fund("KGF", 50_000, cams("2207"), [lot("2025-06-01", 1, 0.86)]),
    ],
  },
  {
    id: "arjun-malhotra", name: "Arjun Malhotra", city: "New Delhi", age: 46, risk: "Moderately aggressive",
    lastReview: "2026-03-28", realisedLtcg: 60_000, dhan: "none",
    holdings: [
      fund("NSB", 780_000, cams("1188"), [lot("2022-11-07", 1, 0.62)]),
      fund("SEL", 320_000, kfin("4407"), [lot("2023-03-20", 1, 0.68)]),
      fund("HN50", 410_000, kfin("4408"), [lot("2024-02-26", 1, 0.8)]),
      fund("BSD", 200_000, cams("1188"), [lot("2024-06-10", 1, 0.9)]),
      fund("LLQ", 40_000, cams("1188"), [lot("2026-10-01", 1, 0.998)]),
    ],
  },
  {
    id: "ananya-rao", name: "Ananya Rao", city: "Bengaluru", age: 29, risk: "Aggressive",
    lastReview: "2026-08-09", realisedLtcg: 0, dhan: "connected",
    holdings: [
      fund("HN50", 220_000, kfin("7012"), [lot("2024-09-02", 1, 0.83)]),
      fund("CSC", 190_000, cams("6634"), [lot("2024-12-16", 1, 0.9)]),
      fund("MFC", 250_000, cams("6634"), [lot("2025-10-30", 1, 0.87)]),
    ],
  },
  {
    id: "vikram-shetty", name: "Vikram Shetty", city: "Mumbai", age: 62, risk: "Conservative",
    lastReview: "2026-09-18", realisedLtcg: 0, dhan: "none",
    holdings: [
      fund("BSD", 1_800_000, cams("0459"), [lot("2021-01-11", 1, 0.8)]),
      fund("HN50", 650_000, kfin("2290"), [lot("2020-12-07", 1, 0.48)]),
      fund("NSB", 350_000, cams("0459"), [lot("2022-05-16", 1, 0.66)]),
      fund("KGF", 300_000, cams("0459"), [lot("2022-02-02", 1, 0.6)]),
      fund("LLQ", 250_000, cams("0459"), [lot("2026-07-21", 1, 0.99)]),
    ],
  },
  {
    id: "neha-joshi", name: "Neha Joshi", city: "Nagpur", age: 37, risk: "Moderate",
    lastReview: "2026-02-14", realisedLtcg: 22_000, dhan: "none",
    holdings: [
      fund("MFC", 510_000, cams("5108"), [lot("2023-08-21", 1, 0.7)]),
      fund("ILM", 430_000, kfin("5109"), [lot("2024-04-08", 1, 0.79)]),
      fund("BSD", 360_000, cams("5108"), [lot("2024-01-05", 1, 0.88)]),
      fund("KGF", 120_000, cams("5108"), [lot("2024-10-14", 1, 0.82)]),
    ],
  },
  {
    id: "farhan-qureshi", name: "Farhan Qureshi", city: "Hyderabad", age: 44, risk: "Moderately aggressive",
    lastReview: "2026-06-30", realisedLtcg: 45_000, dhan: "connected",
    holdings: [
      fund("ILM", 600_000, kfin("8810"), [lot("2023-05-15", 1, 0.66)]),
      fund("CSC", 210_000, cams("3361"), [lot("2024-03-11", 1, 0.85)]),
      fund("BSD", 320_000, cams("3361"), [lot("2023-12-01", 1, 0.87)]),
      fund("KGF", 80_000, cams("3361"), [lot("2024-01-29", 1, 0.78)]),
      fund("LLQ", 60_000, cams("3361"), [lot("2026-09-25", 1, 0.997)]),
    ],
  },
  {
    id: "sneha-kulkarni", name: "Sneha Kulkarni", city: "Pune", age: 51, risk: "Moderate",
    lastReview: "2026-08-27", realisedLtcg: 0, dhan: "none",
    holdings: [
      fund("NSB", 500_000, cams("7720"), [lot("2021-09-13", 1, 0.6)]),
      fund("MFC", 300_000, cams("7720"), [lot("2025-11-12", 1, 0.9)]),
      fund("BSD", 800_000, cams("7720"), [lot("2022-10-03", 1, 0.85)]),
      fund("KGF", 150_000, cams("7720"), [lot("2023-06-19", 1, 0.71)]),
    ],
  },
  {
    id: "ishaan-gupta", name: "Ishaan Gupta", city: "Gurugram", age: 35, risk: "Aggressive",
    lastReview: "2026-01-19", realisedLtcg: 0, dhan: "expired",
    holdings: [
      fund("CSC", 400_000, cams("9041"), [lot("2023-07-24", 1, 0.62)]),
      fund("ILM", 350_000, kfin("9042"), [lot("2024-08-05", 1, 0.83)]),
      fund("MFC", 350_000, cams("9041"), [lot("2024-09-09", 1, 0.84)]),
      fund("HN50", 200_000, kfin("9043"), [lot("2025-01-13", 1, 0.89)]),
    ],
  },
  {
    id: "priyanka-das", name: "Priyanka Das", city: "Kolkata", age: 49, risk: "Moderate",
    lastReview: "2026-09-05", realisedLtcg: 15_000, dhan: "none",
    holdings: [
      fund("HN50", 600_000, kfin("6501"), [lot("2022-01-24", 1, 0.62)]),
      fund("BSD", 700_000, cams("6502"), [lot("2023-04-17", 1, 0.86)]),
      fund("KGF", 140_000, cams("6502"), [lot("2023-11-06", 1, 0.76)]),
      fund("LLQ", 100_000, cams("6502"), [lot("2026-09-30", 1, 0.998)]),
    ],
  },
  {
    id: "aditya-menon", name: "Aditya Menon", city: "Thiruvananthapuram", age: 55, risk: "Moderately aggressive",
    lastReview: "2026-05-04", realisedLtcg: 72_000, dhan: "none",
    holdings: [
      fund("NSB", 450_000, cams("2318"), [lot("2021-02-15", 1, 0.55)]),
      fund("ILM", 380_000, kfin("2319"), [lot("2025-10-24", 1, 0.86)]),
      fund("BSD", 300_000, cams("2318"), [lot("2022-08-08", 1, 0.84)]),
      fund("KGF", 90_000, cams("2318"), [lot("2023-03-27", 1, 0.72)]),
    ],
  },
];

export const sourceAsOf: Record<SourceName, string> = {
  Dhan: "2026-10-16",
  "CDSL CAS": "2026-09-30",
  "CAMS CAS": "2026-09-30",
  "KFintech CAS": "2026-09-30",
};

export interface KbDoc {
  id: string;
  issuer: "Income Tax Dept." | "SEBI" | "AMFI" | "Firm policy";
  title: string;
  section: string;
  summary: string;
  version: string;
  effective: string;
}

/** Summaries are paraphrased for the demo, not quotations. */
export const kb: Record<string, KbDoc> = {
  ltcg: {
    id: "kb-it-ltcg",
    issuer: "Income Tax Dept.",
    title: "Income-tax Act, 2025: long-term capital gains on listed equity and equity-oriented funds",
    section: "Corresponds to s.112A of the 1961 Act",
    summary: "Long-term gains above ₹1.25 lakh in a financial year are taxed at 12.5%. Units held for more than 12 months count as long-term.",
    version: "Act 2025 · Rules 2026",
    effective: "From 1 Apr 2026",
  },
  stcg: {
    id: "kb-it-stcg",
    issuer: "Income Tax Dept.",
    title: "Income-tax Act, 2025: short-term capital gains on listed equity and equity-oriented funds",
    section: "Corresponds to s.111A of the 1961 Act",
    summary: "Gains on units held for 12 months or less are short-term and taxed at 20%.",
    version: "Act 2025 · Rules 2026",
    effective: "From 1 Apr 2026",
  },
  disclosure: {
    id: "kb-sebi-mf-disclosure",
    issuer: "SEBI",
    title: "Master Circular for Mutual Funds: portfolio disclosure",
    section: "Monthly scheme portfolio disclosure",
    summary: "AMCs publish each scheme's full portfolio every month, which is what look-through and overlap are computed from.",
    version: "Master Circular (current)",
    effective: "In force",
  },
  ia: {
    id: "kb-sebi-ia",
    issuer: "SEBI",
    title: "SEBI (Investment Advisers) Regulations, 2013",
    section: "Records of advice and rationale",
    summary: "Advisers keep records of the client's risk profile, suitability and the rationale for advice given.",
    version: "As amended",
    effective: "In force",
  },
  ips: {
    id: "kb-firm-ips",
    issuer: "Firm policy",
    title: "Anand Wealth Investment Policy Statement",
    section: "Model portfolios and rebalancing bands",
    summary: "Rebalancing is reviewed when an asset class drifts more than 5 percentage points from the client's model.",
    version: "v3",
    effective: "From 1 Apr 2026",
  },
};

export const aumHistoryFactors = [0.86, 0.87, 0.89, 0.88, 0.9, 0.92, 0.93, 0.92, 0.95, 0.97, 0.985, 1];
export const aumHistoryMonths = ["Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct"];

/* Team, roles and access (all fictional) */

// Roles and their rules live in lib/roles.ts (mirrors the API).
export type { Role };

export interface Member {
  id: string;
  name: string;
  email: string;
  role: Role;
  status: "Active" | "Invited" | "Suspended";
  mfa: boolean;
  lastActive: string;
  inviteCode?: string; // one-time code an invited person uses to join (demo keeps it in memory)
}

export const members: Member[] = [
  { id: "m-priya", name: "Priya Anand", email: "priya@anandwealth.in", role: "Owner", status: "Active", mfa: true, lastActive: "Now" },
  { id: "m-arun", name: "Arun Kumar", email: "arun@anandwealth.in", role: "Adviser", status: "Active", mfa: true, lastActive: "12 min ago" },
  { id: "m-sana", name: "Sana Sheikh", email: "sana@anandwealth.in", role: "Analyst", status: "Active", mfa: true, lastActive: "Yesterday" },
  { id: "m-dev", name: "Dev Mehra", email: "dev@anandwealth.in", role: "Compliance", status: "Active", mfa: true, lastActive: "3 days ago" },
  { id: "m-neel", name: "Neel Bose", email: "neel@anandwealth.in", role: "Admin", status: "Active", mfa: true, lastActive: "1 hour ago" },
];

/** Primary adviser for each client. */
export const primaryAdviser: Record<string, string> = {
  "rohan-deshpande": "m-priya",
  "meera-iyer": "m-priya",
  "arjun-malhotra": "m-priya",
  "vikram-shetty": "m-priya",
  "sneha-kulkarni": "m-priya",
  "priyanka-das": "m-priya",
  "aditya-menon": "m-priya",
  "kavya-nair": "m-arun",
  "ananya-rao": "m-arun",
  "neha-joshi": "m-arun",
  "farhan-qureshi": "m-arun",
  "ishaan-gupta": "m-arun",
};

export const permissions: { label: string; roles: Role[] }[] = [
  { label: "See all firm clients", roles: ["Owner", "Analyst", "Compliance"] },
  { label: "See assigned clients", roles: ["Owner", "Adviser", "Analyst", "Compliance"] },
  { label: "Upload statements, resolve data exceptions", roles: ["Owner", "Adviser", "Analyst"] },
  { label: "Accept findings and approve reviews", roles: ["Owner", "Adviser"] },
  { label: "Request client access", roles: ["Owner", "Adviser"] },
  { label: "Invite people, change staff roles, suspend", roles: ["Owner", "Admin"] },
  { label: "Appoint or remove Owners and Admins", roles: ["Owner"] },
  { label: "AI kill switch and firm settings", roles: ["Owner"] },
  { label: "Read audit trail", roles: ["Owner", "Admin", "Compliance"] },
];

export type Scope = "Mutual fund statements" | "Dhan holdings" | "Tradebook" | "Tax summary" | "Reports";

export interface AccessRequest {
  id: string;
  clientId: string;
  requestedBy: string; // member id
  forMember: string; // who will get access
  scopes: Scope[];
  reason: string;
  days: number;
  status: "Waiting for client" | "Approved" | "Declined";
  created: string;
}

export const initialRequests: AccessRequest[] = [
  {
    id: "rq-101",
    clientId: "rohan-deshpande",
    requestedBy: "m-priya",
    forMember: "m-arun",
    scopes: ["Mutual fund statements", "Dhan holdings"],
    reason: "Arun covers my clients while I am on leave from 20 Oct to 3 Nov.",
    days: 30,
    status: "Waiting for client",
    created: "2026-10-16",
  },
  {
    id: "rq-102",
    clientId: "rohan-deshpande",
    requestedBy: "m-priya",
    forMember: "m-priya",
    scopes: ["Tradebook"],
    reason: "Purchase dates for your shares, so long-term status is exact.",
    days: 365,
    status: "Waiting for client",
    created: "2026-10-17",
  },
  {
    id: "rq-090",
    clientId: "kavya-nair",
    requestedBy: "m-arun",
    forMember: "m-arun",
    scopes: ["Mutual fund statements", "Dhan holdings"],
    reason: "Annual review.",
    days: 365,
    status: "Approved",
    created: "2026-10-14",
  },
];

export interface ClientShare {
  id: string;
  clientId: string;
  recipient: string;
  relation: "Chartered accountant" | "Family member" | "Another adviser";
  email: string;
  scopes: Scope[];
  until: string;
  status: "Active" | "Revoked";
}

export const initialShares: ClientShare[] = [
  {
    id: "sh-7",
    clientId: "rohan-deshpande",
    recipient: "R. Mehta & Co",
    relation: "Chartered accountant",
    email: "filings@mehtaco.example",
    scopes: ["Tax summary"],
    until: "2026-11-15",
    status: "Active",
  },
];

export interface DeviceSession {
  id: string;
  memberId: string;
  device: string;
  place: string;
  last: string;
  current?: boolean;
}

export const initialSessions: DeviceSession[] = [
  { id: "s1", memberId: "m-priya", device: "Chrome on Windows", place: "Pune, IN", last: "Active now", current: true },
  { id: "s2", memberId: "m-priya", device: "Safari on iPhone", place: "Pune, IN", last: "2 hours ago" },
  { id: "s3", memberId: "m-arun", device: "Edge on Windows", place: "Mumbai, IN", last: "12 min ago" },
  { id: "s4", memberId: "m-sana", device: "Firefox on Ubuntu", place: "Pune, IN", last: "Yesterday" },
];
