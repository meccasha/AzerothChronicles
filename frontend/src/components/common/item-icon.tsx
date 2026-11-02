import { Bird, Box, Crown, Gem, PawPrint, Shield, Sword, ToyBrick } from "lucide-react";
import { cn } from "@/lib/utils";
import { qualityColor } from "@/lib/wow";

const CATEGORY_ICON = { gear: Sword, mount: Bird, pet: PawPrint, toy: ToyBrick, collectible: Gem, other: Box } as const;

export function ItemIcon({ quality, category, iconUrl, size = 44, className, itemClass }: { quality: string; category?: string | null; iconUrl?: string | null; size?: number; className?: string; itemClass?: string | null }) {
  const color = qualityColor(quality);
  const Icon =
    category && category in CATEGORY_ICON
      ? CATEGORY_ICON[category as keyof typeof CATEGORY_ICON]
      : itemClass === "Armor"
        ? Shield
        : quality === "legendary"
          ? Crown
          : Sword;
  return (
    <span
      className={cn("relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-md", quality === "legendary" && "animate-glow", className)}
      style={{ width: size, height: size, boxShadow: `inset 0 0 0 2px ${color}, 0 0 14px -4px ${color}`, background: `radial-gradient(circle at 50% 35%, color-mix(in srgb, ${color} 28%, transparent), #07090e 75%)` }}
    >
      {iconUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={iconUrl} alt="" className="size-full object-cover" />
      ) : (
        <Icon aria-hidden style={{ color, width: size * 0.5, height: size * 0.5 }} />
      )}
    </span>
  );
}
