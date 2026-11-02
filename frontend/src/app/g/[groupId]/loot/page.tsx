"use client";

import { Gem, Search, Sparkles } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import * as React from "react";
import { CharacterName, MemberAvatar } from "@/components/common/avatar";
import { ItemIcon } from "@/components/common/item-icon";
import { EmptyState, ErrorState, Notice, PageHeader } from "@/components/common/misc";
import { ManualEventDialog } from "@/components/timeline/manual-event-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/misc";
import { fmtDate } from "@/lib/format";
import { useFacets, useLoot, useLootHighlights, type LootFilters } from "@/lib/queries";
import type { LootRow } from "@/lib/types";
import { cn } from "@/lib/utils";
import { QUALITY_LABEL, qualityColor } from "@/lib/wow";

const REASON_LABEL: Record<string, string> = { legendary: "Legendary", epic: "Epic", rare: "Rare", mount: "Mount", collectible: "Collectible", favorite: "Group favorite", wishlist: "Wishlist", manual: "Logged manually" };

export default function LootMuseumPage() {
  const { groupId } = useParams<{ groupId: string }>();
  const [filters, setFilters] = React.useState<LootFilters>({ sort: "recent" });
  const [q, setQ] = React.useState("");
  React.useEffect(() => {
    const t = setTimeout(() => setFilters((f) => ({ ...f, q: q || undefined })), 250);
    return () => clearTimeout(t);
  }, [q]);
  const loot = useLoot(groupId, filters);
  const hl = useLootHighlights(groupId);
  const facets = useFacets(groupId);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        icon={Gem}
        title="Loot Museum"
        subtitle="The notable treasures your group has carried home, as recorded by the addon or logged by members."
        actions={
          <ManualEventDialog
            groupId={groupId}
            trigger={
              <Button variant="outline">
                <Gem /> Log a drop manually
              </Button>
            }
          />
        }
      />

      <section className="grid gap-4 md:grid-cols-3">
        <Showcase title="First group legendary" row={hl.data?.first_legendary} loading={hl.isLoading} groupId={groupId} />
        <Showcase title="Latest mount" row={hl.data?.latest_mount} loading={hl.isLoading} groupId={groupId} />
        <Card className="p-5">
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Collection by quality</p>
          <ul className="mt-3 flex flex-col gap-2">
            {Object.entries(hl.data?.by_quality ?? {})
              .sort((a, b) => b[1] - a[1])
              .map(([qual, n]) => (
                <li key={qual} className="flex items-center gap-2 text-sm">
                  <span className="size-2.5 rounded-sm" style={{ background: qualityColor(qual) }} aria-hidden />
                  <span style={{ color: qualityColor(qual) }}>{QUALITY_LABEL[qual] ?? qual}</span>
                  <span className="ml-auto tabular-nums text-muted-foreground">{n}</span>
                </li>
              ))}
          </ul>
          <p className="mt-3 text-xs text-muted-foreground">Only items matching the group&apos;s notable-loot rules are kept.</p>
        </Card>
      </section>

      {hl.data?.most_celebrated.length ? (
        <section>
          <h2 className="mb-3 flex items-center gap-2 text-lg">
            <Sparkles className="size-4 text-gold" /> Most celebrated
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {hl.data.most_celebrated.map((r) => (
              <LootCard key={r.id} row={r} groupId={groupId} />
            ))}
          </div>
          <p className="mt-2 text-xs text-muted-foreground">Ranked by reactions and comments from your group — not by in-game drop rates.</p>
        </section>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-0 flex-1 sm:max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search items…" className="pl-8" aria-label="Search loot" />
        </div>
        <Select aria-label="Quality" className="w-40" value={filters.quality ?? ""} onChange={(e) => setFilters((f) => ({ ...f, quality: e.target.value || undefined }))}>
          <option value="">All qualities</option>
          {["legendary", "epic", "rare", "unknown"].map((x) => (
            <option key={x} value={x}>
              {QUALITY_LABEL[x]}
            </option>
          ))}
        </Select>
        <Select aria-label="Category" className="w-40" value={filters.category ?? ""} onChange={(e) => setFilters((f) => ({ ...f, category: e.target.value || undefined }))}>
          <option value="">All categories</option>
          {["gear", "mount", "pet", "toy", "collectible", "other"].map((x) => (
            <option key={x} value={x} className="capitalize">
              {x[0]!.toUpperCase() + x.slice(1)}
            </option>
          ))}
        </Select>
        <Select aria-label="Member" className="w-44" value={filters.member ?? ""} onChange={(e) => setFilters((f) => ({ ...f, member: e.target.value || undefined }))}>
          <option value="">All members</option>
          {facets.data?.members.map((m) => (
            <option key={m.id} value={m.id}>
              {m.display_name}
            </option>
          ))}
        </Select>
        <Select aria-label="Sort" className="w-44" value={filters.sort} onChange={(e) => setFilters((f) => ({ ...f, sort: e.target.value as LootFilters["sort"] }))}>
          <option value="recent">Most recent</option>
          <option value="oldest">Oldest first</option>
          <option value="celebrated">Most celebrated</option>
        </Select>
        {loot.data ? <span className="text-xs text-muted-foreground">{loot.data.total} items</span> : null}
      </div>

      {loot.isError ? (
        <ErrorState error={loot.error} />
      ) : loot.isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))}
        </div>
      ) : loot.data?.items.length ? (
        <div className={cn("grid gap-3 sm:grid-cols-2 xl:grid-cols-3 transition-opacity", loot.isFetching && "opacity-60")}>
          {loot.data.items.map((r) => (
            <LootCard key={r.id} row={r} groupId={groupId} />
          ))}
        </div>
      ) : (
        <EmptyState icon={Gem} title="The display cases are empty">
          Notable drops are recorded by the AzerothChronicles addon. You can also log one manually.
        </EmptyState>
      )}
      <Notice>Rarity is never inferred: quality comes from the game client or Battle.net item data, and &quot;group first&quot; only means first recorded in this group.</Notice>
    </div>
  );
}

function LootCard({ row, groupId }: { row: LootRow; groupId: string }) {
  const color = qualityColor(row.quality);
  const body = (
    <>
      <ItemIcon quality={row.quality} category={row.category} iconUrl={row.icon_url} size={52} />
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium" style={{ color }} title={row.item_name}>
          {row.item_name}
        </p>
        <p className="mt-0.5 flex items-center gap-1.5 text-xs text-muted-foreground">
          <MemberAvatar user={row.user} size={16} />
          {row.character ? <CharacterName character={row.character} /> : row.user.display_name}
          <span>· {fmtDate(row.obtained_at)}</span>
        </p>
        <div className="mt-1.5 flex flex-wrap gap-1">
          <Badge variant="outline">{REASON_LABEL[row.notable_reason] ?? row.notable_reason}</Badge>
          {row.is_group_first ? <Badge>Group first</Badge> : null}
          {row.source_instance ? <Badge variant="secondary">{row.source_instance}</Badge> : null}
          {row.celebration ? <Badge variant="secondary">🎉 {row.celebration}</Badge> : null}
        </div>
      </div>
    </>
  );
  const cls = cn("flex gap-3 rounded-xl border bg-card/90 p-3.5 parchment card-hover", row.quality === "legendary" && "border-[#ff8000]/40");
  return row.event_id ? (
    <Link href={`/g/${groupId}/timeline/${row.event_id}`} className={cls} data-testid="loot-card">
      {body}
    </Link>
  ) : (
    <div className={cls} data-testid="loot-card">
      {body}
    </div>
  );
}

function Showcase({ title, row, loading, groupId }: { title: string; row?: LootRow | null; loading: boolean; groupId: string }) {
  return (
    <Card className="relative overflow-hidden p-5">
      <div className="absolute inset-0 -z-0 opacity-30" style={{ background: row ? `radial-gradient(80% 90% at 85% 10%, color-mix(in srgb, ${qualityColor(row.quality)} 35%, transparent), transparent 70%)` : undefined }} aria-hidden />
      <p className="relative text-xs uppercase tracking-[0.16em] text-muted-foreground">{title}</p>
      {loading ? (
        <Skeleton className="mt-3 h-16" />
      ) : row ? (
        <Link href={row.event_id ? `/g/${groupId}/timeline/${row.event_id}` : "#"} className="relative mt-3 flex items-center gap-3">
          <ItemIcon quality={row.quality} category={row.category} iconUrl={row.icon_url} size={60} />
          <div className="min-w-0">
            <p className="font-display text-base leading-tight" style={{ color: qualityColor(row.quality) }}>
              {row.item_name}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {row.user.display_name} · {fmtDate(row.obtained_at)}
            </p>
          </div>
        </Link>
      ) : (
        <p className="relative mt-3 text-sm text-muted-foreground">Not recorded yet.</p>
      )}
    </Card>
  );
}
