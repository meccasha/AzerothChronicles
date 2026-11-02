"use client";

import { Users } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import * as React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AuthCard } from "../../auth-card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { useMe } from "@/lib/queries";

export default function InvitePage() {
  const { code } = useParams<{ code: string }>();
  const me = useMe();
  const router = useRouter();
  const qc = useQueryClient();
  const [error, setError] = React.useState<string | null>(null);
  const preview = useQuery({
    queryKey: ["invite", code],
    queryFn: () =>
      api<{ group_name: string; description: string | null; member_count: number | null; expires_at: string; valid: boolean }>(`/invites/${code}`),
    enabled: !!me.data,
  });

  React.useEffect(() => {
    if (me.data === null) router.replace(`/register?next=${encodeURIComponent(`/invite/${code}`)}`);
  }, [me.data, code, router]);

  const accept = async () => {
    try {
      const r = await api<{ group_id: string }>(`/invites/${code}/accept`, { method: "POST" });
      await qc.invalidateQueries();
      router.replace(`/g/${r.group_id}`);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  if (!me.data) return null;
  return (
    <AuthCard title="You're invited" subtitle="Join your friends' private adventure journal">
      {preview.isError ? (
        <p className="text-center text-sm text-red-300">This invite link is not valid.</p>
      ) : preview.data ? (
        <div className="flex flex-col items-center gap-4 text-center">
          <h2 className="text-xl">{preview.data.group_name}</h2>
          {preview.data.description ? <p className="text-sm text-muted-foreground">{preview.data.description}</p> : null}
          {preview.data.member_count != null ? (
            <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <Users className="size-4" /> {preview.data.member_count} members
            </p>
          ) : null}
          {preview.data.valid ? (
            <>
              <Button onClick={accept} className="w-full" disabled={me.data.is_demo}>
                Join group
              </Button>
              <p className="text-xs text-muted-foreground">Expires {fmtDateTime(preview.data.expires_at)}</p>
            </>
          ) : (
            <p className="text-sm text-red-300">This invite has expired or was revoked. Ask for a new link.</p>
          )}
          {me.data.is_demo ? <p className="text-xs text-amber">Sign out of the demo and create an account to join.</p> : null}
          {error ? <p className="text-sm text-red-300">{error}</p> : null}
        </div>
      ) : (
        <p className="text-center text-sm text-muted-foreground">Loading…</p>
      )}
    </AuthCard>
  );
}
