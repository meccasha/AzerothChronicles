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

function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
}

function LoginForm() {
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
      await api("/auth/login", { method: "POST", json: { email: f.get("email"), password: f.get("password") } });
      qc.clear();
      await qc.invalidateQueries({ queryKey: keys.me });
      router.replace(safeNext(params.get("next")));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <AuthCard title="Welcome back" subtitle="Sign in to continue your chronicle">
      <form onSubmit={submit} className="flex flex-col gap-4">
        <Field label="Email" htmlFor="email">
          <Input id="email" name="email" type="email" autoComplete="email" required />
        </Field>
        <Field label="Password" htmlFor="password">
          <Input id="password" name="password" type="password" autoComplete="current-password" required />
        </Field>
        {error ? <p role="alert" className="text-sm text-red-300">{error}</p> : null}
        <Button type="submit" disabled={busy} className="mt-2">
          {busy ? "Signing in…" : "Sign in"}
        </Button>
        <p className="text-center text-sm text-muted-foreground">
          New here?{" "}
          <Link className="text-gold hover:underline" href={`/register${params.get("next") ? `?next=${encodeURIComponent(params.get("next")!)}` : ""}`}>
            Create an account
          </Link>
        </p>
      </form>
    </AuthCard>
  );
}

export default function LoginPage() {
  return (
    <React.Suspense>
      <LoginForm />
    </React.Suspense>
  );
}
