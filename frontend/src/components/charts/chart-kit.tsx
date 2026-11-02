"use client";

import { Table2, BarChart3 } from "lucide-react";
import * as React from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/** Categorical slots validated (dataviz validator, dark mode, surface #141925). Color follows the entity. */
export const SERIES_HEX = {
  boss_kills: "#3987e5",
  achievements: "#d95926",
  loot: "#199e70",
  dungeons: "#c98500",
  wipes: "#d55181",
} as const;
export const SINGLE_HUE = "#3987e5";
export const SURFACE = "#141925";
export const AXIS = { stroke: "#2a3142", tick: { fill: "#9aa3b4", fontSize: 11 } } as const;
export const GRID = "#1f2635";

export type SeriesDef = { key: string; label: string; color: string };

/** Tooltip: value leads (strong), series label follows; short line keys instead of boxes. */
export function ChartTooltip({ active, payload, label, labelFormatter }: { active?: boolean; payload?: { dataKey?: string | number; value?: number; color?: string; name?: string }[]; label?: string | number; labelFormatter?: (l: string) => string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="min-w-36 rounded-lg border border-gold/25 bg-popover/95 px-3 py-2 text-xs shadow-xl backdrop-blur">
      <p className="mb-1.5 text-muted-foreground">{labelFormatter ? labelFormatter(String(label)) : label}</p>
      <ul className="flex flex-col gap-1">
        {payload.map((p) => (
          <li key={String(p.dataKey)} className="flex items-center gap-2">
            <span className="h-0.5 w-3 rounded" style={{ background: p.color }} aria-hidden />
            <span className="font-semibold tabular-nums text-foreground">{p.value}</span>
            <span className="text-muted-foreground">{p.name}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function Legend({ series }: { series: SeriesDef[] }) {
  if (series.length < 2) return null;
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
      {series.map((s) => (
        <li key={s.key} className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-[3px]" style={{ background: s.color }} aria-hidden />
          {s.label}
        </li>
      ))}
    </ul>
  );
}

/** Card with a chart/table toggle so every value is reachable without hovering. */
export function ChartCard({
  title,
  description,
  series,
  rows,
  columns,
  children,
  fetching,
  className,
}: {
  title: string;
  description?: string;
  series?: SeriesDef[];
  rows: Record<string, unknown>[];
  columns: { key: string; label: string; format?: (v: unknown) => string }[];
  children: React.ReactNode;
  fetching?: boolean;
  className?: string;
}) {
  const [table, setTable] = React.useState(false);
  return (
    <Card className={className}>
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div>
          <CardTitle>{title}</CardTitle>
          {description ? <CardDescription>{description}</CardDescription> : null}
        </div>
        <button
          onClick={() => setTable((t) => !t)}
          className="rounded-md border p-1.5 text-muted-foreground transition hover:border-gold/40 hover:text-foreground cursor-pointer"
          aria-label={table ? "Show chart" : "Show data table"}
          title={table ? "Show chart" : "Show data table"}
        >
          {table ? <BarChart3 className="size-4" /> : <Table2 className="size-4" />}
        </button>
      </CardHeader>
      <CardContent className={cn("transition-opacity", fetching && "opacity-50")}>
        {series ? (
          <div className="mb-3">
            <Legend series={series} />
          </div>
        ) : null}
        {table ? (
          <div className="max-h-80 overflow-auto rounded-md border">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 bg-card-2">
                <tr>
                  {columns.map((c) => (
                    <th key={c.key} className="px-3 py-2 font-medium text-muted-foreground">
                      {c.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} className="border-t border-border/60">
                    {columns.map((c) => (
                      <td key={c.key} className="px-3 py-1.5 tabular-nums">
                        {c.format ? c.format(r[c.key]) : String(r[c.key] ?? "–")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : rows.length ? (
          children
        ) : (
          <p className="py-10 text-center text-sm text-muted-foreground">No recorded data in this period.</p>
        )}
      </CardContent>
    </Card>
  );
}
