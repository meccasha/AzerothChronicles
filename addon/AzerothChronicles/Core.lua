-- Azeroth Chronicles: core storage and helpers.
-- This addon only OBSERVES events the game exposes to addons and writes them to SavedVariables.
-- It never automates gameplay, never reads combat-log secrets, and makes no network requests
-- (addons cannot). A website upload or the companion app moves the data out of the game.

local ADDON, ns = ...
ns.VERSION = "1.0.0"
ns.SCHEMA = 1
ns.MAX_RECORDS = 5000

local DEFAULTS = {
  recordEncounters = true,
  recordDungeonBosses = true,
  recordWipes = true,
  recordLoot = true,
  minLootQuality = 4, -- 4 = epic
  recordCollectibles = true,
  recordAchievements = true,
  recordDeaths = true,
  chatNotices = true,
}
ns.DEFAULTS = DEFAULTS

-- Secret values (Midnight+) must never be inspected or stored. Treat them as "unknown".
local issecret = _G.issecretvalue
function ns.clean(v)
  if v == nil then return nil end
  if issecret and issecret(v) then return nil end
  return v
end

function ns.now()
  return GetServerTime and GetServerTime() or time()
end

local REGIONS = { [1] = "us", [2] = "kr", [3] = "eu", [4] = "tw", [5] = "cn" }

local CLASS_NAMES = {
  DEATHKNIGHT = "Death Knight", DEMONHUNTER = "Demon Hunter", DRUID = "Druid", EVOKER = "Evoker",
  HUNTER = "Hunter", MAGE = "Mage", MONK = "Monk", PALADIN = "Paladin", PRIEST = "Priest",
  ROGUE = "Rogue", SHAMAN = "Shaman", WARLOCK = "Warlock", WARRIOR = "Warrior",
}

local function prettyToken(token)
  if not token then return nil end
  local s = token:gsub("(%l)(%u)", "%1 %2")
  return s
end

function ns.playerGUID()
  return ns.clean(UnitGUID("player"))
end

--- Snapshot of the logged-in character's identity (English class/race tokens, not localized names).
function ns.characterInfo()
  local guid = ns.playerGUID()
  if not guid then return nil end
  local name = ns.clean(UnitName("player"))
  local _, classFile = UnitClass("player")
  local _, raceFile = UnitRace("player")
  local faction = UnitFactionGroup("player")
  local spec
  if GetSpecialization and GetSpecializationInfo then
    local idx = GetSpecialization()
    if idx then
      local _, specName = GetSpecializationInfo(idx)
      spec = specName
    end
  end
  local regionId = GetCurrentRegion and GetCurrentRegion() or 1
  return {
    guid = guid,
    name = name,
    realm = GetRealmName(),
    region = REGIONS[regionId] or "us",
    class = CLASS_NAMES[classFile] or classFile,
    race = prettyToken(raceFile),
    faction = faction,
    level = UnitLevel("player"),
    spec = spec,
  }
end

--- Current group members (excluding the player) as {name, realm} — only non-secret values.
function ns.roster()
  local out = {}
  local n = GetNumGroupMembers and GetNumGroupMembers() or 0
  if n == 0 then return out end
  local prefix = IsInRaid() and "raid" or "party"
  local limit = IsInRaid() and n or (n - 1)
  for i = 1, limit do
    local unit = prefix .. i
    if UnitExists(unit) and not UnitIsUnit(unit, "player") then
      local name, realm = UnitName(unit)
      name, realm = ns.clean(name), ns.clean(realm)
      if name and name ~= "" and name ~= UNKNOWNOBJECT then
        out[#out + 1] = { name = name, realm = (realm and realm ~= "") and realm or GetNormalizedRealmName() }
      end
    end
  end
  return out
end

-------------------------------------------------------------------------------------------------
-- Storage
-------------------------------------------------------------------------------------------------
local seen = {}

function ns.initDB()
  AzerothChroniclesDB = AzerothChroniclesDB or {}
  local db = AzerothChroniclesDB
  db.schema = ns.SCHEMA
  db.version = ns.VERSION
  db.characters = db.characters or {}
  db.records = db.records or {}
  db.settings = db.settings or {}
  for k, v in pairs(DEFAULTS) do
    if db.settings[k] == nil then db.settings[k] = v end
  end
  wipe(seen)
  for _, r in ipairs(db.records) do
    if r.id then seen[r.id] = true end
  end
  ns.db = db
end

function ns.setting(key)
  return ns.db and ns.db.settings[key]
end

function ns.rememberCharacter()
  local info = ns.characterInfo()
  if info then
    ns.db.characters[info.guid] = info
  end
  return info
end

--- Append a record unless its stable id was already recorded. Returns true when stored.
function ns.addRecord(rec)
  if not rec or not rec.id or seen[rec.id] then return false end
  rec.character_guid = rec.character_guid or ns.playerGUID()
  local records = ns.db.records
  records[#records + 1] = rec
  seen[rec.id] = true
  -- Bound memory: drop the oldest records (the website ingests idempotently, so re-exports are safe).
  local overflow = #records - ns.MAX_RECORDS
  if overflow > 0 then
    for _ = 1, overflow do
      local old = table.remove(records, 1)
      if old and old.id then seen[old.id] = nil end
    end
  end
  ns.db.lastWrite = ns.now()
  if ns.onRecord then ns.onRecord(rec) end
  return true
end

function ns.hasRecord(id)
  return seen[id] == true
end

function ns.shortGUID()
  local guid = ns.playerGUID() or "unknown"
  return (guid:gsub("^Player%-", ""))
end

function ns.print(msg)
  if ns.setting("chatNotices") ~= false then
    DEFAULT_CHAT_FRAME:AddMessage("|cffd6a94aAzeroth Chronicles|r: " .. msg)
  end
end

ns.wipe = wipe
