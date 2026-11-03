# Ingestion format `azeroth-chronicles/v1`

One JSON envelope (or the equivalent `AzerothChroniclesDB` Lua table in SavedVariables) carries characters
and records. Accepted at:

| Endpoint | Body | Auth |
|---|---|---|
| `POST /api/ingest/envelope` | JSON envelope | session cookie + `X-AC-Client: web`, or `Authorization: Bearer act_…` |
| `POST /api/ingest/savedvariables` | raw `AzerothChronicles.lua` text | same |

Schema source of truth: `backend/app/schemas/ingest.py`.

```json
{
  "format": "azeroth-chronicles/v1",
  "source": "addon",               // addon | companion | simulated
  "addon_version": "1.0.0",
  "exported_at": 1772665200,       // unix seconds
  "characters": [
    {"guid": "Player-3676-0ABC1234", "name": "Thalindra", "realm": "Area 52", "region": "us",
     "class": "Hunter", "race": "Night Elf", "faction": "Alliance", "level": 80, "spec": "Marksmanship"}
  ],
  "records": [ ... ]
}
```

Every record has a source-generated stable `id` (the idempotency key together with `source` and `type`)
and a `character_guid` (optional if the envelope declares exactly one character). Times are unix seconds
from `GetServerTime()`.

| type | fields |
|---|---|
| `encounter` | `encounter_id` (DungeonEncounterID), `encounter_name`, `instance_name`, `instance_id`, `instance_type` (`raid`/`party`; others ignored), `difficulty_id`, `difficulty_name`, `group_size`, `success`, `start_time` (only if the pull start was seen), `end_time`, `roster` `[{name, realm}]`, `deaths` (own deaths; `null` = unknown), `journal_instance_id`, `journal_encounter_id` (optional, for artwork) |
| `achievement` | `achievement_id`, `name`, `points`, `description`, `feat_of_strength`, `earned_at` |
| `loot` | `item_id`, `item_name`, `quality` (0–8), `item_class`, `item_subclass`, `item_level`, `icon_file_id` (client FileDataID), `encounter_id`, `instance_name`, `difficulty_name`, `looted_at`. Legacy `icon`: a FileDataID string or an icon texture name (`inv_sword_39`); URLs are ignored. |
| `mount` / `pet` / `toy` | `collectible_id`, `name`, `item_id`, `icon_file_id`, `learned_at` |
| `dungeon_complete` | `map_id` (challenge-mode map id), `name`, `instance_id` (instance map id), `journal_instance_id`, `keystone_level`, `on_time`, `completed_at`, `duration_ms`, `roster` |

## Processing rules

* Records are stored raw in `ingestion_records` before normalization; a malformed record is `rejected`
  with a reason, an out-of-scope one is `ignored` (e.g. scenario bosses, loot below the group's rules),
  and the rest of the batch continues.
* A `character_guid` already owned by another user is rejected (no hijacking). An unknown GUID creates an
  `addon_reported` character for the uploader, or adopts the uploader's existing character with the same
  name and realm.
* Each record is applied to **every group the uploader belongs to**, using that group's settings.
* Encounters merge across reporters when encounter, difficulty and outcome match and `end_time` is within
  ±180 s. Dungeon completions merge within ±300 s. Achievements merge across members within the group's
  merge window (default 6 h).
* Response: `{received, normalized, duplicates, ignored, rejected, events_created, events_merged, groups,
  messages, sync_job_id}`.
