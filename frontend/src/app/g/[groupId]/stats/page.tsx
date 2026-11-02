"use client";

import { Award, BarChart3, CalendarDays, Gem, ScrollText, Skull, Swords, Users } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import * as React from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, ChartCard, ChartTooltip, GRID, SERIES_HEX, SURFACE } from "@/components/charts/chart-kit";
import { ACTIVITY_SERIES, GroupedBars, RankBars, StackedBars, TrendLine, bucketLabel } from "@/components/charts/charts";
import { MemberAvatar } from "@/components/common/avatar";
import { ErrorState, Notice, PageHeader, StatTile } from "@/components/common/misc";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/misc";
import { fmtDate } from "@/lib/format";
import { useMemberStats, useOverview, useProgression, useTimeseries, type PeriodParams } from "@/lib/queries";

const PERIODS = [
  { key: "all_time", label: "All time" },
  { key: "current_expansion", label: "Current expansion" },
  { key: "current_season", label: "Current season" },
  { key: "last_30_days", label: "Last 30 days" },
  { key: "last_90_days", label: "Last 90 days" },
  { key: "custom", label: "Custom range" },
];

export default function StatsPage() {
  const { groupId } = useParams<{ groupId: string }>();
  const [period, setPeriod] = React.useState("all_time");
  const [start, setStart] = React.useState("");
  const [end, setEnd] = React.useState("");
  const [bucket, setBucket] = React.useState<"week" | "month">("month");

  const params: PeriodParams =
    period === "custom"
      ? { period, start: start ? new Date(start).toISOString() : undefined, end: end ? new Date(end).toISOString() : undefined }
      : { period };
  const ready = period !== "custom" || !!start || !!end;
  const ov = useOverview(groupId, ready ? params : { period: "all_time" });
  const ts = useTimeseries(groupId, ready ? params : { period: "all_time" }, bucket);
  const members = useMemberStats(groupId, ready ? params : { period: "all_time" });
  const prog = useProgression(groupId);

  const o = ov.data;
  const series = ts.data?.series ?? [];
  const fetching = ov.isFetching || ts.isFetching;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader icon={BarChart3} title="Group Statistics" subtitle="Cumulative progression built only from recorded events. Counts are what was tracked, not everything that was played." />

      {/* One filter row, above everything it scopes */}
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Period
          <Select value={period} onChange={(e) => setPeriod(e.target.value)} className="w-48">
            {PERIODS.map((p) => (
              <option key={p.key} value={p.key}>
                {p.label}
              </option>
            ))}
          </Select>
        </label>
        {period === "custom" ? (
          <>
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              From
              <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} className="w-40" />
            </label>
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              To
              <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="w-40" />
            </label>
          </>
        ) : null}
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Chart buckets
          <Select value={bucket} onChange={(e) => setBucket(e.target.value as "week" | "month")} className="w-32">
            <option value="month">Monthly</option>
            <option value="week">Weekly</option>
          </Select>
        </label>
        {o?.label ? <Badge variant="secondary" className="mb-2">{o.label}</Badge> : null}
      </div>

      {ov.isError ? <ErrorState error={ov.error} retry={() => ov.refetch()} /> : null}

      <section className={`grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8 transition-opacity ${fetching ? "opacity-60" : ""}`}>
        {o ? (
          <>
            <StatTile label="Adventures" value={o.tracked_events} icon={ScrollText} />
            <StatTile label="Boss kills" value={o.boss_kills_confirmed} icon={Swords} accent={SERIES_HEX.boss_kills} hint={o.boss_kills_manual ? `+${o.boss_kills_manual} logged manually` : "confirmed"} />
            <StatTile label="Wipes" value={o.wipes_recorded} icon={Skull} accent={SERIES_HEX.wipes} />
            <StatTile label="Achievements" value={o.achievements_recorded} icon={Award} accent={SERIES_HEX.achievements} />
            <StatTile label="Dungeons" value={o.dungeons_recorded} icon={CalendarDays} accent={SERIES_HEX.dungeons} />
            <StatTile label="Notable loot" value={o.notable_loot} icon={Gem} accent={SERIES_HEX.loot} />
            <StatTile label="Legendaries" value={o.legendary_loot} icon={Gem} accent="#ff8000" />
            <StatTile label="Sessions" value={o.play_sessions} icon={Users} />
          </>
        ) : (
          Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-28 rounded-xl" />)
        )}
      </section>

      {o?.coverage ? (
        <Notice>
          <strong className="font-medium">Data coverage:</strong> {o.coverage.addon_reporting}/{o.coverage.members} members upload addon data,{" "}
          {o.coverage.battlenet_linked}/{o.coverage.members} have linked Battle.net. {o.coverage.notes.join(" ")}
          {o.first_recorded_activity ? ` First recorded group activity: ${fmtDate(o.first_recorded_activity)}.` : ""}
        </Notice>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-2">
        <ChartCard
          title="Activity over time"
          description="Recorded events per period, by category"
          series={ACTIVITY_SERIES}
          rows={series as unknown as Record<string, unknown>[]}
          columns={[{ key: "bucket", label: "Period", format: (v) => bucketLabel(bucket)(String(v)) }, ...ACTIVITY_SERIES.map((s) => ({ key: s.key, label: s.label }))]}
          fetching={ts.isFetching}
          className="xl:col-span-2"
        >
          <StackedBars data={series} series={ACTIVITY_SERIES} bucket={bucket} height={300} />
        </ChartCard>
        <ChartCard
          title="Boss kills vs. wipes"
          description="Recorded boss attempts (addon data)"
          series={[
            { key: "boss_kills", label: "Kills", color: SERIES_HEX.boss_kills },
            { key: "wipes", label: "Wipes", color: SERIES_HEX.wipes },
          ]}
          rows={series as unknown as Record<string, unknown>[]}
          columns={[
            { key: "bucket", label: "Period", format: (v) => bucketLabel(bucket)(String(v)) },
            { key: "boss_kills", label: "Kills" },
            { key: "wipes", label: "Wipes" },
          ]}
          fetching={ts.isFetching}
        >
          <GroupedBars
            data={series as unknown as Record<string, unknown>[]}
            bucket={bucket}
            series={[
              { key: "boss_kills", label: "Kills", color: SERIES_HEX.boss_kills },
              { key: "wipes", label: "Wipes", color: SERIES_HEX.wipes },
            ]}
          />
        </ChartCard>
        <ChartCard
          title="Group participation"
          description="Distinct members with at least one recorded event"
          rows={series as unknown as Record<string, unknown>[]}
          columns={[
            { key: "bucket", label: "Period", format: (v) => bucketLabel(bucket)(String(v)) },
            { key: "active_members", label: "Active members" },
          ]}
          fetching={ts.isFetching}
        >
          <TrendLine data={series as unknown as Record<string, unknown>[]} dataKey="active_members" label="Active members" bucket={bucket} max={o?.coverage?.members} />
        </ChartCard>
        <ChartCard
          title="Most active members"
          description="Recorded group activities participated in"
          rows={(members.data?.members ?? []).map((m) => ({ name: m.display_name, events: m.events }))}
          columns={[
            { key: "name", label: "Member" },
            { key: "events", label: "Activities" },
          ]}
          fetching={members.isFetching}
        >
          <RankBars data={(members.data?.members ?? []).map((m) => ({ name: m.display_name, events: m.events }))} dataKey="events" label="Activities" />
        </ChartCard>
        <ChartCard
          title="Progression by expansion & season"
          description="All-time recorded events grouped by configured windows"
          series={ACTIVITY_SERIES}
          rows={(prog.data?.by_period ?? []).map((r) => ({
            bucket: r.season ? (prog.data?.seasons.find((s) => s.key === r.season)?.name ?? r.season) : (prog.data?.expansions.find((x) => x.key === r.expansion)?.name ?? "Unassigned"),
            boss_kills: r.boss_kill ?? 0,
            achievements: r.achievement ?? 0,
            dungeons: r.dungeon_complete ?? 0,
            loot: r.loot ?? 0,
            total: r.total,
          }))}
          columns={[
            { key: "bucket", label: "Window" },
            { key: "boss_kills", label: "Boss kills" },
            { key: "achievements", label: "Achievements" },
            { key: "dungeons", label: "Dungeons" },
            { key: "loot", label: "Loot" },
            { key: "total", label: "All events" },
          ]}
        >
          <PeriodBars rows={prog.data?.by_period ?? []} names={prog.data} />
        </ChartCard>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Member leaderboard</CardTitle>
          <CardDescription>Death counts appear only for members whose addon reports them.</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                <th className="py-2 pr-3 font-medium">Member</th>
                {["Activities", "Boss kills", "Dungeons", "Achievements", "Loot", "Legendaries", "Wipes", "Deaths"].map((h) => (
                  <th key={h} className="px-3 py-2 text-right font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {members.data?.members.map((m) => (
                <tr key={m.user_id} className="border-t border-border/60">
                  <td className="py-2.5 pr-3">
                    <Link href={`/g/${groupId}/members/${m.user_id}`} className="flex items-center gap-2 hover:text-gold">
                      <MemberAvatar user={m} size={26} /> {m.display_name}
                    </Link>
                  </td>
                  {[m.events, m.boss_kills, m.dungeons, m.achievements, m.loot, m.legendaries, m.wipes].map((v, i) => (
                    <td key={i} className="px-3 text-right tabular-nums">
                      {v}
                    </td>
                  ))}
                  <td className="px-3 text-right tabular-nums text-muted-foreground">{m.deaths ?? "n/a"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Boss progression</CardTitle>
          <CardDescription>Recorded attempts per encounter and difficulty</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {prog.data?.encounters.length ? (
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="py-2 pr-3 font-medium">Encounter</th>
                  <th className="px-3 py-2 font-medium">Difficulty</th>
                  <th className="px-3 py-2 text-right font-medium">Kills</th>
                  <th className="px-3 py-2 text-right font-medium">Wipes</th>
                  <th className="px-3 py-2 text-right font-medium">First kill</th>
                </tr>
              </thead>
              <tbody>
                {prog.data.encounters.map((r) => (
                  <tr key={`${r.encounter_id}-${r.difficulty}`} className="border-t border-border/60">
                    <td className="py-2 pr-3">
                      <span className="block">{r.name}</span>
                      <span className="text-xs text-muted-foreground">{r.instance_name}</span>
                    </td>
                    <td className="px-3">
                      <Badge variant={r.difficulty.toLowerCase().includes("mythic") ? "default" : "secondary"}>{r.difficulty}</Badge>
                    </td>
                    <td className="px-3 text-right tabular-nums">{r.kills}</td>
                    <td className="px-3 text-right tabular-nums">{r.wipes}</td>
                    <td className="px-3 text-right text-muted-foreground">{r.first_kill_at ? fmtDate(r.first_kill_at) : "Not yet"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-sm text-muted-foreground">No boss attempts recorded yet. Boss data comes from the AzerothChronicles addon.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function PeriodBars({ rows, names }: { rows: ({ expansion: string | null; season: string | null; total: number } & Record<string, number>)[]; names?: { expansions: { key: string; name: string }[]; seasons: { key: string; name: string }[] } }) {
  const data = rows.map((r) => ({
    bucket: r.season ? (names?.seasons.find((s) => s.key === r.season)?.name ?? r.season) : (names?.expansions.find((x) => x.key === r.expansion)?.name ?? "Unassigned"),
    boss_kills: r.boss_kill ?? 0,
    achievements: r.achievement ?? 0,
    dungeons: r.dungeon_complete ?? 0,
    loot: r.loot ?? 0,
  }));
  return <CategoryStack data={data} />;
}

function CategoryStack({ data }: { data: Record<string, unknown>[] }) {
  const s = ACTIVITY_SERIES;
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ top: 8, right: 4, left: -18, bottom: 0 }} barCategoryGap="30%">
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis dataKey="bucket" {...AXIS} tickLine={false} interval={0} tick={{ ...AXIS.tick, fontSize: 10 }} />
        <YAxis allowDecimals={false} {...AXIS} tickLine={false} axisLine={false} width={44} />
        <Tooltip cursor={{ fill: "rgb(214 169 74 / 0.06)" }} content={<ChartTooltip />} />
        {s.map((x, i) => (
          <Bar key={x.key} dataKey={x.key} name={x.label} stackId="p" fill={x.color} stroke={SURFACE} strokeWidth={2} radius={i === s.length - 1 ? [4, 4, 0, 0] : 0} isAnimationActive={false} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
