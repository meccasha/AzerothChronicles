"use client";

import { BadgeCheck, Shield, UserPlus, Users } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { CharacterName, CharacterPortrait, MemberAvatar } from "@/components/common/avatar";
import { ErrorState, PageHeader } from "@/components/common/misc";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton, Tip } from "@/components/ui/misc";
import { fmtDate } from "@/lib/format";
import { useGroup, useMembers, useMemberStats } from "@/lib/queries";
import { VERIFICATION_LABEL } from "@/lib/wow";


export default function MembersPage() {
  const { groupId } = useParams<{ groupId: string }>();
  const members = useMembers(groupId);
  const stats = useMemberStats(groupId, { period: "all_time" });
  const group = useGroup(groupId);
  const isAdmin = group.data?.my_role === "owner" || group.data?.my_role === "admin";
  if (members.isError) return <ErrorState error={members.error} />;
  const statFor = (id: string) => stats.data?.members.find((m) => m.user_id === id);

  return (
    <div>
      <PageHeader
        icon={Users}
        title="Members"
        subtitle="The adventurers of this group and the characters they bring along — guilds don't matter here."
        actions={
          isAdmin ? (
            <Button variant="outline" asChild>
              <Link href={`/g/${groupId}/settings#members`}>
                <UserPlus /> Invite friends
              </Link>
            </Button>
          ) : null
        }
      />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {members.isLoading
          ? Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-56 rounded-xl" />)
          : members.data?.map((m) => {
              const s = statFor(m.user.id);
              return (
                <Card key={m.user.id} className="flex flex-col p-5 card-hover">
                  <Link href={`/g/${groupId}/members/${m.user.id}`} className="flex items-center gap-3">
                    <MemberAvatar user={m.user} size={52} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-display text-lg hover:text-gold">{m.user.display_name}</p>
                      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        {m.role !== "member" ? <Shield className="size-3 text-gold" /> : null}
                        <span className="capitalize">{m.role}</span> · since {fmtDate(m.joined_at)}
                      </p>
                    </div>
                  </Link>
                  {s ? (
                    <dl className="mt-4 grid grid-cols-4 gap-2 rounded-lg border bg-background-2/60 p-2.5 text-center">
                      {[
                        ["Events", s.events],
                        ["Kills", s.boss_kills],
                        ["Loot", s.loot],
                        ["Achv.", s.achievements],
                      ].map(([k, v]) => (
                        <div key={k as string}>
                          <dd className="font-display text-lg tabular-nums">{v}</dd>
                          <dt className="text-[10px] uppercase tracking-wider text-muted-foreground">{k}</dt>
                        </div>
                      ))}
                    </dl>
                  ) : null}
                  <ul className="mt-4 flex flex-col gap-2">
                    {m.characters.length ? (
                      m.characters.map((c) => {
                        const v = VERIFICATION_LABEL[c.verification]!;
                        return (
                          <li key={c.id} className="flex items-center gap-2.5">
                            <CharacterPortrait character={c} size={32} />
                            <div className="min-w-0 flex-1">
                              <p className="truncate text-sm">
                                <CharacterName character={c} /> {c.is_main ? <span className="text-[10px] text-gold">MAIN</span> : null}
                              </p>
                              <p className="truncate text-xs text-muted-foreground">
                                {[c.level ? `Lv ${c.level}` : null, c.race, c.specialization, c.character_class].filter(Boolean).join(" ")} · {c.realm_name} ({c.region.toUpperCase()})
                              </p>
                            </div>
                            <Tip content={v.tip}>
                              <span>
                                <Badge variant={v.variant}>
                                  {c.verification === "blizzard_verified" ? <BadgeCheck /> : null}
                                  {v.label}
                                </Badge>
                              </span>
                            </Tip>
                          </li>
                        );
                      })
                    ) : (
                      <li className="text-sm text-muted-foreground">No characters linked yet.</li>
                    )}
                  </ul>
                </Card>
              );
            })}
      </div>
    </div>
  );
}
