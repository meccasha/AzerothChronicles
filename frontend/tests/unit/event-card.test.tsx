import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EventCard, eventSubtitle } from "@/components/timeline/event-card";
import type { AdventureEvent } from "@/lib/types";

vi.mock("next/link", () => ({ default: ({ children, href, ...p }: { children: React.ReactNode; href: string }) => <a href={href} {...p}>{children}</a> }));

function ev(over: Partial<AdventureEvent> = {}): AdventureEvent {
  return {
    id: "e1", event_type: "boss_kill", title: "Warden Ossivar defeated", description: "", occurred_at: "2026-05-12T21:00:00Z",
    time_precision: "exact", importance: 80, highlight: null, difficulty: "Heroic", instance_name: "The Gilded Necropolis",
    expansion: null, season: null, source: "addon", provenance: "live", confidence: "confirmed", is_manual: false, is_demo: false,
    hidden: false, pinned: false, favorite: false, achievement: null, encounter: null, item: null, extra: { wipes_before_kill: 3 },
    participants: [], reactions: [], comment_count: 2, media: [], created_by: null, can_edit: false, can_moderate: false, ...over,
  };
}

const wrap = (ui: React.ReactElement) => render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);

describe("EventCard", () => {
  it("describes boss kills with difficulty, instance and recorded wipes", () => {
    expect(eventSubtitle(ev())).toBe("Heroic · The Gilded Necropolis · after 3 recorded wipes");
  });

  it("gives milestones a distinctive banner", () => {
    wrap(<EventCard groupId="g" event={ev({ highlight: "first_raid_kill", extra: { milestone: "First raid boss defeated together" } })} />);
    expect(screen.getByText("First raid boss defeated together")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Warden Ossivar defeated" })).toHaveAttribute("href", "/g/g/timeline/e1");
  });

  it("labels manual and observed-time events honestly", () => {
    wrap(<EventCard groupId="g" event={ev({ is_manual: true, time_precision: "observed", event_type: "achievement", title: "Glory" })} />);
    expect(screen.getByText("Manual")).toBeInTheDocument();
    expect(screen.getByText("Time observed")).toBeInTheDocument();
  });

  it("labels backfilled history", () => {
    wrap(<EventCard groupId="g" event={ev({ provenance: "backfill", event_type: "achievement", title: "Old deed" })} />);
    expect(screen.getByText("Imported history")).toBeInTheDocument();
  });
});
