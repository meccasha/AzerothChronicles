"use client";

import { Plus } from "lucide-react";
import * as React from "react";
import { useToast } from "@/components/common/misc";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { useEventMutation, useMembers } from "@/lib/queries";
import type { AdventureEvent } from "@/lib/types";
import { cn } from "@/lib/utils";

function localNow(): string {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

export function ManualEventDialog({ groupId, trigger }: { groupId: string; trigger?: React.ReactNode }) {
  const [open, setOpen] = React.useState(false);
  const [type, setType] = React.useState("manual");
  const [who, setWho] = React.useState<string[]>([]);
  const [major, setMajor] = React.useState(false);
  const [file, setFile] = React.useState<File | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const members = useMembers(groupId);
  const toast = useToast();

  const create = useEventMutation(groupId, async (body: Record<string, unknown>) => {
    const ev = await api<AdventureEvent>(`/groups/${groupId}/events`, { method: "POST", json: body });
    if (file) {
      const fd = new FormData();
      fd.append("file", file);
      await api(`/groups/${groupId}/events/${ev.id}/media`, { method: "POST", body: fd });
    }
    return ev;
  });

  const submit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const local = String(f.get("occurred_at"));
    const body: Record<string, unknown> = {
      title: f.get("title"),
      description: f.get("description") ?? "",
      occurred_at: new Date(local).toISOString(),
      event_type: type,
      participant_user_ids: who,
      major,
    };
    for (const k of ["instance_name", "difficulty", "encounter_name", "item_name", "item_quality", "item_category"]) {
      const v = f.get(k);
      if (v) body[k] = v;
    }
    for (const k of ["achievement_id", "item_id"]) {
      const v = f.get(k);
      if (v) body[k] = Number(v);
    }
    setError(null);
    create.mutate(body, {
      onSuccess: () => {
        toast("Added to the chronicle");
        setOpen(false);
        setWho([]);
        setFile(null);
        setMajor(false);
      },
      onError: (err) => setError((err as Error).message),
    });
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button>
            <Plus /> Add memory
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Record a memory</DialogTitle>
          <DialogDescription>Manual entries are labelled as such and never counted as confirmed game data.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="grid gap-4">
          <Field label="Title" htmlFor="me-title">
            <Input id="me-title" name="title" required minLength={3} maxLength={200} placeholder="The night we finally downed…" />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Category" htmlFor="me-type">
              <Select id="me-type" value={type} onChange={(e) => setType(e.target.value)}>
                <option value="manual">Memory / story</option>
                <option value="milestone">Group milestone</option>
                <option value="boss_kill">Boss kill (unverified)</option>
                <option value="dungeon_complete">Dungeon run (unverified)</option>
                <option value="achievement">Achievement (unverified)</option>
                <option value="loot">Loot drop</option>
              </Select>
            </Field>
            <Field label="When" htmlFor="me-when">
              <Input id="me-when" name="occurred_at" type="datetime-local" required defaultValue={localNow()} max={localNow()} />
            </Field>
          </div>
          {type === "boss_kill" || type === "dungeon_complete" ? (
            <div className="grid gap-4 sm:grid-cols-3">
              {type === "boss_kill" ? (
                <Field label="Boss" htmlFor="me-enc">
                  <Input id="me-enc" name="encounter_name" maxLength={160} />
                </Field>
              ) : null}
              <Field label="Instance" htmlFor="me-inst">
                <Input id="me-inst" name="instance_name" maxLength={160} />
              </Field>
              <Field label="Difficulty" htmlFor="me-diff">
                <Input id="me-diff" name="difficulty" maxLength={32} placeholder="Heroic" />
              </Field>
            </div>
          ) : null}
          {type === "achievement" ? (
            <Field label="Achievement ID (optional)" htmlFor="me-ach" hint="Links to a known achievement if it is in our catalog.">
              <Input id="me-ach" name="achievement_id" type="number" min={1} />
            </Field>
          ) : null}
          {type === "loot" ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Item name" htmlFor="me-item">
                <Input id="me-item" name="item_name" required maxLength={200} />
              </Field>
              <Field label="Item ID (optional)" htmlFor="me-itemid">
                <Input id="me-itemid" name="item_id" type="number" min={1} />
              </Field>
              <Field label="Quality" htmlFor="me-q">
                <Select id="me-q" name="item_quality" defaultValue="epic">
                  <option value="epic">Epic</option>
                  <option value="legendary">Legendary</option>
                  <option value="rare">Rare</option>
                  <option value="unknown">Unknown</option>
                </Select>
              </Field>
              <Field label="Type" htmlFor="me-cat">
                <Select id="me-cat" name="item_category" defaultValue="gear">
                  <option value="gear">Gear</option>
                  <option value="mount">Mount</option>
                  <option value="pet">Pet</option>
                  <option value="toy">Toy</option>
                  <option value="collectible">Collectible</option>
                  <option value="other">Other</option>
                </Select>
              </Field>
            </div>
          ) : null}
          <Field label="Story" htmlFor="me-desc">
            <Textarea id="me-desc" name="description" maxLength={5000} placeholder="What happened? Who said what?" />
          </Field>
          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Who was there {type === "loot" ? "(first selected receives the item)" : ""}
            </span>
            <div className="flex flex-wrap gap-1.5">
              {members.data?.map((m) => {
                const on = who.includes(m.user.id);
                return (
                  <button
                    type="button"
                    key={m.user.id}
                    aria-pressed={on}
                    onClick={() => setWho((w) => (on ? w.filter((x) => x !== m.user.id) : [...w, m.user.id]))}
                    className={cn("rounded-full border px-3 py-1 text-xs transition cursor-pointer", on ? "border-gold/60 bg-gold/15 text-gold-bright" : "border-border text-muted-foreground hover:border-gold/30")}
                  >
                    {m.user.display_name}
                  </button>
                );
              })}
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Screenshot (optional)" htmlFor="me-file" hint="PNG, JPEG, WEBP or GIF up to 8 MB. Metadata is stripped.">
              <Input id="me-file" type="file" accept="image/png,image/jpeg,image/webp,image/gif" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="h-auto py-1.5 file:mr-3 file:rounded file:border-0 file:bg-secondary file:px-2 file:py-1 file:text-xs file:text-foreground" />
            </Field>
            <label className="flex items-center gap-3 self-end pb-2 text-sm">
              <Switch checked={major} onCheckedChange={setMajor} aria-label="Major moment" /> Major moment (always shown)
            </label>
          </div>
          {error ? <p role="alert" className="text-sm text-red-300">{error}</p> : null}
          <DialogFooter>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Saving…" : "Add to timeline"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
