/**
 * Roles, capabilities and who may grant what — the console's copy of backend/src/aicfo/auth/roles.py.
 * The API enforces these rules; the console uses them to show only the actions you can take.
 *
 * How access works in a firm:
 *  1. The Owner creates the firm account and becomes its first Owner.
 *  2. Owners and Admins give employees access by inviting them with a role.
 *  3. The employee joins with the one-time invite code; nobody can self-register into a firm.
 */

// Every role, from most to least authority.
export const ROLES = ["Owner", "Admin", "Adviser", "Analyst", "Compliance"] as const;
export type Role = (typeof ROLES)[number];

// One thing a role is allowed to do.
export type Capability =
  | "approve" // accept findings and approve client reviews (registered advisers only)
  | "seeAll" // see every client in the firm, not only assigned ones
  | "manageTeam" // invite people, change roles, suspend (limited by the rules below)
  | "manageAdmins" // grant or remove the Owner and Admin roles
  | "requestAccess" // ask a client for consent
  | "settings" // firm settings, including the AI kill switch
  | "audit" // read the audit trail
  | "ingest"; // upload statements, connect brokers

// What each role can do. Admin runs the office (people, audit) but cannot approve advice.
export const CAPABILITIES: Record<Role, readonly Capability[]> = {
  Owner: ["approve", "seeAll", "manageTeam", "manageAdmins", "requestAccess", "settings", "audit", "ingest"],
  Admin: ["manageTeam", "audit"],
  Adviser: ["approve", "requestAccess", "ingest"],
  Analyst: ["seeAll", "ingest"],
  Compliance: ["seeAll", "audit"],
};

// Short descriptions shown when choosing a role.
export const ROLE_HELP: Record<Role, string> = {
  Owner: "Runs the firm; full access, can appoint Admins",
  Admin: "Manages people and access; no client advice",
  Adviser: "Reviews and approves own clients",
  Analyst: "Prepares data, cannot approve",
  Compliance: "Read-only, sees the audit trail",
};

// Roles only an Owner may hand out or take away.
const PRIVILEGED: readonly Role[] = ["Owner", "Admin"];

/** True if `role` includes `capability`. */
export function can(role: Role, capability: Capability): boolean {
  return CAPABILITIES[role].includes(capability);
}

/** The roles `actor` may give someone when inviting or changing a role. */
export function grantable(actor: Role): Role[] {
  if (can(actor, "manageAdmins")) return [...ROLES]; // Owners grant every role
  if (can(actor, "manageTeam")) return ROLES.filter((r) => !PRIVILEGED.includes(r)); // Admins: staff roles only
  return []; // everyone else grants nothing
}

/**
 * Why `actor` may not change `target` (to `newRole`, or suspend when `newRole` is null); null if allowed.
 * Same rules as the API: not yourself; only Owners touch Owners/Admins; only grantable roles;
 * the firm keeps at least one active Owner.
 */
export function checkChange(p: {
  actorId: string;
  actorRole: Role;
  targetId: string;
  targetRole: Role;
  newRole: Role | null;
  activeOwners: number;
}): string | null {
  if (p.actorId === p.targetId) return "You cannot change your own role or access.";
  if (!can(p.actorRole, "manageTeam")) return "Your role cannot manage the team.";
  if (PRIVILEGED.includes(p.targetRole) && !can(p.actorRole, "manageAdmins")) return "Only an Owner can change an Owner or an Admin.";
  if (p.newRole && !grantable(p.actorRole).includes(p.newRole)) return `Your role cannot grant ${p.newRole}.`;
  const leavingOwner = p.targetRole === "Owner" && p.newRole !== "Owner"; // demotion or suspension
  if (leavingOwner && p.activeOwners <= 1) return "The firm must keep at least one active Owner.";
  return null; // every rule passed
}
