"use client";

import { Tabs as T } from "radix-ui";
import * as React from "react";
import { cn } from "@/lib/utils";

export const Tabs = T.Root;
export function TabsList({ className, ...props }: React.ComponentProps<typeof T.List>) {
  return (
    <T.List
      className={cn("inline-flex h-9 max-w-full items-center gap-1 overflow-x-auto rounded-lg border bg-card/70 p-1", className)}
      {...props}
    />
  );
}
export function TabsTrigger({ className, ...props }: React.ComponentProps<typeof T.Trigger>) {
  return (
    <T.Trigger
      className={cn(
        "inline-flex h-7 items-center gap-1.5 whitespace-nowrap rounded-md px-3 text-xs font-medium text-muted-foreground transition hover:text-foreground data-[state=active]:bg-gold/15 data-[state=active]:text-gold-bright data-[state=active]:shadow-[inset_0_0_0_1px_rgb(214_169_74/0.35)] cursor-pointer",
        className,
      )}
      {...props}
    />
  );
}
export const TabsContent = T.Content;
