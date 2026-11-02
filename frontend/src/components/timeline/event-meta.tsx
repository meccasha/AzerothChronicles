import { Award, Gem, Landmark, PenLine, ScrollText, Skull, Swords, type LucideIcon } from "lucide-react";
import type { EventType } from "@/lib/types";

export const EVENT_ICON: Record<EventType, LucideIcon> = {
  achievement: Award,
  boss_kill: Swords,
  dungeon_complete: Landmark,
  loot: Gem,
  milestone: ScrollText,
  manual: PenLine,
};

export const EVENT_ACCENT: Record<EventType, string> = {
  achievement: "var(--series-achievement)",
  boss_kill: "var(--series-boss)",
  dungeon_complete: "var(--series-dungeon)",
  loot: "var(--series-loot)",
  milestone: "var(--gold)",
  manual: "#b9a98a",
};

export { Skull };
