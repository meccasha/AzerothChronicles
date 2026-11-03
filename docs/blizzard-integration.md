# Battle.net integration

## Register an application

1. Sign in at https://develop.battle.net/access/clients and create a client.
2. Redirect URL: `<PUBLIC_API_URL>/integrations/blizzard/callback`
   (local: `http://localhost:3000/api/integrations/blizzard/callback`).
3. Put the id/secret in `.env` as `BLIZZARD_CLIENT_ID` / `BLIZZARD_CLIENT_SECRET` and set
   `BLIZZARD_ADAPTER=live`. Credentials never leave the backend.

## What we call

| Purpose | Request | Token |
|---|---|---|
| Authorize | `GET https://oauth.battle.net/authorize?response_type=code&scope=openid wow.profile&state=…` | — |
| Token exchange | `POST https://oauth.battle.net/token` (`authorization_code`, HTTP Basic client auth) | — |
| App token | `POST https://oauth.battle.net/token` (`client_credentials`) | — |
| Account identity | `GET https://oauth.battle.net/userinfo` | user |
| Account characters | `GET https://{region}.api.blizzard.com/profile/user/wow?namespace=profile-{region}` | user |
| Character profile | `GET /profile/wow/character/{realmSlug}/{name}?namespace=profile-{region}` | app |
| Character achievements | `GET /profile/wow/character/{realmSlug}/{name}/achievements?namespace=profile-{region}` | app |
| Character media | `GET /profile/wow/character/{realmSlug}/{name}/character-media?namespace=profile-{region}` | app |
| Achievement | `GET /data/wow/achievement/{id}?namespace=static-{region}` | app |
| Item / item media | `GET /data/wow/item/{id}`, `GET /data/wow/media/item/{id}` (`static-{region}`) | app |
| Achievement icon | `GET /data/wow/media/achievement/{id}` (asset `icon`) | app |
| Dungeon / raid artwork | `GET /data/wow/journal-instance/index`, `GET /data/wow/journal-instance/{id}`, `GET /data/wow/media/journal-instance/{id}` (asset `tile`) | app |
| Boss portrait | `GET /data/wow/journal-encounter/{id}` → `creatures[].creature_display.id` → `GET /data/wow/media/creature-display/{id}` (asset `zoom`) | app |
| Mount render | `GET /data/wow/mount/{id}` → `creature_displays[].id` → creature-display media | app |

Tokens are sent in the `Authorization: Bearer` header. Regions: `us`, `eu`, `kr`, `tw`.

### Verification status (please read)

The build environment for this project could not reach the Battle.net developer portal, so the endpoint
list above follows Blizzard's published API as known at implementation time and is **not re-verified
against live responses**. The code is written defensively for that reason:

* All Battle.net access is behind `BlizzardAdapter` (`backend/app/integrations/blizzard/adapter.py`);
  business logic only sees typed results (`types.py`).
* Field access tolerates missing/renamed fields and localized-name dicts; a changed shape surfaces as a
  sync error on the Integrations page, never as invented data.
* The mock adapter runs the **same parsing code** against Battle.net-shaped fixtures, and tests cover
  429/5xx retries, 404s, renames and expired user tokens.

Before enabling `live` in production, verify with real credentials:

- [ ] `/profile/user/wow` lists `wow_accounts[].characters[]` with `id`, `name`, `realm.slug`.
- [ ] `/achievements` entries carry `completed_timestamp` (ms) — entries without it are treated as
      "completion time unknown", entries with incomplete `criteria` as in-progress.
- [ ] Character media returns an `avatar` asset.
- [ ] User tokens: confirm lifetime and whether a refresh token is issued (code assumes re-authorization).
- [ ] Rate limits for your client tier (adapter spaces requests to ≤20/s and honours `Retry-After`).
- [ ] Media endpoints return the asset keys used above (`icon`, `tile`, `zoom`) and URLs on
      `render.worldofwarcraft.com` — any other host is discarded by `safe_media_url`.
- [ ] `journal-encounter` responses list `creatures[].creature_display.id`, and `journal-instance` lists
      `encounters[]` and `map.id`.

## Sync semantics

* **Linking** verifies ownership: only characters returned by the user's own `/profile/user/wow` can be
  linked; Blizzard's numeric character id becomes the stable identity (survives renames and transfers).
* **First sync = backfill.** All completed achievements are stored as a snapshot (`blizzard_backfill`).
  A timeline event is created only when Blizzard reports a completion timestamp *after the member joined
  the group*; it is labelled "Imported history".
* **Later syncs** diff against the snapshot. New achievements become live events dated with the real
  completion time, or — when Blizzard gives none — with the observation time, visibly labelled
  "Time observed".
* **Renames/transfers**: each sync first refreshes identities from the account character list (by id),
  because realm+name endpoints 404 after a rename. History is kept in `character_identity_history`.
* **Failures** are per character (`last_sync_error`), roll up into `sync_jobs` (`succeeded|partial|failed`)
  and the source status shown on the Integrations page.

## Game artwork (icons, boss portraits, dungeon art)

`app/services/game_media.py` fills in artwork for everything the group has recorded:

| Shown as | Source | Matching |
|---|---|---|
| Item icons (timeline, Loot Museum) | item media | by item id |
| Achievement icons | achievement media | by achievement id |
| Dungeon & raid artwork (card backdrop, event banner) | journal-instance media `tile` | addon ≥ 1.1 sends the Encounter Journal instance id; older data is matched by name via the journal index |
| Boss portraits | journal-encounter → creature-display `zoom` | addon ≥ 1.1 sends the journal encounter id; otherwise matched by name within the instance |
| Mount renders | mount → creature-display `zoom` | by mount id |

* Runs automatically after every upload and Battle.net sync, in the worker, via
  `python -m app.cli resolve-media`, or from Integrations → Game artwork → *Fetch missing artwork*.
* Needs only an app (client-credentials) token — no Battle.net account linking. With
  `BLIZZARD_ADAPTER=mock` it uses fixtures that only know a few fictional ids.
* Only URLs on Blizzard's render CDN are stored (`safe_media_url`), so the browser never loads images from
  hosts named in uploaded data. Images load lazily with `referrerpolicy=no-referrer`; if one is missing the
  UI falls back to its built-in icon.
* 404s are recorded as unavailable and not retried; transient errors (429/5xx/network) are retried on the
  next run. Runs are serialized with a transaction-scoped Postgres advisory lock.
* The game client itself only exposes icon *FileDataIDs*, not image URLs, which is why the website (not the
  addon) resolves artwork. The addon stores the FileDataID as `icon_file_id` for reference.
* The demo group uses generic game icons that fit each fictional object (never a real boss's artwork).

## What Battle.net does not provide

The Profile API exposes **aggregate** raid/dungeon progress (kill counts, last kill timestamps), not an
event-level history of pulls, wipes, participants or loot. Azeroth Chronicles therefore does **not**
derive boss kills, wipes, participation or loot from Battle.net. Those come only from the addon (or
manual entries), and the UI labels counts as "recorded".
