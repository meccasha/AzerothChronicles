"use client";

import { Copy, Link2, Settings, Trash2, UserPlus } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import * as React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { MemberAvatar } from "@/components/common/avatar";
import { ErrorState, Notice, PageHeader, useToast } from "@/components/common/misc";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { Skeleton, Switch } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { keys, useGroup, useHallOfFame, useInvites, useMe, useMembers } from "@/lib/queries";
import type { Group, GroupSettings } from "@/lib/types";
import { EVENT_TYPE_LABEL } from "@/lib/wow";

export default function SettingsPage() {
  const { groupId } = useParams<{ groupId: string }>();
  const group = useGroup(groupId);
  const me = useMe();
  if (group.isError) return <ErrorState error={group.error} />;
  if (!group.data) return <Skeleton className="h-96 rounded-xl" />;
  const g = group.data;
  const isAdmin = g.my_role === "owner" || g.my_role === "admin";
  return (
    <div className="flex flex-col gap-6">
      <PageHeader icon={Settings} title="Group Settings" subtitle={isAdmin ? "Shape what gets recorded and celebrated." : "Only admins can change group settings. You can view them and leave the group."} />
      <GeneralCard g={g} disabled={!isAdmin} />
      <div className="grid gap-6 lg:grid-cols-2">
        <EventRulesCard g={g} disabled={!isAdmin} />
        <LootRulesCard g={g} disabled={!isAdmin} />
      </div>
      <AwardsCard g={g} disabled={!isAdmin} />
      <MembersCard g={g} isAdmin={isAdmin} myId={me.data?.id} />
      <ItemRulesCard g={g} disabled={!isAdmin} />
      <DangerZone g={g} myId={me.data?.id} />
    </div>
  );
}

function useSave(groupId: string) {
  const qc = useQueryClient();
  const toast = useToast();
  return async (body: Record<string, unknown>) => {
    try {
      await api(`/groups/${groupId}`, { method: "PATCH", json: body });
      await qc.invalidateQueries({ queryKey: keys.group(groupId) });
      await qc.invalidateQueries({ queryKey: keys.groups });
      toast("Settings saved");
    } catch (e) {
      toast((e as Error).message, "error");
    }
  };
}

function GeneralCard({ g, disabled }: { g: Group; disabled: boolean }) {
  const save = useSave(g.id);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Group profile</CardTitle>
        <CardDescription>Created {fmtDateTime(g.created_at)}</CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="grid gap-4 md:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            save({ name: f.get("name"), description: f.get("description"), banner_url: (f.get("banner_url") as string) || null, visibility: f.get("visibility") });
          }}
        >
          <fieldset disabled={disabled} className="contents">
            <Field label="Name" htmlFor="g-name">
              <Input id="g-name" name="name" defaultValue={g.name} minLength={3} maxLength={80} required />
            </Field>
            <Field label="Invite link visibility" htmlFor="g-vis" hint="Groups are always private; this only controls what invite links reveal.">
              <Select id="g-vis" name="visibility" defaultValue={g.visibility}>
                <option value="private">Private — invite shows only the name</option>
                <option value="invite_preview">Preview — invite shows description and size</option>
              </Select>
            </Field>
            <Field label="Description" htmlFor="g-desc">
              <Textarea id="g-desc" name="description" defaultValue={g.description} maxLength={2000} />
            </Field>
            <Field label="Banner image URL (optional)" htmlFor="g-banner" hint="https:// image shown behind the dashboard header">
              <Input id="g-banner" name="banner_url" type="url" defaultValue={g.banner_url ?? ""} placeholder="https://…" />
            </Field>
            {!disabled ? (
              <div className="md:col-span-2">
                <Button type="submit">Save profile</Button>
              </div>
            ) : null}
          </fieldset>
        </form>
      </CardContent>
    </Card>
  );
}

function EventRulesCard({ g, disabled }: { g: Group; disabled: boolean }) {
  const save = useSave(g.id);
  const [ev, setEv] = React.useState<GroupSettings["events"]>(g.settings.events);
  const toggleCat = (c: string) =>
    setEv((e) => ({ ...e, enabled_categories: e.enabled_categories.includes(c) ? e.enabled_categories.filter((x) => x !== c) : [...e.enabled_categories, c] }));
  return (
    <Card>
      <CardHeader>
        <CardTitle>Timeline filters &amp; importance</CardTitle>
        <CardDescription>Keep the journal meaningful. Filtered events are still stored and counted.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <fieldset disabled={disabled} className="contents">
          <Field label={`Default importance cut-off: ${ev.timeline_min_importance}`} hint="Events scoring below this are collapsed on the timeline (manual and pinned events always show).">
            <input type="range" min={0} max={90} step={5} value={ev.timeline_min_importance} onChange={(e) => setEv({ ...ev, timeline_min_importance: Number(e.target.value) })} className="accent-[var(--gold)]" />
          </Field>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Min achievement points" hint="Feats of Strength always post">
              <Input type="number" min={0} max={100} value={ev.achievement_min_points} onChange={(e) => setEv({ ...ev, achievement_min_points: Number(e.target.value) })} />
            </Field>
            <Field label="Merge window (hours)" hint="Same achievement by several members">
              <Input type="number" min={0} max={72} value={ev.achievement_merge_hours} onChange={(e) => setEv({ ...ev, achievement_merge_hours: Number(e.target.value) })} />
            </Field>
            <Field label="Members for a boss kill" hint="Minimum group members present">
              <Input type="number" min={1} max={40} value={ev.encounter_min_members} onChange={(e) => setEv({ ...ev, encounter_min_members: Number(e.target.value) })} />
            </Field>
          </div>
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">Recorded categories</p>
            <div className="flex flex-wrap gap-3">
              {["achievement", "boss_kill", "dungeon_complete", "loot"].map((c) => (
                <label key={c} className="flex items-center gap-2 text-sm">
                  <Switch checked={ev.enabled_categories.includes(c)} onCheckedChange={() => toggleCat(c)} /> {EVENT_TYPE_LABEL[c as keyof typeof EVENT_TYPE_LABEL]}
                </label>
              ))}
            </div>
          </div>
          {!disabled ? (
            <Button className="self-start" onClick={() => save({ settings: { events: ev } })}>
              Save filters
            </Button>
          ) : null}
        </fieldset>
      </CardContent>
    </Card>
  );
}

function LootRulesCard({ g, disabled }: { g: Group; disabled: boolean }) {
  const save = useSave(g.id);
  const [lr, setLr] = React.useState<GroupSettings["loot"]>(g.settings.loot);
  const row = (key: keyof GroupSettings["loot"], label: string, hint: string) => (
    <label className="flex items-start justify-between gap-4 rounded-lg border bg-background-2/50 p-3">
      <span>
        <span className="block text-sm">{label}</span>
        <span className="block text-xs text-muted-foreground">{hint}</span>
      </span>
      <Switch checked={!!lr[key]} onCheckedChange={(v) => setLr({ ...lr, [key]: v })} disabled={disabled} />
    </label>
  );
  return (
    <Card>
      <CardHeader>
        <CardTitle>Notable loot rules</CardTitle>
        <CardDescription>What counts as museum-worthy. Common &amp; uncommon items are never recorded.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2.5">
        {row("record_legendary", "Legendary items", "Recommended: always record")}
        {row("record_mounts", "Mounts", "When the client reports a newly learned mount")}
        {row("record_epic", "Epic items", "Optional; can be busy during progression")}
        {row("record_collectibles", "Pets & toys", "Newly learned collectibles")}
        {row("record_rare", "Rare (blue) items", "Usually too noisy")}
        <Field label="Minimum epic item level (optional)">
          <Input type="number" min={0} disabled={disabled} value={lr.epic_min_item_level ?? ""} onChange={(e) => setLr({ ...lr, epic_min_item_level: e.target.value ? Number(e.target.value) : null })} />
        </Field>
        {!disabled ? (
          <Button className="self-start" onClick={() => save({ settings: { loot: lr } })}>
            Save loot rules
          </Button>
        ) : null}
      </CardContent>
    </Card>
  );
}

function AwardsCard({ g, disabled }: { g: Group; disabled: boolean }) {
  const hof = useHallOfFame(g.id);
  const save = useSave(g.id);
  const [off, setOff] = React.useState<string[]>(g.settings.awards.disabled);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Awards</CardTitle>
        <CardDescription>Turn awards on or off for this group. Disabled awards are not calculated.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
          {hof.data?.awards.map((a) => (
            <label key={a.key} className="flex items-center justify-between gap-3 rounded-lg border bg-background-2/50 p-3 text-sm">
              <span>
                {a.title} {a.kind === "vote" ? <Badge variant="info">vote</Badge> : null}
              </span>
              <Switch checked={!off.includes(a.key)} disabled={disabled} onCheckedChange={(v) => setOff((o) => (v ? o.filter((k) => k !== a.key) : [...o, a.key]))} />
            </label>
          ))}
        </div>
        {!disabled ? (
          <Button className="mt-4" onClick={async () => { await save({ settings: { awards: { disabled: off } } }); await api(`/groups/${g.id}/awards/recompute`, { method: "POST" }); }}>
            Save &amp; recalculate
          </Button>
        ) : null}
      </CardContent>
    </Card>
  );
}

function MembersCard({ g, isAdmin, myId }: { g: Group; isAdmin: boolean; myId?: string }) {
  const members = useMembers(g.id);
  const invites = useInvites(g.id, isAdmin);
  const qc = useQueryClient();
  const toast = useToast();
  const [hours, setHours] = React.useState("72");
  const [uses, setUses] = React.useState("");
  const [email, setEmail] = React.useState("");
  const refresh = () => qc.invalidateQueries({ queryKey: keys.group(g.id) });
  const run = async (fn: () => Promise<unknown>, ok: string) => {
    try {
      await fn();
      await refresh();
      toast(ok);
    } catch (e) {
      toast((e as Error).message, "error");
    }
  };
  return (
    <Card id="members">
      <CardHeader>
        <CardTitle>Members &amp; invitations</CardTitle>
        <CardDescription>Owners and admins manage the roster. Invite links expire automatically.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        <ul className="divide-y divide-border/60">
          {members.data?.map((m) => (
            <li key={m.user.id} className="flex flex-wrap items-center gap-3 py-2.5">
              <MemberAvatar user={m.user} size={30} />
              <span className="min-w-0 flex-1 truncate text-sm">
                {m.user.display_name} {m.user.id === myId ? <span className="text-xs text-muted-foreground">(you)</span> : null}
              </span>
              {isAdmin && m.role !== "owner" && m.user.id !== myId ? (
                <>
                  <Select className="h-8 w-28 text-xs" value={m.role} onChange={(e) => run(() => api(`/groups/${g.id}/members/${m.user.id}`, { method: "PATCH", json: { role: e.target.value } }), "Role updated")} aria-label={`Role for ${m.user.display_name}`}>
                    <option value="member">Member</option>
                    <option value="admin">Admin</option>
                    {g.my_role === "owner" ? <option value="owner">Make owner</option> : null}
                  </Select>
                  <Button size="icon" variant="ghost" aria-label={`Remove ${m.user.display_name}`} onClick={() => confirm(`Remove ${m.user.display_name} from the group?`) && run(() => api(`/groups/${g.id}/members/${m.user.id}`, { method: "DELETE" }), "Member removed")}>
                    <Trash2 className="text-red-300" />
                  </Button>
                </>
              ) : (
                <Badge variant={m.role === "member" ? "secondary" : "default"} className="capitalize">
                  {m.role}
                </Badge>
              )}
            </li>
          ))}
        </ul>
        {isAdmin ? (
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-lg border bg-background-2/50 p-4">
              <p className="mb-3 flex items-center gap-2 text-sm font-medium">
                <Link2 className="size-4 text-gold" /> Create invite link
              </p>
              <div className="flex flex-wrap items-end gap-2">
                <Field label="Expires in">
                  <Select value={hours} onChange={(e) => setHours(e.target.value)} className="w-32">
                    <option value="24">1 day</option>
                    <option value="72">3 days</option>
                    <option value="168">7 days</option>
                    <option value="720">30 days</option>
                  </Select>
                </Field>
                <Field label="Max uses">
                  <Input type="number" min={1} max={100} value={uses} onChange={(e) => setUses(e.target.value)} placeholder="∞" className="w-24" />
                </Field>
                <Button onClick={() => run(() => api(`/groups/${g.id}/invites`, { method: "POST", json: { expires_in_hours: Number(hours), max_uses: uses ? Number(uses) : null } }), "Invite created")} disabled={g.is_demo}>
                  Create
                </Button>
              </div>
              {g.is_demo ? <p className="mt-2 text-xs text-amber">Invites are disabled in the demo group.</p> : null}
            </div>
            <div className="rounded-lg border bg-background-2/50 p-4">
              <p className="mb-3 flex items-center gap-2 text-sm font-medium">
                <UserPlus className="size-4 text-gold" /> Add a registered friend by email
              </p>
              <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); run(() => api(`/groups/${g.id}/members`, { method: "POST", json: { email } }), "Member added").then(() => setEmail("")); }}>
                <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="friend@example.com" />
                <Button type="submit" variant="outline">
                  Add
                </Button>
              </form>
            </div>
          </div>
        ) : null}
        {isAdmin && invites.data?.length ? (
          <ul className="flex flex-col gap-2">
            {invites.data.map((i) => {
              const dead = !!i.revoked_at || new Date(i.expires_at) < new Date() || (i.max_uses != null && i.uses >= i.max_uses);
              return (
                <li key={i.id} className="flex flex-wrap items-center gap-2 rounded-lg border px-3 py-2 text-xs">
                  <code className="min-w-0 flex-1 truncate text-muted-foreground">{i.url}</code>
                  <span className="text-muted-foreground">
                    {i.uses}/{i.max_uses ?? "∞"} uses · {dead ? "inactive" : `expires ${fmtDateTime(i.expires_at)}`}
                  </span>
                  {!dead ? (
                    <>
                      <Button size="sm" variant="ghost" onClick={() => { navigator.clipboard?.writeText(i.url ?? ""); toast("Invite link copied"); }}>
                        <Copy /> Copy
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => run(() => api(`/groups/${g.id}/invites/${i.id}`, { method: "DELETE" }), "Invite revoked")}>
                        Revoke
                      </Button>
                    </>
                  ) : null}
                </li>
              );
            })}
          </ul>
        ) : null}
      </CardContent>
    </Card>
  );
}

function ItemRulesCard({ g, disabled }: { g: Group; disabled: boolean }) {
  const qc = useQueryClient();
  const toast = useToast();
  const rules = useQuery({ queryKey: keys.g(g.id, "item-rules"), queryFn: () => api<{ id: string; item_id: number; item_name: string; rule: string; note: string | null }[]>(`/groups/${g.id}/item-rules`) });
  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    try {
      await api(`/groups/${g.id}/item-rules`, { method: "POST", json: { item_id: Number(f.get("item_id")), item_name: f.get("item_name"), rule: f.get("rule"), note: f.get("note") || null } });
      form.reset();
      await qc.invalidateQueries({ queryKey: keys.g(g.id, "item-rules") });
    } catch (err) {
      toast((err as Error).message, "error");
    }
  };
  return (
    <Card>
      <CardHeader>
        <CardTitle>Favorite, wishlist &amp; excluded items</CardTitle>
        <CardDescription>Favorites and wishlist items are always recorded, regardless of quality. Excluded items never are.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {!disabled ? (
          <form onSubmit={submit} className="grid gap-2 sm:grid-cols-[110px_1fr_140px_1fr_auto]">
            <Input name="item_id" type="number" min={1} required placeholder="Item ID" aria-label="Item ID" />
            <Input name="item_name" required maxLength={160} placeholder="Item name" aria-label="Item name" />
            <Select name="rule" defaultValue="wishlist" aria-label="Rule">
              <option value="wishlist">Wishlist</option>
              <option value="favorite">Favorite</option>
              <option value="exclude">Exclude</option>
            </Select>
            <Input name="note" maxLength={280} placeholder="Note (optional)" aria-label="Note" />
            <Button type="submit" variant="outline">
              Add
            </Button>
          </form>
        ) : null}
        {rules.data?.length ? (
          <ul className="flex flex-col gap-1.5 text-sm">
            {rules.data.map((r) => (
              <li key={r.id} className="flex items-center gap-2 rounded-md border px-3 py-1.5">
                <Badge variant={r.rule === "exclude" ? "danger" : "default"} className="capitalize">
                  {r.rule}
                </Badge>
                <span className="flex-1 truncate">
                  {r.item_name} <span className="text-xs text-muted-foreground">#{r.item_id}</span>
                </span>
                {!disabled ? (
                  <Button size="sm" variant="ghost" onClick={async () => { await api(`/groups/${g.id}/item-rules/${r.id}`, { method: "DELETE" }); qc.invalidateQueries({ queryKey: keys.g(g.id, "item-rules") }); }}>
                    Remove
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No item rules yet.</p>
        )}
      </CardContent>
    </Card>
  );
}

function DangerZone({ g, myId }: { g: Group; myId?: string }) {
  const router = useRouter();
  const qc = useQueryClient();
  const toast = useToast();
  const leave = async () => {
    if (!myId || !confirm("Leave this group? Your past events stay in its history.")) return;
    try {
      await api(`/groups/${g.id}/members/${myId}`, { method: "DELETE" });
      await qc.invalidateQueries();
      router.replace("/");
    } catch (e) {
      toast((e as Error).message, "error");
    }
  };
  const del = async () => {
    if (prompt(`Type the group name to permanently delete it and all of its history:\n${g.name}`) !== g.name) return;
    await api(`/groups/${g.id}`, { method: "DELETE" });
    await qc.invalidateQueries();
    router.replace("/");
  };
  return (
    <Card className="border-destructive/30">
      <CardHeader>
        <CardTitle className="text-red-200">Danger zone</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-3">
        {g.my_role !== "owner" ? (
          <Button variant="outline" onClick={leave}>
            Leave group
          </Button>
        ) : (
          <Notice tone="warn">As the owner, transfer ownership (Members above) before leaving.</Notice>
        )}
        {g.my_role === "owner" && !g.is_demo ? (
          <Button variant="destructive" onClick={del}>
            <Trash2 /> Delete group
          </Button>
        ) : null}
      </CardContent>
    </Card>
  );
}
