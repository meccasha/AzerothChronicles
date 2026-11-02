"use client";

import { useRouter } from "next/navigation";
import * as React from "react";
import { useGroups, useMe } from "@/lib/queries";

export default function AccountRedirect() {
  const router = useRouter();
  const me = useMe();
  const groups = useGroups(!!me.data);
  React.useEffect(() => {
    if (me.data === null) return router.replace("/login?next=/account");
    if (!groups.data) return;
    let last: string | null = null;
    try {
      last = localStorage.getItem("ac:lastGroup");
    } catch {
      /* ignore */
    }
    const g = groups.data.find((x) => x.id === last) ?? groups.data[0];
    router.replace(g ? `/g/${g.id}/account` : "/groups/new");
  }, [me.data, groups.data, router]);
  return null;
}
