/** Mark: a ledger tile with three rising bars and a verification tick. */
export function Logo({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" role="img" aria-label="AI CFO" className="shrink-0">
      <rect width="32" height="32" rx="8" fill="var(--accent)" />
      <rect x="7" y="17" width="4" height="8" rx="1.5" fill="var(--accent-fg)" opacity="0.55" />
      <rect x="14" y="12" width="4" height="13" rx="1.5" fill="var(--accent-fg)" opacity="0.8" />
      <rect x="21" y="7" width="4" height="18" rx="1.5" fill="var(--accent-fg)" />
      <circle cx="25.5" cy="7" r="4.25" fill="var(--accent-fg)" stroke="var(--accent)" strokeWidth="1.5" />
      <path d="M23.6 7.1l1.3 1.3 2.4-2.6" fill="none" stroke="var(--accent)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
