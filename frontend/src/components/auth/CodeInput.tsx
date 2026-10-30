import { useEffect, useRef } from "react";

import { cn } from "@/lib/cn";

/**
 * Six-box one-time-code entry used by firm sign-in, joining a firm and the client portal.
 * A transparent real <input> sits on top of the boxes, so typing, pasting and autofill all work.
 */
export function CodeInput({ value, onChange, id }: { value: string; onChange: (v: string) => void; id: string }) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    ref.current?.focus();
  }, []);
  return (
    <div className="relative">
      <input
        ref={ref}
        id={id}
        inputMode="numeric"
        autoComplete="one-time-code"
        maxLength={6}
        value={value}
        onChange={(e) => onChange(e.target.value.replace(/\D/g, "").slice(0, 6))}
        className="absolute inset-0 h-full w-full cursor-text opacity-0"
        aria-label="6-digit code"
      />
      <div className="grid grid-cols-6 gap-2" aria-hidden>
        {Array.from({ length: 6 }, (_, i) => (
          <div
            key={i}
            className={cn(
              "tabular flex h-12 items-center justify-center rounded-xl border bg-surface text-[20px] font-semibold text-fg transition-colors",
              i === value.length ? "border-accent ring-2 ring-accent/25" : "border-line",
            )}
          >
            {value[i] ?? ""}
          </div>
        ))}
      </div>
    </div>
  );
}
