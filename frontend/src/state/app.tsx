import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { type AuditEntry, append, seedAudit } from "@/lib/audit";
import type { Explanation } from "@/lib/engine";

export type Theme = "system" | "light" | "dark";
export type Decision = "accepted" | "dismissed" | "snoozed";

interface AppState {
  theme: Theme;
  setTheme: (t: Theme) => void;
  aiEnabled: boolean;
  setAiEnabled: (on: boolean) => void;
  locked: boolean;
  setLocked: (on: boolean) => void;
  copilot: { open: boolean; clientId?: string };
  openCopilot: (clientId?: string) => void;
  closeCopilot: () => void;
  commandOpen: boolean;
  setCommandOpen: (open: boolean) => void;
  explanation: Explanation | null;
  explain: (e: Explanation | null) => void;
  decisions: Record<string, Decision>;
  decide: (findingId: string, d: Decision | null) => void;
  approved: Record<string, string>;
  approve: (clientId: string) => void;
  audit: AuditEntry[];
  log: (action: string, object: string) => void;
}

const Ctx = createContext<AppState | null>(null);

function readTheme(): Theme {
  try {
    const t = localStorage.getItem("aicfo.theme");
    return t === "light" || t === "dark" ? t : "system";
  } catch {
    return "system";
  }
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(readTheme);
  const [aiEnabled, setAiEnabledState] = useState(true);
  const [locked, setLockedState] = useState(false);
  const [copilot, setCopilot] = useState<{ open: boolean; clientId?: string }>({ open: false });
  const [commandOpen, setCommandOpen] = useState(false);
  const [explanation, explain] = useState<Explanation | null>(null);
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const [approved, setApproved] = useState<Record<string, string>>({ "vikram-shetty": "2026-10-15" });
  const [audit, setAudit] = useState<AuditEntry[]>(seedAudit);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("aicfo.theme", theme);
    } catch {
      /* storage unavailable: theme still applies for this session */
    }
  }, [theme]);

  const log = useCallback((action: string, object: string) => setAudit((a) => append(a, "priya.anand", action, object)), []);

  const value = useMemo<AppState>(
    () => ({
      theme,
      setTheme: setThemeState,
      aiEnabled,
      setAiEnabled: (on) => {
        setAiEnabledState(on);
        log(on ? "settings.ai.enabled" : "settings.ai.kill_switch", "tenant/anand-wealth");
      },
      locked,
      setLocked: (on) => {
        setLockedState(on);
        log(on ? "vault.locked" : "vault.unlocked", "user/priya.anand");
      },
      copilot,
      openCopilot: (clientId) => setCopilot({ open: true, clientId }),
      closeCopilot: () => setCopilot((c) => ({ ...c, open: false })),
      commandOpen,
      setCommandOpen,
      explanation,
      explain,
      decisions,
      decide: (id, d) => {
        setDecisions((prev) => {
          const next = { ...prev };
          if (d) next[id] = d;
          else delete next[id];
          return next;
        });
        log(d ? `finding.${d}` : "finding.reopened", `finding/${id}`);
      },
      approved,
      approve: (clientId) => {
        setApproved((a) => ({ ...a, [clientId]: "2026-10-17" }));
        log("review.approved", `client/${clientId}`);
      },
      audit,
      log,
    }),
    [theme, aiEnabled, locked, copilot, commandOpen, explanation, decisions, approved, audit, log],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): AppState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useApp must be used inside AppProvider");
  return ctx;
}

/** Client names live only in the browser's Identity Vault; when locked they are hidden. */
export function useClientName() {
  const { locked } = useApp();
  return useCallback((name: string) => (locked ? "•••••• ••••••" : name), [locked]);
}
