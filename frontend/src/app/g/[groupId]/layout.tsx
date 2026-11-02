"use client";

import { useParams } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";

export default function GroupLayout({ children }: { children: React.ReactNode }) {
  const { groupId } = useParams<{ groupId: string }>();
  return <AppShell groupId={groupId}>{children}</AppShell>;
}
