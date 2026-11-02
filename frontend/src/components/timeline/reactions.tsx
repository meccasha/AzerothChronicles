"use client";

import { SmilePlus } from "lucide-react";
import { Popover } from "radix-ui";
import { api } from "@/lib/api";
import { useEventMutation } from "@/lib/queries";
import type { AdventureEvent } from "@/lib/types";
import { cn } from "@/lib/utils";
import { REACTION_EMOJI, REACTIONS } from "@/lib/wow";

export function Reactions({ groupId, event }: { groupId: string; event: AdventureEvent }) {
  const toggle = useEventMutation(groupId, (emoji: string) =>
    api(`/groups/${groupId}/events/${event.id}/reactions`, { method: "POST", json: { emoji } }),
  );
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {event.reactions.map((r) => (
        <button
          key={r.emoji}
          onClick={(e) => {
            e.stopPropagation();
            toggle.mutate(r.emoji);
          }}
          className={cn(
            "inline-flex h-7 items-center gap-1 rounded-full border px-2 text-xs tabular-nums transition hover:border-gold/50 cursor-pointer",
            r.mine ? "border-gold/50 bg-gold/15 text-gold-bright" : "border-border bg-card/60 text-muted-foreground",
          )}
          aria-pressed={r.mine}
          aria-label={`${r.emoji} reaction, ${r.count}`}
        >
          <span aria-hidden>{REACTION_EMOJI[r.emoji] ?? "✨"}</span>
          {r.count}
        </button>
      ))}
      <Popover.Root>
        <Popover.Trigger
          onClick={(e) => e.stopPropagation()}
          className="inline-flex size-7 items-center justify-center rounded-full border border-dashed border-border text-muted-foreground transition hover:border-gold/50 hover:text-gold cursor-pointer"
          aria-label="Add reaction"
        >
          <SmilePlus className="size-3.5" />
        </Popover.Trigger>
        <Popover.Portal>
          <Popover.Content sideOffset={6} className="z-50 flex gap-1 rounded-full border border-gold/30 bg-popover p-1 shadow-xl" onClick={(e) => e.stopPropagation()}>
            {REACTIONS.map((r) => (
              <Popover.Close key={r.key} asChild>
                <button onClick={() => toggle.mutate(r.key)} className="flex size-8 items-center justify-center rounded-full text-lg transition hover:scale-125 hover:bg-accent cursor-pointer" title={r.label} aria-label={r.label}>
                  {r.emoji}
                </button>
              </Popover.Close>
            ))}
          </Popover.Content>
        </Popover.Portal>
      </Popover.Root>
    </div>
  );
}
