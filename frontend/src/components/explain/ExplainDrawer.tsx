import { BookOpen, Check, Copy, Database, FunctionSquare, ListOrdered } from "lucide-react";
import { type ReactNode, useState } from "react";

import { Badge, Button, Sheet } from "@/components/ui";
import { useApp } from "@/state/app";

function Section({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <section className="space-y-2.5 px-5 py-4">
      <h3 className="flex items-center gap-2 text-[12px] font-semibold uppercase tracking-wider text-muted [&_svg]:size-3.5">
        {icon}
        {title}
      </h3>
      {children}
    </section>
  );
}

export function ExplainDrawer() {
  const { explanation: e, explain } = useApp();
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    if (!e) return;
    const note = [
      `${e.title}: ${e.result}`,
      `Method: ${e.formulaWords}`,
      ...e.inputs.map((i) => `- ${i.label}: ${i.value}${i.source ? ` (${i.source})` : ""}`),
      ...e.steps.map((s, i) => `${i + 1}. ${s}`),
      ...e.citations.map((c) => `Source: ${c.title} (${c.version})`),
      e.versions.map((v) => `${v.label} ${v.value}`).join(" · "),
    ].join("\n");
    try {
      await navigator.clipboard.writeText(note);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard refused: nothing to do in the demo */
    }
  };

  return (
    <Sheet
      open={!!e}
      onOpenChange={(o) => !o && explain(null)}
      title="How this number was calculated"
      description={e?.title}
      footer={
        <div className="flex items-center justify-between gap-2">
          <p className="text-[12px] text-muted">Computed by tested code. The AI only wrote the sentence.</p>
          <Button size="sm" variant="outline" onClick={copy}>
            {copied ? <Check /> : <Copy />}
            {copied ? "Copied" : "Copy as audit note"}
          </Button>
        </div>
      }
    >
      {e && (
        <div className="divide-y divide-line">
          <div className="px-5 py-5">
            <p className="eyebrow">Result</p>
            <p className="tabular mt-1 text-[28px] font-semibold tracking-tight text-fg">{e.result}</p>
          </div>
          <Section icon={<FunctionSquare />} title="Method">
            <p className="text-[13.5px] leading-relaxed text-fg-2">{e.formulaWords}</p>
            {e.formula && <p className="rounded-lg bg-surface-2 px-3 py-2 font-mono text-[12.5px] text-fg">{e.formula}</p>}
          </Section>
          <Section icon={<Database />} title="Inputs">
            <div className="overflow-hidden rounded-lg border border-line">
              <table className="w-full text-[12.5px]">
                <tbody className="divide-y divide-line">
                  {e.inputs.map((i) => (
                    <tr key={i.label} className="align-top">
                      <td className="px-3 py-2 text-fg-2">
                        {i.label}
                        {i.source && <div className="text-[11.5px] text-muted">{i.source}</div>}
                      </td>
                      <td className="tabular px-3 py-2 text-right font-medium text-fg">{i.value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
          <Section icon={<ListOrdered />} title="Steps">
            <ol className="space-y-2">
              {e.steps.map((s, i) => (
                <li key={s} className="flex gap-2.5 text-[13px] text-fg-2">
                  <span className="tabular flex size-5 shrink-0 items-center justify-center rounded-full bg-surface-2 text-[11px] font-semibold text-fg">
                    {i + 1}
                  </span>
                  <span className="tabular">{s}</span>
                </li>
              ))}
            </ol>
          </Section>
          <Section icon={<BookOpen />} title="Rules and sources cited">
            {e.citations.map((c) => (
              <div key={c.id} className="rounded-lg border border-line p-3">
                <div className="flex flex-wrap items-center gap-1.5">
                  <Badge tone="accent">{c.issuer}</Badge>
                  <Badge tone="outline">{c.version}</Badge>
                  <Badge tone="outline">{c.effective}</Badge>
                </div>
                <p className="mt-2 text-[13px] font-medium text-fg">{c.title}</p>
                <p className="text-[12px] text-muted">{c.section}</p>
                <p className="mt-2 border-l-2 border-line-strong pl-2.5 text-[12.5px] leading-relaxed text-fg-2">
                  <span className="font-medium text-muted">Summary: </span>
                  {c.summary}
                </p>
              </div>
            ))}
          </Section>
          <div className="flex flex-wrap gap-1.5 px-5 py-4">
            {e.versions.map((v) => (
              <Badge key={v.label} tone="outline" className="font-mono">
                {v.label}: {v.value}
              </Badge>
            ))}
          </div>
        </div>
      )}
    </Sheet>
  );
}
