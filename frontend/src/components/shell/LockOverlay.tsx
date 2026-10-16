import { KeyRound, Lock } from "lucide-react";
import { useState } from "react";

import { Logo } from "@/components/shell/Logo";
import { Button } from "@/components/ui";
import { useApp } from "@/state/app";

export function LockOverlay() {
  const { locked, setLocked } = useApp();
  const [pw, setPw] = useState("demo-passphrase");
  const [busy, setBusy] = useState(false);
  if (!locked) return null;

  return (
    <div className="gutter-x fixed inset-0 z-[60] flex items-center justify-center bg-[var(--overlay)] backdrop-blur-md">
      <form
        className="w-full max-w-sm rounded-2xl border border-line bg-surface p-6 shadow-pop"
        onSubmit={(e) => {
          e.preventDefault();
          setBusy(true);
          setTimeout(() => {
            setBusy(false);
            setLocked(false);
          }, 650);
        }}
      >
        <div className="flex items-center gap-3">
          <Logo size={36} />
          <div>
            <p className="text-[15px] font-semibold text-fg">Vault locked</p>
            <p className="text-[12.5px] text-muted">Anand Wealth Partners</p>
          </div>
        </div>
        <p className="mt-4 text-[13px] leading-relaxed text-fg-2">
          Client names and PANs are encrypted with your firm key. Only this browser can decrypt them; the AI CFO servers never hold the key.
        </p>
        <label htmlFor="vault-pass" className="mt-4 block text-[12.5px] font-medium text-fg">
          Passphrase
        </label>
        <div className="mt-1.5 flex h-10 items-center gap-2 rounded-lg border border-line bg-surface-2 px-3 focus-within:border-accent">
          <KeyRound className="size-4 text-muted" aria-hidden />
          <input
            id="vault-pass"
            type="password"
            value={pw}
            onChange={(e) => setPw(e.target.value)}
            className="flex-1 bg-transparent text-[14px] text-fg outline-none"
            autoComplete="current-password"
          />
        </div>
        <Button type="submit" variant="primary" className="mt-4 w-full" disabled={busy || !pw}>
          <Lock />
          {busy ? "Deriving key…" : "Unlock"}
        </Button>
        <p className="mt-3 text-center text-[11.5px] text-muted">Demo: any passphrase unlocks.</p>
      </form>
    </div>
  );
}
