import { cn } from "@/lib/utils";
import { classColor } from "@/lib/wow";
import { initials } from "@/lib/format";
import type { Character, UserBrief } from "@/lib/types";

export function MemberAvatar({ user, size = 32, className, ring }: { user: Pick<UserBrief, "display_name" | "avatar_color">; size?: number; className?: string; ring?: boolean }) {
  const color = user.avatar_color ?? "#5b6475";
  return (
    <span
      aria-hidden
      className={cn("inline-flex shrink-0 select-none items-center justify-center rounded-full font-display font-semibold text-[#120d05]", ring && "ring-2 ring-background", className)}
      style={{ width: size, height: size, fontSize: Math.max(10, size * 0.38), background: `radial-gradient(circle at 30% 25%, ${color}ee, ${color}99 70%)`, boxShadow: `0 0 0 1px ${color}66` }}
      title={user.display_name}
    >
      {initials(user.display_name)}
    </span>
  );
}

export function AvatarStack({ users, max = 5, size = 26 }: { users: UserBrief[]; max?: number; size?: number }) {
  const shown = users.slice(0, max);
  return (
    <span className="flex items-center -space-x-2" aria-label={users.map((u) => u.display_name).join(", ")}>
      {shown.map((u) => (
        <MemberAvatar key={u.id} user={u} size={size} ring />
      ))}
      {users.length > max ? (
        <span className="inline-flex items-center justify-center rounded-full bg-secondary text-[10px] text-muted-foreground ring-2 ring-background" style={{ width: size, height: size }}>
          +{users.length - max}
        </span>
      ) : null}
    </span>
  );
}

/** Character portrait: Battle.net avatar when available, otherwise a class-coloured crest. */
export function CharacterPortrait({ character, size = 40 }: { character: Pick<Character, "name" | "character_class" | "avatar_url">; size?: number }) {
  const color = classColor(character.character_class);
  if (character.avatar_url) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={character.avatar_url} alt="" width={size} height={size} className="shrink-0 rounded-lg object-cover" style={{ boxShadow: `0 0 0 2px ${color}88` }} />
    );
  }
  return (
    <span
      aria-hidden
      className="inline-flex shrink-0 items-center justify-center rounded-lg font-display font-bold"
      style={{ width: size, height: size, fontSize: size * 0.42, color, background: `linear-gradient(145deg, ${color}26, #0b0f17 80%)`, boxShadow: `inset 0 0 0 1px ${color}66` }}
    >
      {character.name[0]}
    </span>
  );
}

export function CharacterName({ character, className }: { character: Pick<Character, "name" | "character_class">; className?: string }) {
  return (
    <span className={cn("font-medium", className)} style={{ color: classColor(character.character_class) }}>
      {character.name}
    </span>
  );
}
