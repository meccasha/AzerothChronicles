"use client";

import { AlertTriangle, Info, type LucideIcon } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/utils";
import { fmtNumber } from "@/lib/format";
import { Button } from "@/components/ui/button";

export function PageHeader({ title, subtitle, actions, icon: Icon }: { title: string; subtitle?: React.ReactNode; actions?: React.ReactNode; icon?: LucideIcon }) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="flex items-center gap-3 text-2xl font-bold sm:text-3xl">
          {Icon ? <Icon className="size-7 shrink-0 text-gold" aria-hidden /> : null}
          <span className="gold-text">{title}</span>
        </h1>
        {subtitle ? <p className="mt-1.5 max-w-2xl text-sm text-muted-foreground">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function StatTile({ label, value, hint, icon: Icon, accent, className }: { label: string; value: number | string; hint?: string; icon?: LucideIcon; accent?: string; className?: string }) {
  return (
    <div className={cn("relative overflow-hidden rounded-xl border bg-card/80 p-4 parchment", className)}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">{label}</span>
        {Icon ? <Icon className="size-4 text-gold/80" style={accent ? { color: accent } : undefined} aria-hidden /> : null}
      </div>
      <div className="mt-2 font-display text-3xl font-bold tabular-nums text-foreground">{typeof value === "number" ? fmtNumber(value) : value}</div>
      {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

export function EmptyState({ icon: Icon, title, children, action }: { icon: LucideIcon; title: string; children?: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-gold/25 bg-card/40 px-6 py-12 text-center">
      <span className="flex size-12 items-center justify-center rounded-full bg-gold/10 text-gold">
        <Icon className="size-6" aria-hidden />
      </span>
      <h3 className="font-display text-lg">{title}</h3>
      {children ? <div className="max-w-md text-sm text-muted-foreground">{children}</div> : null}
      {action}
    </div>
  );
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const msg = error instanceof Error ? error.message : "Something went wrong";
  return (
    <div role="alert" className="flex items-start gap-3 rounded-xl border border-destructive/40 bg-destructive/10 p-4 text-sm">
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-red-300" />
      <div className="flex-1">
        <p className="font-medium text-red-200">Could not load this section</p>
        <p className="text-red-200/80">{msg}</p>
      </div>
      {retry ? (
        <Button size="sm" variant="outline" onClick={retry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}

export function Notice({ children, tone = "info", className }: { children: React.ReactNode; tone?: "info" | "warn"; className?: string }) {
  return (
    <div className={cn("flex items-start gap-2.5 rounded-lg border px-3.5 py-2.5 text-xs leading-relaxed", tone === "warn" ? "border-amber/30 bg-amber/5 text-amber/90" : "border-sky-500/25 bg-sky-500/5 text-sky-200/90", className)}>
      {tone === "warn" ? <AlertTriangle className="mt-0.5 size-3.5 shrink-0" /> : <Info className="mt-0.5 size-3.5 shrink-0" />}
      <div>{children}</div>
    </div>
  );
}

// ---------------------------------------------------------------- toasts
type Toast = { id: number; title: string; tone: "ok" | "error" };
const ToastCtx = React.createContext<(title: string, tone?: "ok" | "error") => void>(() => {});
export const useToast = () => React.useContext(ToastCtx);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<Toast[]>([]);
  const push = React.useCallback((title: string, tone: "ok" | "error" = "ok") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, title, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4200);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-4 z-[60] flex flex-col items-center gap-2 px-4 sm:items-end sm:pr-6">
        {toasts.map((t) => (
          <div key={t.id} className={cn("pointer-events-auto animate-rise rounded-lg border px-4 py-2.5 text-sm shadow-xl backdrop-blur", t.tone === "error" ? "border-destructive/50 bg-[#2a1416]/95 text-red-100" : "border-gold/40 bg-popover/95 text-foreground")}>
            {t.title}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
