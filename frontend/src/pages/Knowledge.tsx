import { ArrowUp, BookOpen, ExternalLink, Layers, Loader2, Search, ShieldAlert, Sparkles } from "lucide-react";
import { type FormEvent, type ReactNode, useMemo, useState } from "react";

import { Badge, Button, Card, CardHeader } from "@/components/ui";
import { cn } from "@/lib/cn";
import { ask, kbChunks, kbDocuments, type RagAnswer } from "@/lib/rag";

const SUGGESTIONS = [
  "Is the ₹1.25 lakh LTCG exemption per fund or for the whole year?",
  "How long is an ELSS SIP instalment locked in?",
  "What records must an investment adviser keep?",
  "Within how many hours must a data breach be reported?",
  "Who is responsible if a vendor's AI tool gives a wrong output?",
  "Should my client buy more Reliance?",
];

/** Turns "text [1] more [2]" into text with clickable citation chips. */
function Cited({ text, onCite }: { text: string; onCite: (n: number) => void }) {
  const parts = text.split(/(\[\d+\])/g);
  return (
    <>
      {parts.map((p, i) => {
        const m = p.match(/^\[(\d+)\]$/);
        return m ? (
          <button
            key={i}
            onClick={() => onCite(Number(m[1]))}
            className="mx-0.5 inline-flex h-[18px] min-w-[18px] cursor-pointer items-center justify-center rounded-md bg-accent-soft px-1 align-[2px] text-[11px] font-semibold text-accent hover:bg-accent hover:text-accent-fg"
            aria-label={`Source ${m[1]}`}
          >
            {m[1]}
          </button>
        ) : (
          <span key={i}>{p}</span>
        );
      })}
    </>
  );
}

function ModeBadge({ a }: { a: RagAnswer }): ReactNode {
  if (a.mode === "refused") return <Badge tone="critical"><ShieldAlert aria-hidden /> Blocked: asks for a buy/sell call</Badge>;
  if (a.mode === "not_found") return <Badge tone="warning">Not in the knowledge base</Badge>;
  return (
    <Badge tone="accent">
      <Sparkles aria-hidden /> {a.mode === "llm" ? "Generated, citations verified" : "Quoted from sources"} · {a.engine === "api" ? "API hybrid search" : "in-browser BM25"}
    </Badge>
  );
}

export function Knowledge() {
  const [q, setQ] = useState("");
  const [answer, setAnswer] = useState<RagAnswer | null>(null);
  const [busy, setBusy] = useState(false);
  const [focus, setFocus] = useState<number | null>(null);
  const [filter, setFilter] = useState("");

  const run = async (question: string) => {
    if (question.trim().length < 3 || busy) return;
    setQ(question);
    setBusy(true);
    setFocus(null);
    const a = await ask(question);
    setTimeout(() => {
      setAnswer(a);
      setBusy(false);
    }, 250);
  };

  const docs = useMemo(
    () => kbDocuments.filter((d) => `${d.title} ${d.issuer} ${d.sections.map((s) => s.heading).join(" ")}`.toLowerCase().includes(filter.toLowerCase())),
    [filter],
  );

  return (
    <div className="gutter-x mx-auto max-w-[1300px] space-y-5 py-5 sm:py-6">
      <section className="aurora relative overflow-hidden rounded-2xl border border-line p-5 sm:p-7">
        <div className="dot-grid absolute inset-0 opacity-60" aria-hidden />
        <div className="relative">
          <p className="eyebrow flex items-center gap-1.5">
            <BookOpen className="size-3.5" aria-hidden /> Ask the rulebook
          </p>
          <h2 className="mt-1 max-w-2xl font-display text-[24px] font-semibold leading-tight text-fg sm:text-[28px]">
            Answers come only from {kbDocuments.length} cited sources: SEBI, Income Tax, DPDP and your firm policy.
          </h2>
          <form
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              void run(q);
            }}
            className="mt-4 flex items-center gap-2 rounded-2xl border border-line bg-surface p-1.5 pl-4 shadow-card focus-within:border-accent"
          >
            <Search className="size-4 shrink-0 text-muted" aria-hidden />
            <label htmlFor="rag-q" className="sr-only">
              Question
            </label>
            <input
              id="rag-q"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="e.g. How are long-term gains on equity funds taxed?"
              className="h-10 min-w-0 flex-1 bg-transparent text-[14px] text-fg outline-none placeholder:text-muted"
            />
            <Button type="submit" variant="primary" size="icon" aria-label="Ask" disabled={busy || q.trim().length < 3}>
              {busy ? <Loader2 className="animate-spin" /> : <ArrowUp />}
            </Button>
          </form>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {SUGGESTIONS.map((s) => (
              <button key={s} onClick={() => void run(s)} className="cursor-pointer rounded-full border border-line bg-surface/80 px-3 py-1.5 text-[12px] text-fg-2 backdrop-blur transition-colors hover:border-accent hover:text-fg">
                {s}
              </button>
            ))}
          </div>
        </div>
      </section>

      {answer && (
        <div className="grid gap-4 lg:grid-cols-12">
          <Card className="p-5 lg:col-span-7">
            <div className="flex flex-wrap items-center gap-2">
              <ModeBadge a={answer} />
            </div>
            <p className="mt-3 text-[15px] leading-[1.75] text-fg">
              <Cited text={answer.text} onCite={setFocus} />
            </p>
            {answer.citations.length > 0 && (
              <div className="mt-5 space-y-2">
                <p className="eyebrow">Sources</p>
                {answer.citations.map((c) => (
                  <div
                    key={c.n}
                    className={cn("rounded-xl border p-3 transition-colors", focus === c.n ? "border-accent bg-accent-soft/50" : "border-line")}
                  >
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="flex size-5 items-center justify-center rounded-md bg-accent text-[11px] font-semibold text-accent-fg">{c.n}</span>
                      <Badge tone="outline">{c.chunk.doc.issuer}</Badge>
                      <span className="text-[12px] text-muted">{c.chunk.doc.version}</span>
                    </div>
                    <p className="mt-1.5 text-[13px] font-medium text-fg">
                      {c.chunk.doc.title} · <span className="text-fg-2">{c.chunk.section}</span>
                    </p>
                    <p className="mt-1 text-[12.5px] leading-relaxed text-fg-2">{c.chunk.text}</p>
                    <a href={c.chunk.doc.source_url} target="_blank" rel="noreferrer" className="mt-1.5 inline-flex items-center gap-1 text-[12px] text-accent hover:underline">
                      Primary source <ExternalLink className="size-3" aria-hidden />
                    </a>
                  </div>
                ))}
              </div>
            )}
          </Card>
          <Card className="lg:col-span-5">
            <CardHeader title="How this answer was built" description="Retrieve → check relevance → quote → cite" action={<Layers className="size-4 text-muted" />} />
            <ol className="space-y-3 p-5 text-[12.5px]">
              <li className="flex gap-2.5">
                <span className="tabular flex size-5 shrink-0 items-center justify-center rounded-full bg-surface-2 text-[11px] font-semibold text-fg">1</span>
                <span className="text-fg-2">
                  Personal identifiers removed from the question, then a compliance check. {answer.mode === "refused" ? <b className="text-critical-text">Blocked: it asks for a security-specific call.</b> : "Passed."}
                </span>
              </li>
              <li className="flex gap-2.5">
                <span className="tabular flex size-5 shrink-0 items-center justify-center rounded-full bg-surface-2 text-[11px] font-semibold text-fg">2</span>
                <span className="text-fg-2">Searched {kbChunks.length} passages. Top matches:</span>
              </li>
            </ol>
            <ul className="space-y-1.5 px-5">
              {answer.retrieved.map((h) => (
                <li key={h.chunk.id} className="flex items-center gap-2 rounded-lg bg-surface-2/70 px-2.5 py-1.5 text-[12px]">
                  <span className="tabular w-5 text-muted">#{h.rank}</span>
                  <span className="min-w-0 flex-1 truncate text-fg">{h.chunk.section}</span>
                  <span className="tabular font-mono text-[11px] text-muted">{h.score.toFixed(2)}</span>
                </li>
              ))}
            </ul>
            <ol start={3} className="space-y-3 p-5 text-[12.5px]">
              <li className="flex gap-2.5">
                <span className="tabular flex size-5 shrink-0 items-center justify-center rounded-full bg-surface-2 text-[11px] font-semibold text-fg">3</span>
                <span className="text-fg-2">
                  Relevance check: <b className="tabular text-fg">{Math.round(answer.coverage * 100)}%</b> of the question's key terms appear in the best passages (minimum 40%).
                </span>
              </li>
              <li className="flex gap-2.5">
                <span className="tabular flex size-5 shrink-0 items-center justify-center rounded-full bg-surface-2 text-[11px] font-semibold text-fg">4</span>
                <span className="text-fg-2">Answer built from quoted sentences only, each with its source number. With a model connected, the API verifies every citation and number before showing it.</span>
              </li>
            </ol>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader
          title="Library"
          description={`${kbDocuments.length} documents · ${kbChunks.length} passages · plain-language summaries with links to the official text`}
          action={
            <label className="flex h-8 items-center gap-1.5 rounded-lg border border-line bg-surface px-2.5 focus-within:border-accent">
              <Search className="size-3.5 text-muted" aria-hidden />
              <span className="sr-only">Filter documents</span>
              <input id="kb-filter" value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter" className="w-28 bg-transparent text-[12.5px] text-fg outline-none sm:w-40" />
            </label>
          }
        />
        <div className="grid gap-3 p-4 sm:p-5 md:grid-cols-2 xl:grid-cols-3">
          {docs.map((d) => (
            <div key={d.id} className="flex flex-col rounded-xl border border-line p-4">
              <div className="flex flex-wrap gap-1.5">
                <Badge tone={d.issuer === "Firm policy" ? "ai" : "accent"}>{d.issuer}</Badge>
                <Badge tone="outline">{d.effective}</Badge>
              </div>
              <p className="mt-2 text-[13.5px] font-semibold leading-snug text-fg">{d.title}</p>
              <p className="mt-1 text-[12px] text-muted">{d.sections.map((s) => s.heading).join(" · ")}</p>
              <p className="mt-auto pt-3 text-[11.5px] italic text-muted">{d.kind}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
