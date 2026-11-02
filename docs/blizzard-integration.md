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

## What Battle.net does not provide

The Profile API exposes **aggregate** raid/dungeon progress (kill counts, last kill timestamps), not an
event-level history of pulls, wipes, participants or loot. Azeroth Chronicles therefore does **not**
derive boss kills, wipes, participation or loot from Battle.net. Those come only from the addon (or
manual entries), and the UI labels counts as "recorded".
