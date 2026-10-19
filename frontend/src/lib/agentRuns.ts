/**
 * Real outputs of the Python LangGraph review pipeline, exported with
 * `uv run python -m aicfo.agents export` (data/synthetic/agent_runs.json).
 * The console replays these traces; with VITE_API_URL set it can call the API instead.
 */
import raw from "../../../data/synthetic/agent_runs.json";

export interface TraceEvent {
  node: string;
  kind: "tool" | "agent" | "guard";
  ms: number;
  summary: string;
  detail: Record<string, unknown>;
}

export interface AgentDraft {
  id: string;
  kind: string;
  agent: string;
  severity: "high" | "medium" | "low";
  title: string;
  evidence_ids: string[];
  impact: number;
  rationale: string;
  text: string;
  citations: { n: string; doc_id: string; chunk_id: string; title: string; section: string; issuer: string; text: string }[];
  author: string;
  compliance: { profile: string; rules: string; classifier: number; judge: string; advice_like: boolean; blocked?: boolean };
  verifier: { passed: boolean; issues: string[]; rewrites: number };
  status: "draft" | "dropped";
}

export interface AgentRun {
  client_id: string;
  as_of: string;
  engine: string;
  drafts: AgentDraft[];
  trace: TraceEvent[];
}

export const agentRuns = (raw as unknown as { generated: string; runs: Record<string, AgentRun> }).runs;
export const runsGenerated = (raw as unknown as { generated: string }).generated;

export interface AgentInfo {
  node: string;
  name: string;
  kind: "tool" | "agent" | "guard";
  role: string;
  uses: string;
}

/** The review graph, in execution order. Analysts run in parallel. */
export const PIPELINE: AgentInfo[] = [
  { node: "load_snapshot", name: "Load snapshot", kind: "tool", role: "Reads the reconciled portfolio for one client.", uses: "Deterministic core" },
  { node: "compute_evidence", name: "Compute evidence", kind: "tool", role: "Calculates overlap, drift, look-through and tax lots, each with formula, inputs and steps.", uses: "Deterministic core" },
  { node: "overlap_analyst", name: "Overlap & Concentration Analyst", kind: "agent", role: "Decides which fund overlaps and single-company exposures matter for this client.", uses: "LLM or firm policy · evidence tools" },
  { node: "allocation_analyst", name: "Allocation Analyst", kind: "agent", role: "Judges drift from the client's model portfolio and its severity.", uses: "LLM or firm policy · evidence tools" },
  { node: "tax_analyst", name: "Tax Analyst", kind: "agent", role: "Finds lots turning long-term and unused LTCG exemption.", uses: "LLM or firm policy · evidence tools" },
  { node: "rank", name: "Rank", kind: "tool", role: "Orders findings by severity and rupee impact; skips ones you dismissed before.", uses: "Deterministic" },
  { node: "explainer", name: "Explainer", kind: "agent", role: "Writes each finding in plain language and cites the rule it relies on.", uses: "RAG over the rulebook · LLM optional" },
  { node: "compliance", name: "Compliance Judge", kind: "guard", role: "Rules, then the ML advice classifier, then an LLM judge for borderline wording.", uses: "Rules · logistic regression · LLM" },
  { node: "verifier", name: "Verifier", kind: "guard", role: "Rejects any number not in the evidence and any citation that doesn't resolve.", uses: "Deterministic" },
];
