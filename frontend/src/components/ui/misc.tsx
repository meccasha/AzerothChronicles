"use client";

import { Switch as S, Tooltip as T } from "radix-ui";
import * as React from "react";
import { cn } from "@/lib/utils";

export function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("animate-pulse rounded-md bg-muted/70", className)} {...props} />;
}

export function Switch({ className, ...props }: React.ComponentProps<typeof S.Root>) {
  return (
    <S.Root
      className={cn(
        "peer inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border border-border bg-secondary transition data-[state=checked]:border-gold/60 data-[state=checked]:bg-gold/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/40 disabled:opacity-50",
        className,
      )}
      {...props}
    >
      <S.Thumb className="block size-4 translate-x-0.5 rounded-full bg-foreground shadow transition data-[state=checked]:translate-x-[18px]" />
    </S.Root>
  );
}

export const TooltipProvider = T.Provider;

export function Tip({ content, children }: { content: React.ReactNode; children: React.ReactNode }) {
  return (
    <T.Root>
        <T.Trigger asChild>{children}</T.Trigger>
        <T.Portal>
          <T.Content
            sideOffset={6}
            className="z-50 max-w-xs rounded-md border border-gold/25 bg-popover px-2.5 py-1.5 text-xs text-popover-foreground shadow-lg animate-in fade-in-0 zoom-in-95"
          >
            {content}
            <T.Arrow className="fill-popover" />
          </T.Content>
        </T.Portal>
      </T.Root>
  );
}

export function Separator({ className }: { className?: string }) {
  return <div role="separator" className={cn("h-px w-full bg-border", className)} />;
}
