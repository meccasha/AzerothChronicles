"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AuthCard } from "../../auth-card";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { Group } from "@/lib/types";
import { useGroups, useMe } from "@/lib/queries";

export default function NewGroupPage() {
  const me = useMe();
  const groups = useGroups(!!me.data);
  const router = useRouter();
  const qc = useQueryClient();
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (me.data === null) router.replace("/login?next=/groups/new");
  }, [me.data, router]);

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const g = await api<Group>("/groups", {
        method: "POST",
        json: { name: f.get("name"), description: f.get("description") ?? "" },
      });
      await qc.invalidateQueries({ queryKey: ["groups"] });
      router.push(`/g/${g.id}`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };
  if (!me.data) return null;
  return (
    <AuthCard title="Found a new group" subtitle="Groups are private and independent of in-game guilds.">
      {me.data.is_demo ? (
        <p className="text-center text-sm text-amber">The demo visitor cannot create groups. Sign out and register a free account.</p>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-4">
          <Field label="Group name" htmlFor="name">
            <Input id="name" name="name" minLength={3} maxLength={80} required placeholder="The Tuesday Night Wayfarers" />
          </Field>
          <Field label="Description" htmlFor="description">
            <Textarea id="description" name="description" maxLength={2000} placeholder="Who you are and what you're chasing together." />
          </Field>
          {error ? <p role="alert" className="text-sm text-red-300">{error}</p> : null}
          <Button type="submit" disabled={busy}>
            {busy ? "Creating…" : "Create group"}
          </Button>
        </form>
      )}
      {groups.data?.length ? (
        <div className="mt-6 border-t pt-4 text-sm">
          <p className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">Or open one of your groups</p>
          <ul className="flex flex-col gap-1">
            {groups.data.map((g) => (
              <li key={g.id}>
                <Link href={`/g/${g.id}`} className="text-gold hover:underline">
                  {g.name}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="mt-6 text-center text-xs text-muted-foreground">Got an invite link from a friend? Just open it to join their group.</p>
      )}
    </AuthCard>
  );
}
