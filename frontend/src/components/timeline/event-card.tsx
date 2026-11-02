"use client";

import { MessageSquare, Pin, Sparkles, Star } from "lucide-react";
import Link from "next/link";
import { AvatarStack } from "@/components/common/avatar";
import { ProvenanceBadges } from "@/components/common/badges";
import { ItemIcon } from "@/components/common/item-icon";
import { Badge } from "@/components/ui/badge";
import { fmtDateTime, fmtTime } from "@/lib/format";
import type { AdventureEvent } from "@/lib/types";
import { cn } from "@/lib/utils";
import { EVENT_TYPE_LABEL, HIGHLIGHT_LABEL, MAJOR_HIGHLIGHTS, qualityColor } from "@/lib/wow";
import { EVENT_ACCENT, EVENT_ICON } from "./event-meta";
import { Reactions } from "./reactions";

export function eventSubtitle(e: AdventureEvent): string {
  const parts: string[] = [];
  if (e.event_type === "boss_kill") {
    if (e.difficulty) parts.push(e.difficulty);
    if (e.instance_name) parts.push(e.instance_name);
    const w = e.extra.wipes_before_kill;
    if (typeof w === "number" && w > 0) parts.push(`after ${w} recorded wipe${w === 1 ? "" : "s"}`);
  } else if (e.event_type === "dungeon_complete") {
    if (e.extra.on_time === true) parts.push("Timed");
    else if (e.extra.on_time === false) parts.push("Over time");
  } else if (e.event_type === "loot") {
    if (e.extra.item_level) parts.push(`Item level ${e.extra.item_level}`);
    if (e.difficulty) parts.push(e.difficulty);
    if (e.instance_name) parts.push(e.instance_name);
  } else if (e.event_type === "achievement") {
    if (e.extra.feat_of_strength) parts.push("Feat of Strength");
    else if (typeof e.extra.points === "number") parts.push(`${e.extra.points} points`);
  }
  return parts.join(" · ");
}

export function EventCard({ event, groupId, compact }: { event: AdventureEvent; groupId: string; compact?: boolean }) {
  const Icon = EVENT_ICON[event.event_type];
  const accent = event.event_type === "loot" && event.extra.quality ? qualityColor(event.extra.quality) : EVENT_ACCENT[event.event_type];
  const special = !!event.highlight && MAJOR_HIGHLIGHTS.has(event.highlight);
  const href = `/g/${groupId}/timeline/${event.id}`;
  const subtitle = eventSubtitle(event);

  return (
    <article
      className={cn(
        "group relative overflow-hidden rounded-xl border bg-card/90 parchment card-hover",
        special && "border-gold/50 bg-gradient-to-br from-[#2a2213]/90 via-card/95 to-card/95 animate-glow",
        event.hidden && "opacity-60",
      )}
      data-testid="event-card"
    >
      {special ? (
        <div className="flex items-center gap-2 border-b border-gold/30 bg-gradient-to-r from-gold/20 via-gold/5 to-transparent px-4 py-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-gold-bright">
          <Sparkles className="size-3.5" />
          {event.extra.milestone ?? HIGHLIGHT_LABEL[event.highlight!] ?? "Highlight"}
        </div>
      ) : null}
      <div className={cn("flex gap-3.5 p-4", compact && "p-3")}>
        {event.event_type === "loot" ? (
          <ItemIcon quality={String(event.extra.quality ?? event.item?.quality ?? "epic")} category={event.extra.category as string} iconUrl={event.item?.icon_url} size={compact ? 38 : 46} />
        ) : (
          <span
            className="flex shrink-0 items-center justify-center rounded-lg"
            style={{ width: compact ? 38 : 46, height: compact ? 38 : 46, color: accent, background: `color-mix(in srgb, ${accent} 14%, transparent)`, boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${accent} 45%, transparent)` }}
          >
            <Icon className={compact ? "size-[18px]" : "size-5"} aria-hidden />
          </span>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] uppercase tracking-wider text-muted-foreground">
            <span style={{ color: accent }} className="font-semibold">
              {EVENT_TYPE_LABEL[event.event_type]}
            </span>
            <span aria-hidden>·</span>
            <time dateTime={event.occurred_at} title={fmtDateTime(event.occurred_at)}>
              {compact ? fmtDateTime(event.occurred_at) : fmtTime(event.occurred_at)}
            </time>
            {event.highlight && !special && HIGHLIGHT_LABEL[event.highlight] ? (
              <Badge variant="default" className="normal-case tracking-normal">
                {HIGHLIGHT_LABEL[event.highlight]}
              </Badge>
            ) : null}
            {event.pinned ? <Pin className="size-3 text-gold" aria-label="Pinned" /> : null}
            {event.favorite ? <Star className="size-3 fill-gold text-gold" aria-label="Favorite" /> : null}
          </div>
          <h3 className={cn("mt-1 font-display font-semibold leading-snug", compact ? "text-sm" : "text-base sm:text-lg")}>
            <Link href={href} className="outline-none after:absolute after:inset-0 hover:text-gold-bright focus-visible:text-gold-bright" style={event.event_type === "loot" ? { color: accent } : undefined}>
              {event.title}
            </Link>
          </h3>
          {subtitle ? <p className="mt-0.5 text-sm text-muted-foreground">{subtitle}</p> : null}
          {!compact && event.description && !["boss_kill", "loot", "dungeon_complete"].includes(event.event_type) ? (
            <p className="mt-2 line-clamp-3 text-sm text-foreground/85">{event.description}</p>
          ) : null}
          {!compact && event.media.length ? (
            <div className="relative z-10 mt-3 flex gap-2 overflow-x-auto">
              {event.media.slice(0, 3).map((m) => (
                // eslint-disable-next-line @next/next/no-img-element
                <img key={m.id} src={m.url} alt={m.caption ?? "Screenshot"} className="h-24 rounded-md border object-cover" />
              ))}
            </div>
          ) : null}
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
            <div className="flex min-w-0 items-center gap-2">
              {event.participants.length ? <AvatarStack users={event.participants.map((p) => p.user)} size={compact ? 22 : 26} /> : null}
              <span className="truncate text-xs text-muted-foreground">
                {event.participants.length === 1
                  ? (event.participants[0]!.character?.name ?? event.participants[0]!.user.display_name)
                  : event.participants.length > 1
                    ? `${event.participants.length} members`
                    : ""}
              </span>
            </div>
            {!compact ? <ProvenanceBadges event={event} compact /> : null}
          </div>
          {!compact ? (
            <div className="relative z-10 mt-3 flex items-center justify-between gap-2">
              <Reactions groupId={groupId} event={event} />
              <Link href={href} className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-gold">
                <MessageSquare className="size-3.5" /> {event.comment_count}
              </Link>
            </div>
          ) : null}
        </div>
      </div>
    </article>
  );
}
