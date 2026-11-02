"use client";

import { ArrowRight, Award, CalendarDays, Crown, Gem, Plug, ScrollText, Skull, Sparkles, Swords, Users } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AwardIcon } from "@/components/common/award-icon";
import { MemberAvatar } from "@/components/common/avatar";
import { EmptyState, ErrorState, Notice, StatTile } from "@/components/common/misc";
import { EventCard } from "@/components/timeline/event-card";
import { ManualEventDialog } from "@/components/timeline/manual-event-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/misc";
import { fmtDate, fmtNumber } from "@/lib/format";
import { useDashboard, useGroup } from "@/lib/queries";
import type { AdventureEvent } from "@/lib/types";

export default function DashboardPage() {
  const { groupId } = useParams<{ groupId: string }>();
  const group = useGroup(groupId);
  const dash = useDashboard(groupId);

  if (dash.isError) return <ErrorState error={dash.error} retry={() => dash.refetch()} />;
  const d = dash.data;
  const o = d?.overview;

  return (
    <div className="flex flex-col gap-6">
      {/* Banner */}
      <section
        className="relative overflow-hidden rounded-2xl border border-gold/25 p-6 sm:p-8"
        style={{
          backgroundImage: group.data?.banner_url
            ? `linear-gradient(90deg, rgb(10 14 22 / 0.95) 30%, rgb(10 14 22 / 0.55)), url(${group.data.banner_url})`
            : "radial-gradient(120% 140% at 100% 0%, rgb(214 169 74 / 0.22), transparent 55%), radial-gradient(80% 120% at 0% 100%, rgb(57 135 229 / 0.12), transparent 60%), linear-gradient(135deg, #151b27, #0d121b)",
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        <div className="absolute -right-10 -top-10 size-56 rounded-full border border-gold/10" aria-hidden />
        <div className="absolute -right-2 -top-2 size-36 rounded-full border border-gold/15" aria-hidden />
        <p className="text-xs uppercase tracking-[0.3em] text-gold/80">The chronicle of</p>
        <h1 className="mt-2 text-3xl font-bold sm:text-4xl">
          <span className="gold-text">{group.data?.name ?? <Skeleton className="h-9 w-64" />}</span>
        </h1>
        {group.data?.description ? <p className="mt-3 max-w-2xl text-sm text-muted-foreground sm:text-base">{group.data.description}</p> : null}
        <div className="mt-5 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <Users className="size-4 text-gold" /> {group.data?.member_count ?? "–"} adventurers
          </span>
          {o?.first_recorded_activity ? (
            <span className="flex items-center gap-1.5">
              <CalendarDays className="size-4 text-gold" /> First recorded adventure {fmtDate(o.first_recorded_activity)}
            </span>
          ) : null}
          <span className="flex items-center gap-1.5">
            <ScrollText className="size-4 text-gold" /> {o ? fmtNumber(o.tracked_events) : "–"} tracked adventures
          </span>
        </div>
        <div className="mt-6 flex flex-wrap gap-2">
          <ManualEventDialog groupId={groupId} />
          <Button variant="outline" asChild>
            <Link href={`/g/${groupId}/timeline`}>
              Open the timeline <ArrowRight />
            </Link>
          </Button>
        </div>
      </section>

      {/* Stat tiles */}
      <section className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6" aria-label="Group totals">
        {o ? (
          <>
            <StatTile label="Adventures" value={o.tracked_events} icon={ScrollText} hint="recorded timeline events" />
            <StatTile label="Boss kills" value={o.boss_kills_confirmed} icon={Swords} accent="var(--series-boss)" hint="confirmed by game data" />
            <StatTile label="Wipes" value={o.wipes_recorded} icon={Skull} accent="var(--series-wipe)" hint="recorded by the addon" />
            <StatTile label="Achievements" value={o.achievements_recorded} icon={Award} accent="var(--series-achievement)" hint="posted to the timeline" />
            <StatTile label="Notable loot" value={o.notable_loot} icon={Gem} accent="var(--series-loot)" hint={`${o.legendary_loot} legendary · ${o.mounts} mounts`} />
            <StatTile label="Play sessions" value={o.play_sessions} icon={CalendarDays} hint="derived from activity" />
          </>
        ) : (
          Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-28 rounded-xl" />)
        )}
      </section>

      {d && d.coverage.notes.length > 1 ? (
        <Notice>
          <span className="font-medium">About these numbers: </span>
          {d.coverage.notes.join(" ")}{" "}
          <Link href={`/g/${groupId}/integrations`} className="underline underline-offset-2">
            Improve coverage
          </Link>
        </Notice>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
        <div className="flex min-w-0 flex-col gap-6">
          {d?.featured ? (
            <section>
              <SectionTitle icon={Sparkles} title="Featured milestone" />
              <EventCard event={d.featured} groupId={groupId} />
            </section>
          ) : null}
          <section>
            <SectionTitle icon={ScrollText} title="Recent activity" href={`/g/${groupId}/timeline`} />
            {d ? (
              d.recent_activity.length ? (
                <div className="flex flex-col gap-3">
                  {d.recent_activity.map((e) => (
                    <EventCard key={e.id} event={e} groupId={groupId} />
                  ))}
                </div>
              ) : (
                <EmptyState icon={Plug} title="Your chronicle is empty" action={<ManualEventDialog groupId={groupId} />}>
                  Connect the addon or Battle.net from Integrations, import simulated events, or record your first memory by hand.
                </EmptyState>
              )
            ) : (
              <Skeleton className="h-64 rounded-xl" />
            )}
          </section>
        </div>

        <aside className="flex flex-col gap-6">
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <Crown className="size-4 text-gold" /> Award leaders
              </CardTitle>
              <span className="text-xs text-muted-foreground">{d?.award_period_label}</span>
            </CardHeader>
            <CardContent>
              {d?.award_leaders.length ? (
                <ul className="flex flex-col divide-y divide-border/60">
                  {d.award_leaders.map((a) => (
                    <li key={a.award_key} className="flex items-center gap-3 py-2.5">
                      <AwardIcon name={a.icon} className="size-4 shrink-0 text-gold" />
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm">{a.title}</span>
                        <span className="block text-xs text-muted-foreground">
                          {a.value} {a.unit}
                          {a.status === "tied" ? " · tied" : ""}
                        </span>
                      </span>
                      <MemberAvatar user={a.winner} size={26} />
                      <span className="max-w-24 truncate text-xs">{a.winner.display_name}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">No awards decided yet this month.</p>
              )}
              <Button variant="link" asChild className="mt-1 px-0">
                <Link href={`/g/${groupId}/hall-of-fame`}>
                  Visit the Hall of Fame <ArrowRight />
                </Link>
              </Button>
            </CardContent>
          </Card>
          <MiniList title="Recent boss kills" icon={Swords} events={d?.recent_boss_kills} groupId={groupId} />
          <MiniList title="Recent achievements" icon={Award} events={d?.recent_achievements} groupId={groupId} />
          <MiniList title="Recent notable loot" icon={Gem} events={d?.recent_loot} groupId={groupId} href={`/g/${groupId}/loot`} />
          {o?.most_active.length ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="size-4 text-gold" /> Most active adventurers
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ol className="flex flex-col gap-2.5">
                  {o.most_active.map((m, i) => (
                    <li key={m.user_id} className="flex items-center gap-3 text-sm">
                      <span className="w-4 text-right font-display text-gold/80">{i + 1}</span>
                      <MemberAvatar user={m} size={26} />
                      <Link href={`/g/${groupId}/members/${m.user_id}`} className="flex-1 truncate hover:text-gold">
                        {m.display_name}
                      </Link>
                      <span className="tabular-nums text-muted-foreground">{m.events}</span>
                    </li>
                  ))}
                </ol>
              </CardContent>
            </Card>
          ) : null}
        </aside>
      </div>
    </div>
  );
}

function SectionTitle({ icon: Icon, title, href }: { icon: typeof Swords; title: string; href?: string }) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <h2 className="flex items-center gap-2 text-lg">
        <Icon className="size-4 text-gold" /> {title}
      </h2>
      {href ? (
        <Link href={href} className="text-xs text-muted-foreground hover:text-gold">
          View all →
        </Link>
      ) : null}
    </div>
  );
}

function MiniList({ title, icon: Icon, events, groupId, href }: { title: string; icon: typeof Swords; events?: AdventureEvent[]; groupId: string; href?: string }) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <Icon className="size-4 text-gold" /> {title}
        </CardTitle>
        {href ? (
          <Link href={href} className="text-xs text-muted-foreground hover:text-gold">
            More
          </Link>
        ) : null}
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {events === undefined ? <Skeleton className="h-24" /> : events.length ? events.map((e) => <EventCard key={e.id} event={e} groupId={groupId} compact />) : <p className="text-sm text-muted-foreground">Nothing recorded yet.</p>}
      </CardContent>
    </Card>
  );
}
