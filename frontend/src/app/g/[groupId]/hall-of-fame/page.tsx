"use client";

import { ChevronDown, Crown, Info, RefreshCw, Vote } from "lucide-react";
import { useParams } from "next/navigation";
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { AwardIcon } from "@/components/common/award-icon";
import { MemberAvatar } from "@/components/common/avatar";
import { ErrorState, Notice, PageHeader, useToast } from "@/components/common/misc";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/misc";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { fmtRelative } from "@/lib/format";
import { useEventMutation, useGroup, useHallOfFame, useMembers } from "@/lib/queries";
import type { Award, AwardResult } from "@/lib/types";
import { cn } from "@/lib/utils";

const PERIOD_LABEL: Record<string, string> = { week: "This week", month: "This month", season: "This season", all_time: "All time" };

export default function HallOfFamePage() {
  const { groupId } = useParams<{ groupId: string }>();
  const hof = useHallOfFame(groupId);
  const group = useGroup(groupId);
  const members = useMembers(groupId);
  const toast = useToast();
  const [period, setPeriod] = React.useState<"week" | "month" | "season" | "all_time">("all_time");
  const isAdmin = group.data?.my_role === "owner" || group.data?.my_role === "admin";
  const recompute = useEventMutation(groupId, () => api(`/groups/${groupId}/awards/recompute`, { method: "POST" }));

  if (hof.isError) return <ErrorState error={hof.error} retry={() => hof.refetch()} />;
  const awards = hof.data?.awards.filter((a) => a.enabled) ?? [];
  const cabinet = Object.entries(hof.data?.trophy_cabinet ?? {})
    .map(([uid, n]) => ({ user: members.data?.find((m) => m.user.id === uid)?.user, n }))
    .filter((x) => x.user)
    .sort((a, b) => b.n - a.n);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        icon={Crown}
        title="Hall of Fame"
        subtitle="Friendly rivalries, decided by recorded data. Every award's rules are published below and results are reproducible."
        actions={
          isAdmin ? (
            <Button variant="outline" onClick={() => recompute.mutate(undefined, { onSuccess: () => toast("Awards recalculated") })} disabled={recompute.isPending}>
              <RefreshCw className={cn(recompute.isPending && "animate-spin")} /> Recalculate
            </Button>
          ) : null
        }
      />

      {cabinet.length ? (
        <Card className="overflow-hidden">
          <div className="flex flex-col gap-4 bg-gradient-to-r from-gold/10 via-transparent to-transparent p-5 sm:flex-row sm:items-center">
            <div className="shrink-0">
              <p className="font-display text-sm uppercase tracking-[0.2em] text-gold-bright">Trophy cabinet</p>
              <p className="text-xs text-muted-foreground">Completed weekly, monthly &amp; seasonal awards won outright</p>
            </div>
            <ol className="flex flex-wrap gap-4 sm:ml-auto">
              {cabinet.map(({ user, n }, i) => (
                <li key={user!.id} className="flex items-center gap-2">
                  <span className={cn("font-display text-lg", i === 0 ? "text-gold-bright" : "text-muted-foreground")}>{i + 1}</span>
                  <MemberAvatar user={user!} size={30} />
                  <span className="text-sm">{user!.display_name}</span>
                  <Badge>{n} 🏆</Badge>
                </li>
              ))}
            </ol>
          </div>
        </Card>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs value={period} onValueChange={(v) => setPeriod(v as typeof period)}>
          <TabsList>
            {(["week", "month", "season", "all_time"] as const).map((p) => (
              <TabsTrigger key={p} value={p}>
                {PERIOD_LABEL[p]}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        {hof.data?.last_computed_at ? <span className="text-xs text-muted-foreground">Calculated {fmtRelative(hof.data.last_computed_at)}</span> : null}
      </div>
      {hof.data && period !== "all_time" ? <p className="-mt-3 text-xs text-muted-foreground">Period: {hof.data.current_labels[period]}</p> : null}

      {hof.isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-64 rounded-xl" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {awards.map((a) => (
            <AwardCard key={a.key} award={a} period={period} groupId={groupId} />
          ))}
        </div>
      )}
      <Notice>
        Ties are shown as ties (the listed name breaks the tie by earliest membership). Death-based awards are only calculated when members&apos; addons report
        death data; otherwise they show &quot;not enough data&quot; instead of guessing.
      </Notice>
    </div>
  );
}

function AwardCard({ award, period, groupId }: { award: Award; period: "week" | "month" | "season" | "all_time"; groupId: string }) {
  const [showRules, setShowRules] = React.useState(false);
  const supported = award.period_types.includes(period);
  const r = supported ? award.current[period] : null;
  const fallbackPeriod = !supported ? (award.period_types[0] as keyof Award["current"]) : null;
  const shown: AwardResult | null | undefined = r ?? (fallbackPeriod ? award.current[fallbackPeriod] : null);
  const won = shown && (shown.status === "awarded" || shown.status === "tied") && shown.winner;

  return (
    <Card className={cn("flex flex-col overflow-hidden card-hover", won && "border-gold/40")}>
      <div className="relative flex items-start gap-4 p-5">
        <span className={cn("flex size-14 shrink-0 items-center justify-center rounded-xl border", won ? "border-gold/50 bg-gradient-to-br from-gold/30 to-ember/10 text-gold-bright" : "border-border bg-secondary text-muted-foreground")}>
          <AwardIcon name={award.icon} className="size-7" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <h3 className="font-display text-lg leading-tight">{award.title}</h3>
            {award.kind === "vote" ? (
              <Badge variant="info">
                <Vote /> Voted
              </Badge>
            ) : null}
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{award.description}</p>
          {!supported ? <p className="mt-1 text-xs text-amber/90">Awarded {award.period_types.map((p) => PERIOD_LABEL[p]?.toLowerCase()).join(", ")} only</p> : null}
        </div>
      </div>

      <div className="mx-5 rounded-lg border bg-background-2/60 p-4">
        {won ? (
          <div className="flex items-center gap-3">
            <MemberAvatar user={shown!.winner!} size={44} />
            <div className="min-w-0 flex-1">
              <p className="truncate font-display text-lg text-gold-bright">{shown!.winner!.display_name}</p>
              <p className="text-sm text-muted-foreground">
                <span className="font-semibold tabular-nums text-foreground">{shown!.winning_value}</span> {award.unit}
                {shown!.status === "tied" ? <Badge variant="warning" className="ml-2">Tied</Badge> : null}
              </p>
            </div>
          </div>
        ) : shown?.status === "insufficient_data" ? (
          <p className="text-sm text-muted-foreground">Not enough data — requires {award.requires === "death_data" ? "death data from members' addons" : "more recorded activity"}.</p>
        ) : (
          <p className="text-sm text-muted-foreground">No winner yet for this period.</p>
        )}
        {shown?.standings && shown.standings.length > 1 ? (
          <ol className="mt-3 flex flex-col gap-1 border-t pt-3 text-xs">
            {shown.standings.slice(0, 5).map((s) => (
              <li key={s.user_id} className="flex items-center gap-2">
                <span className="w-4 text-right text-muted-foreground">{s.rank}</span>
                <span className="flex-1 truncate">{s.display_name}</span>
                <span className="tabular-nums text-muted-foreground">{s.value}</span>
              </li>
            ))}
          </ol>
        ) : null}
      </div>

      {award.kind === "vote" ? <Voting groupId={groupId} awardKey={award.key} /> : null}

      <div className="mt-auto px-5 pb-4 pt-3">
        <button onClick={() => setShowRules((v) => !v)} className="flex items-center gap-1 text-xs text-muted-foreground hover:text-gold cursor-pointer" aria-expanded={showRules}>
          <Info className="size-3.5" /> How it&apos;s calculated <ChevronDown className={cn("size-3.5 transition", showRules && "rotate-180")} />
        </button>
        {showRules ? <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{award.rules}</p> : null}
        {award.history.length ? (
          <details className="mt-2 text-xs">
            <summary className="cursor-pointer text-muted-foreground hover:text-gold">Past winners ({award.history.length})</summary>
            <ul className="mt-2 flex flex-col gap-1">
              {award.history.slice(0, 12).map((h) => (
                <li key={`${h.period_type}-${h.period_label}`} className="flex items-center gap-2">
                  <Badge variant="outline" className="capitalize">
                    {h.period_type === "all_time" ? "all time" : h.period_type}
                  </Badge>
                  <span className="text-muted-foreground">{h.period_label}</span>
                  <span className="ml-auto truncate">{h.winner?.display_name}</span>
                  <span className="tabular-nums text-muted-foreground">{h.winning_value}</span>
                </li>
              ))}
            </ul>
          </details>
        ) : null}
      </div>
    </Card>
  );
}

function Voting({ groupId, awardKey }: { groupId: string; awardKey: string }) {
  const members = useMembers(groupId);
  const toast = useToast();
  const noms = useQuery({
    queryKey: ["group", groupId, "noms", awardKey],
    queryFn: () =>
      api<{ period_label: string; my_vote: string | null; nominations: { id: string; nominee: { id: string; display_name: string; avatar_color: string | null }; reason: string; votes: number }[] }>(
        `/groups/${groupId}/awards/${awardKey}/nominations`,
      ),
  });
  const [nominee, setNominee] = React.useState("");
  const nominate = useEventMutation(groupId, () => api(`/groups/${groupId}/awards/${awardKey}/nominations`, { method: "POST", json: { nominee_user_id: nominee } }));
  const vote = useEventMutation(groupId, (id: string) => api(`/groups/${groupId}/awards/${awardKey}/vote`, { method: "PUT", json: { nomination_id: id } }));
  const refresh = () => noms.refetch();
  return (
    <div className="mx-5 mt-3 rounded-lg border border-sky-500/20 bg-sky-500/5 p-3 text-sm">
      <p className="mb-2 text-xs text-sky-200/90">Voting for {noms.data?.period_label}</p>
      <ul className="flex flex-col gap-1.5">
        {noms.data?.nominations.map((n) => (
          <li key={n.id} className="flex items-center gap-2">
            <MemberAvatar user={n.nominee} size={22} />
            <span className="flex-1 truncate">{n.nominee.display_name}</span>
            <span className="text-xs tabular-nums text-muted-foreground">{n.votes} votes</span>
            <Button size="sm" variant={noms.data?.my_vote === n.id ? "default" : "outline"} className="h-7" onClick={() => vote.mutate(n.id, { onSuccess: () => { refresh(); toast("Vote cast"); } })}>
              {noms.data?.my_vote === n.id ? "Your vote" : "Vote"}
            </Button>
          </li>
        ))}
      </ul>
      <div className="mt-2 flex gap-2">
        <Select value={nominee} onChange={(e) => setNominee(e.target.value)} className="h-8 text-xs" aria-label="Nominate a member">
          <option value="">Nominate a member…</option>
          {members.data?.map((m) => (
            <option key={m.user.id} value={m.user.id}>
              {m.user.display_name}
            </option>
          ))}
        </Select>
        <Button size="sm" variant="outline" disabled={!nominee} onClick={() => nominate.mutate(undefined, { onSuccess: () => { setNominee(""); refresh(); } })}>
          Nominate
        </Button>
      </div>
    </div>
  );
}
