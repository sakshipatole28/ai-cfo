import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Link, Outlet, useNavigate, useRouterState } from "@tanstack/react-router";
import {
  BookOpen,
  Bot,
  BrainCircuit,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Database,
  EyeOff,
  FileText,
  GraduationCap,
  Handshake,
  Inbox,
  LayoutGrid,
  Lock,
  LogOut,
  Monitor,
  Moon,
  MoreHorizontal,
  Search,
  Settings,
  ShieldCheck,
  Sun,
  UserCog,
  Users,
} from "lucide-react";
import { toast } from "sonner";
import { useEffect, useState } from "react";

import { CommandMenu } from "@/components/shell/CommandMenu";
import { LockOverlay } from "@/components/shell/LockOverlay";
import { Logo } from "@/components/shell/Logo";
import { CopilotPanel } from "@/components/copilot/CopilotPanel";
import { ExplainDrawer } from "@/components/explain/ExplainDrawer";
import { Avatar, Badge, Button, Kbd, Sheet, Tip } from "@/components/ui";
import { firm } from "@/data/demo";
import { cn } from "@/lib/cn";
import { type Capability, type Theme, useApp, useVisiblePortfolios } from "@/state/app";

type NavItem = { to: string; label: string; icon: typeof Inbox; badge?: "review" | "data" | "access"; needs?: Capability };
const GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: "Work",
    items: [
      { to: "/", label: "Today", icon: LayoutGrid },
      { to: "/review", label: "Review inbox", icon: Inbox, badge: "review" },
      { to: "/clients", label: "Clients", icon: Users },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { to: "/agents", label: "Agents", icon: BrainCircuit },
      { to: "/knowledge", label: "Ask the rulebook", icon: BookOpen },
      { to: "/guide", label: "How it works", icon: GraduationCap },
    ],
  },
  {
    label: "Data and access",
    items: [
      { to: "/data", label: "Data inbox", icon: Database, badge: "data", needs: "ingest" },
      { to: "/access", label: "Client access", icon: Handshake, badge: "access" },
      { to: "/anonymise", label: "Share without identities", icon: EyeOff },
      { to: "/reports", label: "Reports", icon: FileText },
    ],
  },
  {
    label: "Firm",
    items: [
      { to: "/team", label: "Team", icon: UserCog },
      { to: "/audit", label: "Audit trail", icon: ShieldCheck, needs: "audit" },
      { to: "/settings", label: "Settings", icon: Settings },
    ],
  },
];
const NAV: NavItem[] = GROUPS.flatMap((g) => g.items);

export function usePendingCount() {
  const { decisions, approved } = useApp();
  const visible = useVisiblePortfolios();
  return visible.flatMap((p) => p.findings).filter((f) => !decisions[f.id] && !approved[f.clientId]).length;
}

function isActive(path: string, to: string) {
  return to === "/" ? path === "/" : path === to || path.startsWith(`${to}/`);
}

function useTitle(path: string) {
  const hit = [...NAV].reverse().find((n) => isActive(path, n.to));
  return hit?.label ?? "AI CFO";
}

function ThemeMenu() {
  const { theme, setTheme } = useApp();
  const options: { v: Theme; label: string; Icon: typeof Sun }[] = [
    { v: "light", label: "Light", Icon: Sun },
    { v: "dark", label: "Dark", Icon: Moon },
    { v: "system", label: "System", Icon: Monitor },
  ];
  const Current = options.find((o) => o.v === theme)?.Icon ?? Monitor;
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <Button variant="ghost" size="icon" aria-label="Theme">
          <Current />
        </Button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content align="end" sideOffset={6} className="z-50 min-w-36 rounded-lg border border-line bg-surface p-1 shadow-pop">
          {options.map(({ v, label, Icon }) => (
            <DropdownMenu.Item
              key={v}
              onSelect={() => setTheme(v)}
              className={cn(
                "flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-[13px] text-fg-2 outline-none data-[highlighted]:bg-surface-2 [&_svg]:size-4",
                theme === v && "text-fg font-medium",
              )}
            >
              <Icon /> {label}
            </DropdownMenu.Item>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

function UserMenu() {
  const { setLocked, me, signOut } = useApp();
  const navigate = useNavigate();
  if (!me) return null;
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button className="cursor-pointer rounded-full" aria-label="Account menu">
          <Avatar name={me.name} />
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content align="end" sideOffset={6} className="z-50 w-60 rounded-lg border border-line bg-surface p-1 shadow-pop">
          <div className="px-2 py-2">
            <p className="text-[13px] font-semibold text-fg">{me.name}</p>
            <p className="text-[12px] text-muted">
              {me.role} · {firm.name}
            </p>
            <p className="mt-1 text-[11.5px] text-muted">Signed in with password + authenticator · auto sign-out after 30 min idle</p>
          </div>
          <DropdownMenu.Separator className="my-1 h-px bg-line" />
          {[
            { label: "Lock vault", Icon: Lock, on: () => setLocked(true) },
            { label: "Team and sessions", Icon: UserCog, on: () => navigate({ to: "/team" }) },
            {
              label: "Sign out",
              Icon: LogOut,
              on: () => {
                signOut();
                navigate({ to: "/signin" });
                toast("Signed out", { description: "Vault locked and keys cleared from this browser." });
              },
            },
          ].map(({ label, Icon, on }) => (
            <DropdownMenu.Item
              key={label}
              onSelect={on}
              className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-[13px] text-fg-2 outline-none data-[highlighted]:bg-surface-2 [&_svg]:size-4"
            >
              <Icon /> {label}
            </DropdownMenu.Item>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

function AiPill() {
  const { aiEnabled } = useApp();
  return (
    <Tip label={aiEnabled ? "AI drafting is on · India-hosted model · client identities never sent" : "AI kill switch is on: no drafts are generated"}>
      <Link
        to="/settings"
        className={cn(
          "hidden h-8 items-center gap-1.5 rounded-full border px-2.5 text-[12px] font-medium sm:inline-flex",
          aiEnabled ? "border-line bg-surface text-fg-2" : "border-critical/40 bg-critical-soft text-critical-text",
        )}
      >
        <span className={cn("size-1.5 rounded-full", aiEnabled ? "bg-good" : "bg-critical")} aria-hidden />
        AI {aiEnabled ? "on" : "off"}
        <span className="hidden text-muted lg:inline">· India-hosted</span>
      </Link>
    </Tip>
  );
}

export function AppShell() {
  const path = useRouterState({ select: (s) => s.location.pathname });
  const { setCommandOpen, openCopilot, can, requests, me } = useApp();
  const pending = usePendingCount();
  const nav = NAV.filter((n) => !n.needs || can(n.needs));
  const waitingAccess = requests.filter((r) => r.status === "Waiting for client").length;
  const [collapsed, setCollapsed] = useState(() => typeof window !== "undefined" && window.innerWidth < 1280);
  const [moreOpen, setMoreOpen] = useState(false);
  const title = useTitle(path);

  useEffect(() => {
    setMoreOpen(false);
  }, [path]);

  const badgeFor = (b?: NavItem["badge"]) => (b === "review" ? pending : b === "data" ? 3 : b === "access" ? waitingAccess : 0);

  return (
    <div className="flex h-full min-h-0">
      {/* Sidebar (tablet and up): a floating rail on the page canvas */}
      <aside
        className={cn("hidden shrink-0 flex-col p-3 pr-0 transition-[width] duration-200 md:flex", collapsed ? "w-[84px]" : "w-[260px]")}
        style={{ paddingLeft: "max(12px, env(safe-area-inset-left, 0px))" }}
      >
        <div className="flex min-h-0 flex-1 flex-col rounded-2xl border border-line bg-surface/70 shadow-card backdrop-blur-sm">
          {/* Firm switcher */}
          <Link
            to="/team"
            className={cn("m-2 flex items-center gap-2.5 rounded-xl p-2 transition-colors hover:bg-surface-2", collapsed && "justify-center")}
          >
            <Logo size={32} />
            {!collapsed && (
              <span className="min-w-0 flex-1 leading-tight">
                <span className="block font-display text-[16px] font-semibold text-fg">AI CFO</span>
                <span className="block truncate text-[12px] text-fg-2">{firm.name}</span>
                <span className="mt-1 inline-flex items-center gap-1 rounded-md bg-accent-soft px-1.5 py-0.5 text-[11px] font-semibold text-accent">
                  {me?.name.split(" ")[0]} · {me?.role}
                </span>
              </span>
            )}
          </Link>
          <nav className="scrollbar-thin flex-1 overflow-y-auto px-2 pb-2" aria-label="Main">
            {GROUPS.map((g) => {
              const items = g.items.filter((n) => !n.needs || can(n.needs));
              if (!items.length) return null;
              return (
                <div key={g.label} className="mt-3 first:mt-1">
                  {!collapsed ? (
                    <p className="px-2.5 pb-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-fg-2">{g.label}</p>
                  ) : (
                    <div className="mx-auto mb-1 h-px w-6 bg-line" aria-hidden />
                  )}
                  <ul className="space-y-0.5">
                    {items.map(({ to, label, icon: Icon, badge }) => {
                      const active = isActive(path, to);
                      const count = badgeFor(badge);
                      const link = (
                        <Link
                          to={to}
                          aria-current={active ? "page" : undefined}
                          className={cn(
                            "group relative flex h-9 items-center gap-2.5 rounded-xl px-2.5 text-[13.5px] font-medium transition-all",
                            active ? "bg-surface text-fg shadow-card ring-1 ring-line" : "text-fg-2 hover:bg-surface-2 hover:text-fg",
                            collapsed && "justify-center px-0",
                          )}
                        >
                          <span
                            className={cn(
                              "flex size-7 shrink-0 items-center justify-center rounded-lg transition-colors [&_svg]:size-[17px]",
                              active ? "bg-gradient-to-br from-[var(--mint)] to-[var(--sky)] text-[#05303a]" : "text-fg-2 group-hover:text-fg",
                            )}
                          >
                            <Icon aria-hidden />
                          </span>
                          {!collapsed && <span className="flex-1 truncate">{label}</span>}
                          {count > 0 && !collapsed && (
                            <span className={cn("tabular rounded-full px-1.5 text-[11px] font-semibold", active ? "bg-accent text-accent-fg" : "bg-surface-3 text-fg")}>
                              {count}
                            </span>
                          )}
                          {count > 0 && collapsed && <span className="absolute right-3 top-1.5 size-2 rounded-full bg-accent ring-2 ring-surface" aria-hidden />}
                        </Link>
                      );
                      return (
                        <li key={to}>
                          {collapsed ? (
                            <Tip label={count ? `${label} (${count})` : label} side="right">
                              {link}
                            </Tip>
                          ) : (
                            link
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </div>
              );
            })}
          </nav>

          {/* Agents pulse + Copilot */}
          <div className="space-y-2 border-t border-line p-2">
            {!collapsed && (
              <Link to="/agents" className="block rounded-xl bg-gradient-to-br from-[var(--accent-soft)] to-[var(--ai-soft)] p-3 transition-transform hover:-translate-y-0.5">
                <p className="flex items-center gap-1.5 text-[12px] font-semibold text-fg">
                  <span className="relative flex size-2">
                    <span className="absolute inline-flex size-full animate-ping rounded-full bg-accent opacity-60" />
                    <span className="relative inline-flex size-2 rounded-full bg-accent" />
                  </span>
                  Agents ran at 08:30
                </p>
                <p className="mt-0.5 text-[12px] text-fg-2">12 portfolios · 0 unsupported numbers</p>
                <p className="mt-1 flex items-center text-[12px] font-medium text-accent">
                  See the run <ChevronRight className="size-3.5" aria-hidden />
                </p>
              </Link>
            )}
            <button
              onClick={() => openCopilot()}
              className={cn(
                "flex h-10 w-full cursor-pointer items-center gap-2 rounded-xl border border-ai/30 bg-surface px-3 text-[13px] text-fg-2 transition-colors hover:border-ai hover:text-fg",
                collapsed && "justify-center px-0",
              )}
            >
              <Bot className="size-4 text-ai" aria-hidden />
              {!collapsed && <span className="flex-1 text-left">Ask Copilot…</span>}
            </button>
            <button
              onClick={() => setCollapsed((c) => !c)}
              className={cn("flex h-8 w-full cursor-pointer items-center gap-2 rounded-lg px-3 text-[12.5px] text-fg-2 hover:bg-surface-2 hover:text-fg", collapsed && "justify-center px-0")}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              {collapsed ? <ChevronsRight className="size-4" /> : <ChevronsLeft className="size-4" />}
              {!collapsed && <span>Collapse</span>}
            </button>
          </div>
        </div>
      </aside>

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="gutter-x flex h-8 shrink-0 items-center justify-center gap-2 bg-gradient-to-r from-[var(--accent)] to-[var(--ai)] text-[12px] text-white">
          <span className="font-medium">Demo workspace</span>
          <span className="hidden sm:inline">· Synthetic clients and funds. No real person's data.</span>
          <span className="hidden items-center gap-3 pl-3 lg:flex">
            <span className="flex items-center gap-1"><span className="size-2 rounded-full bg-mint" /> computed</span>
            <span className="flex items-center gap-1"><span className="size-2 rounded-full bg-sky" /> AI draft</span>
          </span>
        </div>
        <header
          className="gutter-x sticky z-20 flex h-14 shrink-0 items-center gap-2 border-b border-line/70 bg-bg/80 backdrop-blur-md"
          style={{ top: "env(safe-area-inset-top, 0px)" }}
        >
          <div className="flex min-w-0 flex-1 items-center gap-2.5">
            <span className="md:hidden">
              <Logo />
            </span>
            <h1 className="truncate font-display text-[17px] font-semibold text-fg">{title}</h1>
          </div>
          <button
            onClick={() => setCommandOpen(true)}
            className="hidden h-9 w-72 cursor-pointer items-center gap-2 rounded-lg border border-line bg-surface-2 px-3 text-[13px] text-muted transition-colors hover:border-line-strong lg:flex"
          >
            <Search className="size-4" aria-hidden />
            <span className="flex-1 truncate text-left">Search or run a command</span>
            <Kbd>Ctrl</Kbd>
            <Kbd>K</Kbd>
          </button>
          <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Search" onClick={() => setCommandOpen(true)}>
            <Search />
          </Button>
          <AiPill />
          <ThemeMenu />
          <UserMenu />
        </header>

        <main className="scrollbar-thin min-h-0 flex-1 overflow-y-auto pb-[calc(64px+env(safe-area-inset-bottom,0px))] md:pb-0">
          <Outlet />
        </main>
      </div>

      {/* Bottom nav (phones) */}
      <nav
        className="fixed inset-x-0 bottom-0 z-30 flex border-t border-line bg-surface/95 backdrop-blur-md md:hidden"
        style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)", paddingLeft: "env(safe-area-inset-left, 0px)", paddingRight: "env(safe-area-inset-right, 0px)" }}
        aria-label="Primary"
      >
        {[
          { to: "/", label: "Today", Icon: LayoutGrid },
          { to: "/review", label: "Inbox", Icon: Inbox, count: pending },
          { to: "/clients", label: "Clients", Icon: Users },
        ].map(({ to, label, Icon, count }) => (
          <Link
            key={to}
            to={to}
            className={cn("relative flex h-16 flex-1 flex-col items-center justify-center gap-1 text-[11px] font-medium", isActive(path, to) ? "text-accent" : "text-muted")}
          >
            <Icon className="size-5" aria-hidden />
            {label}
            {count ? (
              <span className="tabular absolute left-1/2 top-2 ml-2 rounded-full bg-accent px-1.5 text-[10px] font-semibold text-accent-fg">{count}</span>
            ) : null}
          </Link>
        ))}
        <button onClick={() => openCopilot()} className="flex h-16 flex-1 cursor-pointer flex-col items-center justify-center gap-1 text-[11px] font-medium text-ai">
          <Bot className="size-5" aria-hidden />
          Copilot
        </button>
        <button onClick={() => setMoreOpen(true)} className="flex h-16 flex-1 cursor-pointer flex-col items-center justify-center gap-1 text-[11px] font-medium text-muted">
          <MoreHorizontal className="size-5" aria-hidden />
          More
        </button>
      </nav>

      <Sheet open={moreOpen} onOpenChange={setMoreOpen} side="bottom" title="More">
        <div className="grid grid-cols-3 gap-2 p-4">
          {nav.filter((n) => !["/", "/review", "/clients"].includes(n.to)).map(({ to, label, icon: Icon, badge }) => (
            <Link key={to} to={to} className="flex flex-col items-center gap-2 rounded-xl border border-line p-3 text-center text-[12.5px] font-medium text-fg-2 hover:bg-surface-2">
              <Icon className="size-5 text-accent" aria-hidden />
              {label}
              {badgeFor(badge) > 0 && <Badge tone="accent">{badgeFor(badge)}</Badge>}
            </Link>
          ))}
        </div>
      </Sheet>

      <CommandMenu />
      <ExplainDrawer />
      <CopilotPanel />
      <LockOverlay />
    </div>
  );
}
