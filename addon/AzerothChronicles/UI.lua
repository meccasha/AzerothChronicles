-- Slash commands, a status/export window and an options panel.
local _, ns = ...

local function counts()
  local c = { encounter = 0, kills = 0, wipes = 0, loot = 0, achievement = 0, dungeon_complete = 0, mount = 0, toy = 0 }
  for _, r in ipairs(ns.db.records) do
    c[r.type] = (c[r.type] or 0) + 1
    if r.type == "encounter" then
      if r.success then c.kills = c.kills + 1 else c.wipes = c.wipes + 1 end
    end
  end
  return c
end

local function statusLines()
  local c = counts()
  local lines = {
    string.format("Version %s - %d records stored (max %d).", ns.VERSION, #ns.db.records, ns.MAX_RECORDS),
    string.format("Boss kills %d, wipes %d, loot %d, achievements %d, M+ runs %d, collectibles %d.",
      c.kills, c.wipes, c.loot, c.achievement, c.dungeon_complete, c.mount + c.toy),
    ns.db.lastExport and ("Last in-game export: " .. date("%Y-%m-%d %H:%M", ns.db.lastExport.at) ..
      string.format(" (%d records)", ns.db.lastExport.count)) or "Not exported in-game yet.",
    "Data leaves the game only when SavedVariables are written (logout or /reload) and then uploaded.",
  }
  if ns.db.lastError then lines[#lines + 1] = "|cffff6060Last handler error: " .. ns.db.lastError .. "|r" end
  return lines
end

-------------------------------------------------------------------------------------------------
-- Export window
-------------------------------------------------------------------------------------------------
local exportFrame
local function showExport(onlyNew)
  local since = onlyNew and ns.db.lastExport and ns.db.lastExport.index or 0
  if since > #ns.db.records then since = 0 end
  local json, n = ns.buildExport(since)
  if not exportFrame then
    exportFrame = CreateFrame("Frame", "AzerothChroniclesExportFrame", UIParent, "BasicFrameTemplateWithInset")
    exportFrame:SetSize(560, 420)
    exportFrame:SetPoint("CENTER")
    exportFrame:SetMovable(true)
    exportFrame:EnableMouse(true)
    exportFrame:RegisterForDrag("LeftButton")
    exportFrame:SetScript("OnDragStart", exportFrame.StartMoving)
    exportFrame:SetScript("OnDragStop", exportFrame.StopMovingOrSizing)
    exportFrame:SetFrameStrata("DIALOG")
    exportFrame.title = exportFrame:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
    exportFrame.title:SetPoint("TOP", 0, -5)
    exportFrame.title:SetText("Azeroth Chronicles - Export")
    exportFrame.help = exportFrame:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    exportFrame.help:SetPoint("TOPLEFT", 14, -32)
    exportFrame.help:SetPoint("TOPRIGHT", -14, -32)
    exportFrame.help:SetJustifyH("LEFT")
    local scroll = CreateFrame("ScrollFrame", nil, exportFrame, "UIPanelScrollFrameTemplate")
    scroll:SetPoint("TOPLEFT", 14, -64)
    scroll:SetPoint("BOTTOMRIGHT", -32, 14)
    local box = CreateFrame("EditBox", nil, scroll)
    box:SetMultiLine(true)
    box:SetAutoFocus(true)
    box:SetFontObject(ChatFontNormal)
    box:SetWidth(500)
    box:SetScript("OnEscapePressed", function() exportFrame:Hide() end)
    scroll:SetScrollChild(box)
    exportFrame.box = box
  end
  exportFrame.help:SetText(string.format("%d record(s). Press Ctrl+A then Ctrl+C, and paste into Integrations > Import on the website.", n))
  exportFrame.box:SetText(json)
  exportFrame.box:HighlightText()
  exportFrame:Show()
  ns.db.lastExport = { at = ns.now(), index = #ns.db.records, count = n }
end
ns.showExport = showExport

-------------------------------------------------------------------------------------------------
-- Options panel (Settings API, guarded for client differences)
-------------------------------------------------------------------------------------------------
local OPTIONS = {
  { "recordEncounters", "Record raid boss encounters" },
  { "recordDungeonBosses", "Record dungeon boss encounters" },
  { "recordWipes", "Record wipes (failed pulls)" },
  { "recordDeaths", "Count my own deaths during boss pulls" },
  { "recordLoot", "Record my notable loot (epic and better)" },
  { "recordCollectibles", "Record new mounts and toys" },
  { "recordAchievements", "Record achievements as I earn them" },
  { "chatNotices", "Show chat notices when something is recorded" },
}

local function registerOptions()
  if not (Settings and Settings.RegisterVerticalLayoutCategory and Settings.RegisterAddOnSetting) then return end
  local ok = pcall(function()
    local category = Settings.RegisterVerticalLayoutCategory("Azeroth Chronicles")
    for _, opt in ipairs(OPTIONS) do
      local key, label = opt[1], opt[2]
      local setting = Settings.RegisterAddOnSetting(category, "AZCHRON_" .. key, key, ns.db.settings,
        type(ns.DEFAULTS[key]), label, ns.DEFAULTS[key])
      Settings.CreateCheckbox(category, setting, label)
    end
    Settings.RegisterAddOnCategory(category)
    ns.settingsCategory = category
  end)
  if not ok then ns.settingsCategory = nil end
end

ns.onLogin = function()
  registerOptions()
end

-------------------------------------------------------------------------------------------------
-- Slash commands
-------------------------------------------------------------------------------------------------
SLASH_AZCHRON1 = "/achron"
SLASH_AZCHRON2 = "/azerothchronicles"
SlashCmdList.AZCHRON = function(input)
  local cmd, arg = (input or ""):match("^(%S*)%s*(.-)$")
  cmd = (cmd or ""):lower()
  if cmd == "export" then
    showExport(arg == "new")
  elseif cmd == "options" or cmd == "config" then
    if ns.settingsCategory and Settings.OpenToCategory then
      Settings.OpenToCategory(ns.settingsCategory:GetID())
    else
      ns.print("Options panel unavailable; use /achron toggle <setting>.")
    end
  elseif cmd == "toggle" and ns.DEFAULTS[arg] ~= nil and type(ns.DEFAULTS[arg]) == "boolean" then
    ns.db.settings[arg] = not ns.db.settings[arg]
    ns.print(string.format("%s = %s", arg, tostring(ns.db.settings[arg])))
  elseif cmd == "prune" then
    -- Remove records older than N days (default 90) that were already exported in-game.
    local days = tonumber(arg) or 90
    local cutoff = ns.now() - days * 86400
    local kept, removed = {}, 0
    for _, r in ipairs(ns.db.records) do
      local t = r.end_time or r.looted_at or r.earned_at or r.completed_at or r.learned_at or 0
      if t < cutoff then removed = removed + 1 else kept[#kept + 1] = r end
    end
    ns.db.records = kept
    ns.db.lastExport = nil
    ns.initDB()
    ns.print(string.format("Pruned %d record(s) older than %d days. Upload first if you haven't!", removed, days))
  else
    for _, line in ipairs(statusLines()) do ns.print(line) end
    ns.print("Commands: /achron export [new] | options | toggle <setting> | prune [days]")
  end
end
