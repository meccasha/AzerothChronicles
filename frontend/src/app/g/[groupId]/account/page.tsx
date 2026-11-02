"use client";

import { Download, Plus, Star, Trash2, UserCog } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { CharacterName, CharacterPortrait } from "@/components/common/avatar";
import { Notice, PageHeader, useToast } from "@/components/common/misc";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/input";
import { api } from "@/lib/api";
import { fmtRelative } from "@/lib/format";
import { useMe, useMyCharacters } from "@/lib/queries";
import { CLASS_COLORS, VERIFICATION_LABEL } from "@/lib/wow";

export default function AccountPage() {
  const me = useMe();
  const chars = useMyCharacters();
  const qc = useQueryClient();
  const router = useRouter();
  const toast = useToast();
  const refresh = () => qc.invalidateQueries();

  const addChar = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const f = Object.fromEntries(new FormData(form).entries());
    try {
      await api("/me/characters", { method: "POST", json: { ...f, level: f.level ? Number(f.level) : null, faction: f.faction || null, character_class: f.character_class || null } });
      form.reset();
      refresh();
      toast("Character added");
    } catch (err) {
      toast((err as Error).message, "error");
    }
  };
  const exportData = async () => {
    const data = await api<unknown>("/me/export");
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "azeroth-chronicles-export.json";
    a.click();
  };
  const deleteAccount = async () => {
    const pw = me.data?.is_demo ? null : prompt("Enter your password to permanently delete your account and personal data:");
    if (!me.data?.is_demo && !pw) return;
    try {
      await api("/me", { method: "DELETE", json: { confirm: "DELETE", password: pw } });
      qc.clear();
      router.replace("/");
    } catch (e) {
      toast((e as Error).message, "error");
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <PageHeader icon={UserCog} title="Your account" subtitle={me.data ? `${me.data.display_name} · ${me.data.email}` : undefined} />
      <Card>
        <CardHeader>
          <CardTitle>Your characters</CardTitle>
          <CardDescription>
            Characters are shared with every group you belong to. Prefer <Link className="text-gold hover:underline" href="../integrations">Battle.net linking</Link> for verified ownership; manual characters are labelled unverified.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <ul className="grid gap-2 md:grid-cols-2">
            {chars.data?.map((c) => (
              <li key={c.id} className="flex items-center gap-3 rounded-lg border bg-background-2/50 p-3">
                <CharacterPortrait character={c} size={40} />
                <div className="min-w-0 flex-1">
                  <p className="truncate">
                    <CharacterName character={c} /> <span className="text-xs text-muted-foreground">{c.realm_name}-{c.region.toUpperCase()}</span>
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {c.last_synced_at ? `synced ${fmtRelative(c.last_synced_at)}` : "not synced"} {c.last_sync_error ? <span className="text-red-300">· {c.last_sync_error}</span> : null}
                  </p>
                </div>
                <Badge variant={VERIFICATION_LABEL[c.verification]!.variant}>{VERIFICATION_LABEL[c.verification]!.label}</Badge>
                <Button size="icon" variant="ghost" aria-label={c.is_main ? "Main character" : "Make main"} onClick={async () => { await api(`/me/characters/${c.id}`, { method: "PATCH", json: { is_main: true } }); refresh(); }}>
                  <Star className={c.is_main ? "fill-gold text-gold" : ""} />
                </Button>
                <Button size="icon" variant="ghost" aria-label={`Remove ${c.name}`} onClick={async () => { if (confirm(`Remove ${c.name}? Past events keep you as a participant.`)) { await api(`/me/characters/${c.id}`, { method: "DELETE" }); refresh(); } }}>
                  <Trash2 className="text-red-300" />
                </Button>
              </li>
            ))}
          </ul>
          <form onSubmit={addChar} className="grid gap-3 rounded-lg border border-dashed p-4 sm:grid-cols-3 lg:grid-cols-6">
            <Field label="Name">
              <Input name="name" required minLength={2} maxLength={12} />
            </Field>
            <Field label="Realm">
              <Input name="realm" required maxLength={64} />
            </Field>
            <Field label="Region">
              <Select name="region" defaultValue="us">
                <option value="us">US</option>
                <option value="eu">EU</option>
                <option value="kr">KR</option>
                <option value="tw">TW</option>
              </Select>
            </Field>
            <Field label="Class">
              <Select name="character_class" defaultValue="">
                <option value="">—</option>
                {Object.keys(CLASS_COLORS).map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </Select>
            </Field>
            <Field label="Faction">
              <Select name="faction" defaultValue="">
                <option value="">—</option>
                <option>Alliance</option>
                <option>Horde</option>
              </Select>
            </Field>
            <div className="flex items-end gap-2">
              <Field label="Level">
                <Input name="level" type="number" min={1} max={90} />
              </Field>
              <Button type="submit" variant="outline" disabled={me.data?.is_demo} aria-label="Add character">
                <Plus />
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Your data</CardTitle>
          <CardDescription>
            Download everything we hold about you, or delete your account. See the <Link className="text-gold hover:underline" href="/privacy">privacy policy</Link>.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          <Button variant="outline" onClick={exportData}>
            <Download /> Export my data
          </Button>
          <Button variant="destructive" onClick={deleteAccount}>
            <Trash2 /> Delete my account
          </Button>
          <Notice className="w-full">Deleting your account removes your profile, characters, comments, reactions, tokens and Battle.net link. Groups you own pass to the next admin; empty groups are deleted.</Notice>
        </CardContent>
      </Card>
    </div>
  );
}
