/**
 * Talking to the API. With VITE_API_URL unset (the Netlify offline demo) nothing here makes a
 * request and the console runs on in-browser demo state. With it set:
 *   - sign-up, joining, sign-in and team management go to /v1/auth/* and /v1/team/*;
 *   - approvals are stored in Postgres, added to the hash-chained audit log and announced to n8n.
 *
 * Only pseudonymous client references are sent, never client names.
 */
import type { Role } from "@/lib/roles";

// Base URL without a trailing slash, e.g. "https://aicfo-api.onrender.com".
const base = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "");

/** True when the console is connected to a real API. */
export const apiEnabled = Boolean(base);

const TOKEN_KEY = "aicfo.session"; // sessionStorage key: the token ends when the tab closes

/** The current session token, if signed in through the API. */
export function getToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null; // storage blocked (private mode): treat as signed out
  }
}

/** Store (or with null, clear) the session token. */
export function setToken(token: string | null): void {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage blocked: the session lasts until reload */
  }
}

/** Result of an API call: data on success, a readable message on failure. */
export type Result<T> = { ok: true; data: T } | { ok: false; status: number; error: string };

/** One JSON request, with the session token attached when present. */
async function call<T>(method: string, path: string, body?: unknown): Promise<Result<T>> {
  if (!base) return { ok: false, status: 0, error: "No API configured" };
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`; // who is calling
  try {
    const r = await fetch(`${base}${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
    const data = (await r.json().catch(() => ({}))) as { detail?: unknown };
    if (r.ok) return { ok: true, data: data as T };
    // FastAPI puts the reason in "detail" (a string, or a list of validation errors).
    const detail = typeof data.detail === "string" ? data.detail : "Please check the form and try again.";
    return { ok: false, status: r.status, error: detail };
  } catch {
    return { ok: false, status: 0, error: "Cannot reach the server. Check your connection." };
  }
}

/** Authenticator setup returned after creating an account (shown once). */
export interface MfaSetup {
  user_id: string;
  totp_secret: string; // key to type into the authenticator app
  totp_uri: string; // otpauth:// link
}

/** A member as the API returns them. */
export interface ApiMember {
  id: string;
  name: string;
  email: string;
  role: Role;
  status: "pending_mfa" | "active" | "suspended";
  last_login_at: string | null;
}

/** The signed-in member, their firm and what they may do. */
export interface ApiMe extends ApiMember {
  firm: { id: string; name: string; type: "RIA" | "MFD"; registration: string | null; slug: string };
  capabilities: string[];
  can_grant: Role[];
}

export const authApi = {
  /** Owner creates the firm (step 1 of 2; step 2 is confirmMfa). */
  createFirm: (b: { firm_name: string; firm_type: "RIA" | "MFD"; registration: string | null; owner_name: string; email: string; password: string }) =>
    call<MfaSetup>("POST", "/v1/auth/firms", b),
  /** Employee joins with the invite code their Owner/Admin gave them (step 1 of 2). */
  acceptInvite: (b: { code: string; name: string; password: string }) => call<MfaSetup>("POST", "/v1/auth/invites/accept", b),
  /** First code from the authenticator app: activates the account and signs in. */
  confirmMfa: (b: { email: string; password: string; code: string }) => call<{ token: string }>("POST", "/v1/auth/mfa/confirm", b),
  /** Normal sign-in. */
  signIn: (b: { email: string; password: string; code: string }) => call<{ token: string }>("POST", "/v1/auth/sign-in", b),
  me: () => call<ApiMe>("GET", "/v1/me"),
  team: () => call<{ members: ApiMember[]; invites: { id: string; email: string; role: Role; expires_at: string }[] }>("GET", "/v1/team"),
  /** Give someone access with a role; returns the one-time code to pass on. */
  invite: (b: { email: string; role: Role }) => call<{ code: string; email: string; role: Role }>("POST", "/v1/team/invites", b),
  setRole: (id: string, role: Role) => call<ApiMember>("PATCH", `/v1/team/${encodeURIComponent(id)}`, { role }),
  setStatus: (id: string, status: "active" | "suspended") => call<ApiMember>("PATCH", `/v1/team/${encodeURIComponent(id)}`, { status }),
};

/** Store an approval server-side (no-op offline). Decisions use the console's finding ids. */
export async function syncApproval(clientId: string, decisions: Record<string, string>): Promise<boolean> {
  if (!base || !getToken()) return false; // offline demo, or signed in locally
  const r = await call("POST", `/v1/clients/${encodeURIComponent(clientId)}/reviews/approve`, { decisions });
  return r.ok;
}
