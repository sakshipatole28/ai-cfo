import * as DialogPrimitive from "@radix-ui/react-dialog";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { AlertOctagon, AlertTriangle, Info, X } from "lucide-react";
import { type ButtonHTMLAttributes, type ComponentProps, forwardRef, type HTMLAttributes, type ReactNode } from "react";

import { cn } from "@/lib/cn";
import type { Explanation, Severity } from "@/lib/engine";
import { initials } from "@/lib/format";
import { useApp } from "@/state/app";

/* Button */
type ButtonVariant = "primary" | "secondary" | "ghost" | "outline" | "danger";
type ButtonSize = "sm" | "md" | "icon" | "icon-sm";

const buttonBase =
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0 cursor-pointer";
const buttonVariants: Record<ButtonVariant, string> = {
  primary: "bg-accent text-accent-fg hover:bg-accent-hover shadow-card",
  secondary: "bg-surface-2 text-fg hover:bg-surface-3",
  ghost: "text-fg-2 hover:bg-surface-2 hover:text-fg",
  outline: "border border-line bg-surface text-fg hover:bg-surface-2 shadow-card",
  danger: "bg-critical text-white hover:opacity-90",
};
const buttonSizes: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-[13px]",
  md: "h-9 px-3.5 text-sm",
  icon: "size-9",
  "icon-sm": "size-8",
};

export function buttonClass(variant: ButtonVariant = "secondary", size: ButtonSize = "md", className?: string): string {
  return cn(buttonBase, buttonVariants[variant], buttonSizes[size], className);
}

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: ButtonSize }
>(({ className, variant = "secondary", size = "md", type = "button", ...props }, ref) => (
  <button ref={ref} type={type} className={cn(buttonBase, buttonVariants[variant], buttonSizes[size], className)} {...props} />
));
Button.displayName = "Button";

/* Badge */
type Tone = "neutral" | "accent" | "ai" | "good" | "warning" | "critical" | "outline";
const tones: Record<Tone, string> = {
  neutral: "bg-surface-2 text-fg-2",
  accent: "bg-accent-soft text-accent",
  ai: "bg-ai-soft text-ai",
  good: "bg-good-soft text-good-text",
  warning: "bg-warning-soft text-warning-text",
  critical: "bg-critical-soft text-critical-text",
  outline: "border border-line text-fg-2",
};
export function Badge({ tone = "neutral", className, ...props }: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={cn(
        "inline-flex h-5 items-center gap-1 whitespace-nowrap rounded-md px-1.5 text-[11.5px] font-medium [&_svg]:size-3",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}

/* Card */
export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("min-w-0 rounded-xl border border-line bg-surface shadow-card", className)} {...props} />;
}
export function CardHeader({
  title,
  description,
  action,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-start justify-between gap-3 px-4 pt-4 sm:px-5", className)}>
      <div className="min-w-0">
        <h2 className="text-[14px] font-semibold text-fg">{title}</h2>
        {description && <p className="mt-0.5 text-[12.5px] text-muted">{description}</p>}
      </div>
      {action && <div className="flex shrink-0 items-center gap-2">{action}</div>}
    </div>
  );
}

export function Kbd({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <kbd
      className={cn(
        "inline-flex h-5 min-w-5 items-center justify-center rounded border border-line bg-surface-2 px-1 font-mono text-[10.5px] text-muted",
        className,
      )}
    >
      {children}
    </kbd>
  );
}

export function Avatar({ name, className }: { name: string; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-accent-soft text-[11.5px] font-semibold text-accent",
        className,
      )}
    >
      {name.startsWith("•") ? "••" : initials(name)}
    </span>
  );
}

/* Severity: colour + icon + label, never colour alone */
const severityStyle: Record<Severity, { tone: Tone; label: string; Icon: typeof Info }> = {
  high: { tone: "critical", label: "High", Icon: AlertOctagon },
  medium: { tone: "warning", label: "Medium", Icon: AlertTriangle },
  low: { tone: "neutral", label: "Low", Icon: Info },
};
export function SeverityBadge({ severity }: { severity: Severity }) {
  const { tone, label, Icon } = severityStyle[severity];
  return (
    <Badge tone={tone}>
      <Icon aria-hidden />
      {label}
    </Badge>
  );
}
export const severityBar: Record<Severity, string> = {
  high: "bg-critical",
  medium: "bg-warning",
  low: "bg-line-strong",
};

/* Clickable, explainable number */
export function Num({ e, children, className }: { e: Explanation; children: ReactNode; className?: string }) {
  const { explain } = useApp();
  return (
    <button
      type="button"
      onClick={(ev) => {
        ev.stopPropagation();
        explain(e);
      }}
      className={cn(
        "tabular cursor-pointer rounded-[4px] bg-accent-soft/70 px-1 font-semibold text-fg underline decoration-accent/50 decoration-dotted underline-offset-[3px] transition-colors hover:bg-accent-soft hover:decoration-accent",
        className,
      )}
      title="Show how this number was calculated"
    >
      {children}
    </button>
  );
}

export function Meter({ value, className, tone = "accent", label = "Progress" }: { value: number; className?: string; tone?: "accent" | "warning" | "critical"; label?: string }) {
  const fill = { accent: "bg-accent", warning: "bg-warning", critical: "bg-critical" }[tone];
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-surface-3", className)} role="meter" aria-label={label} aria-valuenow={Math.round(value)} aria-valuemin={0} aria-valuemax={100}>
      <div className={cn("h-full rounded-full", fill)} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}

export function Switch({ checked, onChange, id, label }: { checked: boolean; onChange: (v: boolean) => void; id: string; label: string }) {
  return (
    <button
      id={id}
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full transition-colors",
        checked ? "bg-accent" : "bg-line-strong",
      )}
    >
      <span className={cn("inline-block size-5 rounded-full bg-white shadow transition-transform", checked ? "translate-x-5.5" : "translate-x-0.5")} />
    </button>
  );
}

/* Tabs */
export const Tabs = TabsPrimitive.Root;
export function TabsList({ className, ...props }: ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn("scrollbar-thin flex gap-1 overflow-x-auto border-b border-line", className)}
      {...props}
    />
  );
}
export function TabsTrigger({ className, ...props }: ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        "relative -mb-px flex h-10 shrink-0 cursor-pointer items-center gap-1.5 border-b-2 border-transparent px-3 text-[13px] font-medium text-muted transition-colors hover:text-fg data-[state=active]:border-accent data-[state=active]:text-fg [&_svg]:size-4",
        className,
      )}
      {...props}
    />
  );
}
export const TabsContent = TabsPrimitive.Content;

/* Sheet (side or bottom panel) */
export function Sheet({
  open,
  onOpenChange,
  title,
  description,
  children,
  side = "right",
  className,
  footer,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  side?: "right" | "bottom";
  className?: string;
  footer?: ReactNode;
}) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-[var(--overlay)] backdrop-blur-[2px] data-[state=open]:animate-[fade-in_150ms_ease-out]" />
        <DialogPrimitive.Content
          className={cn(
            "fixed z-50 flex flex-col bg-surface shadow-pop outline-none",
            side === "right"
              ? "inset-y-0 right-0 w-full border-l border-line sm:w-[480px] sm:max-w-[92vw] data-[state=open]:animate-[slide-in-right_220ms_cubic-bezier(.2,.8,.2,1)]"
              : "inset-x-0 bottom-0 max-h-[88vh] rounded-t-2xl border-t border-line data-[state=open]:animate-[slide-in-up_220ms_cubic-bezier(.2,.8,.2,1)]",
            className,
          )}
          style={{
            paddingTop: side === "right" ? "env(safe-area-inset-top, 0px)" : undefined,
            paddingBottom: "env(safe-area-inset-bottom, 0px)",
            paddingRight: "env(safe-area-inset-right, 0px)",
          }}
        >
          <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
            <div className="min-w-0">
              <DialogPrimitive.Title className="text-[15px] font-semibold text-fg">{title}</DialogPrimitive.Title>
              {description ? (
                <DialogPrimitive.Description className="mt-0.5 text-[12.5px] text-muted">{description}</DialogPrimitive.Description>
              ) : (
                <DialogPrimitive.Description className="sr-only">Panel</DialogPrimitive.Description>
              )}
            </div>
            <DialogPrimitive.Close asChild>
              <Button variant="ghost" size="icon-sm" aria-label="Close">
                <X />
              </Button>
            </DialogPrimitive.Close>
          </div>
          <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto">{children}</div>
          {footer && <div className="border-t border-line px-5 py-3">{footer}</div>}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

/* Tooltip */
export function Tip({ label, children, side = "top" }: { label: ReactNode; children: ReactNode; side?: "top" | "right" | "bottom" | "left" }) {
  return (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          side={side}
          sideOffset={6}
          className="z-50 max-w-64 rounded-md bg-fg px-2 py-1 text-[12px] text-bg shadow-pop"
        >
          {label}
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}
export const TooltipProvider = TooltipPrimitive.Provider;

export function EmptyState({ icon, title, children }: { icon: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-14 text-center">
      <div className="flex size-11 items-center justify-center rounded-full bg-surface-2 text-muted [&_svg]:size-5">{icon}</div>
      <p className="text-[14px] font-semibold text-fg">{title}</p>
      {children && <div className="max-w-sm text-[13px] text-muted">{children}</div>}
    </div>
  );
}
