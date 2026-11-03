-- Event collection. Every API used here is guarded: if Blizzard removes or restricts something,
-- the addon degrades to recording less rather than erroring.
local _, ns = ...

local frame = CreateFrame("Frame")
ns.frame = frame
local handlers = {}
local current -- active encounter {id, name, difficultyID, start, deaths}

local function register(event, fn)
  handlers[event] = fn
  -- RegisterEvent errors for unknown/removed events on some clients; pcall keeps us loading.
  local ok = pcall(frame.RegisterEvent, frame, event)
  if not ok then handlers[event] = nil end
end

frame:SetScript("OnEvent", function(_, event, ...)
  local fn = handlers[event]
  if fn then
    local ok, err = pcall(fn, ...)
    if not ok and ns.db then
      ns.db.lastError = string.format("%s: %s", event, tostring(err))
    end
  end
end)

local function instanceInfo()
  local name, instanceType, difficultyID, difficultyName, maxPlayers, _, _, instanceID = GetInstanceInfo()
  return ns.clean(name), ns.clean(instanceType), ns.clean(difficultyID), ns.clean(difficultyName), maxPlayers,
    ns.clean(instanceID)
end

--- Encounter Journal ids for the current instance (and boss), so the website can show the exact
--- dungeon artwork and boss portrait from Blizzard's Game Data API. Returns nils when unavailable.
local function journalIds(dungeonEncounterID)
  local jInstance, jEncounter
  local ok = pcall(function()
    if C_Map and C_Map.GetBestMapForUnit and EJ_GetInstanceForMap then
      local uiMap = C_Map.GetBestMapForUnit("player")
      if uiMap then jInstance = ns.clean(EJ_GetInstanceForMap(uiMap)) end
    end
    if jInstance == 0 then jInstance = nil end
    if jInstance and dungeonEncounterID and EJ_GetEncounterInfoByIndex then
      for i = 1, 40 do
        local name, _, jEncID, _, _, _, dungeonEncID = EJ_GetEncounterInfoByIndex(i, jInstance)
        if not name then break end
        if ns.clean(dungeonEncID) == dungeonEncounterID then
          jEncounter = ns.clean(jEncID)
          break
        end
      end
    end
  end)
  if not ok then return nil, nil end
  return jInstance, jEncounter
end
ns.journalIds = journalIds

-------------------------------------------------------------------------------------------------
-- Lifecycle
-------------------------------------------------------------------------------------------------
register("ADDON_LOADED", function(name)
  if name ~= "AzerothChronicles" then return end
  ns.initDB()
end)

register("PLAYER_LOGIN", function()
  if not ns.db then ns.initDB() end
  ns.rememberCharacter()
  if ns.onLogin then ns.onLogin() end
end)

register("PLAYER_LEVEL_UP", function() ns.rememberCharacter() end)
register("PLAYER_SPECIALIZATION_CHANGED", function(unit)
  if unit == "player" then ns.rememberCharacter() end
end)

-------------------------------------------------------------------------------------------------
-- Boss encounters (ENCOUNTER_START / ENCOUNTER_END) and personal deaths (PLAYER_DEAD)
-------------------------------------------------------------------------------------------------
register("ENCOUNTER_START", function(encounterID, encounterName, difficultyID, groupSize)
  encounterID = ns.clean(encounterID)
  if not encounterID then return end
  current = {
    id = encounterID,
    name = ns.clean(encounterName),
    difficultyID = ns.clean(difficultyID),
    groupSize = ns.clean(groupSize),
    start = ns.now(),
    deaths = 0,
  }
end)

register("PLAYER_DEAD", function()
  if current and ns.setting("recordDeaths") then
    current.deaths = current.deaths + 1
  end
end)

register("ENCOUNTER_END", function(encounterID, encounterName, difficultyID, groupSize, success)
  encounterID, success = ns.clean(encounterID), ns.clean(success)
  if not encounterID or success == nil then current = nil; return end
  if not ns.setting("recordEncounters") then current = nil; return end
  local instName, instType, _, diffName, _, instID = instanceInfo()
  if instType ~= "raid" and instType ~= "party" then current = nil; return end
  if instType == "party" and not ns.setting("recordDungeonBosses") then current = nil; return end
  local won = success == 1 or success == true
  if not won and not ns.setting("recordWipes") then current = nil; return end

  local endTime = ns.now()
  local matching = current and current.id == encounterID
  local jInstance, jEncounter = journalIds(encounterID)
  difficultyID = ns.clean(difficultyID)
  if GetDifficultyInfo and difficultyID then
    diffName = GetDifficultyInfo(difficultyID) or diffName
  end
  local rec = {
    id = string.format("enc-%s-%d-%d-%d", ns.shortGUID(), encounterID, difficultyID or 0, endTime),
    type = "encounter",
    encounter_id = encounterID,
    encounter_name = ns.clean(encounterName) or (matching and current.name) or ("Encounter " .. encounterID),
    instance_name = instName,
    instance_id = instID,
    instance_type = instType,
    journal_instance_id = jInstance,
    journal_encounter_id = jEncounter,
    difficulty_id = difficultyID,
    difficulty_name = diffName,
    group_size = ns.clean(groupSize),
    success = won,
    start_time = matching and current.start or nil,
    end_time = endTime,
    roster = ns.roster(),
    -- Only meaningful if we saw the start of the pull; otherwise unknown (nil), never 0.
    deaths = (matching and ns.setting("recordDeaths")) and current.deaths or nil,
  }
  current = nil
  if ns.addRecord(rec) and won then
    ns.print(string.format("Recorded %s (%s).", rec.encounter_name, diffName or "?"))
  end
end)

-------------------------------------------------------------------------------------------------
-- Mythic+ completion
-------------------------------------------------------------------------------------------------
register("CHALLENGE_MODE_COMPLETED", function()
  if not C_ChallengeMode then return end
  local mapID, level, timeMs, onTime
  if C_ChallengeMode.GetChallengeCompletionInfo then
    local info = C_ChallengeMode.GetChallengeCompletionInfo()
    if info then
      mapID, level, timeMs, onTime = info.mapChallengeModeID, info.level, info.time, info.onTime
    end
  elseif C_ChallengeMode.GetCompletionInfo then
    mapID, level, timeMs, onTime = C_ChallengeMode.GetCompletionInfo()
  end
  mapID, level = ns.clean(mapID), ns.clean(level)
  if not mapID then return end
  local name = C_ChallengeMode.GetMapUIInfo and C_ChallengeMode.GetMapUIInfo(mapID) or ("Dungeon " .. mapID)
  local now = ns.now()
  local _, _, _, _, _, instID = instanceInfo()
  local jInstance = journalIds(nil)
  ns.addRecord({
    id = string.format("mplus-%s-%d-%d", ns.shortGUID(), mapID, now),
    type = "dungeon_complete",
    map_id = mapID,
    instance_id = instID,
    journal_instance_id = jInstance,
    name = name,
    keystone_level = level,
    on_time = ns.clean(onTime),
    completed_at = now,
    duration_ms = ns.clean(timeMs),
    roster = ns.roster(),
  })
  ns.print(string.format("Recorded %s +%s.", name, tostring(level)))
end)

-------------------------------------------------------------------------------------------------
-- Achievements
-------------------------------------------------------------------------------------------------
local FEATS_OF_STRENGTH = 81

register("ACHIEVEMENT_EARNED", function(achievementID, alreadyEarned)
  achievementID = ns.clean(achievementID)
  if not achievementID or alreadyEarned or not ns.setting("recordAchievements") then return end
  local _, name, points, _, _, _, _, description = GetAchievementInfo(achievementID)
  local fos = false
  if GetAchievementCategory and GetCategoryInfo then
    local cat = GetAchievementCategory(achievementID)
    local _, parent = GetCategoryInfo(cat or 0)
    fos = cat == FEATS_OF_STRENGTH or parent == FEATS_OF_STRENGTH
  end
  ns.addRecord({
    id = string.format("ach-%s-%d", ns.shortGUID(), achievementID),
    type = "achievement",
    achievement_id = achievementID,
    name = name or ("Achievement " .. achievementID),
    points = points or 0,
    description = description,
    feat_of_strength = fos,
    earned_at = ns.now(),
  })
end)

-------------------------------------------------------------------------------------------------
-- Loot (own loot only: attribution for other players is not reliable)
-------------------------------------------------------------------------------------------------
local function recordItem(itemLink, encounterID)
  if not itemLink or not ns.setting("recordLoot") then return end
  local itemID = C_Item and C_Item.GetItemInfoInstant and C_Item.GetItemInfoInstant(itemLink)
  if not itemID then return end
  local now = ns.now()
  local id = string.format("loot-%s-%d-%d", ns.shortGUID(), itemID, math.floor(now / 60))
  if ns.hasRecord(id) then return end -- ENCOUNTER_LOOT_RECEIVED and CHAT_MSG_LOOT can both fire
  local instName, _, _, diffName = instanceInfo()

  local function store()
    local name, _, quality, _, _, itemType, itemSubType, _, _, icon = C_Item.GetItemInfo(itemLink)
    if not name or not quality then return end
    if quality < (ns.setting("minLootQuality") or 4) then return end
    local ilvl = C_Item.GetDetailedItemLevelInfo and C_Item.GetDetailedItemLevelInfo(itemLink)
    if ns.addRecord({
      id = id, type = "loot", item_id = itemID, item_name = name, quality = quality,
      item_class = itemType, item_subclass = itemSubType, item_level = ilvl,
      -- The client only exposes icon FileDataIDs; the website resolves the image via Battle.net.
      icon_file_id = tonumber(icon),
      encounter_id = encounterID, instance_name = instName, difficulty_name = diffName, looted_at = now,
    }) then
      ns.print("Recorded loot: " .. itemLink)
    end
  end

  -- Item data may not be cached yet; wait for it instead of recording partial info.
  if Item and Item.CreateFromItemLink then
    local item = Item:CreateFromItemLink(itemLink)
    item:ContinueOnItemLoad(store)
  else
    store()
  end
end

register("ENCOUNTER_LOOT_RECEIVED", function(encounterID, itemID, itemLink, quantity, playerName)
  playerName, itemLink = ns.clean(playerName), ns.clean(itemLink)
  if not playerName or not itemLink then return end
  if Ambiguate(playerName, "short") ~= UnitName("player") then return end
  recordItem(itemLink, ns.clean(encounterID))
end)

-- Build a Lua pattern from the localized LOOT_ITEM_SELF globals ("You receive loot: %s.").
local selfPatterns = {}
for _, g in ipairs({ "LOOT_ITEM_SELF", "LOOT_ITEM_SELF_MULTIPLE", "LOOT_ITEM_PUSHED_SELF", "LOOT_ITEM_PUSHED_SELF_MULTIPLE" }) do
  local s = _G[g]
  if type(s) == "string" then
    s = s:gsub("([%%%(%)%.%+%-%*%?%[%]%^%$])", "%%%1"):gsub("%%%%s", "(.+)"):gsub("%%%%d", "%%d+")
    selfPatterns[#selfPatterns + 1] = "^" .. s .. "$"
  end
end

register("CHAT_MSG_LOOT", function(msg)
  msg = ns.clean(msg)
  if not msg then return end
  for _, p in ipairs(selfPatterns) do
    local link = msg:match(p)
    if link then
      link = link:match("(|c.-|h.-|h|r)") or link
      recordItem(link, nil)
      return
    end
  end
end)

-------------------------------------------------------------------------------------------------
-- Collectibles
-------------------------------------------------------------------------------------------------
register("NEW_MOUNT_ADDED", function(mountID)
  mountID = ns.clean(mountID)
  if not mountID or not ns.setting("recordCollectibles") or not C_MountJournal then return end
  local name, _, icon = C_MountJournal.GetMountInfoByID(mountID)
  ns.addRecord({
    id = string.format("mount-%s-%d", ns.shortGUID(), mountID),
    type = "mount", collectible_id = mountID, name = name or ("Mount " .. mountID),
    icon_file_id = tonumber(ns.clean(icon)), learned_at = ns.now(),
  })
  ns.print("Recorded new mount: " .. tostring(name))
end)

register("NEW_TOY_ADDED", function(itemID)
  itemID = ns.clean(itemID)
  if not itemID or not ns.setting("recordCollectibles") or not C_ToyBox then return end
  local _, name = C_ToyBox.GetToyInfo(itemID)
  ns.addRecord({
    id = string.format("toy-%s-%d", ns.shortGUID(), itemID),
    type = "toy", collectible_id = itemID, item_id = itemID, name = name or ("Toy " .. itemID), learned_at = ns.now(),
  })
end)

ns._handlers = handlers -- exposed for the offline test harness
