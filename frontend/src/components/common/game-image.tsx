"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

// URLs that failed once (missing texture, CDN hiccup, offline) are remembered so other cards don't retry.
const broken = new Set<string>();

/**
 * Artwork from Blizzard's render CDN. Lazy-loaded, decoded off the main thread, sends no referrer,
 * and swaps to `fallback` if the image is missing or blocked.
 */
export function GameImage({ src, alt = "", className, fallback = null, style }: { src?: string | null; alt?: string; className?: string; fallback?: React.ReactNode; style?: React.CSSProperties }) {
  const [failed, setFailed] = React.useState(() => !!src && broken.has(src));
  React.useEffect(() => setFailed(!!src && broken.has(src)), [src]);
  if (!src || failed) return <>{fallback}</>;
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={alt}
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      draggable={false}
      className={cn("select-none", className)}
      style={style}
      onError={() => {
        broken.add(src);
        setFailed(true);
      }}
    />
  );
}
