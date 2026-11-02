"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AuthCard } from "../auth-card";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { keys } from "@/lib/queries";

function RegisterForm() {
  const router = useRouter();
  const params = useSearchParams();
  const qc = useQueryClient();
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      await api("/auth/register", {
        method: "POST",
        json: { email: f.get("email"), display_name: f.get("display_name"), password: f.get("password") },
      });
      qc.clear();
      await qc.invalidateQueries({ queryKey: keys.me });
      const next = params.get("next");
      router.replace(next && next.startsWith("/") && !next.startsWith("//") ? next : "/groups/new");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <AuthCard title="Begin your chronicle" subtitle="We never ask for your Battle.net password.">
      <form onSubmit={submit} className="flex flex-col gap-4">
        <Field label="Display name" htmlFor="display_name" hint="How your friends will see you.">
          <Input id="display_name" name="display_name" minLength={2} maxLength={40} required />
        </Field>
        <Field label="Email" htmlFor="email">
          <Input id="email" name="email" type="email" autoComplete="email" required />
        </Field>
        <Field label="Password" htmlFor="password" hint="At least 10 characters.">
          <Input id="password" name="password" type="password" minLength={10} autoComplete="new-password" required />
        </Field>
        {error ? <p role="alert" className="text-sm text-red-300">{error}</p> : null}
        <Button type="submit" disabled={busy} className="mt-2">
          {busy ? "Creating…" : "Create account"}
        </Button>
        <p className="text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link className="text-gold hover:underline" href="/login">
            Sign in
          </Link>
        </p>
      </form>
    </AuthCard>
  );
}

export default function RegisterPage() {
  return (
    <React.Suspense>
      <RegisterForm />
    </React.Suspense>
  );
}
