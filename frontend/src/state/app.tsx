import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";

import {
  type AccessRequest,
  type ClientShare,
  type DeviceSession,
  initialRequests,
  initialSessions,
  initialShares,
  type Member,
  members as seedMembers,
  primaryAdviser,
  type Role,
} from "@/data/demo";
import { type AuditEntry, append, seedAudit } from "@/lib/audit";
import { type Portfolio, portfolios } from "@/lib/engine";
import type { Explanation } from "@/lib/engine";

export type Theme = "system" | "light" | "dark";
export type Decision = "accepted" | "dismissed" | "snoozed";
export type Capability = "approve" | "seeAll" | "manageTeam" | "requestAccess" | "settings" | "audit" | "ingest";

const CAPS: Record<Role, Capability[]> = {
  Owner: ["approve", "seeAll", "manageTeam", "requestAccess", "settings", "audit", "ingest"],
  Adviser: ["approve", "requestAccess", "ingest"],
  Analyst: ["seeAll", "ingest"],
  Compliance: ["seeAll", "audit"],
};

interface AppState {
  theme: Theme;
  setTheme: (t: Theme) => void;
  // Firm session
  me: Member | null;
  signIn: (memberId: string) => void;
  signOut: (reason?: string) => void;
  can: (c: Capability) => boolean;
  members: Member[];
  invite: (m: Omit<Member, "id" | "status" | "mfa" | "lastActive">) => void;
  setRole: (id: string, role: Role) => void;
  setStatus: (id: string, status: Member["status"]) => void;
  sessions: DeviceSession[];
  endSession: (id: string) => void;
  endOtherSessions: () => void;
  // Client session (portal)
  clientId: string | null;
  clientSignIn: (clientId: string) => void;
  clientSignOut: () => void;
  // Access and consent
  requests: AccessRequest[];
  createRequest: (r: Omit<AccessRequest, "id" | "status" | "created">) => void;
  decideRequest: (id: string, approve: boolean) => void;
  shares: ClientShare[];
  addShare: (s: Omit<ClientShare, "id" | "status">) => void;
  revokeShare: (id: string) => void;
  // Workspace
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
  log: (action: string, object: string, actor?: string) => void;
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

const actorId = (m: Member | null) => (m ? m.email.split("@")[0]! : "system");

export function AppProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(readTheme);
  const [me, setMe] = useState<Member | null>(null);
  const [members, setMembers] = useState<Member[]>(seedMembers);
  const [sessions, setSessions] = useState<DeviceSession[]>(initialSessions);
  const [clientId, setClientId] = useState<string | null>(null);
  const [requests, setRequests] = useState<AccessRequest[]>(initialRequests);
  const [shares, setShares] = useState<ClientShare[]>(initialShares);
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

  const log = useCallback(
    (action: string, object: string, actor?: string) => setAudit((a) => append(a, actor ?? "system", action, object)),
    [],
  );

  const value = useMemo<AppState>(() => {
    const who = actorId(me);
    return {
      theme,
      setTheme: setThemeState,
      me,
      signIn: (id) => {
        const m = members.find((x) => x.id === id) ?? null;
        setMe(m);
        setLockedState(false);
        if (m) log("auth.signed_in", `user/${actorId(m)} (password + TOTP)`, actorId(m));
      },
      signOut: (reason = "user") => {
        log("auth.signed_out", `user/${who} (${reason}; vault keys cleared)`, who);
        setMe(null);
        setCopilot({ open: false });
        setCommandOpen(false);
        explain(null);
      },
      can: (c) => (me ? CAPS[me.role].includes(c) : false),
      members,
      invite: (m) => {
        const id = `m-${Date.now()}`;
        setMembers((all) => [...all, { ...m, id, status: "Invited", mfa: false, lastActive: "Never" }]);
        log("team.invited", `user/${m.email.split("@")[0]} as ${m.role}`, who);
      },
      setRole: (id, role) => {
        setMembers((all) => all.map((m) => (m.id === id ? { ...m, role } : m)));
        log("team.role_changed", `user/${id} → ${role}`, who);
      },
      setStatus: (id, status) => {
        setMembers((all) => all.map((m) => (m.id === id ? { ...m, status } : m)));
        if (status === "Suspended") setSessions((s) => s.filter((x) => x.memberId !== id));
        log(`team.${status.toLowerCase()}`, `user/${id}${status === "Suspended" ? " (all sessions ended)" : ""}`, who);
      },
      sessions,
      endSession: (id) => {
        setSessions((s) => s.filter((x) => x.id !== id));
        log("auth.session_ended", `session/${id}`, who);
      },
      endOtherSessions: () => {
        setSessions((s) => s.filter((x) => x.current || x.memberId !== me?.id));
        log("auth.other_sessions_ended", `user/${who}`, who);
      },
      clientId,
      clientSignIn: (id) => {
        setClientId(id);
        log("portal.signed_in", `client/${id} (OTP)`, `client:${id}`);
      },
      clientSignOut: () => {
        if (clientId) log("portal.signed_out", `client/${clientId}`, `client:${clientId}`);
        setClientId(null);
      },
      requests,
      createRequest: (r) => {
        const id = `rq-${Math.floor(Math.random() * 900 + 100)}`;
        setRequests((all) => [{ ...r, id, status: "Waiting for client", created: "2026-10-17" }, ...all]);
        log("access.requested", `client/${r.clientId} for user/${r.forMember} (${r.scopes.join(", ")})`, who);
      },
      decideRequest: (id, ok) => {
        const r = requests.find((x) => x.id === id);
        setRequests((all) => all.map((x) => (x.id === id ? { ...x, status: ok ? "Approved" : "Declined" } : x)));
        if (r) log(ok ? "access.approved_by_client" : "access.declined_by_client", `request/${id}`, `client:${r.clientId}`);
      },
      shares,
      addShare: (s) => {
        setShares((all) => [{ ...s, id: `sh-${Date.now()}`, status: "Active" }, ...all]);
        log("share.created_by_client", `client/${s.clientId} → ${s.relation} (${s.scopes.join(", ")})`, `client:${s.clientId}`);
      },
      revokeShare: (id) => {
        const s = shares.find((x) => x.id === id);
        setShares((all) => all.map((x) => (x.id === id ? { ...x, status: "Revoked" } : x)));
        if (s) log("share.revoked_by_client", `share/${id}`, `client:${s.clientId}`);
      },
      aiEnabled,
      setAiEnabled: (on) => {
        setAiEnabledState(on);
        log(on ? "settings.ai.enabled" : "settings.ai.kill_switch", "tenant/anand-wealth", who);
      },
      locked,
      setLocked: (on) => {
        setLockedState(on);
        log(on ? "vault.locked" : "vault.unlocked", `user/${who}`, who);
      },
      copilot,
      openCopilot: (id) => setCopilot({ open: true, clientId: id }),
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
        log(d ? `finding.${d}` : "finding.reopened", `finding/${id}`, who);
      },
      approved,
      approve: (id) => {
        setApproved((a) => ({ ...a, [id]: "2026-10-17" }));
        log("review.approved", `client/${id}`, who);
      },
      audit,
      log,
    };
  }, [theme, me, members, sessions, clientId, requests, shares, aiEnabled, locked, copilot, commandOpen, explanation, decisions, approved, audit, log]);

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

/** Owners, analysts and compliance see the whole book; advisers see the clients assigned to them. */
export function useVisiblePortfolios(): Portfolio[] {
  const { me, can, requests } = useApp();
  return useMemo(() => {
    if (!me) return [];
    if (can("seeAll")) return portfolios;
    const covering = new Set(requests.filter((r) => r.forMember === me.id && r.status === "Approved").map((r) => r.clientId));
    return portfolios.filter((p) => primaryAdviser[p.spec.id] === me.id || covering.has(p.spec.id));
  }, [me, can, requests]);
}
