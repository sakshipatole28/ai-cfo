import { Check, Clock, Copy, KeyRound, LogOut, MailPlus, Minus, Monitor, Send, ShieldCheck, Smartphone, UserCog, X } from "lucide-react";
import { type FormEvent, type ReactNode, useState } from "react";
import { toast } from "sonner";

import { Avatar, Badge, Button, Card, CardHeader, Sheet, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui";
import { type Member, permissions, primaryAdviser, type Scope } from "@/data/demo";
import { cn } from "@/lib/cn";
import { portfolios } from "@/lib/engine";
import { fmtDate } from "@/lib/format";
import { ROLE_HELP, ROLES, type Role } from "@/lib/roles";
import { useApp, useClientName } from "@/state/app";

// Badge colour per role.
const roleTone: Record<Role, "accent" | "ai" | "neutral" | "warning"> = { Owner: "accent", Admin: "accent", Adviser: "ai", Analyst: "neutral", Compliance: "warning" };

function Page({ children }: { children: ReactNode }) {
  return <div className="gutter-x mx-auto max-w-[1200px] space-y-4 py-5 sm:py-6">{children}</div>;
}

/* ----------------------------- Team ----------------------------- */
export function Team() {
  const { me, firm, members, can, canGrant, whyNot, setRole, setStatus, invite, sessions, endSession, endOtherSessions } = useApp();
  const [inviteOpen, setInviteOpen] = useState(false);
  // Owners and Admins can manage people; what they may change is decided per person (whyNot).
  const manage = can("manageTeam");
  // Clients column: advisers and owners see assigned clients; Admins see none; others read all.
  const clientCount = (m: Member) => (m.role === "Adviser" || m.role === "Owner" ? Object.values(primaryAdviser).filter((x) => x === m.id).length : portfolios.length);
  // Show a server or rule error as a toast; do nothing on success.
  const report = (error: string | null, ok: string, description?: string) => (error ? toast.error(error) : toast.success(ok, { description }));

  return (
    <Page>
      <Card className="aurora relative overflow-hidden p-5">
        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center">
          <div className="flex-1">
            <p className="eyebrow">Firm</p>
            <h2 className="font-display text-[24px] font-semibold text-fg">{firm.name}</h2>
            <p className="text-[13px] text-fg-2">
              {firm.type === "RIA" ? "SEBI RIA" : "AMFI ARN"} {firm.registration} · {members.filter((m) => m.status === "Active").length} active people · two-step sign-in enforced for everyone
            </p>
          </div>
          {manage ? (
            <Button variant="primary" onClick={() => setInviteOpen(true)}>
              <MailPlus /> Invite someone
            </Button>
          ) : (
            <Badge tone="outline">Only Owners and Admins can change the team</Badge>
          )}
        </div>
      </Card>

      <Card className="overflow-hidden">
        <CardHeader title="People" description="Each person sees only what their role allows" />
        <div className="scrollbar-thin mt-3 overflow-x-auto">
          <table className="w-full min-w-[760px] text-[13px]">
            <thead className="border-y border-line bg-surface-2/60 text-left text-[11.5px] uppercase tracking-wider text-muted">
              <tr>
                <th className="px-5 py-2.5 font-semibold">Person</th>
                <th className="px-3 py-2.5 font-semibold">Role</th>
                <th className="px-3 py-2.5 font-semibold">Clients</th>
                <th className="px-3 py-2.5 font-semibold">Two-step</th>
                <th className="px-3 py-2.5 font-semibold">Last active</th>
                <th className="px-3 py-2.5 font-semibold">Status</th>
                <th className="px-5 py-2.5 text-right font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {members.map((m) => (
                <tr key={m.id}>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-3">
                      <Avatar name={m.name} />
                      <div>
                        <p className="font-medium text-fg">
                          {m.name} {m.id === me?.id && <span className="text-muted">(you)</span>}
                        </p>
                        <p className="text-[12px] text-muted">{m.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-3 py-3">
                    {/* The role picker appears only when the rules let you change this person. */}
                    {manage && !whyNot(m, m.role) && m.status !== "Invited" ? (
                      <>
                        <label className="sr-only" htmlFor={`role-${m.id}`}>
                          Role for {m.name}
                        </label>
                        <select
                          id={`role-${m.id}`}
                          value={m.role}
                          onChange={async (e) => {
                            const next = e.target.value as Role;
                            report(await setRole(m.id, next), `${m.name} is now ${next}`);
                          }}
                          className="h-8 cursor-pointer rounded-lg border border-line bg-surface px-2 text-[12.5px] text-fg"
                        >
                          {/* Offer only roles you may grant (an Admin cannot hand out Owner or Admin). */}
                          {ROLES.filter((r) => r === m.role || canGrant.includes(r)).map((r) => (
                            <option key={r}>{r}</option>
                          ))}
                        </select>
                      </>
                    ) : (
                      <Badge tone={roleTone[m.role]}>{m.role}</Badge>
                    )}
                  </td>
                  <td className="tabular px-3 py-3 text-fg-2">{m.role === "Adviser" ? `${clientCount(m)} assigned` : m.role === "Owner" ? `All · ${clientCount(m)} own` : m.role === "Admin" ? "No client data" : "All (read)"}</td>
                  <td className="px-3 py-3">{m.mfa ? <Badge tone="good"><ShieldCheck aria-hidden /> On</Badge> : <Badge tone="warning">Pending setup</Badge>}</td>
                  <td className="px-3 py-3 text-fg-2">{m.lastActive}</td>
                  <td className="px-3 py-3">
                    <Badge tone={m.status === "Active" ? "good" : m.status === "Invited" ? "ai" : "critical"}>{m.status}</Badge>
                  </td>
                  <td className="px-5 py-3 text-right">
                    {/* Suspend/restore only where the rules allow; otherwise explain why not. */}
                    {manage && m.status !== "Invited" && (
                      whyNot(m, m.status === "Suspended" ? m.role : null) ? (
                        <span className="text-[12px] text-muted" title={whyNot(m, null) ?? undefined}>
                          {m.id === me?.id ? "" : "Owner only"}
                        </span>
                      ) : m.status === "Suspended" ? (
                        <Button size="sm" variant="ghost" onClick={async () => report(await setStatus(m.id, "Active"), `${m.name} restored`)}>
                          Restore
                        </Button>
                      ) : (
                        <Button size="sm" variant="ghost" onClick={async () => report(await setStatus(m.id, "Suspended"), `${m.name} suspended`, "All their sessions were signed out.")}>
                          <Minus /> Suspend
                        </Button>
                      )
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="What each role can do" description="Enforced by the API and by row-level security in the database" />
          <div className="scrollbar-thin mt-3 overflow-x-auto pb-2">
            <table className="w-full min-w-[460px] text-[12.5px]">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wider text-muted">
                  <th className="px-5 pb-2 font-semibold">Permission</th>
                  {ROLES.map((r) => (
                    <th key={r} className="px-2 pb-2 text-center font-semibold">{r}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {permissions.map((p) => (
                  <tr key={p.label}>
                    <td className="px-5 py-2 text-fg-2">{p.label}</td>
                    {ROLES.map((r) => (
                      <td key={r} className="px-2 py-2 text-center">
                        {p.roles.includes(r) ? <Check className="mx-auto size-4 text-accent" aria-label="Allowed" /> : <X className="mx-auto size-3.5 text-line-strong" aria-label="Not allowed" />}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Signed-in devices"
            description={manage ? "End any session; the person must sign in again with their code" : "Your sessions"}
            action={
              <Button size="sm" variant="outline" onClick={() => { endOtherSessions(); toast.success("Signed out of all your other devices"); }}>
                <LogOut /> Sign out other devices
              </Button>
            }
          />
          <ul className="mt-3 divide-y divide-line">
            {sessions.filter((s) => manage || s.memberId === me?.id).map((s) => (
              <li key={s.id} className="flex items-center gap-3 px-4 py-3 sm:px-5">
                <span className="flex size-9 items-center justify-center rounded-xl bg-surface-2 text-fg-2">
                  {s.device.includes("iPhone") ? <Smartphone className="size-4" /> : <Monitor className="size-4" />}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] font-medium text-fg">
                    {members.find((m) => m.id === s.memberId)?.name} · {s.device}
                  </p>
                  <p className="text-[12px] text-muted">
                    {s.place} · {s.last}
                  </p>
                </div>
                {s.current ? (
                  <Badge tone="accent">This device</Badge>
                ) : (
                  <Button size="sm" variant="ghost" onClick={() => { endSession(s.id); toast("Session ended"); }}>
                    End
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <InviteSheet open={inviteOpen} onOpenChange={setInviteOpen} roles={canGrant} onInvite={invite} />
    </Page>
  );
}

/** Give someone access: pick their role; they join with the one-time code shown afterwards. */
function InviteSheet({
  open,
  onOpenChange,
  roles,
  onInvite,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  roles: Role[]; // only the roles the signed-in person may grant
  onInvite: (m: { name: string; email: string; role: Role }) => Promise<{ code: string } | { error: string }>;
}) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRoleState] = useState<Role>(roles.includes("Adviser") ? "Adviser" : (roles[0] ?? "Adviser"));
  const [code, setCode] = useState<string | null>(null); // set after a successful invite
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !email.includes("@")) return toast.error("Add a name and a work email");
    setBusy(true);
    const r = await onInvite({ name: name.trim(), email: email.trim().toLowerCase(), role });
    setBusy(false);
    if ("error" in r) return toast.error(r.error);
    setCode(r.code); // shown once: only a hash is kept on the server
  };

  const close = (o: boolean) => {
    onOpenChange(o);
    if (!o) {
      setCode(null); // clear everything when the sheet closes
      setName("");
      setEmail("");
    }
  };

  return (
    <Sheet open={open} onOpenChange={close} title="Give someone access" description="They join with a one-time code that expires in 72 hours">
      {code ? (
        <div className="space-y-4 p-5">
          <div className="flex size-11 items-center justify-center rounded-2xl bg-accent-soft text-accent">
            <KeyRound className="size-5" aria-hidden />
          </div>
          <div>
            <p className="font-display text-[20px] font-semibold text-fg">Invite ready for {name}</p>
            <p className="mt-1 text-[13px] text-muted">
              Send them this code privately. They open <span className="font-medium text-fg-2">Join your firm</span> on the sign-in page, enter it, and set a password and authenticator. It is shown only once.
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-xl border border-line bg-surface-2 p-3">
            <code className="tabular flex-1 text-[22px] font-semibold tracking-widest text-fg">{code}</code>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                void navigator.clipboard?.writeText(code);
                toast.success("Code copied");
              }}
            >
              <Copy /> Copy
            </Button>
          </div>
          <Button variant="primary" className="h-10 w-full" onClick={() => close(false)}>
            Done
          </Button>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4 p-5">
          <label className="block text-[12.5px] font-medium text-fg">
            Full name
            <input id="inv-name" value={name} onChange={(e) => setName(e.target.value)} className="mt-1.5 h-10 w-full rounded-lg border border-line bg-surface px-3 text-[13.5px] font-normal text-fg outline-none focus:border-accent" />
          </label>
          <label className="block text-[12.5px] font-medium text-fg">
            Work email
            <input id="inv-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1.5 h-10 w-full rounded-lg border border-line bg-surface px-3 text-[13.5px] font-normal text-fg outline-none focus:border-accent" />
          </label>
          <fieldset>
            <legend className="text-[12.5px] font-medium text-fg">Role</legend>
            <div className="mt-1.5 grid grid-cols-2 gap-2">
              {roles.map((r) => (
                <button type="button" key={r} onClick={() => setRoleState(r)} className={cn("cursor-pointer rounded-lg border p-2.5 text-left", role === r ? "border-accent bg-accent-soft" : "border-line")}>
                  <span className="block text-[13px] font-medium text-fg">{r}</span>
                  <span className="block text-[11.5px] text-muted">{ROLE_HELP[r]}</span>
                </button>
              ))}
            </div>
          </fieldset>
          <Button type="submit" variant="primary" className="h-10 w-full" disabled={busy}>
            <Send /> {busy ? "Creating…" : "Create invite"}
          </Button>
        </form>
      )}
    </Sheet>
  );
}

/* ----------------------------- Access ----------------------------- */
export function Access() {
  const { requests, shares, members, createRequest, can, me } = useApp();
  const displayName = useClientName();
  const [open, setOpen] = useState(false);
  const nameOf = (id: string) => members.find((m) => m.id === id)?.name ?? id;
  const clientName = (id: string) => displayName(portfolios.find((p) => p.spec.id === id)?.spec.name ?? id);
  const waiting = requests.filter((r) => r.status === "Waiting for client");

  return (
    <Page>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="font-display text-[24px] font-semibold text-fg">Client access</h2>
          <p className="text-[13px] text-fg-2">Clients approve every request from their own portal. Nothing is shared without their consent.</p>
        </div>
        {can("requestAccess") && (
          <Button variant="primary" onClick={() => setOpen(true)}>
            <UserCog /> Request access
          </Button>
        )}
      </div>

      <Tabs defaultValue="requests">
        <TabsList>
          <TabsTrigger value="requests">
            Requests {waiting.length > 0 && <Badge tone="warning">{waiting.length}</Badge>}
          </TabsTrigger>
          <TabsTrigger value="consents">Consents</TabsTrigger>
          <TabsTrigger value="shares">Shared by clients</TabsTrigger>
        </TabsList>

        <TabsContent value="requests" className="mt-4">
          <Card>
            <ul className="divide-y divide-line">
              {requests.map((r) => (
                <li key={r.id} className="flex flex-col gap-2 px-4 py-3.5 sm:flex-row sm:items-center sm:px-5">
                  <div className="min-w-0 flex-1">
                    <p className="text-[13.5px] font-medium text-fg">
                      {clientName(r.clientId)} → {nameOf(r.forMember)}
                    </p>
                    <p className="text-[12.5px] text-muted">
                      {r.scopes.join(", ")} · {r.days} days · requested by {nameOf(r.requestedBy)} on {fmtDate(r.created)}
                    </p>
                  </div>
                  <Badge tone={r.status === "Approved" ? "good" : r.status === "Declined" ? "critical" : "warning"}>
                    {r.status === "Waiting for client" ? <Clock aria-hidden /> : r.status === "Approved" ? <Check aria-hidden /> : <X aria-hidden />}
                    {r.status}
                  </Badge>
                  {r.status === "Waiting for client" && (
                    <Button size="sm" variant="ghost" onClick={() => toast("Reminder sent", { description: "SMS with a link to the client portal." })}>
                      Remind
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          </Card>
          <p className="mt-2 text-[12px] text-muted">Tip: sign in as the client (sign out, then “I'm a client”) to approve a request and watch it update here.</p>
        </TabsContent>

        <TabsContent value="consents" className="mt-4">
          <Card className="overflow-hidden">
            <div className="scrollbar-thin overflow-x-auto">
              <table className="w-full min-w-[700px] text-[13px]">
                <thead className="border-b border-line bg-surface-2/60 text-left text-[11.5px] uppercase tracking-wider text-muted">
                  <tr>
                    <th className="px-5 py-2.5 font-semibold">Client</th>
                    <th className="px-3 py-2.5 font-semibold">Primary adviser</th>
                    <th className="px-3 py-2.5 font-semibold">Scopes</th>
                    <th className="px-3 py-2.5 font-semibold">Valid until</th>
                    <th className="px-3 py-2.5 font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {portfolios.map((p, i) => (
                    <tr key={p.spec.id}>
                      <td className="px-5 py-2.5 font-medium text-fg">{displayName(p.spec.name)}</td>
                      <td className="px-3 py-2.5 text-fg-2">{nameOf(primaryAdviser[p.spec.id]!)}</td>
                      <td className="px-3 py-2.5">
                        <div className="flex flex-wrap gap-1">
                          <Badge tone="outline">Statements</Badge>
                          {p.spec.dhan !== "none" && <Badge tone="outline">Dhan</Badge>}
                        </div>
                      </td>
                      <td className="tabular px-3 py-2.5 text-fg-2">{fmtDate(i % 5 === 3 ? "2026-11-02" : "2027-09-30")}</td>
                      <td className="px-3 py-2.5">{i % 5 === 3 ? <Badge tone="warning">Expires soon</Badge> : <Badge tone="good">Active</Badge>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="shares" className="mt-4">
          <Card>
            <ul className="divide-y divide-line">
              {shares.map((s) => (
                <li key={s.id} className="flex items-center gap-3 px-4 py-3.5 sm:px-5">
                  <Avatar name={s.recipient} className="bg-ai-soft text-ai" />
                  <div className="min-w-0 flex-1">
                    <p className="text-[13.5px] font-medium text-fg">
                      {clientName(s.clientId)} shared with {s.recipient}
                    </p>
                    <p className="text-[12.5px] text-muted">
                      {s.relation} · {s.scopes.join(", ")} · until {fmtDate(s.until)}
                    </p>
                  </div>
                  <Badge tone={s.status === "Active" ? "good" : "neutral"}>{s.status}</Badge>
                </li>
              ))}
            </ul>
          </Card>
          <p className="mt-2 text-[12px] text-muted">Clients create and revoke these shares themselves. The firm sees them for transparency only.</p>
        </TabsContent>
      </Tabs>

      <RequestSheet
        open={open}
        onOpenChange={setOpen}
        meId={me?.id ?? ""}
        onCreate={(r) => {
          createRequest(r);
          setOpen(false);
          toast.success("Request sent to the client", { description: "They approve it from their portal with a one-time code." });
        }}
      />
    </Page>
  );
}

function RequestSheet({
  open,
  onOpenChange,
  meId,
  onCreate,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  meId: string;
  onCreate: (r: { clientId: string; requestedBy: string; forMember: string; scopes: Scope[]; reason: string; days: number }) => void;
}) {
  const { members } = useApp();
  const displayName = useClientName();
  const [clientId, setClientId] = useState(portfolios[0]!.spec.id);
  const [forMember, setForMember] = useState(meId || "m-priya");
  const [scopes, setScopes] = useState<Scope[]>(["Mutual fund statements"]);
  const [reason, setReason] = useState("Quarterly portfolio review.");
  const [days, setDays] = useState(90);
  const all: Scope[] = ["Mutual fund statements", "Dhan holdings", "Tradebook", "Tax summary"];
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Request access from a client" description="The client sees exactly this text and approves or declines it">
      <form
        className="space-y-4 p-5"
        onSubmit={(e) => {
          e.preventDefault();
          if (!scopes.length) return toast.error("Pick at least one item");
          onCreate({ clientId, requestedBy: meId, forMember, scopes, reason, days });
        }}
      >
        <label className="block text-[12.5px] font-medium text-fg">
          Client
          <select id="rq-client" value={clientId} onChange={(e) => setClientId(e.target.value)} className="mt-1.5 h-10 w-full rounded-lg border border-line bg-surface px-2 text-[13.5px] font-normal text-fg">
            {portfolios.map((p) => (
              <option key={p.spec.id} value={p.spec.id}>
                {displayName(p.spec.name)}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-[12.5px] font-medium text-fg">
          Access for
          <select id="rq-member" value={forMember} onChange={(e) => setForMember(e.target.value)} className="mt-1.5 h-10 w-full rounded-lg border border-line bg-surface px-2 text-[13.5px] font-normal text-fg">
            {members.filter((m) => m.role === "Owner" || m.role === "Adviser").map((m) => (
              <option key={m.id} value={m.id}>
                {m.name} ({m.role})
              </option>
            ))}
          </select>
        </label>
        <fieldset>
          <legend className="text-[12.5px] font-medium text-fg">Data needed</legend>
          <div className="mt-1.5 grid grid-cols-2 gap-1.5">
            {all.map((s) => (
              <label key={s} className="flex cursor-pointer items-center gap-2 rounded-lg border border-line px-2.5 py-2 text-[12.5px] text-fg-2">
                <input type="checkbox" checked={scopes.includes(s)} onChange={(e) => setScopes((c) => (e.target.checked ? [...c, s] : c.filter((x) => x !== s)))} className="size-4 accent-[var(--accent)]" />
                {s}
              </label>
            ))}
          </div>
        </fieldset>
        <label className="block text-[12.5px] font-medium text-fg">
          Reason shown to the client
          <textarea id="rq-reason" value={reason} onChange={(e) => setReason(e.target.value)} rows={2} className="mt-1.5 w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13.5px] font-normal text-fg outline-none focus:border-accent" />
        </label>
        <fieldset>
          <legend className="text-[12.5px] font-medium text-fg">Duration</legend>
          <div className="mt-1.5 grid grid-cols-4 gap-2">
            {[30, 90, 180, 365].map((d) => (
              <button type="button" key={d} onClick={() => setDays(d)} className={cn("h-9 cursor-pointer rounded-lg border text-[12.5px]", days === d ? "border-accent bg-accent-soft text-accent" : "border-line text-fg-2")}>
                {d} days
              </button>
            ))}
          </div>
        </fieldset>
        <Button type="submit" variant="primary" className="h-10 w-full">
          <Send /> Send request
        </Button>
      </form>
    </Sheet>
  );
}
