# AzerothChronicles WoW addon

A Retail addon that **observes** game events and writes them to SavedVariables. It never automates
gameplay, never reads protected/secret values, and cannot make network requests (no WoW addon can).

## Install & use

1. Copy `addon/AzerothChronicles` to `World of Warcraft/_retail_/Interface/AddOns/`.
2. If the client calls it out of date, update `## Interface:` in the `.toc` to the value of
   `/dump select(4, GetBuildInfo())`.
3. Play. `/achron` prints what has been recorded; `/achron options` opens settings;
   `/achron export [new]` opens a copyable JSON export; `/achron toggle <setting>`; `/achron prune [days]`.
4. Get the data out — SavedVariables are written on logout, `/reload` or exit:
   * upload `WTF/Account/<ACCOUNT>/SavedVariables/AzerothChronicles.lua` on the Integrations page, or
   * paste the `/achron export` text into Integrations → Import, or
   * run the [companion uploader](../companion/README.md) to upload automatically after each logout.

Uploads are idempotent, so exporting or uploading the same data repeatedly is safe.

## What it records

| Data | Game events / APIs | Notes |
|---|---|---|
| Boss pulls (kills **and** wipes) | `ENCOUNTER_START`, `ENCOUNTER_END`, `GetInstanceInfo`, `GetDifficultyInfo` | raid and dungeon instances only |
| Group roster at pull end | `GetNumGroupMembers`, `IsInRaid`, `UnitName(unit)` | used for "seen in roster" participation |
| Own deaths during a pull | `PLAYER_DEAD` between START/END | only if the pull start was observed; otherwise `null` (unknown) |
| Mythic+ completions | `CHALLENGE_MODE_COMPLETED`, `C_ChallengeMode.GetChallengeCompletionInfo` (fallback `GetCompletionInfo`), `GetMapUIInfo` | |
| Achievements | `ACHIEVEMENT_EARNED`, `GetAchievementInfo`, `GetAchievementCategory` | skips `alreadyEarned` (earned earlier on the account) |
| Own notable loot | `ENCOUNTER_LOOT_RECEIVED` (own name only), `CHAT_MSG_LOOT` matched against localized `LOOT_ITEM_SELF*` globals, `C_Item.*`, `Item:ContinueOnItemLoad` | quality ≥ epic by default; other players' loot is not recorded |
| Mounts, toys | `NEW_MOUNT_ADDED`, `C_MountJournal.GetMountInfoByID`, `NEW_TOY_ADDED`, `C_ToyBox.GetToyInfo` | |
| Character identity | `UnitGUID`, `UnitClass`/`UnitRace` file tokens, `UnitFactionGroup`, `GetRealmName`, `GetCurrentRegion`, specialization APIs | English tokens so data is locale-independent |

Not used, on purpose: `COMBAT_LOG_EVENT_UNFILTERED` (removed from addons in Midnight / 12.0), any protected
function, any secret value.

## Restrictions, secret values and verification

* Every value from the game passes through `ns.clean()`, which drops it if `issecretvalue(v)` is true.
  A secret value is treated as unknown — never stored, compared, or worked around.
* Every event registration and handler is wrapped in `pcall`; if Blizzard removes an event the addon simply
  records less. The last handler error is kept in `AzerothChroniclesDB.lastError` and shown by `/achron`.
* **Verification status:** the development environment had no access to the game client or to
  warcraft.wiki.gg, so API availability was checked against Blizzard's documented API as known at
  implementation time, not in a live 12.x client. In particular confirm in-game:
  - the argument order of `ENCOUNTER_LOOT_RECEIVED` (expected `encounterID, itemID, itemLink, quantity,
    playerName, className`; if it differs, the `CHAT_MSG_LOOT` path still captures own loot),
  - that `ENCOUNTER_START/END` and `CHAT_MSG_LOOT` payloads are not secret inside instances on your patch
    (if they are, those records are skipped rather than guessed),
  - the `## Interface:` number.
* `backend/tests/test_addon_harness.py` executes the real addon files under Lua 5.1 against a mocked WoW
  API (`backend/tests/wow_mock.lua`) and feeds the output into the backend parser and ingestion.

## Storage

`AzerothChroniclesDB` (account-wide): `schema`, `version`, `settings`, `characters[guid]`, `records[]`,
`lastWrite`, `lastExport`, `lastError`. Records have deterministic ids (e.g.
`enc-<guid>-<encounterID>-<difficultyID>-<endTime>`), an in-memory index prevents duplicates (rebuilt on
load), and the list is capped at 5,000 records (oldest dropped first; `/achron prune` removes old ones).
