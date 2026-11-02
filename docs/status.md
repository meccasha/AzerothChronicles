# Status, risks and roadmap

## Implementation plan (as executed)

| Phase | Scope | Status |
|---|---|---|
| 1. Foundation | Monorepo, FastAPI + Postgres + Alembic, auth (sessions), groups/roles/invites, all models + migration, UI shell, demo data, Docker Compose | ✅ |
| 2. Core | Timeline (filters, search, grouping, cursor paging), manual events, comments, reactions, favorites, pins, hide/delete, screenshots, member profiles, statistics, Hall of Fame, Loot Museum, settings | ✅ |
| 3. Battle.net | Adapter interface, live client (OAuth, retries, rate spacing, caching), mock adapter on fixtures, character linking, backfill-aware achievement sync, rename handling, item metadata enrichment, provenance | ✅ code + tests; ⚠️ not verified against live Battle.net (see below) |
| 4. Addon | Lua addon (encounters, wipes, deaths, M+, achievements, loot, mounts/toys), SavedVariables + in-game JSON export, upload page, companion uploader, addon status on Integrations | ✅ code + harness tests; ⚠️ not run in a live client |
| 5. Polish | Animations, special-event styling, mobile layout + bottom nav, query batching, tests, deployment docs | ✅ (ongoing) |

## Definition of done — MVP

| Requirement | Where |
|---|---|
| Start locally | `docker compose up --build` or `make` targets ([development.md](development.md)) |
| Log in, create a private group, invite/add members | `/register`, `/groups/new`, Settings → Members & invitations |
| Associate characters | Account page (manual), Integrations (Battle.net), addon uploads (automatic) |
| Browse timeline, create events | `/g/:id/timeline`, "Add memory" |
| Import simulated normalized events | Integrations → Import → Generate simulated events |
| Statistics, Loot Museum, automatic awards | `/stats`, `/loot`, `/hall-of-fame` — all computed server-side from the DB |
| Multiple groups without leaks | membership-scoped queries; covered by `test_auth_and_privacy.py` |

## Test coverage

* Backend (61): auth, CSRF, privacy/isolation, invites & roles, account deletion/export, ingestion
  (cross-reporter dedup, roster attribution, idempotency, out-of-order firsts, wipe streaks, GUID hijack,
  validation, scenarios), loot rules, achievements merge/min points, dungeon merge, renames, partial data,
  Battle.net OAuth/state, backfill vs live, observed timestamps, failures/retries/404/expired tokens,
  item enrichment, statistics, award rules/ties/reproducibility/voting, SavedVariables parsing (incl.
  rejecting code), upload tokens, the real addon Lua under a mocked WoW API, and an API-level end-to-end flow.
* Frontend: TypeScript, Vitest (grouping, query strings, event-card provenance labels), Playwright
  (register → create group → import → dedup on re-import → timeline/manual event/stats/Hall of Fame/Loot
  Museum; demo browse + unauthenticated access check on desktop and mobile).

## Known limitations & risks

* **External verification.** No access to the Battle.net developer portal, a live WoW 12.x client or
  warcraft.wiki.gg from the build environment. Endpoint shapes and addon APIs follow Blizzard's documented
  APIs as known at implementation time; both integrations are isolated, defensive, and come with
  verification checklists ([blizzard-integration.md](blizzard-integration.md), [addon.md](addon.md)).
* **Secret values (Midnight).** If chat/encounter payloads are secret in some contexts, the addon records
  less rather than circumventing restrictions. Death tracking is own-character only (`PLAYER_DEAD`).
* **No real-time sync.** Data arrives when SavedVariables are written and uploaded.
* **Battle.net user tokens** are short-lived; re-linking is required to refresh the account character list.
* **Characters are shared** with every group the member belongs to (no per-group character selection yet).
* **First-claim GUID ownership.** An unverified addon upload claims a GUID for the uploader; Battle.net
  linking is the ownership proof. A dispute flow (admin reassignment) is not built yet.
* **Season/expansion windows** are configuration (`backend/app/data/periods.json`) and must be maintained.
* Weekly award history is computed for the most recent 26 weeks.
* Login rate limiting is in-process (per API replica).

## Not yet implemented (next steps)

1. Discord integration (webhook posts for highlights; slash command for the weekly recap).
2. Combat-log ingestion via the companion (`WoWCombatLog.txt` parsing) for richer encounter data — only if
   it can be done within Blizzard's terms; the addon deliberately avoids the combat log.
3. Per-group character visibility and an admin tool to resolve disputed character ownership.
4. Email delivery (invites, password reset). Password reset currently requires an operator.
5. Object storage for screenshots and thumbnails; image lightbox.
6. Use Battle.net aggregate raid progression (`/encounters/raids`) as a cross-check — clearly separated from
   event-level addon data.
7. Notifications / weekly digest page; award announcement events on the timeline.
