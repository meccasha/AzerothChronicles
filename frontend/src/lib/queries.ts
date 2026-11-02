"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, qs } from "./api";
import type {
  AdventureEvent,
  ApiToken,
  Character,
  Comment,
  Dashboard,
  EventPage,
  Facets,
  Group,
  HallOfFame,
  IngestResult,
  IntegrationStatus,
  Invite,
  LootRow,
  Member,
  MemberStatRow,
  Overview,
  ProgressionRow,
  SeriesPoint,
  User,
} from "./types";

export const keys = {
  me: ["me"] as const,
  groups: ["groups"] as const,
  group: (id: string) => ["group", id] as const,
  g: (id: string, ...rest: unknown[]) => ["group", id, ...rest] as const,
};

// ------------------------------------------------------------------ session
export function useMe() {
  return useQuery({
    queryKey: keys.me,
    queryFn: async () => {
      try {
        return await api<User>("/me");
      } catch (e) {
        if ((e as { status?: number }).status === 401) return null;
        throw e;
      }
    },
    staleTime: 60_000,
  });
}

export function useGroups(enabled = true) {
  return useQuery({ queryKey: keys.groups, queryFn: () => api<Group[]>("/groups"), enabled });
}

export function useGroup(groupId: string) {
  return useQuery({ queryKey: keys.group(groupId), queryFn: () => api<Group>(`/groups/${groupId}`) });
}

export function useMembers(groupId: string) {
  return useQuery({ queryKey: keys.g(groupId, "members"), queryFn: () => api<Member[]>(`/groups/${groupId}/members`) });
}

export function useDashboard(groupId: string) {
  return useQuery({ queryKey: keys.g(groupId, "dashboard"), queryFn: () => api<Dashboard>(`/groups/${groupId}/dashboard`) });
}

// ------------------------------------------------------------------ timeline
export interface TimelineFilters {
  types?: string;
  member?: string;
  character?: string;
  expansion?: string;
  season?: string;
  q?: string;
  favorites?: boolean;
  pinned?: boolean;
  highlights?: boolean;
  show_all?: boolean;
  include_hidden?: boolean;
  order?: "asc" | "desc";
  start?: string;
  end?: string;
}

export function useTimeline(groupId: string, filters: TimelineFilters) {
  return useInfiniteQuery({
    queryKey: keys.g(groupId, "events", filters),
    queryFn: ({ pageParam }) =>
      api<EventPage>(`/groups/${groupId}/events${qs({ ...filters, cursor: pageParam, limit: 25 })}`),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    placeholderData: (prev) => prev,
  });
}

export function useFacets(groupId: string) {
  return useQuery({ queryKey: keys.g(groupId, "facets"), queryFn: () => api<Facets>(`/groups/${groupId}/events/facets`) });
}

export function useEvent(groupId: string, eventId: string) {
  return useQuery({
    queryKey: keys.g(groupId, "event", eventId),
    queryFn: () => api<AdventureEvent>(`/groups/${groupId}/events/${eventId}`),
  });
}

export function useComments(groupId: string, eventId: string, enabled = true) {
  return useQuery({
    queryKey: keys.g(groupId, "comments", eventId),
    queryFn: () => api<Comment[]>(`/groups/${groupId}/events/${eventId}/comments`),
    enabled,
  });
}

/** Invalidate everything derived from events after a mutation. */
export function useInvalidateGroup(groupId: string) {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: keys.group(groupId) });
}

export function useEventMutation<TVars>(groupId: string, fn: (vars: TVars) => Promise<unknown>) {
  const invalidate = useInvalidateGroup(groupId);
  return useMutation({ mutationFn: fn, onSuccess: () => invalidate() });
}

// ------------------------------------------------------------------ stats
export function useOverview(groupId: string, period: PeriodParams) {
  return useQuery({
    queryKey: keys.g(groupId, "overview", period),
    queryFn: () => api<Overview>(`/groups/${groupId}/stats/overview${qs({ ...period })}`),
    placeholderData: (p) => p,
  });
}

export interface PeriodParams {
  period: string;
  start?: string;
  end?: string;
}

export function useTimeseries(groupId: string, period: PeriodParams, bucket: "week" | "month") {
  return useQuery({
    queryKey: keys.g(groupId, "timeseries", period, bucket),
    queryFn: () =>
      api<{ series: SeriesPoint[]; label: string }>(`/groups/${groupId}/stats/timeseries${qs({ ...period, bucket })}`),
    placeholderData: (p) => p,
  });
}

export function useMemberStats(groupId: string, period: PeriodParams) {
  return useQuery({
    queryKey: keys.g(groupId, "memberstats", period),
    queryFn: () => api<{ members: MemberStatRow[] }>(`/groups/${groupId}/stats/members${qs({ ...period })}`),
    placeholderData: (p) => p,
  });
}

export function useProgression(groupId: string) {
  return useQuery({
    queryKey: keys.g(groupId, "progression"),
    queryFn: () =>
      api<{
        encounters: ProgressionRow[];
        by_period: ({ expansion: string | null; season: string | null; total: number } & Record<string, number>)[];
        expansions: { key: string; name: string }[];
        seasons: { key: string; name: string }[];
      }>(`/groups/${groupId}/stats/progression`),
  });
}

// ------------------------------------------------------------------ awards & loot
export function useHallOfFame(groupId: string) {
  return useQuery({ queryKey: keys.g(groupId, "awards"), queryFn: () => api<HallOfFame>(`/groups/${groupId}/awards`) });
}

export interface LootFilters {
  q?: string;
  quality?: string;
  member?: string;
  category?: string;
  sort?: "recent" | "oldest" | "celebrated";
}

export function useLoot(groupId: string, filters: LootFilters) {
  return useQuery({
    queryKey: keys.g(groupId, "loot", filters),
    queryFn: () => api<{ total: number; items: LootRow[] }>(`/groups/${groupId}/loot${qs({ ...filters, limit: 120 })}`),
    placeholderData: (p) => p,
  });
}

export function useLootHighlights(groupId: string) {
  return useQuery({
    queryKey: keys.g(groupId, "loot-highlights"),
    queryFn: () =>
      api<{
        first_legendary: LootRow | null;
        latest_mount: LootRow | null;
        most_celebrated: LootRow[];
        by_quality: Record<string, number>;
        by_category: Record<string, number>;
      }>(`/groups/${groupId}/loot/highlights`),
  });
}

// ------------------------------------------------------------------ account & integrations
export function useMyCharacters() {
  return useQuery({ queryKey: ["my-characters"], queryFn: () => api<Character[]>("/me/characters") });
}

export function useIntegrationStatus() {
  return useQuery({
    queryKey: ["integrations"],
    queryFn: () => api<IntegrationStatus>("/integrations/status"),
    refetchInterval: (q) => (q.state.data?.jobs.some((j) => j.status === "running") ? 3000 : false),
  });
}

export function useTokens() {
  return useQuery({ queryKey: ["tokens"], queryFn: () => api<ApiToken[]>("/me/tokens") });
}

export function useInvites(groupId: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.g(groupId, "invites"),
    queryFn: () => api<Invite[]>(`/groups/${groupId}/invites`),
    enabled,
  });
}

export type { IngestResult };
