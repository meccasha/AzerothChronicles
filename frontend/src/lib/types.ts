// Mirrors backend/app/schemas/api.py

export type Role = "owner" | "admin" | "member";
export type EventType = "achievement" | "boss_kill" | "dungeon_complete" | "loot" | "milestone" | "manual";
export type Confirmation = "confirmed" | "roster" | "claimed";

export interface User {
  id: string;
  email: string;
  display_name: string;
  avatar_color: string | null;
  is_demo: boolean;
  created_at: string;
}

export interface UserBrief {
  id: string;
  display_name: string;
  avatar_color: string | null;
}

export interface GroupSettings {
  loot: {
    record_legendary: boolean;
    record_epic: boolean;
    record_rare: boolean;
    record_mounts: boolean;
    record_collectibles: boolean;
    epic_min_item_level: number | null;
  };
  events: {
    timeline_min_importance: number;
    achievement_min_points: number;
    achievement_merge_hours: number;
    encounter_min_members: number;
    enabled_categories: string[];
  };
  awards: { disabled: string[] };
}

export interface Group {
  id: string;
  name: string;
  slug: string;
  description: string;
  banner_url: string | null;
  visibility: "private" | "invite_preview";
  is_demo: boolean;
  created_at: string;
  settings: GroupSettings;
  my_role: Role | null;
  member_count: number | null;
}

export interface Character {
  id: string;
  owner_user_id: string;
  name: string;
  realm_name: string;
  realm_slug: string;
  region: string;
  faction: string | null;
  race: string | null;
  character_class: string | null;
  specialization: string | null;
  level: number | null;
  achievement_points: number | null;
  avatar_url: string | null;
  verification: "blizzard_verified" | "addon_reported" | "manual";
  is_active: boolean;
  is_main: boolean;
  last_synced_at: string | null;
  last_sync_error: string | null;
}

export interface Member {
  user: UserBrief;
  role: Role;
  joined_at: string;
  characters: Character[];
}

export interface Participant {
  user: UserBrief;
  character: Character | null;
  confirmation: Confirmation;
}

export interface ReactionSummary {
  emoji: string;
  count: number;
  mine: boolean;
}

export interface Media {
  id: string;
  url: string;
  content_type: string;
  width: number | null;
  height: number | null;
  caption: string | null;
}

export interface AdventureEvent {
  id: string;
  event_type: EventType;
  title: string;
  description: string;
  occurred_at: string;
  time_precision: "exact" | "observed" | "approximate";
  importance: number;
  highlight: string | null;
  difficulty: string | null;
  instance_name: string | null;
  expansion: string | null;
  season: string | null;
  source: string;
  provenance: "live" | "backfill" | "manual";
  confidence: "confirmed" | "unconfirmed";
  is_manual: boolean;
  is_demo: boolean;
  hidden: boolean;
  pinned: boolean;
  favorite: boolean;
  achievement: { id: number; name: string; points: number; icon_url: string | null } | null;
  encounter: { id: number; name: string; instance_name: string | null; instance_type: string } | null;
  item: { id: number; name: string; quality: string; icon_url: string | null; item_class: string | null } | null;
  extra: Record<string, unknown> & {
    milestone?: string;
    first_kill?: boolean;
    wipes_before_kill?: number;
    quality?: string;
    category?: string;
    item_level?: number;
    keystone_level?: number;
    on_time?: boolean;
    points?: number;
    duration_s?: number | null;
    encounter_name?: string;
  };
  participants: Participant[];
  reactions: ReactionSummary[];
  comment_count: number;
  media: Media[];
  created_by: UserBrief | null;
  can_edit: boolean;
  can_moderate: boolean;
}

export interface EventPage {
  items: AdventureEvent[];
  next_cursor: string | null;
  total: number;
  hidden_below_threshold: number;
}

export interface Comment {
  id: string;
  user: UserBrief;
  body: string;
  created_at: string;
  can_delete: boolean;
}

export interface Facets {
  members: { id: string; display_name: string; avatar_color: string | null }[];
  characters: { id: string; name: string; realm: string; character_class: string | null; owner_user_id: string }[];
  expansions: { key: string; name: string; has_events: boolean }[];
  seasons: { key: string; name: string; expansion: string | null; has_events: boolean }[];
  types: EventType[];
  timeline_min_importance: number;
}

export interface MemberActivity {
  user_id: string;
  display_name: string;
  avatar_color: string | null;
  events: number;
}

export interface Coverage {
  members: number;
  battlenet_linked: number;
  addon_reporting: number;
  attempts_with_death_data: number;
  notes: string[];
}

export interface Overview {
  period?: string;
  label?: string;
  tracked_events: number;
  achievements_recorded: number;
  boss_kills_confirmed: number;
  boss_kills_manual: number;
  wipes_recorded: number;
  dungeons_recorded: number;
  manual_events: number;
  notable_loot: number;
  legendary_loot: number;
  mounts: number;
  play_sessions: number;
  first_event_in_range: string | null;
  first_recorded_activity: string | null;
  most_active: MemberActivity[];
  coverage?: Coverage;
}

export interface SeriesPoint {
  bucket: string;
  events: number;
  achievements: number;
  boss_kills: number;
  wipes: number;
  loot: number;
  dungeons: number;
  active_members: number;
}

export interface MemberStatRow {
  user_id: string;
  display_name: string;
  avatar_color: string | null;
  role: Role;
  joined_at: string;
  events: number;
  achievements: number;
  boss_kills: number;
  dungeons: number;
  loot: number;
  legendaries: number;
  wipes: number;
  deaths: number | null;
  attempts_with_death_data: number;
}

export interface ProgressionRow {
  encounter_id: number;
  name: string;
  instance_name: string | null;
  instance_type: string;
  difficulty: string;
  kills: number;
  wipes: number;
  first_kill_at: string | null;
  first_attempt_at: string | null;
}

export interface Standing {
  user_id: string;
  display_name: string;
  value: number;
  rank: number;
  tied?: boolean;
}

export interface AwardResult {
  award_key: string;
  period_type: string;
  period_label: string;
  period_start: string;
  period_end: string;
  status: "awarded" | "tied" | "no_data" | "insufficient_data";
  winner: UserBrief | null;
  winning_value: number | null;
  standings: Standing[];
  is_final: boolean;
  computed_at: string;
  calculation_version: string;
}

export interface Award {
  key: string;
  title: string;
  description: string;
  icon: string;
  kind: "auto" | "vote";
  rules: string;
  requires: string | null;
  unit: string;
  period_types: string[];
  enabled: boolean;
  current: Partial<Record<"week" | "month" | "season" | "all_time", AwardResult | null>>;
  history: AwardResult[];
}

export interface HallOfFame {
  awards: Award[];
  current_labels: Record<string, string>;
  trophy_cabinet: Record<string, number>;
  last_computed_at: string | null;
}

export interface LootRow {
  id: string;
  event_id: string | null;
  item_id: number | null;
  item_name: string;
  quality: string;
  category: string;
  icon_url: string | null;
  obtained_at: string;
  source_instance: string | null;
  difficulty: string | null;
  notable_reason: string;
  is_group_first: boolean;
  source: string;
  is_demo: boolean;
  celebration: number;
  user: UserBrief;
  character: { id: string; name: string; character_class: string | null } | null;
}

export interface Dashboard {
  overview: Overview;
  coverage: Coverage;
  recent_activity: AdventureEvent[];
  recent_boss_kills: AdventureEvent[];
  recent_achievements: AdventureEvent[];
  recent_loot: AdventureEvent[];
  featured: AdventureEvent | null;
  award_leaders: {
    award_key: string;
    title: string;
    icon: string;
    unit: string;
    value: number;
    status: string;
    winner: UserBrief;
  }[];
  award_period_label: string;
}

export interface Invite {
  id: string;
  code: string;
  role: string;
  expires_at: string;
  max_uses: number | null;
  uses: number;
  revoked_at: string | null;
  url: string | null;
}

export interface IntegrationStatus {
  blizzard: {
    adapter_mode: string;
    configured: boolean;
    linked: boolean;
    battletag: string | null;
    region: string | null;
    authorization_expired: boolean;
    source: SourceStatus | null;
    characters: {
      id: string;
      name: string;
      realm: string;
      verification: string;
      last_synced_at: string | null;
      last_sync_error: string | null;
      backfilled: boolean;
    }[];
  };
  addon: { source: SourceStatus | null; active_tokens: number };
  jobs: {
    id: string;
    kind: string;
    status: string;
    started_at: string | null;
    finished_at: string | null;
    stats: Record<string, unknown>;
    error: string | null;
  }[];
  recent_errors: { id: string; record_type: string; detail: string | null; received_at: string }[];
}

export interface SourceStatus {
  status: string;
  last_attempt_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
  details: Record<string, unknown>;
}

export interface IngestResult {
  received: number;
  normalized: number;
  duplicates: number;
  ignored: number;
  rejected: number;
  events_created: number;
  events_merged: number;
  groups: string[];
  messages: string[];
  sync_job_id: string;
}

export interface ApiToken {
  id: string;
  name: string;
  token_prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}
