"use client";

import { useRouter, useSearchParams } from "next/navigation";
import * as React from "react";
import { useGroups } from "@/lib/queries";

/** OAuth callbacks land here; forward to the integrations page of the last-used group. */
function Forward() {
  const router = useRouter();
  const params = useSearchParams();
  const groups = useGroups();
  React.useEffect(() => {
    if (!groups.data) return;
    let last: string | null = null;
    try {
      last = localStorage.getItem("ac:lastGroup");
    } catch {
      /* ignore */
    }
    const g = groups.data.find((x) => x.id === last) ?? groups.data[0];
    router.replace(g ? `/g/${g.id}/integrations?${params.toString()}` : "/groups/new");
  }, [groups.data, params, router]);
  return null;
}

export default function IntegrationsRedirect() {
  return (
    <React.Suspense>
      <Forward />
    </React.Suspense>
  );
}
