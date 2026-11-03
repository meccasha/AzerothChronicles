"use client";

import { ArrowLeft, Clock, EyeOff, Eye, ImagePlus, MapPin, Pencil, Pin, Shield, Sparkles, Star, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import * as React from "react";
import { CharacterName, CharacterPortrait, MemberAvatar } from "@/components/common/avatar";
import { ProvenanceBadges } from "@/components/common/badges";
import { GameImage } from "@/components/common/game-image";
import { ErrorState, useToast } from "@/components/common/misc";
import { eventSubtitle } from "@/components/timeline/event-card";
import { EventArt } from "@/components/timeline/event-art";
import { EVENT_ACCENT } from "@/components/timeline/event-meta";
import { Reactions } from "@/components/timeline/reactions";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { Skeleton, Tip } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { fmtDateTime, fmtRelative } from "@/lib/format";
import { useComments, useEvent, useEventMutation, useGroup } from "@/lib/queries";
import { cn } from "@/lib/utils";
import { CONFIRMATION_LABEL, EVENT_TYPE_LABEL, HIGHLIGHT_LABEL, MAJOR_HIGHLIGHTS, QUALITY_LABEL, qualityColor, SOURCE_LABEL } from "@/lib/wow";

export default function EventDetailPage() {
  const { groupId, eventId } = useParams<{ groupId: string; eventId: string }>();
  const ev = useEvent(groupId, eventId);
  const group = useGroup(groupId);
  const isAdmin = group.data?.my_role === "owner" || group.data?.my_role === "admin";
  const router = useRouter();
  const toast = useToast();
  const base = `/groups/${groupId}/events/${eventId}`;
  const patch = useEventMutation(groupId, (body: Record<string, unknown>) => api(base, { method: "PATCH", json: body }));
  const fav = useEventMutation(groupId, (on: boolean) => api(`${base}/favorite`, { method: on ? "PUT" : "DELETE" }));
  const del = useEventMutation(groupId, () => api(base, { method: "DELETE" }));
  const upload = useEventMutation(groupId, (fd: FormData) => api(`${base}/media`, { method: "POST", body: fd }));
  const [editing, setEditing] = React.useState(false);

  if (ev.isError) return <ErrorState error={ev.error} />;
  if (!ev.data) return <Skeleton className="h-96 rounded-xl" />;
  const e = ev.data;
  const accent = e.event_type === "loot" && e.extra.quality ? qualityColor(e.extra.quality) : EVENT_ACCENT[e.event_type];
  const special = !!e.highlight && MAJOR_HIGHLIGHTS.has(e.highlight);

  const onUpload = (f: File | undefined) => {
    if (!f) return;
    const fd = new FormData();
    fd.append("file", f);
    upload.mutate(fd, { onSuccess: () => toast("Screenshot added"), onError: (err) => toast((err as Error).message, "error") });
  };

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <Link href={`/g/${groupId}/timeline`} className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-gold">
        <ArrowLeft className="size-4" /> Back to the timeline
      </Link>

      <Card className={cn("overflow-hidden", special && "border-gold/50 glow")}>
        {special ? (
          <div className="flex items-center gap-2 border-b border-gold/30 bg-gradient-to-r from-gold/25 via-gold/5 to-transparent px-6 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-gold-bright">
            <Sparkles className="size-4" /> {e.extra.milestone ?? HIGHLIGHT_LABEL[e.highlight!]}
          </div>
        ) : null}
        {e.scene_url ? (
          <div className="relative h-36 overflow-hidden sm:h-44" aria-hidden>
            <GameImage src={e.scene_url} className="size-full object-cover" />
            <div className="absolute inset-0 bg-gradient-to-t from-card via-card/40 to-transparent" />
          </div>
        ) : null}
        <div className={cn("flex flex-col gap-5 p-6 sm:flex-row", e.scene_url && "-mt-14 relative")}>
          <EventArt event={e} size={88} />
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold uppercase tracking-[0.18em]" style={{ color: accent }}>
              {EVENT_TYPE_LABEL[e.event_type]}
              {e.event_type === "loot" && e.extra.quality ? ` · ${QUALITY_LABEL[String(e.extra.quality)] ?? ""}` : ""}
            </p>
            {editing ? (
              <EditForm
                title={e.title}
                description={e.description}
                busy={patch.isPending}
                onCancel={() => setEditing(false)}
                onSave={(title, description) => patch.mutate({ title, description }, { onSuccess: () => setEditing(false), onError: (err) => toast((err as Error).message, "error") })}
              />
            ) : (
              <>
                <h1 className="mt-1 text-2xl font-bold sm:text-3xl" style={e.event_type === "loot" ? { color: accent } : undefined}>
                  {e.title}
                </h1>
                {eventSubtitle(e) ? <p className="mt-1 text-muted-foreground">{eventSubtitle(e)}</p> : null}
                {e.description ? <p className="mt-4 whitespace-pre-line text-foreground/90">{e.description}</p> : null}
              </>
            )}
            <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <Clock className="size-4 text-gold" />
                <time dateTime={e.occurred_at}>{fmtDateTime(e.occurred_at)}</time>
                {e.time_precision === "observed" ? <span className="text-amber">(observed, not completion time)</span> : null}
              </span>
              {e.instance_name && e.event_type !== "boss_kill" ? (
                <span className="flex items-center gap-1.5">
                  <MapPin className="size-4 text-gold" /> {e.instance_name}
                </span>
              ) : null}
              {e.extra.encounter_name ? <span>Boss: {e.extra.encounter_name}</span> : null}
              {e.achievement ? <span>Achievement #{e.achievement.id}</span> : null}
              {e.item ? <span>Item #{e.item.id}</span> : null}
              {e.encounter ? <span>Encounter #{e.encounter.id}</span> : null}
            </div>
            <div className="mt-4">
              <ProvenanceBadges event={e} />
            </div>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t px-6 py-3">
          <Reactions groupId={groupId} event={e} />
          <div className="flex flex-wrap gap-1.5">
            <Button size="sm" variant="ghost" onClick={() => fav.mutate(!e.favorite)} aria-pressed={e.favorite}>
              <Star className={cn(e.favorite && "fill-gold text-gold")} /> {e.favorite ? "Favorited" : "Favorite"}
            </Button>
            <label className="inline-flex">
              <input type="file" accept="image/png,image/jpeg,image/webp,image/gif" className="sr-only" onChange={(ev2) => onUpload(ev2.target.files?.[0])} />
              <span className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-md px-3 text-xs hover:bg-accent/70">
                <ImagePlus className="size-4" /> {upload.isPending ? "Uploading…" : "Add screenshot"}
              </span>
            </label>
            {e.can_edit ? (
              <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
                <Pencil /> Edit
              </Button>
            ) : null}
            {e.can_moderate ? (
              <AdminActions
                e={e}
                isAdmin={isAdmin}
                onPin={() => patch.mutate({ pinned: !e.pinned }, { onError: (err) => toast((err as Error).message, "error") })}
                onHide={() => patch.mutate({ hidden: !e.hidden }, { onError: (err) => toast((err as Error).message, "error") })}
                onDelete={() => {
                  if (!confirm("Delete this event from the timeline? This cannot be undone.")) return;
                  del.mutate(undefined, { onSuccess: () => router.replace(`/g/${groupId}/timeline`) });
                }}
              />
            ) : null}
          </div>
        </div>
      </Card>

      {e.media.length ? (
        <section className="grid gap-3 sm:grid-cols-2">
          {e.media.map((m) => (
            <figure key={m.id} className="overflow-hidden rounded-xl border bg-card">
              <a href={m.url} target="_blank" rel="noreferrer">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={m.url} alt={m.caption ?? "Screenshot"} className="w-full object-cover" />
              </a>
              {m.caption ? <figcaption className="px-3 py-2 text-xs text-muted-foreground">{m.caption}</figcaption> : null}
            </figure>
          ))}
        </section>
      ) : null}

      <div className="grid gap-6 md:grid-cols-[1fr_320px]">
        <Comments groupId={groupId} eventId={eventId} />
        <Card>
          <CardHeader>
            <CardTitle>Participants</CardTitle>
          </CardHeader>
          <CardContent>
            {e.participants.length ? (
              <ul className="flex flex-col gap-3">
                {e.participants.map((p) => (
                  <li key={p.user.id} className="flex items-center gap-3">
                    {p.character ? <CharacterPortrait character={p.character} size={34} /> : <MemberAvatar user={p.user} size={34} />}
                    <span className="min-w-0 flex-1">
                      <Link href={`/g/${groupId}/members/${p.user.id}`} className="block truncate text-sm hover:text-gold">
                        {p.user.display_name}
                      </Link>
                      {p.character ? <CharacterName character={p.character} className="text-xs" /> : null}
                    </span>
                    <Tip content={CONFIRMATION_LABEL[p.confirmation]}>
                      <span>
                        <Badge variant={p.confirmation === "confirmed" ? "success" : p.confirmation === "roster" ? "info" : "secondary"}>{p.confirmation}</Badge>
                      </span>
                    </Tip>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">No participants recorded.</p>
            )}
            <div className="mt-5 border-t pt-4 text-xs text-muted-foreground">
              <p className="flex items-center gap-1.5 font-medium text-foreground/80">
                <Shield className="size-3.5 text-gold" /> Provenance
              </p>
              <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
                <dt>Source</dt>
                <dd>{SOURCE_LABEL[e.source] ?? e.source}</dd>
                <dt>Capture</dt>
                <dd>{e.provenance === "backfill" ? "Historical import" : e.provenance === "manual" ? "Manual" : "Live capture"}</dd>
                <dt>Confidence</dt>
                <dd>{e.confidence}</dd>
                <dt>Event ID</dt>
                <dd className="truncate font-mono text-[10px]">{e.id}</dd>
              </dl>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function AdminActions({ e, isAdmin, onPin, onHide, onDelete }: { e: { pinned: boolean; hidden: boolean }; isAdmin: boolean; onPin: () => void; onHide: () => void; onDelete: () => void }) {
  return (
    <>
      {isAdmin ? (
        <>
          <Button size="sm" variant="ghost" onClick={onPin}>
            <Pin /> {e.pinned ? "Unpin" : "Pin"}
          </Button>
          <Button size="sm" variant="ghost" onClick={onHide}>
            {e.hidden ? <Eye /> : <EyeOff />} {e.hidden ? "Unhide" : "Hide"}
          </Button>
        </>
      ) : null}
      <Button size="sm" variant="ghost" onClick={onDelete} className="text-red-300 hover:text-red-200">
        <Trash2 /> Delete
      </Button>
    </>
  );
}

function EditForm({ title, description, onSave, onCancel, busy }: { title: string; description: string; onSave: (t: string, d: string) => void; onCancel: () => void; busy: boolean }) {
  const [t, setT] = React.useState(title);
  const [d, setD] = React.useState(description);
  return (
    <div className="mt-2 flex flex-col gap-2">
      <Input value={t} onChange={(x) => setT(x.target.value)} aria-label="Title" />
      <Textarea value={d} onChange={(x) => setD(x.target.value)} aria-label="Description" rows={5} />
      <div className="flex gap-2">
        <Button size="sm" onClick={() => onSave(t, d)} disabled={busy}>
          Save
        </Button>
        <Button size="sm" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

function Comments({ groupId, eventId }: { groupId: string; eventId: string }) {
  const comments = useComments(groupId, eventId);
  const [body, setBody] = React.useState("");
  const add = useEventMutation(groupId, (text: string) => api(`/groups/${groupId}/events/${eventId}/comments`, { method: "POST", json: { body: text } }));
  const remove = useEventMutation(groupId, (id: string) => api(`/groups/${groupId}/events/${eventId}/comments/${id}`, { method: "DELETE" }));
  return (
    <Card>
      <CardHeader>
        <CardTitle>Comments</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {comments.data?.length ? (
          <ul className="flex flex-col gap-4">
            {comments.data.map((c) => (
              <li key={c.id} className="flex gap-3">
                <MemberAvatar user={c.user} size={30} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm">
                    <span className="font-medium">{c.user.display_name}</span> <span className="text-xs text-muted-foreground">{fmtRelative(c.created_at)}</span>
                  </p>
                  <p className="whitespace-pre-line break-words text-sm text-foreground/90">{c.body}</p>
                </div>
                {c.can_delete ? (
                  <button className="self-start rounded p-1 text-muted-foreground hover:text-red-300" onClick={() => remove.mutate(c.id)} aria-label="Delete comment">
                    <Trash2 className="size-3.5" />
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No comments yet. Say something nice (or roast the tank).</p>
        )}
        <form
          className="flex flex-col gap-2"
          onSubmit={(ev) => {
            ev.preventDefault();
            if (!body.trim()) return;
            add.mutate(body, { onSuccess: () => setBody("") });
          }}
        >
          <Textarea value={body} onChange={(e) => setBody(e.target.value)} placeholder="Add a comment…" maxLength={2000} rows={2} aria-label="New comment" />
          <Button type="submit" size="sm" className="self-end" disabled={add.isPending || !body.trim()}>
            Post comment
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
