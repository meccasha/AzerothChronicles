-- Minimal mock of the WoW client API surface used by the addon (test-only).
T = { now = 1772660000, events = {}, chat = {}, secret = {} }
local frames = {}
function GetServerTime() return T.now end
function time() return T.now end
function date(fmt, t) return os.date(fmt, t) end
function wipe(t) for k in pairs(t) do t[k] = nil end return t end
function issecretvalue(v) return T.secret[v] == true end
UNKNOWNOBJECT = "Unknown"
LOOT_ITEM_SELF = "You receive loot: %s."
LOOT_ITEM_PUSHED_SELF = "You receive item: %s."
DEFAULT_CHAT_FRAME = { AddMessage = function(_, m) table.insert(T.chat, m) end }
UIParent = {}
SlashCmdList = {}

function CreateFrame()
  local f = { events = {} }
  function f:RegisterEvent(e) if e == "REMOVED_EVENT" then error("unknown event") end self.events[e] = true end
  function f:SetScript(_, fn) self.onEvent = fn end
  table.insert(frames, f)
  return f
end
function T.fire(event, ...)
  for _, f in ipairs(frames) do
    if f.events[event] and f.onEvent then f.onEvent(f, event, ...) end
  end
end

T.player = { guid = "Player-3676-0ABC1234", name = "Thalindra" }
function UnitGUID(u) if u == "player" then return T.player.guid end end
function UnitName(u)
  if u == "player" then return T.player.name end
  local m = T.group[u]
  if m then return m[1], m[2] end
end
function UnitClass() return "Hunter", "HUNTER", 3 end
function UnitRace() return "Night Elf", "NightElf", 4 end
function UnitFactionGroup() return "Alliance", "Alliance" end
function UnitLevel() return 80 end
function GetSpecialization() return 2 end
function GetSpecializationInfo() return 254, "Marksmanship" end
function GetCurrentRegion() return 1 end
function GetRealmName() return "Area 52" end
function GetNormalizedRealmName() return "Area52" end
T.group = {}
function GetNumGroupMembers() local n = 0 for _ in pairs(T.group) do n = n + 1 end return n == 0 and 0 or n + 1 end
function IsInRaid() return false end
function UnitExists(u) return T.group[u] ~= nil end
function UnitIsUnit(a, b) return a == b end
T.instance = { "Fixture Citadel", "raid", 15, "Heroic", 20, 0, false, 2769 }
function GetInstanceInfo() return unpack(T.instance) end
function GetDifficultyInfo(id) return ({ [14] = "Normal", [15] = "Heroic", [16] = "Mythic" })[id] end
function Ambiguate(n) return (n:gsub("%-.*$", "")) end

function GetAchievementInfo(id) return id, "Fixture Feat " .. id, 10, true, 1, 1, 26, "Do the thing." end
function GetAchievementCategory() return 15 end
function GetCategoryInfo() return "Raids", -1 end

C_Item = {}
function C_Item.GetItemInfoInstant(link) return tonumber(link:match("item:(%d+)")) end
function C_Item.GetItemInfo(link)
  local id = tonumber(link:match("item:(%d+)"))
  local q = id == 1 and 2 or 4
  return "Item " .. id, link, q, 600, 70, "Armor", "Plate", 1, "INVTYPE_HEAD", 12345
end
function C_Item.GetDetailedItemLevelInfo() return 639 end
Item = { CreateFromItemLink = function(_, link) return { ContinueOnItemLoad = function(_, cb) cb() end } end }
C_MountJournal = { GetMountInfoByID = function(id) return "Fixture Gryphon", 100 end }
C_ChallengeMode = {
  GetChallengeCompletionInfo = function() return { mapChallengeModeID = 501, level = 12, time = 1700000, onTime = true } end,
  GetMapUIInfo = function() return "Fixture Depths" end,
}

-- Serialize a table the way WoW writes SavedVariables.
function T.serialize(name, v)
  local out = {}
  local function w(s) out[#out + 1] = s end
  local function val(x, ind)
    local t = type(x)
    if t == "string" then w(string.format("%q", x))
    elseif t == "number" or t == "boolean" then w(tostring(x))
    elseif t == "table" then
      w("{\n")
      local keys = {}
      for k in pairs(x) do keys[#keys + 1] = k end
      table.sort(keys, function(a, b) return tostring(a) < tostring(b) end)
      for _, k in ipairs(keys) do
        w(ind .. "\t[" .. (type(k) == "string" and string.format("%q", k) or tostring(k)) .. "] = ")
        val(x[k], ind .. "\t")
        w(",\n")
      end
      w(ind .. "}")
    else w("nil") end
  end
  w(name .. " = ")
  val(v, "")
  w("\n")
  return table.concat(out)
end
