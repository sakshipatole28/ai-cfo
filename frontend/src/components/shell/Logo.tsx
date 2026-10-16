import { useId } from "react";

/** Mark: a mint-to-sky tile with three rising bars and a verification tick. */
export function Logo({ size = 30 }: { size?: number }) {
  const id = useId();
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" role="img" aria-label="AI CFO" className="shrink-0">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#5ee6c1" />
          <stop offset="1" stopColor="#38b6ff" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill={`url(#${id})`} />
      <rect x="7" y="17" width="4" height="8" rx="1.5" fill="#06303a" opacity="0.5" />
      <rect x="14" y="12" width="4" height="13" rx="1.5" fill="#06303a" opacity="0.75" />
      <rect x="21" y="9" width="4" height="16" rx="1.5" fill="#06303a" />
      <circle cx="25" cy="7.5" r="4.4" fill="#ffffff" />
      <path d="M23 7.6l1.4 1.4 2.5-2.7" fill="none" stroke="#0a7d68" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
