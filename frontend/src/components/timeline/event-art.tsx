import { GameImage } from "@/components/common/game-image";
import { ItemIcon } from "@/components/common/item-icon";
import type { AdventureEvent } from "@/lib/types";
import { cn } from "@/lib/utils";
import { qualityColor } from "@/lib/wow";
import { EVENT_ACCENT, EVENT_ICON } from "./event-meta";

/** The square artwork slot of an event: item icon, achievement icon, boss portrait or dungeon art. */
export function EventArt({ event, size }: { event: AdventureEvent; size: number }) {
  if (event.event_type === "loot") {
    return (
      <ItemIcon
        quality={String(event.extra.quality ?? event.item?.quality ?? "epic")}
        category={event.extra.category as string}
        iconUrl={event.image_url ?? event.item?.icon_url}
        size={size}
      />
    );
  }
  const Icon = EVENT_ICON[event.event_type];
  const accent = EVENT_ACCENT[event.event_type];
  const glyph = <Icon style={{ width: size * 0.44, height: size * 0.44 }} aria-hidden />;
  return (
    <span
      className="relative flex shrink-0 items-center justify-center overflow-hidden rounded-lg"
      style={{ width: size, height: size, color: accent, background: `color-mix(in srgb, ${accent} 14%, transparent)`, boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${accent} 45%, transparent)` }}
    >
      <GameImage
        src={event.image_url}
        className={cn("size-full object-cover", event.image_kind === "portrait" && "object-top", event.image_kind === "icon" && "rounded-[inherit] p-[2px]")}
        fallback={glyph}
      />
    </span>
  );
}

/** Faded dungeon/raid artwork on the right side of a card. */
export function SceneBackdrop({ url, className }: { url?: string | null; className?: string }) {
  if (!url) return null;
  return (
    <div aria-hidden className={cn("pointer-events-none absolute inset-y-0 right-0 w-1/2 overflow-hidden", className)}>
      <GameImage
        src={url}
        className="size-full object-cover opacity-30 [mask-image:linear-gradient(to_left,black_20%,transparent)]"
      />
    </div>
  );
}

export { qualityColor };
