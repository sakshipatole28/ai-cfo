import { useNavigate } from "@tanstack/react-router";
import { Check, Clock, Eye, FileText, Link2Off, LogOut, Plus, ShieldCheck, Trash2, UserPlus, X } from "lucide-react";
import { type FormEvent, useState } from "react";
import { toast } from "sonner";

import { LiveConnectSheet } from "@/components/live/LiveConnect";
import { Logo } from "@/components/shell/Logo";
import { Avatar, Badge, Button, Card, CardHeader, Sheet } from "@/components/ui";
import { type ClientShare, firm, primaryAdviser, type Scope } from "@/data/demo";
import { cn } from "@/lib/cn";
import { portfolioById } from "@/lib/engine";
import { fmtDate, inrShort } from "@/lib/format";
import { useApp } from "@/state/app";

const SHARE_SCOPES: Scope[] = ["Tax summary", "Reports", "Mutual fund statements", "Dhan holdings"];

export function Portal() {
  const { clientId, clientSignOut, requests, decideRequest, shares, addShare, revokeShare, members, audit, dhanStatus, liveSync } = useApp();
  const [liveOpen, setLiveOpen] = useState(false);
  const navigate = useNavigate();
  const [shareOpen, setShareOpen] = useState(false);
  const [confirming, setConfirming] = useState<string | null>(null);
  const id = clientId ?? "rohan-deshpande";
  const pf = portfolioById[id]!;
  const first = pf.spec.name.split(" ")[0];
  const memberName = (mid: string) => members.find((m) => m.id === mid)?.name ?? "Adviser";
  const pending = requests.filter((r) => r.clientId === id && r.status === "Waiting for client");
  const approvedReqs = requests.filter((r) => r.clientId === id && r.status === "Approved");
  const myShares = shares.filter((s) => s.clientId === id);
  const activity = audit.filter((e) => e.object.includes(id) || e.actor === `client:${id}`).slice(-6).reverse();

  const signOut = () => {
    clientSignOut();
    navigate({ to: "/signin" });
    toast("Signed out of the client portal");
  };

  return (
    <div className="min-h-full bg-bg">
      <header className="aurora relative overflow-hidden border-b border-line">
        <div className="dot-grid absolute inset-0 opacity-60" aria-hidden />
        <div className="gutter-x relative mx-auto max-w-3xl py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Logo size={30} />
              <span className="text-[13px] font-medium text-fg-2">Client portal · {firm.name}</span>
            </div>
            <Button variant="outline" size="sm" onClick={signOut}>
              <LogOut /> Sign out
            </Button>
          </div>
          <h1 className="mt-6 font-display text-[30px] font-semibold leading-tight text-fg">Hi {first}, you decide who sees your money.</h1>
          <p className="mt-1.5 max-w-xl text-[14px] text-fg-2">
            Your portfolio of <b className="tabular text-fg">{inrShort(pf.total)}</b> is shared only with the people listed below. Every view and change is recorded.
          </p>
        </div>
      </header>

      <main className="gutter-x mx-auto max-w-3xl space-y-5 py-6">
        {/* Requests */}
        <section aria-labelledby="req-h">
          <h2 id="req-h" className="mb-2.5 flex items-center gap-2 text-[15px] font-semibold text-fg">
            Waiting for your approval {pending.length > 0 && <Badge tone="warning">{pending.length}</Badge>}
          </h2>
          {pending.length === 0 && (
            <Card className="p-5 text-[13.5px] text-muted">
              <Check className="mr-1.5 inline size-4 text-good" aria-hidden /> Nothing waiting. You'll get an SMS when your adviser asks for access.
            </Card>
          )}
          <div className="space-y-3">
            {pending.map((r) => (
              <Card key={r.id} className="overflow-hidden">
                <div className="p-4 sm:p-5">
                  <div className="flex items-start gap-3">
                    <Avatar name={memberName(r.requestedBy)} />
                    <div className="min-w-0 flex-1">
                      <p className="text-[14px] font-semibold text-fg">
                        {memberName(r.requestedBy)} asks to {r.forMember === r.requestedBy ? "add access" : `give ${memberName(r.forMember)} access`}
                      </p>
                      <p className="mt-1 text-[13px] leading-relaxed text-fg-2">“{r.reason}”</p>
                      <div className="mt-2.5 flex flex-wrap gap-1.5">
                        {r.scopes.map((s) => (
                          <Badge key={s} tone="outline">
                            <Eye aria-hidden /> {s}
                          </Badge>
                        ))}
                        <Badge tone="neutral">
                          <Clock aria-hidden /> {r.days} days
                        </Badge>
                        <Badge tone="neutral">Read-only</Badge>
                      </div>
                    </div>
                  </div>
                </div>
                <div className="flex gap-2 border-t border-line bg-surface-2/50 px-4 py-3 sm:px-5">
                  {confirming === r.id ? (
                    <>
                      <p className="flex-1 self-center text-[12.5px] text-fg-2">Confirm with the code sent to your phone (demo: auto-filled).</p>
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => {
                          decideRequest(r.id, true);
                          setConfirming(null);
                          toast.success("Access approved", { description: `${memberName(r.forMember)} can view ${r.scopes.join(" and ").toLowerCase()} for ${r.days} days.` });
                        }}
                      >
                        <ShieldCheck /> Confirm 482 913
                      </Button>
                    </>
                  ) : (
                    <>
                      <Button variant="primary" size="sm" className="flex-1 sm:flex-none" onClick={() => setConfirming(r.id)}>
                        <Check /> Approve
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="flex-1 sm:flex-none"
                        onClick={() => {
                          decideRequest(r.id, false);
                          toast("Request declined", { description: "Your adviser has been told. Nothing was shared." });
                        }}
                      >
                        <X /> Decline
                      </Button>
                    </>
                  )}
                </div>
              </Card>
            ))}
          </div>
        </section>

        {/* Who can see */}
        <Card>
          <CardHeader title="Who can see your portfolio" description="Revoke any access at any time; it takes effect immediately." />
          <ul className="mt-2 divide-y divide-line">
            <li className="flex items-center gap-3 px-4 py-3 sm:px-5">
              <Avatar name={memberName(primaryAdviser[id]!)} />
              <div className="min-w-0 flex-1">
                <p className="text-[13.5px] font-medium text-fg">{memberName(primaryAdviser[id]!)} · your adviser</p>
                <p className="text-[12px] text-muted">Full review access · consent valid to 16 Oct 2027</p>
              </div>
              <Badge tone="accent">Primary</Badge>
            </li>
            {approvedReqs.map((r) => (
              <li key={r.id} className="flex items-center gap-3 px-4 py-3 sm:px-5">
                <Avatar name={memberName(r.forMember)} />
                <div className="min-w-0 flex-1">
                  <p className="text-[13.5px] font-medium text-fg">{memberName(r.forMember)} · {firm.name}</p>
                  <p className="text-[12px] text-muted">{r.scopes.join(", ")} · {r.days} days from approval</p>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    decideRequest(r.id, false);
                    toast("Access revoked");
                  }}
                >
                  Revoke
                </Button>
              </li>
            ))}
            {myShares.map((s) => (
              <ShareRow key={s.id} share={s} onRevoke={() => {
                revokeShare(s.id);
                toast("Share revoked", { description: `${s.recipient} can no longer open the link.` });
              }} />
            ))}
          </ul>
          <div className="border-t border-line p-4 sm:px-5">
            <Button variant="outline" onClick={() => setShareOpen(true)} className="w-full sm:w-auto">
              <UserPlus /> Share with someone else
            </Button>
          </div>
        </Card>

        {/* Accounts */}
        <Card>
          <CardHeader title="Connected accounts" description="Where your adviser's data comes from" />
          <ul className="mt-2 divide-y divide-line">
            {pf.sourceMix.map((s) => (
              <li key={s.source} className="flex items-center gap-3 px-4 py-3 sm:px-5">
                <span className="flex size-9 items-center justify-center rounded-xl bg-surface-2 text-accent">
                  {s.source === "Dhan" && dhanStatus(id) !== "connected" ? <Link2Off className="size-4 text-warning-text" /> : <FileText className="size-4" />}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-[13.5px] font-medium text-fg">{s.source}</p>
                  <p className="text-[12px] text-muted">
                    {s.source === "Dhan" ? "Read-only · signs in on Dhan's own page · access lasts 24 hours" : "Monthly statement, forwarded automatically"} · last {fmtDate(s.asOf)}
                  </p>
                </div>
                {s.source === "Dhan" ? (
                  dhanStatus(id) === "connected" && liveSync[id] ? (
                    <Badge tone="good">Live · just synced</Badge>
                  ) : (
                    <Button size="sm" variant="primary" onClick={() => setLiveOpen(true)}>
                      Connect live
                    </Button>
                  )
                ) : (
                  <Badge tone="good">Active</Badge>
                )}
              </li>
            ))}
          </ul>
        </Card>

        {/* Activity */}
        <Card>
          <CardHeader title="Recent activity" description="Who viewed or changed access to your data" />
          <ul className="mt-2 space-y-0.5 px-2 pb-3">
            {activity.map((e) => (
              <li key={e.seq} className="flex items-center gap-3 rounded-lg px-2 py-2 text-[12.5px]">
                <span className="size-1.5 shrink-0 rounded-full bg-accent" aria-hidden />
                <span className="flex-1 text-fg-2">
                  <span className="font-mono text-[11.5px] text-fg">{e.action}</span> · {e.actor.replace("client:", "you · ")}
                </span>
                <span className="shrink-0 text-muted">{new Date(e.at).toLocaleDateString("en-IN", { day: "2-digit", month: "short" })}</span>
              </li>
            ))}
          </ul>
        </Card>

        <p className="pb-6 text-center text-[12px] text-muted">
          Want to stop sharing everything?{" "}
          <button className="cursor-pointer text-critical-text underline" onClick={() => toast("Withdraw consent", { description: "Demo: your adviser's access would end and your data would be erased." })}>
            Withdraw consent and erase my data
          </button>
        </p>
      </main>

      <LiveConnectSheet clientId={id} open={liveOpen} onOpenChange={setLiveOpen} audience="client" />
      <ShareSheet
        open={shareOpen}
        onOpenChange={setShareOpen}
        onShare={(s) => {
          addShare({ ...s, clientId: id });
          setShareOpen(false);
          toast.success(`Shared with ${s.recipient}`, { description: `Read-only until ${fmtDate(s.until)}. You can revoke it any time.` });
        }}
      />
    </div>
  );
}

function ShareRow({ share, onRevoke }: { share: ClientShare; onRevoke: () => void }) {
  const revoked = share.status === "Revoked";
  return (
    <li className={cn("flex items-center gap-3 px-4 py-3 sm:px-5", revoked && "opacity-55")}>
      <Avatar name={share.recipient} className="bg-ai-soft text-ai" />
      <div className="min-w-0 flex-1">
        <p className="text-[13.5px] font-medium text-fg">
          {share.recipient} · {share.relation.toLowerCase()}
        </p>
        <p className="truncate text-[12px] text-muted">
          {share.scopes.join(", ")} · {revoked ? "revoked" : `until ${fmtDate(share.until)}`} · shared by you
        </p>
      </div>
      {revoked ? (
        <Badge tone="neutral">Revoked</Badge>
      ) : (
        <Button size="sm" variant="ghost" onClick={onRevoke}>
          <Trash2 /> Revoke
        </Button>
      )}
    </li>
  );
}

function ShareSheet({ open, onOpenChange, onShare }: { open: boolean; onOpenChange: (o: boolean) => void; onShare: (s: Omit<ClientShare, "id" | "status" | "clientId">) => void }) {
  const [recipient, setRecipient] = useState("");
  const [email, setEmail] = useState("");
  const [relation, setRelation] = useState<ClientShare["relation"]>("Chartered accountant");
  const [scopes, setScopes] = useState<Scope[]>(["Tax summary"]);
  const [days, setDays] = useState(30);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!recipient.trim() || !email.includes("@") || scopes.length === 0) return toast.error("Add a name, an email and at least one item to share");
    const until = new Date("2026-10-17T00:00:00");
    until.setDate(until.getDate() + days);
    onShare({ recipient: recipient.trim(), email: email.trim(), relation, scopes, until: until.toISOString().slice(0, 10) });
    setRecipient("");
    setEmail("");
  };
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Share a read-only view" description="They get a link that expires. They cannot change anything or see other clients.">
      <form onSubmit={submit} className="space-y-4 p-5">
        <label className="block text-[12.5px] font-medium text-fg">
          Name
          <input id="share-name" value={recipient} onChange={(e) => setRecipient(e.target.value)} placeholder="e.g. R. Mehta & Co" className="mt-1.5 h-10 w-full rounded-lg border border-line bg-surface px-3 text-[13.5px] font-normal text-fg outline-none focus:border-accent" />
        </label>
        <label className="block text-[12.5px] font-medium text-fg">
          Email
          <input id="share-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@example.com" className="mt-1.5 h-10 w-full rounded-lg border border-line bg-surface px-3 text-[13.5px] font-normal text-fg outline-none focus:border-accent" />
        </label>
        <fieldset>
          <legend className="text-[12.5px] font-medium text-fg">Relationship</legend>
          <div className="mt-1.5 flex flex-wrap gap-2">
            {(["Chartered accountant", "Family member", "Another adviser"] as const).map((r) => (
              <button type="button" key={r} onClick={() => setRelation(r)} className={cn("h-8 cursor-pointer rounded-full border px-3 text-[12.5px]", relation === r ? "border-accent bg-accent-soft text-accent" : "border-line text-fg-2")}>
                {r}
              </button>
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend className="text-[12.5px] font-medium text-fg">What they can see</legend>
          <div className="mt-1.5 space-y-1.5">
            {SHARE_SCOPES.map((s) => (
              <label key={s} className="flex cursor-pointer items-center gap-2.5 rounded-lg border border-line px-3 py-2 text-[13px] text-fg-2">
                <input type="checkbox" checked={scopes.includes(s)} onChange={(e) => setScopes((cur) => (e.target.checked ? [...cur, s] : cur.filter((x) => x !== s)))} className="size-4 accent-[var(--accent)]" />
                {s}
              </label>
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend className="text-[12.5px] font-medium text-fg">For how long</legend>
          <div className="mt-1.5 grid grid-cols-3 gap-2">
            {[7, 30, 90].map((d) => (
              <button type="button" key={d} onClick={() => setDays(d)} className={cn("h-9 cursor-pointer rounded-lg border text-[13px]", days === d ? "border-accent bg-accent-soft text-accent" : "border-line text-fg-2")}>
                {d} days
              </button>
            ))}
          </div>
        </fieldset>
        <Button type="submit" variant="primary" className="h-10 w-full">
          <Plus /> Share read-only view
        </Button>
      </form>
    </Sheet>
  );
}
