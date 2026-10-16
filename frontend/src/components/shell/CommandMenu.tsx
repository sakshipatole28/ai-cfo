import { useNavigate } from "@tanstack/react-router";
import { Command } from "cmdk";
import { ArrowRight, Bot, Lock, Moon, Play, Search, Sun } from "lucide-react";
import { type ReactNode, useEffect } from "react";
import { toast } from "sonner";

import { Avatar, Kbd } from "@/components/ui";
import { inrShort } from "@/lib/format";
import { useApp, useClientName, useVisiblePortfolios } from "@/state/app";

const PAGES = [
  ["/", "Today"],
  ["/clients", "Clients"],
  ["/review", "Review inbox"],
  ["/data", "Data inbox"],
  ["/reports", "Reports"],
  ["/knowledge", "Ask the rulebook"],
  ["/access", "Client access"],
  ["/team", "Team"],
  ["/audit", "Audit trail"],
  ["/settings", "Settings"],
] as const;

function Item({ onSelect, children, value }: { onSelect: () => void; children: ReactNode; value: string }) {
  return (
    <Command.Item
      value={value}
      onSelect={onSelect}
      className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13.5px] text-fg-2 data-[selected=true]:bg-surface-2 data-[selected=true]:text-fg [&_svg]:size-4 [&_svg]:text-muted"
    >
      {children}
    </Command.Item>
  );
}

const group = "px-1.5 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-3 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-muted";

export function CommandMenu() {
  const { commandOpen, setCommandOpen, setTheme, setLocked, openCopilot, locked } = useApp();
  const navigate = useNavigate();
  const displayName = useClientName();
  const portfolios = useVisiblePortfolios();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommandOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setCommandOpen]);

  const run = (fn: () => void) => {
    setCommandOpen(false);
    fn();
  };

  return (
    <Command.Dialog
      open={commandOpen}
      onOpenChange={setCommandOpen}
      label="Command menu"
      overlayClassName="fixed inset-0 z-40 bg-[var(--overlay)] backdrop-blur-[2px]"
      contentClassName="fixed left-1/2 top-[12vh] z-50 w-[min(640px,calc(100vw-32px))] -translate-x-1/2 overflow-hidden rounded-2xl border border-line bg-surface shadow-pop"
    >
      <div className="flex items-center gap-2 border-b border-line px-4">
        <Search className="size-4 text-muted" aria-hidden />
        <Command.Input
          placeholder={locked ? "Vault locked: client names are hidden" : "Search clients, pages or actions…"}
          className="h-12 flex-1 bg-transparent text-[14px] text-fg outline-none placeholder:text-muted"
        />
        <Kbd>Esc</Kbd>
      </div>
      <Command.List className="scrollbar-thin max-h-[56vh] overflow-y-auto pb-2">
        <Command.Empty className="px-4 py-8 text-center text-[13px] text-muted">No matches.</Command.Empty>
        {!locked && (
          <Command.Group heading="Clients" className={group}>
            {portfolios.map((p) => (
              <Item
                key={p.spec.id}
                value={`client ${p.spec.name} ${p.spec.city}`}
                onSelect={() => run(() => navigate({ to: "/clients/$clientId", params: { clientId: p.spec.id } }))}
              >
                <Avatar name={displayName(p.spec.name)} className="size-6 text-[10px]" />
                <span className="flex-1 text-fg">{displayName(p.spec.name)}</span>
                <span className="tabular text-[12px] text-muted">{inrShort(p.total)}</span>
              </Item>
            ))}
          </Command.Group>
        )}
        <Command.Group heading="Actions" className={group}>
          <Item value="run review rohan deshpande" onSelect={() => run(() => toast.success("Review queued for Rohan Deshpande", { description: "Drafts appear in the Review inbox in about a minute." }))}>
            <Play /> Run review for Rohan Deshpande
          </Item>
          <Item value="ask copilot" onSelect={() => run(() => openCopilot())}>
            <Bot /> Ask Copilot
          </Item>
          <Item value="lock vault" onSelect={() => run(() => setLocked(true))}>
            <Lock /> Lock vault
          </Item>
          <Item value="theme light" onSelect={() => run(() => setTheme("light"))}>
            <Sun /> Switch to light theme
          </Item>
          <Item value="theme dark" onSelect={() => run(() => setTheme("dark"))}>
            <Moon /> Switch to dark theme
          </Item>
        </Command.Group>
        <Command.Group heading="Go to" className={group}>
          {PAGES.map(([to, label]) => (
            <Item key={to} value={`go ${label}`} onSelect={() => run(() => navigate({ to }))}>
              <ArrowRight /> {label}
            </Item>
          ))}
        </Command.Group>
      </Command.List>
    </Command.Dialog>
  );
}
