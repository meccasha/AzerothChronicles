"use client";

import { Loader2 } from "lucide-react";
import * as React from "react";
import { Button } from "@/components/ui/button";
import { groupBy, groupKey, groupLabel, type Grouping } from "@/lib/format";
import type { AdventureEvent } from "@/lib/types";
import { EventCard } from "./event-card";

export function TimelineView({
  events,
  groupId,
  grouping,
  hasMore,
  loadMore,
  loadingMore,
}: {
  events: AdventureEvent[];
  groupId: string;
  grouping: Grouping;
  hasMore: boolean;
  loadMore: () => void;
  loadingMore: boolean;
}) {
  const sections = groupBy(events, (e) => groupKey(e.occurred_at, grouping));
  const sentinel = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => {
    const el = sentinel.current;
    if (!el || !hasMore) return;
    const io = new IntersectionObserver((entries) => entries[0]?.isIntersecting && !loadingMore && loadMore(), { rootMargin: "600px" });
    io.observe(el);
    return () => io.disconnect();
  }, [hasMore, loadMore, loadingMore]);

  return (
    <div className="relative">
      <div className="timeline-rail absolute bottom-0 left-[15px] top-2 w-px sm:left-[19px]" aria-hidden />
      <ol className="flex flex-col gap-8">
        {sections.map((s) => (
          <li key={s.key}>
            <div className="sticky top-14 z-20 mb-4 flex items-center gap-3 lg:top-2">
              <span className="relative z-10 flex size-8 items-center justify-center rounded-full border border-gold/50 bg-background shadow-[0_0_0_4px_var(--background)] sm:size-10">
                <span className="size-2.5 rotate-45 bg-gold shadow-[0_0_10px_var(--gold)]" />
              </span>
              <h2 className="rounded-md bg-background/95 px-2 py-0.5 font-display text-sm font-semibold uppercase tracking-[0.14em] text-gold-bright sm:text-base">
                {groupLabel(s.key, grouping)}
              </h2>
            </div>
            <ol className="flex flex-col gap-3 pl-11 sm:pl-14">
              {s.items.map((e, i) => (
                <li key={e.id} className="relative animate-rise" style={{ animationDelay: `${Math.min(i, 8) * 35}ms` }}>
                  <span className="absolute -left-[33px] top-6 h-px w-6 bg-gold/30 sm:-left-[37px] sm:w-7" aria-hidden />
                  <span className="absolute -left-[36px] top-[21px] size-2 rounded-full border border-gold/60 bg-background sm:-left-[40px]" aria-hidden />
                  <EventCard event={e} groupId={groupId} />
                </li>
              ))}
            </ol>
          </li>
        ))}
      </ol>
      <div ref={sentinel} className="flex justify-center py-8">
        {hasMore ? (
          <Button variant="outline" onClick={loadMore} disabled={loadingMore}>
            {loadingMore ? <Loader2 className="animate-spin" /> : null} Load older adventures
          </Button>
        ) : events.length ? (
          <p className="ornament-divider w-full max-w-sm text-xs uppercase tracking-[0.25em]">The beginning</p>
        ) : null}
      </div>
    </div>
  );
}
