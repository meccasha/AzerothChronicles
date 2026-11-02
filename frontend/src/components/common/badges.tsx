import { BadgeCheck, Clock, Eye, FlaskConical, History, PenLine, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Tip } from "@/components/ui/misc";
import type { AdventureEvent } from "@/lib/types";
import { SOURCE_LABEL } from "@/lib/wow";

/** Shows where an event came from and how trustworthy its timestamp/participation is. */
export function ProvenanceBadges({ event, compact }: { event: AdventureEvent; compact?: boolean }) {
  const out: React.ReactNode[] = [];
  if (event.is_demo) {
    out.push(
      <Tip key="demo" content="Fictional demonstration data">
        <Badge variant="info">
          <FlaskConical /> Demo
        </Badge>
      </Tip>,
    );
  }
  if (event.is_manual) {
    out.push(
      <Tip key="man" content={`Added manually${event.created_by ? ` by ${event.created_by.display_name}` : ""}. Not verified by game data.`}>
        <Badge variant="secondary">
          <PenLine /> Manual
        </Badge>
      </Tip>,
    );
  } else if (!compact) {
    out.push(
      <Tip key="src" content={`Captured automatically via ${SOURCE_LABEL[event.source] ?? event.source}`}>
        <Badge variant="outline">
          <BadgeCheck /> {SOURCE_LABEL[event.source] ?? event.source}
        </Badge>
      </Tip>,
    );
  }
  if (event.provenance === "backfill") {
    out.push(
      <Tip key="bf" content="Imported from Blizzard achievement history when the character was linked — not captured live.">
        <Badge variant="outline">
          <History /> Imported history
        </Badge>
      </Tip>,
    );
  }
  if (event.time_precision === "observed") {
    out.push(
      <Tip key="obs" content="Blizzard did not report a completion time, so this shows when our sync first observed it.">
        <Badge variant="warning">
          <Eye /> Time observed
        </Badge>
      </Tip>,
    );
  } else if (event.time_precision === "approximate" && !compact) {
    out.push(
      <Tip key="appr" content="Date and time entered by a member">
        <Badge variant="outline">
          <Clock /> Member-entered time
        </Badge>
      </Tip>,
    );
  }
  const roster = event.participants.filter((p) => p.confirmation === "roster").length;
  if (roster && !compact) {
    out.push(
      <Tip key="ros" content={`${roster} participant(s) were seen in a group-mate's roster rather than reported by their own addon.`}>
        <Badge variant="outline">
          <Users /> {roster} via roster
        </Badge>
      </Tip>,
    );
  }
  return <span className="flex flex-wrap items-center gap-1.5">{out}</span>;
}
