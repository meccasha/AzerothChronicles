/** Display conventions for World of Warcraft concepts. */
import type { EventType } from "./types";

export const CLASS_COLORS: Record<string, string> = {
  "Death Knight": "#C41E3A",
  "Demon Hunter": "#A330C9",
  Druid: "#FF7C0A",
  Evoker: "#33937F",
  Hunter: "#AAD372",
  Mage: "#3FC7EB",
  Monk: "#00FF98",
  Paladin: "#F48CBA",
  Priest: "#FFFFFF",
  Rogue: "#FFF468",
  Shaman: "#0070DD",
  Warlock: "#8788EE",
  Warrior: "#C69B6D",
};

export function classColor(cls: string | null | undefined): string {
  return (cls && CLASS_COLORS[cls]) || "#9aa3b4";
}

export const QUALITY_COLORS: Record<string, string> = {
  poor: "var(--q-poor)",
  common: "var(--q-common)",
  uncommon: "var(--q-uncommon)",
  rare: "var(--q-rare)",
  epic: "var(--q-epic)",
  legendary: "var(--q-legendary)",
  artifact: "var(--q-artifact)",
  heirloom: "var(--q-heirloom)",
};

export function qualityColor(q: string | null | undefined): string {
  return (q && QUALITY_COLORS[q]) || "var(--muted-foreground)";
}

export const QUALITY_LABEL: Record<string, string> = {
  poor: "Poor",
  common: "Common",
  uncommon: "Uncommon",
  rare: "Rare",
  epic: "Epic",
  legendary: "Legendary",
  artifact: "Artifact",
  heirloom: "Heirloom",
  unknown: "Unknown quality",
};

export const EVENT_TYPE_LABEL: Record<EventType, string> = {
  achievement: "Achievement",
  boss_kill: "Boss kill",
  dungeon_complete: "Dungeon",
  loot: "Loot",
  milestone: "Milestone",
  manual: "Memory",
};

export const HIGHLIGHT_LABEL: Record<string, string> = {
  first_raid_kill: "First raid kill together",
  first_kill: "First group kill",
  first_heroic_kill: "First heroic victory",
  first_mythic_kill: "First mythic victory",
  first_group_dungeon: "First dungeon together",
  first_legendary: "First group legendary",
  legendary: "Legendary",
  mount: "Mount",
  group_achievement: "Shared achievement",
  feat_of_strength: "Feat of Strength",
  custom_milestone: "Group milestone",
};

/** Highlights that deserve the large, glowing "special event" treatment. */
export const MAJOR_HIGHLIGHTS = new Set([
  "first_raid_kill",
  "first_heroic_kill",
  "first_mythic_kill",
  "first_group_dungeon",
  "first_legendary",
  "legendary",
  "mount",
  "custom_milestone",
  "feat_of_strength",
]);

export const SOURCE_LABEL: Record<string, string> = {
  addon: "WoW addon",
  blizzard_api: "Battle.net",
  manual: "Manual entry",
  demo: "Demo (fictional)",
  simulated: "Simulated import",
  import: "Import",
};

export const CONFIRMATION_LABEL: Record<string, string> = {
  confirmed: "Confirmed by their own game data",
  roster: "Seen in a group-mate's roster",
  claimed: "Added manually (unverified)",
};

export const REACTIONS: { key: string; emoji: string; label: string }[] = [
  { key: "gg", emoji: "🤝", label: "GG" },
  { key: "fire", emoji: "🔥", label: "Fire" },
  { key: "trophy", emoji: "🏆", label: "Trophy" },
  { key: "heart", emoji: "❤️", label: "Love" },
  { key: "laugh", emoji: "😂", label: "Laugh" },
  { key: "skull", emoji: "💀", label: "RIP" },
  { key: "gem", emoji: "💎", label: "Shiny" },
  { key: "salute", emoji: "🫡", label: "Salute" },
];
export const REACTION_EMOJI: Record<string, string> = Object.fromEntries(REACTIONS.map((r) => [r.key, r.emoji]));

export const SERIES = {
  boss_kills: { label: "Boss kills", color: "var(--series-boss)" },
  achievements: { label: "Achievements", color: "var(--series-achievement)" },
  loot: { label: "Notable loot", color: "var(--series-loot)" },
  dungeons: { label: "Dungeons", color: "var(--series-dungeon)" },
  wipes: { label: "Wipes", color: "var(--series-wipe)" },
} as const;

export const VERIFICATION_LABEL: Record<string, { label: string; tip: string; variant: "success" | "info" | "secondary" }> = {
  blizzard_verified: { label: "Battle.net", tip: "Ownership verified through Battle.net", variant: "success" },
  addon_reported: { label: "Addon", tip: "Reported by this member's AzerothChronicles addon", variant: "info" },
  manual: { label: "Manual", tip: "Added by hand; not verified", variant: "secondary" },
};
