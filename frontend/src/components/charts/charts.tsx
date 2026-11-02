"use client";

import { format, parseISO } from "date-fns";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, ChartTooltip, GRID, SERIES_HEX, SINGLE_HUE, SURFACE, type SeriesDef } from "./chart-kit";

export const ACTIVITY_SERIES: SeriesDef[] = [
  { key: "boss_kills", label: "Boss kills", color: SERIES_HEX.boss_kills },
  { key: "achievements", label: "Achievements", color: SERIES_HEX.achievements },
  { key: "loot", label: "Notable loot", color: SERIES_HEX.loot },
  { key: "dungeons", label: "Dungeons", color: SERIES_HEX.dungeons },
];

export const bucketLabel = (bucket: "week" | "month") => (iso: string) =>
  format(parseISO(iso), bucket === "month" ? "MMM yyyy" : "'Week of' MMM d");
const tickLabel = (bucket: "week" | "month") => (iso: string) => format(parseISO(iso), bucket === "month" ? "MMM yy" : "MMM d");

/** Stacked bars: 2px surface gap between segments, 4px rounding only on the top segment. */
export function StackedBars({ data, series, bucket, height = 280 }: { data: object[]; series: SeriesDef[]; bucket: "week" | "month"; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data as Record<string, unknown>[]} margin={{ top: 8, right: 4, left: -18, bottom: 0 }} barCategoryGap="22%">
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis dataKey="bucket" tickFormatter={tickLabel(bucket)} {...AXIS} tickLine={false} minTickGap={16} />
        <YAxis allowDecimals={false} {...AXIS} tickLine={false} axisLine={false} width={44} />
        <Tooltip cursor={{ fill: "rgb(214 169 74 / 0.06)" }} content={<ChartTooltip labelFormatter={bucketLabel(bucket)} />} />
        {series.map((s, i) => (
          <Bar
            key={s.key}
            dataKey={s.key}
            name={s.label}
            stackId="a"
            fill={s.color}
            stroke={SURFACE}
            strokeWidth={2}
            radius={i === series.length - 1 ? [4, 4, 0, 0] : 0}
            isAnimationActive={false}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Grouped (side-by-side) bars for two comparable measures (same unit, one axis). */
export function GroupedBars({ data, series, bucket, height = 240 }: { data: Record<string, unknown>[]; series: SeriesDef[]; bucket: "week" | "month"; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 4, left: -18, bottom: 0 }} barGap={2} barCategoryGap="24%">
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis dataKey="bucket" tickFormatter={tickLabel(bucket)} {...AXIS} tickLine={false} minTickGap={16} />
        <YAxis allowDecimals={false} {...AXIS} tickLine={false} axisLine={false} width={44} />
        <Tooltip cursor={{ fill: "rgb(214 169 74 / 0.06)" }} content={<ChartTooltip labelFormatter={bucketLabel(bucket)} />} />
        {series.map((s) => (
          <Bar key={s.key} dataKey={s.key} name={s.label} fill={s.color} radius={[4, 4, 0, 0]} isAnimationActive={false} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Single-series line with crosshair (the tooltip cursor) and >= 8px active marker. */
export function TrendLine({ data, dataKey, label, bucket, height = 220, max }: { data: Record<string, unknown>[]; dataKey: string; label: string; bucket: "week" | "month"; height?: number; max?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis dataKey="bucket" tickFormatter={tickLabel(bucket)} {...AXIS} tickLine={false} minTickGap={16} />
        <YAxis allowDecimals={false} domain={[0, max ?? "auto"]} {...AXIS} tickLine={false} axisLine={false} width={44} />
        <Tooltip cursor={{ stroke: "#d6a94a", strokeOpacity: 0.5, strokeWidth: 1 }} content={<ChartTooltip labelFormatter={bucketLabel(bucket)} />} />
        <Line type="monotone" dataKey={dataKey} name={label} stroke={SINGLE_HUE} strokeWidth={2} dot={false} activeDot={{ r: 5, stroke: SURFACE, strokeWidth: 2 }} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

/** Horizontal single-series bars (ranking). Category labels on the axis; one hue. */
export function RankBars({ data, dataKey, label, height }: { data: { name: string; [k: string]: unknown }[]; dataKey: string; label: string; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height ?? Math.max(140, data.length * 38)}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 24, left: 8, bottom: 0 }} barCategoryGap="28%">
        <CartesianGrid horizontal={false} stroke={GRID} />
        <XAxis type="number" allowDecimals={false} {...AXIS} tickLine={false} />
        <YAxis type="category" dataKey="name" {...AXIS} tickLine={false} axisLine={false} width={110} />
        <Tooltip cursor={{ fill: "rgb(214 169 74 / 0.06)" }} content={<ChartTooltip />} />
        <Bar dataKey={dataKey} name={label} fill={SINGLE_HUE} radius={[0, 4, 4, 0]} isAnimationActive={false} label={{ position: "right", fill: "#c7cbd4", fontSize: 11 }} />
      </BarChart>
    </ResponsiveContainer>
  );
}
