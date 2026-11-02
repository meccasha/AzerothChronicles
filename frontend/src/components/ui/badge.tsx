import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium leading-4 whitespace-nowrap [&_svg]:size-3",
  {
    variants: {
      variant: {
        default: "border-gold/40 bg-gold/10 text-gold-bright",
        secondary: "border-border bg-secondary text-secondary-foreground",
        outline: "border-border text-muted-foreground",
        warning: "border-amber/40 bg-amber/10 text-amber",
        danger: "border-destructive/40 bg-destructive/10 text-red-300",
        success: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
        info: "border-sky-500/40 bg-sky-500/10 text-sky-300",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export function Badge({ className, variant, ...props }: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
