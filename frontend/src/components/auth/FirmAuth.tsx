import { useNavigate } from "@tanstack/react-router";
import { ArrowRight, Building2, Copy, KeyRound, Loader2, Mail, ShieldCheck, Smartphone, UserRound } from "lucide-react";
import { type FormEvent, type InputHTMLAttributes, useState } from "react";
import { toast } from "sonner";

import { CodeInput } from "@/components/auth/CodeInput";
import { Avatar, Button } from "@/components/ui";
import { type MfaSetup, apiEnabled, authApi, setToken } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useApp } from "@/state/app";

/**
 * Everything a firm employee does before reaching the console:
 *   signin  existing account: email + password + authenticator code
 *   create  the Owner creates the firm (they become its first Owner)
 *   join    an employee joins with the one-time invite code from their Owner/Admin
 * With VITE_API_URL set these call the API; without it they run on in-browser demo accounts.
 */
type Mode = "signin" | "create" | "join";
type Step = "form" | "code" | "unlock"; // form → authenticator code → unlocking spinner

const MIN_PASSWORD = 12; // same rule as the API (long passphrases beat complexity rules)

/** A labelled text input with an icon; wrapping the input in the label keeps it accessible. */
function Field({ label, icon: Icon, ...input }: { label: string; icon: typeof Mail } & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="block">
      <span className="text-[12.5px] font-medium text-fg">{label}</span>
      <span className="mt-1.5 flex h-11 items-center gap-2 rounded-xl border border-line bg-surface px-3 focus-within:border-accent">
        <Icon className="size-4 text-muted" aria-hidden />
        <input {...input} className="flex-1 bg-transparent text-[14px] text-fg outline-none" />
      </span>
    </label>
  );
}

export function FirmAuth() {
  const { members, signIn, signInWithApi, createFirm, acceptInvite } = useApp();
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("signin");
  const [step, setStep] = useState<Step>("form");
  const [setup, setSetup] = useState<MfaSetup | null>(null); // authenticator key, shown once after creating an account
  const [code, setCode] = useState(""); // the 6-digit authenticator code being typed
  // Offline demo starts with a demo account filled in; real accounts start empty.
  const [f, setF] = useState({
    email: apiEnabled ? "" : members[0]!.email,
    password: apiEnabled ? "" : "demo-password",
    firmName: "",
    firmType: "RIA" as "RIA" | "MFD",
    registration: "",
    name: "",
    inviteCode: "",
  });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF((x) => ({ ...x, [k]: e.target.value }));

  const email = f.email.trim().toLowerCase();
  const demoMember = members.find((m) => m.email === email); // offline demo accounts only

  /** Switch between sign in / create / join and start that form fresh. */
  const go = (m: Mode) => {
    setMode(m);
    setStep("form");
    setSetup(null);
    setCode("");
  };

  /** Real accounts: store the token, load who I am, enter the console. */
  const enter = async (token: string) => {
    setToken(token); // later API calls send this token
    const me = await authApi.me();
    if (!me.ok) throw new Error(me.error);
    await signInWithApi(me.data); // sets the firm, the member and the team list
    toast.success(`Welcome, ${me.data.name.split(" ")[0]}`, { description: `${me.data.firm.name} · ${me.data.role}` });
    void navigate({ to: "/" });
  };

  /** Step 1: validate the form and, for new accounts, create them (API) before asking for the code. */
  const submitForm = async (e: FormEvent) => {
    e.preventDefault();
    if (mode !== "signin" && f.password.length < MIN_PASSWORD) return toast.error(`Use at least ${MIN_PASSWORD} characters for the password`);
    if (mode === "signin") {
      if (!apiEnabled) {
        // Offline demo: pick a known demo account.
        if (!demoMember) return toast.error("No account with that email", { description: "Pick one of the demo accounts below." });
        if (demoMember.status === "Suspended") return toast.error("This account is suspended", { description: "Ask your firm's Owner or Admin to restore access." });
      }
      return setStep("code"); // the API checks password and code together, so it never reveals which emails exist
    }
    if (!apiEnabled) return setStep("code"); // offline demo: create/join happens after the code
    const r =
      mode === "create"
        ? await authApi.createFirm({ firm_name: f.firmName, firm_type: f.firmType, registration: f.registration || null, owner_name: f.name, email: f.email, password: f.password })
        : await authApi.acceptInvite({ code: f.inviteCode, name: f.name, password: f.password });
    if (!r.ok) return toast.error(r.error);
    setSetup(r.data); // show the authenticator key
    setStep("code");
  };

  /** Step 2: the 6-digit code arrived; finish whatever the user is doing. */
  const complete = async (value: string) => {
    setStep("unlock");
    try {
      if (apiEnabled) {
        // New accounts confirm their authenticator first; existing ones sign in.
        const body = { email: f.email, password: f.password, code: value };
        const r = mode === "signin" ? await authApi.signIn(body) : await authApi.confirmMfa(body);
        if (!r.ok) throw new Error(r.error);
        return await enter(r.data.token);
      }
      // Offline demo: any 6 digits work; the animation mimics deriving the vault key.
      await new Promise((resolve) => setTimeout(resolve, 900));
      let member = demoMember;
      if (mode === "create") member = createFirm({ firmName: f.firmName, firmType: f.firmType, registration: f.registration, ownerName: f.name, email: f.email });
      if (mode === "join") {
        const joined = acceptInvite(f.inviteCode, f.name);
        if (typeof joined === "string") {
          toast.error(joined); // wrong or already-used code
          setStep("form");
          return setCode("");
        }
        member = joined;
      }
      if (!member) throw new Error("No account with that email");
      if (mode === "signin") signIn(member.id); // creating a firm or joining already signed the member in
      toast.success(`Welcome, ${member.name.split(" ")[0]}`, { description: "Vault unlocked in this browser." });
      void navigate({ to: "/" });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Something went wrong");
      setCode(""); // let them try the code again
      setStep("code");
    }
  };

  // ---------- unlocking ----------
  if (step === "unlock")
    return (
      <div className="flex flex-col items-center gap-3 py-12 text-center">
        <Loader2 className="size-8 animate-spin text-accent" aria-hidden />
        <p className="font-display text-[20px] font-semibold text-fg">Unlocking your vault</p>
        <p className="max-w-xs text-[13px] text-muted">Deriving your key in this browser. Client names are decrypted here and never sent to our servers.</p>
      </div>
    );

  // ---------- authenticator code ----------
  if (step === "code")
    return (
      <div className="space-y-5">
        <div>
          <span className="flex size-11 items-center justify-center rounded-2xl bg-accent-soft text-accent">
            <Smartphone className="size-5" aria-hidden />
          </span>
          <h2 className="mt-4 font-display text-[26px] font-semibold text-fg">{setup ? "Set up your authenticator" : "Two-step check"}</h2>
          <p className="mt-1 text-[13.5px] text-muted">
            {setup
              ? "In an authenticator app (Google Authenticator, Authy, 1Password…) add a new account with the setup key below, then enter the 6-digit code it shows."
              : `Enter the 6-digit code from the authenticator app for ${f.email}.`}
          </p>
        </div>
        {setup && (
          <div className="rounded-xl border border-line bg-surface-2 p-3">
            <p className="text-[11.5px] font-medium uppercase tracking-wider text-muted">Setup key (shown once)</p>
            <div className="mt-1 flex items-center gap-2">
              <code className="min-w-0 flex-1 break-all text-[14px] font-semibold tracking-wider text-fg">{setup.totp_secret}</code>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => {
                  void navigator.clipboard?.writeText(setup.totp_secret);
                  toast.success("Key copied");
                }}
              >
                <Copy /> Copy
              </Button>
            </div>
          </div>
        )}
        <CodeInput
          id="totp"
          value={code}
          onChange={(v) => {
            setCode(v);
            if (v.length === 6) void complete(v); // submit as soon as the sixth digit is typed
          }}
        />
        {!apiEnabled && <p className="text-[12px] text-muted">Demo: any 6 digits work.</p>}
        <button type="button" onClick={() => go(mode)} className="cursor-pointer text-[13px] text-accent">
          ← Back
        </button>
      </div>
    );

  // ---------- forms ----------
  return (
    <form onSubmit={submitForm} className="space-y-4">
      <div>
        <h2 className="font-display text-[26px] font-semibold text-fg">{mode === "signin" ? "Sign in to your firm" : mode === "create" ? "Create your firm" : "Join your firm"}</h2>
        <p className="mt-1 text-[13.5px] text-muted">
          {mode === "signin"
            ? "Use your work email, password and authenticator code."
            : mode === "create"
              ? "You become the firm's Owner. Your team gets access only when you or an Admin invite them."
              : "Enter the invite code your firm's Owner or Admin gave you."}
        </p>
      </div>

      {mode === "create" && (
        <>
          <Field label="Firm name" icon={Building2} value={f.firmName} onChange={set("firmName")} required minLength={2} autoComplete="organization" />
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-[12.5px] font-medium text-fg">
              Firm type
              <select value={f.firmType} onChange={set("firmType")} className="mt-1.5 h-11 w-full cursor-pointer rounded-xl border border-line bg-surface px-3 text-[14px] font-normal text-fg">
                <option value="RIA">Investment adviser (RIA)</option>
                <option value="MFD">Fund distributor (MFD)</option>
              </select>
            </label>
            <Field label={f.firmType === "RIA" ? "SEBI registration" : "AMFI ARN"} icon={ShieldCheck} value={f.registration} onChange={set("registration")} placeholder={f.firmType === "RIA" ? "INA000…" : "ARN-…"} />
          </div>
        </>
      )}
      {mode === "join" && <Field label="Invite code" icon={KeyRound} value={f.inviteCode} onChange={set("inviteCode")} required autoComplete="one-time-code" placeholder="e.g. 7F3A91C2E0" />}
      {mode !== "signin" && <Field label="Your full name" icon={UserRound} value={f.name} onChange={set("name")} required minLength={2} autoComplete="name" />}
      <Field label={mode === "join" ? "Work email (the one that was invited)" : "Work email"} icon={Mail} type="email" value={f.email} onChange={set("email")} required autoComplete="username" />
      <Field
        label={mode === "signin" ? "Password" : `Password (at least ${MIN_PASSWORD} characters)`}
        icon={KeyRound}
        type="password"
        value={f.password}
        onChange={set("password")}
        required
        autoComplete={mode === "signin" ? "current-password" : "new-password"}
      />
      <Button type="submit" variant="primary" className="h-11 w-full text-[14px]">
        {mode === "signin" ? "Continue" : mode === "create" ? "Create firm" : "Join firm"} <ArrowRight />
      </Button>

      {mode === "signin" && !apiEnabled && (
        <div>
          <p className="mb-2 text-[12px] font-medium uppercase tracking-wider text-muted">Demo accounts, one per role</p>
          <div className="grid grid-cols-2 gap-2">
            {members.filter((m) => m.status === "Active").map((m) => (
              <button
                type="button"
                key={m.id}
                onClick={() => setF((x) => ({ ...x, email: m.email }))}
                className={cn("flex cursor-pointer items-center gap-2 rounded-xl border p-2 text-left transition-colors", f.email === m.email ? "border-accent bg-accent-soft/60" : "border-line hover:border-line-strong")}
              >
                <Avatar name={m.name} className="size-7 text-[10px]" />
                <span className="min-w-0">
                  <span className="block truncate text-[12.5px] font-medium text-fg">{m.name}</span>
                  <span className="block text-[11px] text-muted">{m.role}</span>
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Switch between the three ways in. */}
      <p className="text-center text-[13px] text-muted">
        {mode === "signin" ? (
          <>
            New firm?{" "}
            <button type="button" className="cursor-pointer font-medium text-accent" onClick={() => go("create")}>
              Create a firm account
            </button>
            {" · "}
            <button type="button" className="cursor-pointer font-medium text-accent" onClick={() => go("join")}>
              Join with an invite code
            </button>
          </>
        ) : (
          <button type="button" className="cursor-pointer font-medium text-accent" onClick={() => go("signin")}>
            ← Back to sign in
          </button>
        )}
      </p>
    </form>
  );
}
