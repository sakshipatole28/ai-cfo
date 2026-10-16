/**
 * In-browser RAG over the same knowledge base the API uses (data/kb/*.md).
 * Retrieval here is BM25 only; the API adds dense embeddings (bge-small) and
 * fuses both rankings with Reciprocal Rank Fusion. If VITE_API_URL is set,
 * `ask` calls the API instead.
 */

const RAW = import.meta.glob("../../../data/kb/*.md", { query: "?raw", import: "default", eager: true }) as Record<string, string>;

export interface KbDocument {
  id: string;
  issuer: string;
  title: string;
  source_url: string;
  version: string;
  effective: string;
  kind: string;
  sections: { heading: string; text: string }[];
}

export interface KbChunk {
  id: string;
  doc: KbDocument;
  section: string;
  text: string;
}

export interface RetrievedChunk {
  chunk: KbChunk;
  rank: number;
  score: number;
}

export interface RagCitation {
  n: number;
  chunk: KbChunk;
}

export interface RagAnswer {
  question: string;
  text: string;
  mode: "extractive" | "refused" | "not_found" | "llm";
  citations: RagCitation[];
  retrieved: RetrievedChunk[];
  coverage: number;
  engine: "browser" | "api";
}

const STOP = new Set(
  "a an and are as at be been but by can could did do does for from had has have how i if in into is it its may me must my of on or our shall should so than that the their them then there these they this those to was we were what when where which who whom why will with would you your per also any each such".split(" "),
);

/** Light suffix stemmer (the API uses Snowball; this keeps the browser bundle small). */
function stem(t: string): string {
  if (/\d/.test(t) || t.length <= 4) return t;
  for (const [suf, rep] of [
    ["ational", "ate"], ["ations", "ate"], ["ation", "ate"], ["utions", "ute"], ["ution", "ute"],
    ["ments", ""], ["ment", ""], ["ings", ""], ["ing", ""], ["ies", "y"], ["ors", ""], ["ers", ""],
    ["ed", ""], ["es", ""], ["s", ""],
  ] as const) {
    if (t.endsWith(suf) && t.length - suf.length >= 3) return t.slice(0, t.length - suf.length) + rep;
  }
  return t;
}

export function tokenize(text: string): string[] {
  return (text.toLowerCase().replace(/\[redacted_[a-z]+\]/g, " ").match(/[a-z0-9₹]+(?:\.[0-9]+)?/g) ?? [])
    .filter((t) => !STOP.has(t))
    .map(stem);
}

export function sentences(text: string): string[] {
  return text.split(/(?<=[.!?])\s+(?=[A-Z₹0-9"'(])/).map((s) => s.trim()).filter(Boolean);
}

function parse(raw: string): KbDocument {
  const lines = raw.trim().split("\n");
  const end = lines.indexOf("---", 1);
  const meta: Record<string, string> = {};
  for (const line of lines.slice(1, end)) {
    const i = line.indexOf(":");
    if (i > 0) meta[line.slice(0, i).trim()] = line.slice(i + 1).trim();
  }
  const sections: KbDocument["sections"] = [];
  let heading = meta.title ?? "";
  let buf: string[] = [];
  const flush = () => {
    const text = buf.join(" ").replace(/\s+/g, " ").trim();
    if (text) sections.push({ heading, text });
  };
  for (const line of lines.slice(end + 1)) {
    if (line.startsWith("## ")) {
      flush();
      heading = line.slice(3).trim();
      buf = [];
    } else buf.push(line);
  }
  flush();
  return {
    id: meta.id ?? "",
    issuer: meta.issuer ?? "",
    title: meta.title ?? "",
    source_url: meta.source_url ?? "",
    version: meta.version ?? "",
    effective: meta.effective ?? "",
    kind: meta.kind ?? "",
    sections,
  };
}

export const kbDocuments: KbDocument[] = Object.values(RAW).map(parse).sort((a, b) => a.issuer.localeCompare(b.issuer) || a.title.localeCompare(b.title));

export const kbChunks: KbChunk[] = kbDocuments.flatMap((doc) => {
  const out: KbChunk[] = [];
  for (const s of doc.sections) {
    let cur: string[] = [];
    for (const sentence of sentences(s.text)) {
      if (cur.length && [...cur, sentence].join(" ").length > 700) {
        out.push({ id: `${doc.id}#${out.length}`, doc, section: s.heading, text: cur.join(" ") });
        cur = [cur[cur.length - 1]!];
      }
      cur.push(sentence);
    }
    if (cur.length) out.push({ id: `${doc.id}#${out.length}`, doc, section: s.heading, text: cur.join(" ") });
  }
  return out;
});

const indexText = (c: KbChunk) => `${c.doc.title}. ${c.section}. ${c.text}`;

class BM25 {
  private tf: Map<string, number>[];
  private len: number[];
  private avg: number;
  idf = new Map<string, number>();

  constructor(docs: string[][], private k1 = 1.5, private b = 0.75) {
    this.tf = docs.map((d) => {
      const m = new Map<string, number>();
      for (const t of d) m.set(t, (m.get(t) ?? 0) + 1);
      return m;
    });
    this.len = docs.map((d) => d.length);
    this.avg = this.len.reduce((a, b) => a + b, 0) / Math.max(docs.length, 1);
    const df = new Map<string, number>();
    for (const m of this.tf) for (const t of m.keys()) df.set(t, (df.get(t) ?? 0) + 1);
    for (const [t, f] of df) this.idf.set(t, Math.log(1 + (docs.length - f + 0.5) / (f + 0.5)));
  }

  scores(query: string[]): number[] {
    const q = [...new Set(query)];
    return this.tf.map((m, i) => {
      let s = 0;
      for (const t of q) {
        const f = m.get(t);
        if (!f) continue;
        const norm = this.k1 * (1 - this.b + (this.b * this.len[i]!) / this.avg);
        s += (this.idf.get(t)! * f * (this.k1 + 1)) / (f + norm);
      }
      return s;
    });
  }
}

const bm25 = new BM25(kbChunks.map((c) => tokenize(indexText(c))));
const maxIdf = Math.max(...bm25.idf.values());

export function search(query: string, k = 5): RetrievedChunk[] {
  return bm25
    .scores(tokenize(query))
    .map((score, i) => ({ score, i }))
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, k)
    .map((x, r) => ({ chunk: kbChunks[x.i]!, rank: r + 1, score: x.score }));
}

/** IDF-weighted share of the question's terms found in a passage. */
export function coverage(question: string, chunk: KbChunk): number {
  const terms = [...new Set(tokenize(question))];
  if (!terms.length) return 0;
  const present = new Set(tokenize(indexText(chunk)));
  const w = (t: string) => bm25.idf.get(t) ?? maxIdf;
  return terms.filter((t) => present.has(t)).reduce((s, t) => s + w(t), 0) / terms.reduce((s, t) => s + w(t), 0);
}

const ADVICE = [
  /\b(should|shall|can|must)\s+(i|we|he|she|they|my client|the client|\w+)\s+(buy|sell|invest in|exit|switch to|add|book)\b/i,
  /\b(which|what|best)\s+(stocks?|shares?|funds?|schemes?)\s+(should|to|will)\b/i,
  /\b(multibagger|target price|guaranteed returns?|sure[- ]shot|double my money)\b/i,
];

export function isAdviceRequest(q: string): boolean {
  return ADVICE.some((r) => r.test(q));
}

function redact(q: string): string {
  return q.replace(/\b[A-Z]{5}[0-9]{4}[A-Z]\b/g, "[REDACTED_PAN]").replace(/\b[\w.+-]+@[\w-]+\.[\w.-]+\b/g, "[REDACTED_EMAIL]");
}

export function askLocal(raw: string): RagAnswer {
  const question = redact(raw.trim());
  if (isAdviceRequest(question)) {
    const hit = search("investment adviser suitability rationale for advice", 1);
    return {
      question,
      text: "This assistant explains rules and computed facts; it does not recommend buying or selling a specific security. That decision rests with the registered adviser, recorded with the client's risk profile and the rationale [1].",
      mode: "refused",
      citations: hit.map((h) => ({ n: 1, chunk: h.chunk })),
      retrieved: hit,
      coverage: 0,
      engine: "browser",
    };
  }
  const retrieved = search(question, 4);
  const cov = Math.max(0, ...retrieved.slice(0, 3).map((h) => coverage(question, h.chunk)));
  if (!retrieved.length || cov < 0.4) {
    return { question, text: "The knowledge base does not cover this question. Try rephrasing, or check the primary source.", mode: "not_found", citations: [], retrieved, coverage: cov, engine: "browser" };
  }
  const q = new Set(tokenize(question));
  const scored: { score: number; overlap: number; n: number; s: string }[] = [];
  retrieved.forEach((h, idx) =>
    sentences(h.chunk.text).forEach((s, pos) => {
      const overlap = tokenize(s).filter((t, i, a) => q.has(t) && a.indexOf(t) === i).length;
      if (overlap) scored.push({ score: overlap + 0.5 / (idx + 1) - 0.01 * pos, overlap, n: idx + 1, s });
    }),
  );
  const best = Math.max(...scored.map((x) => x.overlap));
  const floor = best === 1 ? 1 : Math.max(2, Math.ceil(0.6 * best));
  const picked: { n: number; s: string }[] = [];
  for (const x of scored.filter((x) => x.overlap >= floor).sort((a, b) => b.score - a.score)) {
    if (!picked.some((p) => p.s === x.s)) picked.push(x);
    if (picked.length === 3) break;
  }
  const used = [...new Set(picked.map((p) => p.n))].sort((a, b) => a - b);
  return {
    question,
    text: picked.map((p) => `${p.s} [${p.n}]`).join(" "),
    mode: "extractive",
    citations: used.map((n) => ({ n, chunk: retrieved[n - 1]!.chunk })),
    retrieved,
    coverage: cov,
    engine: "browser",
  };
}

/** Uses the API when configured (hybrid retrieval + optional LLM), otherwise the in-browser engine. */
export async function ask(question: string): Promise<RagAnswer> {
  const api = import.meta.env.VITE_API_URL as string | undefined;
  if (!api) return askLocal(question);
  try {
    const r = await fetch(`${api}/v1/rag/ask`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question }) });
    if (!r.ok) throw new Error(String(r.status));
    const body = (await r.json()) as {
      answer: string;
      mode: RagAnswer["mode"];
      citations: { n: number; chunk_id: string }[];
      retrieved: { chunk_id: string; score: number }[];
    };
    const byId = new Map(kbChunks.map((c) => [c.id, c]));
    return {
      question,
      text: body.answer,
      mode: body.mode,
      citations: body.citations.filter((c) => byId.has(c.chunk_id)).map((c) => ({ n: c.n, chunk: byId.get(c.chunk_id)! })),
      retrieved: body.retrieved.filter((h) => byId.has(h.chunk_id)).map((h, i) => ({ chunk: byId.get(h.chunk_id)!, rank: i + 1, score: h.score })),
      coverage: 1,
      engine: "api",
    };
  } catch {
    return askLocal(question);
  }
}
