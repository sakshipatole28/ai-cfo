import { Bot, Calculator, CheckCircle2, FileText, Link2, Search, ShieldCheck, UserCheck, Users } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge, Card, CardHeader } from "@/components/ui";
import { glossary, type GlossaryEntry } from "@/data/glossary";

const STEPS = [
  {
    Icon: Users,
    who: "Firm",
    title: "The firm signs in and adds a client",
    text: "Each person signs in with a password and a code from their phone. The client's name and PAN are locked in the adviser's browser; our servers only ever see a code like C-7F3A.",
  },
  {
    Icon: UserCheck,
    who: "Client",
    title: "The client gives permission",
    text: "The client opens a link, reads what will be shared and why, and approves with a one-time code. They can withdraw at any time.",
  },
  {
    Icon: Link2,
    who: "Data",
    title: "Holdings come in, from two places",
    text: "Live: the client connects their broker (Dhan) once by signing in on Dhan's own page; we read current shares, read-only. Statements: the monthly consolidated statement (CAS) covers every mutual fund and demat account. The two are compared, and any difference goes to the adviser.",
  },
  {
    Icon: Calculator,
    who: "Code",
    title: "Exact calculations, no AI",
    text: "Tested code works out the true split of the money, how far it is from the agreed target, which companies the client really owns through funds, how similar the funds are, and each purchase's tax position.",
  },
  {
    Icon: Bot,
    who: "AI agents",
    title: "Agents decide what matters and explain it",
    text: "Three analyst agents look at overlap, allocation and tax in parallel. A writer agent explains each finding in plain language and quotes the rule it relies on. A compliance check and a verifier reject advice-like wording and any number the calculations did not produce.",
  },
  {
    Icon: CheckCircle2,
    who: "Adviser",
    title: "The adviser approves",
    text: "Nothing reaches the client until the adviser accepts, edits or dismisses each finding and approves the review. Every step is recorded in the audit trail.",
  },
  {
    Icon: FileText,
    who: "Client",
    title: "The client gets a clear report",
    text: "A branded report with the findings, the sources and the date of the data. Names are filled in by the adviser's browser, not by our servers.",
  },
];

const GROUPS: GlossaryEntry["group"][] = ["Money and markets", "Tax", "People and rules", "Data and connections", "Security and privacy", "Artificial intelligence"];

export function Guide() {
  const [q, setQ] = useState("");
  const items = useMemo(
    () => glossary.filter((g) => `${g.term} ${g.full ?? ""} ${g.plain}`.toLowerCase().includes(q.toLowerCase())),
    [q],
  );
  return (
    <div className="gutter-x mx-auto max-w-[1100px] space-y-6 py-5 sm:py-6">
      <section className="aurora relative overflow-hidden rounded-2xl border border-line p-5 sm:p-7">
        <div className="dot-grid absolute inset-0 opacity-60" aria-hidden />
        <div className="relative max-w-2xl">
          <p className="eyebrow">How AI CFO works</p>
          <h2 className="mt-1 font-display text-[28px] font-semibold leading-tight text-fg">From a client's scattered investments to an approved review, in seven steps.</h2>
          <p className="mt-2 text-[14px] text-fg-2">Every financial term has a plain explanation in the glossary below. Underlined words anywhere in the app show their meaning when you point at or tap them.</p>
        </div>
      </section>

      <ol className="relative space-y-3 before:absolute before:bottom-6 before:left-[27px] before:top-6 before:w-px before:bg-line-strong">
        {STEPS.map(({ Icon, who, title, text }, i) => (
          <li key={title} className="relative flex gap-4">
            <span className="relative z-10 flex size-14 shrink-0 flex-col items-center justify-center rounded-2xl border border-line bg-surface shadow-card">
              <Icon className="size-5 text-accent" aria-hidden />
              <span className="tabular text-[10.5px] font-semibold text-fg-2">{i + 1}</span>
            </span>
            <Card className="flex-1 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-[15px] font-semibold text-fg">{title}</p>
                <Badge tone={who === "AI agents" ? "ai" : who === "Code" ? "neutral" : "accent"}>{who}</Badge>
              </div>
              <p className="mt-1 text-[13.5px] leading-relaxed text-fg-2">{text}</p>
            </Card>
          </li>
        ))}
      </ol>

      <Card>
        <CardHeader
          title="Glossary"
          description={`${glossary.length} terms in plain language`}
          action={
            <label className="flex h-9 items-center gap-2 rounded-lg border border-line bg-surface px-3 focus-within:border-accent">
              <Search className="size-4 text-fg-2" aria-hidden />
              <span className="sr-only">Search the glossary</span>
              <input id="glossary-q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search a term" className="w-36 bg-transparent text-[13px] text-fg outline-none sm:w-52" />
            </label>
          }
        />
        <div className="space-y-6 p-4 sm:p-5">
          {GROUPS.map((group) => {
            const list = items.filter((g) => g.group === group);
            if (!list.length) return null;
            return (
              <section key={group}>
                <h3 className="mb-2 flex items-center gap-2 text-[12px] font-semibold uppercase tracking-wider text-fg-2">
                  <ShieldCheck className="size-3.5 text-accent" aria-hidden /> {group}
                </h3>
                <dl className="grid gap-2.5 md:grid-cols-2">
                  {list.map((g) => (
                    <div key={g.term} className="rounded-xl border border-line p-3">
                      <dt className="text-[13.5px] font-semibold text-fg">
                        {g.term}
                        {g.full && <span className="font-normal text-fg-2"> · {g.full}</span>}
                      </dt>
                      <dd className="mt-1 text-[13px] leading-relaxed text-fg-2">{g.plain}</dd>
                      {g.example && <dd className="mt-1 text-[12.5px] text-fg-2">Example: {g.example}</dd>}
                    </div>
                  ))}
                </dl>
              </section>
            );
          })}
          {items.length === 0 && <p className="py-6 text-center text-[13px] text-fg-2">No term matches “{q}”.</p>}
        </div>
      </Card>
    </div>
  );
}
