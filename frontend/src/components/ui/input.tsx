import * as React from "react";
import { cn } from "@/lib/utils";

export const fieldClass =
  "w-full min-w-0 rounded-md border border-input bg-background-2/80 px-3 py-1.5 text-sm text-foreground shadow-xs transition placeholder:text-muted-foreground/70 focus-visible:outline-none focus-visible:border-gold/60 focus-visible:ring-2 focus-visible:ring-gold/25 disabled:opacity-50 aria-invalid:border-destructive";

export function Input({ className, ...props }: React.ComponentProps<"input">) {
  return <input className={cn(fieldClass, "h-9", className)} {...props} />;
}

export function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return <textarea className={cn(fieldClass, "min-h-20 py-2", className)} {...props} />;
}

export function Label({ className, ...props }: React.ComponentProps<"label">) {
  return <label className={cn("text-xs font-medium uppercase tracking-wider text-muted-foreground", className)} {...props} />;
}

/** Native select styled to match (accessible on mobile, keyboard-friendly). */
export function Select({ className, children, ...props }: React.ComponentProps<"select">) {
  return (
    <select
      className={cn(
        fieldClass,
        "h-9 appearance-none bg-[url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2212%22 height=%2212%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%239aa3b4%22 stroke-width=%222%22><path d=%22m6 9 6 6 6-6%22/></svg>')] bg-[length:12px] bg-[right_0.6rem_center] bg-no-repeat pr-8",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
}

export function Field({ label, hint, children, htmlFor }: { label: string; hint?: string; children: React.ReactNode; htmlFor?: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}
