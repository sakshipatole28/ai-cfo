import { Num } from "@/components/ui";
import type { Seg } from "@/lib/engine";

/** Renders a finding: plain text, clickable computed numbers, and the client name filled in by the browser. */
export function FindingBody({ body, name }: { body: Seg[]; name: string }) {
  return (
    <>
      {body.map((seg, i) =>
        typeof seg === "string" ? (
          <span key={i}>{seg.replaceAll("{client}", name)}</span>
        ) : (
          <Num key={i} e={seg.e}>
            {seg.n}
          </Num>
        ),
      )}
    </>
  );
}
