import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";

import {
  type AccessRequest,
  type ClientShare,
  type DeviceSession,
  firm as seedFirm,
  initialRequests,
  initialSessions,
  initialShares,
  type Member,
  members as seedMembers,
  primaryAdviser,
  type Role,
} from "@/data/demo";
import { type ApiMe, type ApiMember, apiEnabled, authApi, getToken, setToken, syncApproval } from "@/lib/api";
import { type AuditEntry, append, seedAudit } from "@/lib/audit";
import { type Portfolio, portfolios } from "@/lib/engine";
import type { Explanation } from "@/lib/engine";
import { type Capability, can as roleCan, checkChange, grantable } from "@/lib/roles";

export type Theme = "system" | "light" | "dark";
export type Decision = "accepted" | "dismissed" | "snoozed";
export type { Capability }; // capabilities and role rules live in lib/roles.ts

/** The firm the console is signed in to (created by its Owner at sign-up). */
export interface FirmInfo {
  name: string;
  registration: string; // SEBI RIA or AMFI ARN number
  type: "RIA" | "MFD";
}

/** What the Owner fills in to create a firm account. */
export interface NewFirm {
  firmName: string;
  firmType: "RIA" | "MFD";
  registration: string;
  ownerName: string;
  email: string;
}

/** Convert a member from the API into the console's shape. */
function fromApi(m: ApiMember): Member {
  const status: Member["status"] = m.status === "active" ? "Active" : m.status === "suspended" ? "Suspended" : "Invited";
  return { id: m.id, name: m.name, email: m.email, role: m.role, status, mfa: m.status !== "pending_mfa", lastActive: m.last_login_at ? "Recently" : "Never" };
}

interface AppState {
  theme: Theme;
  setTheme: (t: Theme) => void;
  // Firm and firm session
  firm: FirmInfo;
  me: Member | null;
  signIn: (memberId: string) => void;
  /** Sign in with a member and firm returned by the API (real accounts). */
  signInWithApi: (me: ApiMe) => Promise<void>;
  /** True while a saved API session is being checked after a page refresh. */
  restoring: boolean;
  signOut: (reason?: string) => void;
  can: (c: Capability) => boolean;
  /** Roles the signed-in member may give to others. */
  canGrant: Role[];
  /** Why the signed-in member may not change `member` (to `role`, or suspend); null if allowed. */
  whyNot: (member: Member, role: Role | null) => string | null;
  members: Member[];
  /** Offline demo: the Owner creates a new firm and becomes its only member. */
  createFirm: (f: NewFirm) => Member;
  /** Offline demo: join with an invite code. Returns the member, or an error message. */
  acceptInvite: (code: string, name: string) => Member | string;
  /** Give someone access with a role. Resolves to the one-time code, or an error message. */
  invite: (m: { name: string; email: string; role: Role }) => Promise<{ code: string } | { error: string }>;
  setRole: (id: string, role: Role) => Promise<string | null>;
  setStatus: (id: string, status: Member["status"]) => Promise<string | null>;
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
  // Live broker connections (demo state on top of the synthetic book)
  liveSync: Record<string, { at: string; expires: string }>;
  markSynced: (clientId: string) => void;
  dhanStatus: (clientId: string) => "connected" | "expired" | "none";
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

// The audit trail records member ids, never emails or names (CLAUDE.md).
const actorId = (m: Member | null) => (m ? m.id : "system");

// A readable one-time invite code, e.g. "7F3A-91C2" (demo only; the API makes its own).
const newCode = () =>
  Array.from(crypto.getRandomValues(new Uint8Array(4)), (b) => b.toString(16).padStart(2, "0"))
    .join("")
    .toUpperCase()
    .replace(/^(.{4})/, "$1-");

export function AppProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(readTheme);
  const [firm, setFirm] = useState<FirmInfo>({ name: seedFirm.name, registration: seedFirm.registration, type: seedFirm.type });
  const [me, setMe] = useState<Member | null>(null);
  const [members, setMembers] = useState<Member[]>(seedMembers);
  const [sessions, setSessions] = useState<DeviceSession[]>(initialSessions);
  const [clientId, setClientId] = useState<string | null>(null);
  const [requests, setRequests] = useState<AccessRequest[]>(initialRequests);
  const [shares, setShares] = useState<ClientShare[]>(initialShares);
  const [liveSync, setLiveSync] = useState<Record<string, { at: string; expires: string }>>({});
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

  // Load the firm, the member and (for managers) the team after the API confirmed who is signed in.
  const applyApiMe = useCallback(
    async (apiMe: ApiMe) => {
      const m = fromApi(apiMe);
      setFirm({ name: apiMe.firm.name, registration: apiMe.firm.registration ?? "", type: apiMe.firm.type });
      setMe(m);
      setLockedState(false);
      const team = roleCan(m.role, "manageTeam") ? await authApi.team() : null; // only managers may list the team
      setMembers(team?.ok ? team.data.members.map(fromApi) : [m]); // everyone else sees just themselves
      log("auth.signed_in", `user/${m.id} (API: password + TOTP)`, m.id);
    },
    [log],
  );

  // After a refresh the token is still in sessionStorage: ask the API who it belongs to.
  const [restoring, setRestoring] = useState(apiEnabled && getToken() !== null);
  useEffect(() => {
    if (!restoring) return;
    void authApi
      .me()
      .then((r) => (r.ok ? applyApiMe(r.data) : setToken(null))) // expired or suspended: forget the token
      .finally(() => setRestoring(false));
  }, [restoring, applyApiMe]);

  const value = useMemo<AppState>(() => {
    const who = actorId(me);
    return {
      theme,
      setTheme: setThemeState,
      me,
      firm,
      signIn: (id) => {
        // Offline demo sign-in: password and code were checked by the sign-in screen.
        const m = members.find((x) => x.id === id) ?? null;
        setMe(m);
        setLockedState(false);
        if (m) log("auth.signed_in", `user/${actorId(m)} (password + TOTP)`, actorId(m));
      },
      signInWithApi: applyApiMe,
      restoring,
      signOut: (reason = "user") => {
        log("auth.signed_out", `user/${who} (${reason}; vault keys cleared)`, who);
        setToken(null); // forget the API session token, if any
        setMe(null);
        setCopilot({ open: false });
        setCommandOpen(false);
        explain(null);
      },
      can: (c) => (me ? roleCan(me.role, c) : false),
      canGrant: me ? grantable(me.role) : [],
      whyNot: (target, role) =>
        me
          ? checkChange({
              actorId: me.id,
              actorRole: me.role,
              targetId: target.id,
              targetRole: target.role,
              newRole: role,
              activeOwners: members.filter((x) => x.role === "Owner" && x.status === "Active").length,
            })
          : "Sign in first.",
      members,
      createFirm: (f) => {
        // The Owner's account starts the firm; employees join later by invitation only.
        const owner: Member = { id: `m-${Date.now()}`, name: f.ownerName, email: f.email.toLowerCase(), role: "Owner", status: "Active", mfa: true, lastActive: "Now" };
        setFirm({ name: f.firmName, registration: f.registration, type: f.firmType });
        setMembers([owner]);
        setSessions((all) => all.filter((x) => x.current).map((x) => ({ ...x, memberId: owner.id })));
        setMe(owner); // sign the Owner in directly: the members list above has not updated yet in this render
        setLockedState(false);
        log("firm.created", `tenant/${f.firmName.toLowerCase().replace(/\s+/g, "-")}`, owner.id);
        return owner;
      },
      acceptInvite: (code, name) => {
        // Match the code to a pending invite; it works once.
        const m = members.find((x) => x.status === "Invited" && x.inviteCode === code.trim().toUpperCase());
        if (!m) return "This invite code is not valid. Ask your firm's Owner or Admin for a new one.";
        const joined: Member = { ...m, name: name.trim() || m.name, status: "Active", mfa: true, lastActive: "Now", inviteCode: undefined };
        setMembers((all) => all.map((x) => (x.id === m.id ? joined : x)));
        setMe(joined); // sign them in directly (the members list has not updated yet in this render)
        setLockedState(false);
        log("team.joined", `user/${m.id} as ${m.role}`, m.id);
        return joined;
      },
      invite: async (m) => {
        if (!me || !grantable(me.role).includes(m.role)) return { error: `Your role cannot grant ${m.role}.` };
        if (members.some((x) => x.email === m.email)) return { error: "This person already has an account." };
        if (apiEnabled && getToken()) {
          // Real accounts: the API creates the invite and returns the code once.
          const r = await authApi.invite({ email: m.email, role: m.role });
          if (!r.ok) return { error: r.error };
          setMembers((all) => [...all, { id: `inv-${Date.now()}`, name: m.name, email: m.email, role: m.role, status: "Invited", mfa: false, lastActive: "Never" }]);
          return { code: r.data.code };
        }
        const code = newCode(); // offline demo: keep the code in memory
        const id = `m-${Date.now()}`;
        setMembers((all) => [...all, { ...m, id, status: "Invited", mfa: false, lastActive: "Never", inviteCode: code }]);
        log("team.invited", `user/${id} as ${m.role}`, who);
        return { code };
      },
      setRole: async (id, role) => {
        const target = members.find((x) => x.id === id);
        if (!me || !target) return "Member not found.";
        const reason = checkChange({ actorId: me.id, actorRole: me.role, targetId: id, targetRole: target.role, newRole: role, activeOwners: members.filter((x) => x.role === "Owner" && x.status === "Active").length });
        if (reason) return reason; // the same rule the API enforces
        if (apiEnabled && getToken()) {
          const r = await authApi.setRole(id, role);
          if (!r.ok) return r.error;
        }
        setMembers((all) => all.map((m) => (m.id === id ? { ...m, role } : m)));
        log("team.role_changed", `user/${id} → ${role}`, who);
        return null;
      },
      setStatus: async (id, status) => {
        const target = members.find((x) => x.id === id);
        if (!me || !target) return "Member not found.";
        const suspending = status === "Suspended";
        const reason = checkChange({ actorId: me.id, actorRole: me.role, targetId: id, targetRole: target.role, newRole: suspending ? null : target.role, activeOwners: members.filter((x) => x.role === "Owner" && x.status === "Active").length });
        if (reason) return reason;
        if (apiEnabled && getToken()) {
          const r = await authApi.setStatus(id, suspending ? "suspended" : "active");
          if (!r.ok) return r.error;
        }
        setMembers((all) => all.map((m) => (m.id === id ? { ...m, status } : m)));
        if (suspending) setSessions((s) => s.filter((x) => x.memberId !== id)); // signed out everywhere
        log(`team.${status.toLowerCase()}`, `user/${id}${suspending ? " (all sessions ended)" : ""}`, who);
        return null;
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
      liveSync,
      markSynced: (id) => {
        const now = new Date();
        const exp = new Date(now.getTime() + 24 * 3600 * 1000);
        setLiveSync((m) => ({ ...m, [id]: { at: now.toISOString(), expires: exp.toISOString() } }));
        log("connection.dhan.synced", `client/${id} (read-only; access pass discarded)`, `client:${id}`);
      },
      dhanStatus: (id) => (liveSync[id] ? "connected" : (portfolios.find((p) => p.spec.id === id)?.spec.dhan ?? "none")),
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
        const mine: Record<string, Decision> = {};
        for (const f of portfolios.find((p) => p.spec.id === id)?.findings ?? []) {
          const d = decisions[f.id];
          if (d) mine[f.id] = d;
        }
        void syncApproval(id, mine).then((ok) => {
          if (ok) log("review.synced", `client/${id} (stored server-side)`, who);
        });
      },
      audit,
      log,
    };
  }, [theme, firm, me, members, restoring, applyApiMe, sessions, clientId, requests, shares, liveSync, aiEnabled, locked, copilot, commandOpen, explanation, decisions, approved, audit, log]);

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
