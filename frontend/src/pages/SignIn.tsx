import { useNavigate } from "@tanstack/react-router";
import { ArrowRight, Building2, CheckCircle2, KeyRound, Loader2, Mail, ShieldCheck, Smartphone, Sparkles, UserRound } from "lucide-react";
import { type FormEvent, type ReactNode, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Logo } from "@/components/shell/Logo";
import { Avatar, Badge, Button } from "@/components/ui";
import { firm } from "@/data/demo";
import { cn } from "@/lib/cn";
import { useApp } from "@/state/app";

function CodeInput({ value, onChange, id }: { value: string; onChange: (v: string) => void; id: string }) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => ref.current?.focus(), []);
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

function FloatingChip({ className, children, delay = 0 }: { className: string; children: ReactNode; delay?: number }) {
  return (
    <div
      className={cn("absolute rounded-2xl border border-line bg-surface/85 px-3.5 py-2.5 text-[12.5px] shadow-pop backdrop-blur-md", className)}
      style={{ animation: `float 7s ease-in-out ${delay}s infinite` }}
    >
      {children}
    </div>
  );
}

export function SignIn() {
  const { members, signIn, clientSignIn } = useApp();
  const navigate = useNavigate();
  const [tab, setTab] = useState<"firm" | "client">("firm");
  const [step, setStep] = useState<"password" | "code" | "unlock">("password");
  const [email, setEmail] = useState(members[0]!.email);
  const [password, setPassword] = useState("demo-password");
  const [code, setCode] = useState("");
  const [clientStep, setClientStep] = useState<"phone" | "code">("phone");
  const [phone, setPhone] = useState("98•••• 4821");
  const [clientCode, setClientCode] = useState("");

  const member = members.find((m) => m.email === email.trim().toLowerCase());

  const submitPassword = (e: FormEvent) => {
    e.preventDefault();
    if (!member) return toast.error("No account with that email", { description: "Pick one of the demo accounts below." });
    if (member.status === "Suspended") return toast.error("This account is suspended", { description: "Ask your firm owner to restore access." });
    setStep("code");
  };

  const submitCode = (e?: FormEvent) => {
    e?.preventDefault();
    if (code.length !== 6 || !member) return;
    setStep("unlock");
    setTimeout(() => {
      signIn(member.id);
      navigate({ to: "/" });
      toast.success(`Welcome back, ${member.name.split(" ")[0]}`, { description: "Vault unlocked in this browser." });
    }, 900);
  };

  useEffect(() => {
    if (code.length === 6) submitCode();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);

  const submitClient = (e: FormEvent) => {
    e.preventDefault();
    if (clientStep === "phone") return setClientStep("code");
    if (clientCode.length !== 6) return;
    clientSignIn("rohan-deshpande");
    navigate({ to: "/portal" });
  };

  return (
    <div className="grid min-h-full lg:grid-cols-[1.05fr_1fr]">
      {/* Story panel */}
      <section className="aurora relative hidden overflow-hidden lg:block">
        <div className="dot-grid absolute inset-0 opacity-70" aria-hidden />
        <div className="relative flex h-full flex-col justify-between p-12">
          <div className="flex items-center gap-3">
            <Logo size={38} />
            <span className="font-display text-[22px] font-semibold text-fg">AI CFO</span>
          </div>
          <div className="relative h-[340px]">
            <FloatingChip className="left-0 top-4" delay={0}>
              <span className="text-muted">Equity vs model</span>
              <p className="tabular mt-0.5 flex items-center gap-1.5 text-[18px] font-semibold text-fg">
                +14.2 pts <Badge tone="accent"><CheckCircle2 aria-hidden /> computed</Badge>
              </p>
            </FloatingChip>
            <FloatingChip className="right-6 top-24" delay={1.4}>
              <p className="flex items-center gap-1.5 font-medium text-ai">
                <Sparkles className="size-3.5" aria-hidden /> AI draft · awaiting approval
              </p>
              <p className="mt-0.5 max-w-60 text-fg-2">Two funds share 69% of their holdings.</p>
            </FloatingChip>
            <FloatingChip className="bottom-6 left-14" delay={2.6}>
              <p className="flex items-center gap-1.5 font-medium text-fg">
                <ShieldCheck className="size-4 text-accent" aria-hidden /> Client approved access
              </p>
              <p className="text-muted">Dhan holdings · 30 days · audit #1,284</p>
            </FloatingChip>
          </div>
          <div className="max-w-md">
            <h1 className="font-display text-[38px] font-semibold leading-[1.05] text-fg">Portfolio reviews your clients can trust.</h1>
            <p className="mt-3 text-[15px] leading-relaxed text-fg-2">
              <span className="font-medium text-accent">Mint</span> marks numbers our engine computed and verified.{" "}
              <span className="font-medium text-ai">Sky</span> marks text an AI drafted for you to approve.
            </p>
          </div>
        </div>
      </section>

      {/* Forms */}
      <section className="gutter-x flex items-center justify-center py-10">
        <div className="w-full max-w-[420px]">
          <div className="mb-8 flex items-center gap-2.5 lg:hidden">
            <Logo size={34} />
            <span className="font-display text-[20px] font-semibold text-fg">AI CFO</span>
          </div>

          <div className="grid grid-cols-2 rounded-xl bg-surface-2 p-1" role="tablist">
            {(
              [
                ["firm", "Firm team", Building2],
                ["client", "I'm a client", UserRound],
              ] as const
            ).map(([key, label, Icon]) => (
              <button
                key={key}
                role="tab"
                aria-selected={tab === key}
                onClick={() => setTab(key)}
                className={cn(
                  "flex h-9 cursor-pointer items-center justify-center gap-2 rounded-lg text-[13px] font-medium transition-colors",
                  tab === key ? "bg-surface text-fg shadow-card" : "text-muted hover:text-fg",
                )}
              >
                <Icon className="size-4" aria-hidden /> {label}
              </button>
            ))}
          </div>

          {tab === "firm" ? (
            <div className="mt-7">
              {step === "password" && (
                <form onSubmit={submitPassword} className="space-y-4">
                  <div>
                    <h2 className="font-display text-[26px] font-semibold text-fg">Sign in to your firm</h2>
                    <p className="mt-1 text-[13.5px] text-muted">{firm.name} · SEBI RIA {firm.registration}</p>
                  </div>
                  <label className="block">
                    <span className="text-[12.5px] font-medium text-fg">Work email</span>
                    <span className="mt-1.5 flex h-11 items-center gap-2 rounded-xl border border-line bg-surface px-3 focus-within:border-accent">
                      <Mail className="size-4 text-muted" aria-hidden />
                      <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" className="flex-1 bg-transparent text-[14px] text-fg outline-none" />
                    </span>
                  </label>
                  <label className="block">
                    <span className="flex justify-between text-[12.5px] font-medium text-fg">
                      Password
                      <button type="button" className="cursor-pointer font-normal text-accent" onClick={() => toast("Reset link sent", { description: "Demo: no email is sent." })}>
                        Forgot?
                      </button>
                    </span>
                    <span className="mt-1.5 flex h-11 items-center gap-2 rounded-xl border border-line bg-surface px-3 focus-within:border-accent">
                      <KeyRound className="size-4 text-muted" aria-hidden />
                      <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" className="flex-1 bg-transparent text-[14px] text-fg outline-none" />
                    </span>
                  </label>
                  <Button type="submit" variant="primary" className="h-11 w-full text-[14px]">
                    Continue <ArrowRight />
                  </Button>
                  <div>
                    <p className="mb-2 text-[12px] font-medium uppercase tracking-wider text-muted">Demo accounts, one per role</p>
                    <div className="grid grid-cols-2 gap-2">
                      {members.filter((m) => m.status !== "Invited").map((m) => (
                        <button
                          type="button"
                          key={m.id}
                          onClick={() => setEmail(m.email)}
                          className={cn(
                            "flex cursor-pointer items-center gap-2 rounded-xl border p-2 text-left transition-colors",
                            email === m.email ? "border-accent bg-accent-soft/60" : "border-line hover:border-line-strong",
                          )}
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
                </form>
              )}
              {step === "code" && member && (
                <form onSubmit={submitCode} className="space-y-5">
                  <div>
                    <span className="flex size-11 items-center justify-center rounded-2xl bg-accent-soft text-accent">
                      <Smartphone className="size-5" aria-hidden />
                    </span>
                    <h2 className="mt-4 font-display text-[26px] font-semibold text-fg">Two-step check</h2>
                    <p className="mt-1 text-[13.5px] text-muted">Enter the 6-digit code from the authenticator app for {member.email}.</p>
                  </div>
                  <CodeInput id="totp" value={code} onChange={setCode} />
                  <p className="text-[12px] text-muted">Demo: any 6 digits work.</p>
                  <button type="button" onClick={() => setStep("password")} className="cursor-pointer text-[13px] text-accent">
                    ← Use a different account
                  </button>
                </form>
              )}
              {step === "unlock" && (
                <div className="flex flex-col items-center gap-3 py-12 text-center">
                  <Loader2 className="size-8 animate-spin text-accent" aria-hidden />
                  <p className="font-display text-[20px] font-semibold text-fg">Unlocking your vault</p>
                  <p className="max-w-xs text-[13px] text-muted">Deriving your key in this browser. Client names are decrypted here and never sent to our servers.</p>
                </div>
              )}
            </div>
          ) : (
            <form onSubmit={submitClient} className="mt-7 space-y-5">
              <div>
                <h2 className="font-display text-[26px] font-semibold text-fg">Client portal</h2>
                <p className="mt-1 text-[13.5px] text-muted">See who can view your portfolio, approve requests and share with your CA.</p>
              </div>
              {clientStep === "phone" ? (
                <>
                  <label className="block">
                    <span className="text-[12.5px] font-medium text-fg">Mobile number registered with your adviser</span>
                    <span className="mt-1.5 flex h-11 items-center gap-2 rounded-xl border border-line bg-surface px-3 focus-within:border-accent">
                      <Smartphone className="size-4 text-muted" aria-hidden />
                      <input id="phone" value={phone} onChange={(e) => setPhone(e.target.value)} className="flex-1 bg-transparent text-[14px] text-fg outline-none" />
                    </span>
                  </label>
                  <Button type="submit" variant="primary" className="h-11 w-full text-[14px]">
                    Send code <ArrowRight />
                  </Button>
                  <p className="text-[12px] text-muted">Demo: signs you in as Rohan Deshpande, a fictional client.</p>
                </>
              ) : (
                <>
                  <CodeInput id="client-otp" value={clientCode} onChange={setClientCode} />
                  <Button type="submit" variant="primary" className="h-11 w-full text-[14px]" disabled={clientCode.length !== 6}>
                    Verify and continue
                  </Button>
                  <p className="text-[12px] text-muted">Demo: any 6 digits work.</p>
                </>
              )}
            </form>
          )}
          <p className="mt-10 text-center text-[12px] text-muted">Demo workspace · synthetic data · no real person's information</p>
        </div>
      </section>
    </div>
  );
}
