"use client";

import { Filter, Search, ScrollText, SlidersHorizontal, Star, X } from "lucide-react";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import * as React from "react";
import { EmptyState, ErrorState, PageHeader } from "@/components/common/misc";
import { ManualEventDialog } from "@/components/timeline/manual-event-dialog";
import { TimelineView } from "@/components/timeline/timeline-view";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { Skeleton, Switch } from "@/components/ui/misc";
import type { Grouping } from "@/lib/format";
import { useFacets, useGroup, useTimeline, type TimelineFilters } from "@/lib/queries";
import { cn } from "@/lib/utils";
import { EVENT_TYPE_LABEL } from "@/lib/wow";
import type { EventType } from "@/lib/types";

const TYPES: EventType[] = ["boss_kill", "achievement", "loot", "dungeon_complete", "milestone", "manual"];

function TimelineInner() {
  const { groupId } = useParams<{ groupId: string }>();
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const facets = useFacets(groupId);
  const group = useGroup(groupId);
  const isAdmin = group.data?.my_role === "owner" || group.data?.my_role === "admin";
  const [showFilters, setShowFilters] = React.useState(false);
  const [search, setSearch] = React.useState(params.get("q") ?? "");

  const get = (k: string) => params.get(k) ?? undefined;
  const filters: TimelineFilters = {
    types: get("types"),
    member: get("member"),
    character: get("character"),
    expansion: get("expansion"),
    season: get("season"),
    q: get("q"),
    favorites: params.get("favorites") === "1",
    highlights: params.get("highlights") === "1",
    show_all: params.get("all") === "1",
    include_hidden: params.get("hidden") === "1",
    order: (get("order") as "asc" | "desc") ?? "desc",
  };
  const grouping = (get("group") as Grouping) ?? "month";

  const set = React.useCallback(
    (patch: Record<string, string | undefined>) => {
      const next = new URLSearchParams(params.toString());
      for (const [k, v] of Object.entries(patch)) {
        if (v) next.set(k, v);
        else next.delete(k);
      }
      router.replace(`${pathname}?${next.toString()}`, { scroll: false });
    },
    [params, pathname, router],
  );

  React.useEffect(() => {
    const t = setTimeout(() => {
      if ((params.get("q") ?? "") !== search) set({ q: search || undefined });
    }, 300);
    return () => clearTimeout(t);
  }, [search, params, set]);

  const tl = useTimeline(groupId, filters);
  const events = tl.data?.pages.flatMap((p) => p.items) ?? [];
  const first = tl.data?.pages[0];
  const activeTypes = filters.types ? filters.types.split(",") : [];
  const activeCount = ["member", "character", "expansion", "season"].filter((k) => params.get(k)).length + (filters.favorites ? 1 : 0) + (filters.highlights ? 1 : 0);

  const toggleType = (t: string) => {
    const next = activeTypes.includes(t) ? activeTypes.filter((x) => x !== t) : [...activeTypes, t];
    set({ types: next.join(",") || undefined });
  };

  return (
    <div>
      <PageHeader
        icon={ScrollText}
        title="Adventure Timeline"
        subtitle="Every recorded moment of your group's journey, newest first. Minor events are tucked away unless you ask for them."
        actions={<ManualEventDialog groupId={groupId} />}
      />

      <div className="sticky top-[52px] z-30 -mx-4 mb-6 flex flex-col gap-3 border-y bg-background/90 px-4 py-3 backdrop-blur sm:mx-0 sm:rounded-xl sm:border lg:top-0">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-0 flex-1 sm:max-w-xs">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search bosses, items, stories…" className="pl-8" aria-label="Search timeline" />
          </div>
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Event categories">
            {TYPES.map((t) => (
              <button
                key={t}
                onClick={() => toggleType(t)}
                aria-pressed={activeTypes.includes(t)}
                className={cn("rounded-full border px-3 py-1 text-xs transition cursor-pointer", activeTypes.includes(t) ? "border-gold/60 bg-gold/15 text-gold-bright" : "border-border text-muted-foreground hover:border-gold/30 hover:text-foreground")}
              >
                {EVENT_TYPE_LABEL[t]}
              </button>
            ))}
          </div>
          <Button variant="outline" size="sm" onClick={() => setShowFilters((s) => !s)} aria-expanded={showFilters} className="ml-auto">
            <SlidersHorizontal /> Filters {activeCount ? <span className="rounded-full bg-gold/20 px-1.5 text-gold-bright">{activeCount}</span> : null}
          </Button>
        </div>
        {showFilters ? (
          <div className="grid gap-3 border-t pt-3 sm:grid-cols-2 lg:grid-cols-4">
            <Select aria-label="Member" value={filters.member ?? ""} onChange={(e) => set({ member: e.target.value || undefined, character: undefined })}>
              <option value="">All members</option>
              {facets.data?.members.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.display_name}
                </option>
              ))}
            </Select>
            <Select aria-label="Character" value={filters.character ?? ""} onChange={(e) => set({ character: e.target.value || undefined })}>
              <option value="">All characters</option>
              {facets.data?.characters
                .filter((c) => !filters.member || c.owner_user_id === filters.member)
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} – {c.realm}
                  </option>
                ))}
            </Select>
            <Select aria-label="Expansion" value={filters.expansion ?? ""} onChange={(e) => set({ expansion: e.target.value || undefined })}>
              <option value="">All expansions</option>
              {facets.data?.expansions.map((x) => (
                <option key={x.key} value={x.key}>
                  {x.name}
                  {x.has_events ? "" : " (no events)"}
                </option>
              ))}
            </Select>
            <Select aria-label="Season" value={filters.season ?? ""} onChange={(e) => set({ season: e.target.value || undefined })}>
              <option value="">All seasons</option>
              {facets.data?.seasons.map((x) => (
                <option key={x.key} value={x.key}>
                  {x.name}
                  {x.has_events ? "" : " (no events)"}
                </option>
              ))}
            </Select>
            <Select aria-label="Group by" value={grouping} onChange={(e) => set({ group: e.target.value })}>
              <option value="day">Group by day</option>
              <option value="month">Group by month</option>
              <option value="year">Group by year</option>
            </Select>
            <Select aria-label="Order" value={filters.order} onChange={(e) => set({ order: e.target.value === "asc" ? "asc" : undefined })}>
              <option value="desc">Newest first</option>
              <option value="asc">Oldest first (read the saga)</option>
            </Select>
            <label className="flex items-center gap-2 text-sm">
              <Switch checked={filters.favorites} onCheckedChange={(v) => set({ favorites: v ? "1" : undefined })} /> <Star className="size-3.5 text-gold" /> My favorites
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Switch checked={filters.highlights} onCheckedChange={(v) => set({ highlights: v ? "1" : undefined })} /> Highlights &amp; pins only
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Switch checked={filters.show_all} onCheckedChange={(v) => set({ all: v ? "1" : undefined })} /> Include minor events
            </label>
            {isAdmin ? (
              <label className="flex items-center gap-2 text-sm">
                <Switch checked={filters.include_hidden} onCheckedChange={(v) => set({ hidden: v ? "1" : undefined })} /> Show hidden (admin)
              </label>
            ) : null}
            <Button variant="ghost" size="sm" onClick={() => router.replace(pathname)} className="justify-start">
              <X /> Clear all
            </Button>
          </div>
        ) : null}
      </div>

      {first ? (
        <p className="mb-4 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <Filter className="size-3.5" /> {first.total} event{first.total === 1 ? "" : "s"}
          {first.hidden_below_threshold && !filters.show_all ? (
            <button className="text-gold underline-offset-2 hover:underline cursor-pointer" onClick={() => set({ all: "1" })}>
              + {first.hidden_below_threshold} minor events hidden — show them
            </button>
          ) : null}
        </p>
      ) : null}

      {tl.isError ? (
        <ErrorState error={tl.error} retry={() => tl.refetch()} />
      ) : tl.isLoading ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-32 rounded-xl" />
          ))}
        </div>
      ) : events.length ? (
        <div className={cn("transition-opacity", tl.isFetching && !tl.isFetchingNextPage && "opacity-60")}>
          <TimelineView events={events} groupId={groupId} grouping={grouping} hasMore={!!tl.hasNextPage} loadMore={() => tl.fetchNextPage()} loadingMore={tl.isFetchingNextPage} />
        </div>
      ) : (
        <EmptyState icon={ScrollText} title="No adventures match" action={<ManualEventDialog groupId={groupId} />}>
          Try clearing filters, including minor events, or record a memory by hand.
        </EmptyState>
      )}
    </div>
  );
}

export default function TimelinePage() {
  return (
    <React.Suspense>
      <TimelineInner />
    </React.Suspense>
  );
}
