import { Compass, Crown, Flag, Flame, Gem, Shield, Skull, Sparkles, Sunrise, Swords, Trophy, type LucideIcon } from "lucide-react";

const ICONS: Record<string, LucideIcon> = { trophy: Trophy, gem: Gem, sparkles: Sparkles, swords: Swords, compass: Compass, flag: Flag, shield: Shield, skull: Skull, sunrise: Sunrise, flame: Flame, crown: Crown };

export function AwardIcon({ name, className }: { name: string; className?: string }) {
  const Icon = ICONS[name] ?? Trophy;
  return <Icon className={className} aria-hidden />;
}
