import { ArrowUp, Bot, ShieldAlert, ShieldCheck, Sparkles, Wrench } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";

import { Badge, Button, Num, Sheet } from "@/components/ui";
import { FY_LABEL, kb, type KbDoc } from "@/data/demo";
import { type Portfolio, portfolioById, type Seg } from "@/lib/engine";
import { inrShort, pct, signedPts } from "@/lib/format";
import { useApp, useClientName } from "@/state/app";

interface Answer {
  tools: string[];
  body: Seg[];
  citations: KbDoc[];
  blocked?: boolean;
}
interface Message {
  id: number;
  role: "user" | "assistant";
  text?: string;
  answer?: Answer;
}

function respond(q: string, pf: Portfolio, first: string): Answer {
  const s = q.toLowerCase();
  if (/\b(buy|sell|should .* (buy|sell|invest)|recommend|which stock|tip)\b/.test(s)) {
    const rel = pf.exposures.find((e) => e.symbol === "RELIANCE");
    return {
      blocked: true,
      tools: ["compliance.rules → blocked: security-specific instruction"],
      body: [
        "I can't tell you to buy or sell a specific security; that decision belongs to you as the adviser, recorded with your rationale. ",
        rel ? `For context, ${first}'s look-through exposure to Reliance Industries is ${pct(rel.pctOfTotal)} of the portfolio (${inrShort(rel.value)}).` : "",
      ],
      citations: [kb.ia!],
    };
  }
  const drift = pf.findings.find((f) => f.kind === "drift");
  if (/(drift|equity|allocation|target|model|risk)/.test(s)) {
    const e = drift?.evidence[0];
    return {
      tools: [`get_drift(client=${pf.spec.id})`],
      body: e
        ? [
            `Equity is ${pct(pf.allocationPct.Equity)} of ${first}'s portfolio against a ${pf.target.Equity}% model, `,
            { n: signedPts(pf.drift.Equity), e },
            `. Most of the excess comes from four equity funds plus direct shares held at Dhan. Debt is ${signedPts(pf.drift.Debt)} versus the model.`,
          ]
        : [`${first}'s allocation is within 5 points of the model in every asset class.`],
      citations: [kb.ips!],
    };
  }
  const ov = pf.findings.find((f) => f.kind === "overlap");
  if (/(overlap|similar|same|duplicate|fund)/.test(s)) {
    const top = pf.overlaps[0];
    return {
      tools: [`get_overlap(client=${pf.spec.id})`],
      body:
        top && ov
          ? [
              `${top.a.shortName} and ${top.b.shortName} overlap the most: `,
              { n: pct(top.pct, 0), e: ov.evidence[0]! },
              `. The largest shared positions are ${top.common.slice(0, 3).map((c) => c.name).join(", ")}.`,
            ]
          : [top ? `The highest pairwise overlap is ${pct(top.pct, 0)}, below the 60% review threshold.` : "There is only one equity fund, so there is no overlap to measure."],
      citations: [kb.disclosure!],
    };
  }
  if (/(tax|ltcg|stcg|exemption|harvest|lot)/.test(s)) {
    const h = pf.findings.find((f) => f.kind === "harvest" || f.kind === "tax-timing");
    return {
      tools: [`get_tax_position(client=${pf.spec.id}, fy="${FY_LABEL}")`],
      body: h
        ? [
            `${first} has ${inrShort(pf.exemptionLeft)} of the ₹1.25 lakh exemption left in ${FY_LABEL}. `,
            ...(pf.upcomingLots[0]
              ? [`${pf.upcomingLots.length} lot${pf.upcomingLots.length > 1 ? "s" : ""} turn long-term within 30 days; the nearest is `, { n: `${pf.upcomingLots[0].lot.daysToLong} days`, e: h.evidence[0]! }, " away."]
              : ["No lots turn long-term in the next 30 days."]),
          ]
        : [`${first} has no tax timing items this financial year.`],
      citations: [kb.ltcg!, kb.stcg!],
    };
  }
  return {
    tools: ["search_rules(query)"],
    body: ["In the demo I can answer questions about allocation drift, fund overlap and the tax position, using the same calculations as the review."],
    citations: [],
  };
}

export function CopilotPanel() {
  const { copilot, closeCopilot, aiEnabled } = useApp();
  const displayName = useClientName();
  const pf = portfolioById[copilot.clientId ?? "rohan-deshpande"]!;
  const first = displayName(pf.spec.name).split(" ")[0] ?? "";
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [thinking, setThinking] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => setMessages([]), [pf.spec.id]);
  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }), [messages, thinking]);

  const ask = (q: string) => {
    if (!q.trim() || thinking) return;
    const id = Date.now();
    setMessages((m) => [...m, { id, role: "user", text: q }]);
    setDraft("");
    setThinking(true);
    setTimeout(() => {
      setMessages((m) => [...m, { id: id + 1, role: "assistant", answer: respond(q, pf, first) }]);
      setThinking(false);
    }, 700);
  };

  const suggestions = [
    "Why is equity above target?",
    "Which funds overlap the most?",
    "How much LTCG exemption is left?",
    `Should ${first} buy more Reliance?`,
  ];

  return (
    <Sheet
      open={copilot.open}
      onOpenChange={(o) => !o && closeCopilot()}
      title={
        <span className="flex items-center gap-2">
          <Bot className="size-4 text-ai" aria-hidden /> Copilot
        </span>
      }
      description={`Context: ${displayName(pf.spec.name)} · answers use tested calculations and cited rules`}
      footer={
        aiEnabled ? (
          <form
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              ask(draft);
            }}
            className="flex items-end gap-2"
          >
            <label htmlFor="copilot-input" className="sr-only">
              Ask a question
            </label>
            <textarea
              id="copilot-input"
              rows={1}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  ask(draft);
                }
              }}
              placeholder={`Ask about ${first}'s portfolio…`}
              className="max-h-32 min-h-10 flex-1 resize-none rounded-lg border border-line bg-surface-2 px-3 py-2.5 text-[13.5px] text-fg outline-none placeholder:text-muted focus:border-accent"
            />
            <Button type="submit" variant="primary" size="icon" aria-label="Send" disabled={!draft.trim() || thinking}>
              <ArrowUp />
            </Button>
          </form>
        ) : null
      }
    >
      {!aiEnabled ? (
        <div className="p-6 text-center">
          <ShieldAlert className="mx-auto size-8 text-critical" aria-hidden />
          <p className="mt-3 text-[14px] font-semibold text-fg">AI is switched off for this firm</p>
          <p className="mt-1 text-[13px] text-muted">The kill switch in Settings stops all AI drafting and chat. Calculations and reports still work.</p>
        </div>
      ) : (
        <div className="space-y-4 p-5">
          {messages.length === 0 && (
            <div className="rounded-xl border border-line bg-surface-2/60 p-4">
              <p className="flex items-center gap-2 text-[13px] font-semibold text-fg">
                <Sparkles className="size-4 text-ai" aria-hidden /> Try asking
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    onClick={() => ask(s)}
                    className="cursor-pointer rounded-full border border-line bg-surface px-3 py-1.5 text-left text-[12.5px] text-fg-2 transition-colors hover:border-accent hover:text-fg"
                  >
                    {s}
                  </button>
                ))}
              </div>
              <p className="mt-3 text-[11.5px] text-muted">The model sees pseudonymised data only. Names are filled in by your browser.</p>
            </div>
          )}
          {messages.map((m) =>
            m.role === "user" ? (
              <div key={m.id} className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-accent px-3.5 py-2 text-[13.5px] text-accent-fg">
                {m.text}
              </div>
            ) : (
              <div key={m.id} className="max-w-[95%] space-y-2">
                <div className="flex flex-wrap gap-1.5">
                  {m.answer!.tools.map((t) => (
                    <Badge key={t} tone="outline" className="font-mono">
                      <Wrench aria-hidden /> {t}
                    </Badge>
                  ))}
                </div>
                <div className="rounded-2xl rounded-bl-md border border-line bg-surface px-3.5 py-3 text-[13.5px] leading-relaxed text-fg-2">
                  {m.answer!.body.map((seg, i) =>
                    typeof seg === "string" ? (
                      <span key={i}>{seg}</span>
                    ) : (
                      <Num key={i} e={seg.e}>
                        {seg.n}
                      </Num>
                    ),
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                  {m.answer!.blocked ? (
                    <Badge tone="critical">
                      <ShieldAlert aria-hidden /> Blocked: security-specific advice
                    </Badge>
                  ) : (
                    <Badge tone="good">
                      <ShieldCheck aria-hidden /> Compliance passed
                    </Badge>
                  )}
                  {m.answer!.citations.map((c) => (
                    <Badge key={c.id} tone="accent">
                      {c.issuer}: {c.section}
                    </Badge>
                  ))}
                </div>
              </div>
            ),
          )}
          {thinking && (
            <div className="flex items-center gap-2 text-[12.5px] text-muted">
              <span className="flex gap-1" aria-hidden>
                <span className="size-1.5 animate-bounce rounded-full bg-ai [animation-delay:-0.2s]" />
                <span className="size-1.5 animate-bounce rounded-full bg-ai [animation-delay:-0.1s]" />
                <span className="size-1.5 animate-bounce rounded-full bg-ai" />
              </span>
              Calling tools…
            </div>
          )}
          <div ref={endRef} />
        </div>
      )}
    </Sheet>
  );
}
