import { describe, expect, it } from "vitest";
import { qs } from "@/lib/api";
import { groupBy, groupKey, groupLabel, initials } from "@/lib/format";

describe("timeline grouping", () => {
  const items = ["2026-10-31T21:00:00Z", "2026-10-02T20:00:00Z", "2026-09-30T20:00:00Z", "2025-12-01T20:00:00Z"];

  it("groups consecutive events by month without reordering", () => {
    const g = groupBy(items, (i) => groupKey(i, "month"));
    expect(g.map((s) => [s.key, s.items.length])).toEqual([
      ["2026-10", 2],
      ["2026-09", 1],
      ["2025-12", 1],
    ]);
  });

  it("supports day and year grouping with readable labels", () => {
    expect(groupBy(items, (i) => groupKey(i, "year")).map((s) => s.key)).toEqual(["2026", "2025"]);
    expect(groupLabel("2026-10", "month")).toBe("October 2026");
    expect(groupLabel("2026", "year")).toBe("2026");
  });

  it("builds initials", () => {
    expect(initials("Mira Vale")).toBe("MV");
    expect(initials("solo")).toBe("S");
  });
});

describe("qs", () => {
  it("drops empty and false values", () => {
    expect(qs({ a: 1, b: "", c: undefined, d: false, e: true, f: "x y" })).toBe("?a=1&e=true&f=x+y");
    expect(qs({})).toBe("");
  });
});
