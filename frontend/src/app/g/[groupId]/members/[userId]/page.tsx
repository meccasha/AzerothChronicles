"use client";

import { ArrowLeft, Award, Gem, Skull, Swords, Trophy } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AwardIcon } from "@/components/common/award-icon";
import { CharacterName, CharacterPortrait, MemberAvatar } from "@/components/common/avatar";
import { ErrorState, StatTile } from "@/components/common/misc";
import { EventCard } from "@/components/timeline/event-card";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import type { AdventureEvent, Character, MemberStatRow, UserBrief } from "@/lib/types";
import { VERIFICATION_LABEL } from "@/lib/wow";

interface Profile {
  user: UserBrief;
  role: string;
  joined_at: string;
  stats: MemberStatRow | null;
  characters: (Character & { group_events: number })[];
  recent_events: AdventureEvent[];
  award_wins: { award_key: string; title: string; icon: string; count: number }[];
}

export default function MemberProfilePage() {
  const { groupId, userId } = useParams<{ groupId: string; userId: string }>();
  const p = useQuery({ queryKey: ["group", groupId, "profile", userId], queryFn: () => api<Profile>(`/groups/${groupId}/members/${userId}/profile`) });
  if (p.isError) return <ErrorState error={p.error} />;
  if (!p.data) return <Skeleton className="h-96 rounded-xl" />;
  const d = p.data;
  const s = d.stats;
  return (
    <div className="flex flex-col gap-6">
      <Link href={`/g/${groupId}/members`} className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-gold">
        <ArrowLeft className="size-4" /> All members
      </Link>
      <Card className="flex flex-col gap-4 p-6 sm:flex-row sm:items-center">
        <MemberAvatar user={d.user} size={80} />
        <div className="flex-1">
          <h1 className="text-3xl font-bold gold-text">{d.user.display_name}</h1>
          <p className="mt-1 text-sm capitalize text-muted-foreground">
            {d.role} · member since {fmtDate(d.joined_at)}
          </p>
          {d.award_wins.length ? (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {d.award_wins.map((w) => (
                <Badge key={w.award_key}>
                  <AwardIcon name={w.icon} /> {w.title} ×{w.count}
                </Badge>
              ))}
            </div>
          ) : null}
        </div>
      </Card>
      {s ? (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <StatTile label="Activities" value={s.events} icon={Trophy} />
          <StatTile label="Boss kills" value={s.boss_kills} icon={Swords} hint="game-data confirmed" />
          <StatTile label="Dungeons" value={s.dungeons} icon={Swords} />
          <StatTile label="Achievements" value={s.achievements} icon={Award} />
          <StatTile label="Notable loot" value={s.loot} icon={Gem} hint={`${s.legendaries} legendary`} />
          <StatTile label="Deaths" value={s.deaths ?? "n/a"} icon={Skull} hint={s.deaths == null ? "no death data reported" : `over ${s.attempts_with_death_data} attempts`} />
        </div>
      ) : null}
      <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Characters</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {d.characters.length ? (
              d.characters.map((c) => (
                <div key={c.id} className="flex items-center gap-3 rounded-lg border bg-background-2/50 p-3">
                  <CharacterPortrait character={c} size={46} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate">
                      <CharacterName character={c} /> {c.is_main ? <span className="text-[10px] text-gold">MAIN</span> : null}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">
                      {[c.level ? `Level ${c.level}` : null, c.race, c.specialization, c.character_class].filter(Boolean).join(" ")}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">
                      {c.realm_name}-{c.region.toUpperCase()} · {c.faction ?? "Unknown faction"} · {c.group_events} group events
                    </p>
                  </div>
                  <Badge variant={VERIFICATION_LABEL[c.verification]!.variant}>{VERIFICATION_LABEL[c.verification]!.label}</Badge>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No characters yet.</p>
            )}
          </CardContent>
        </Card>
        <section>
          <h2 className="mb-3 text-lg">Recent adventures</h2>
          <div className="flex flex-col gap-3">
            {d.recent_events.length ? d.recent_events.map((e) => <EventCard key={e.id} event={e} groupId={groupId} />) : <p className="text-sm text-muted-foreground">Nothing recorded yet.</p>}
          </div>
        </section>
      </div>
    </div>
  );
}
