"use client";

import { useId } from "react";

export function Logo({ size = 32 }: { size?: number }) {
  // Unique gradient id: several logos can be on the page (one may be display:none).
  const id = `lg-gold-${useId().replace(/:/g, "")}`;
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#f7dc96" />
          <stop offset="0.55" stopColor="#d6a94a" />
          <stop offset="1" stopColor="#8a6424" />
        </linearGradient>
      </defs>
      <path d="M32 3 56 14v18c0 14-10 24-24 29C18 56 8 46 8 32V14L32 3Z" fill="#111722" stroke={`url(#${id})`} strokeWidth="3" />
      <path d="M20 44c3-10 6-17 12-27 6 10 9 17 12 27" fill="none" stroke={`url(#${id})`} strokeWidth="3" strokeLinecap="round" />
      <path d="M24 36h16" stroke={`url(#${id})`} strokeWidth="3" strokeLinecap="round" />
      <circle cx="32" cy="12" r="2.5" fill="#f2c86a" />
    </svg>
  );
}
