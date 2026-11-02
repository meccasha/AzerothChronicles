import { format, formatDistanceToNowStrict, parseISO } from "date-fns";

export const fmtDate = (iso: string) => format(parseISO(iso), "MMM d, yyyy");
export const fmtDateTime = (iso: string) => format(parseISO(iso), "MMM d, yyyy · HH:mm");
export const fmtTime = (iso: string) => format(parseISO(iso), "HH:mm");
export const fmtRelative = (iso: string) => `${formatDistanceToNowStrict(parseISO(iso))} ago`;
export const fmtNumber = (n: number) => new Intl.NumberFormat("en-US").format(n);

export type Grouping = "day" | "month" | "year";

export function groupKey(iso: string, grouping: Grouping): string {
  const d = parseISO(iso);
  if (grouping === "year") return format(d, "yyyy");
  if (grouping === "month") return format(d, "yyyy-MM");
  return format(d, "yyyy-MM-dd");
}

export function groupLabel(key: string, grouping: Grouping): string {
  if (grouping === "year") return key;
  if (grouping === "month") return format(parseISO(`${key}-01`), "MMMM yyyy");
  return format(parseISO(key), "EEEE, MMMM d, yyyy");
}

/** Group an already-sorted list into consecutive sections (stable; never reorders items). */
export function groupBy<T>(items: T[], keyOf: (t: T) => string): { key: string; items: T[] }[] {
  const out: { key: string; items: T[] }[] = [];
  for (const item of items) {
    const k = keyOf(item);
    const last = out[out.length - 1];
    if (last && last.key === k) last.items.push(item);
    else out.push({ key: k, items: [item] });
  }
  return out;
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join("");
}
