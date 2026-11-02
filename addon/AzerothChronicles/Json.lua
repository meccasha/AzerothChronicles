-- Minimal JSON encoder for the in-game export string (records are plain tables of scalars/arrays).
local _, ns = ...

local escapes = { ['"'] = '\\"', ["\\"] = "\\\\", ["\b"] = "\\b", ["\f"] = "\\f", ["\n"] = "\\n", ["\r"] = "\\r", ["\t"] = "\\t" }

local function escapeString(s)
  return '"' .. s:gsub('[%c"\\]', function(c)
    return escapes[c] or string.format("\\u%04x", c:byte())
  end) .. '"'
end

local function isArray(t)
  local n = 0
  for k in pairs(t) do
    if type(k) ~= "number" then return false end
    n = n + 1
  end
  return n == #t
end

local encode
encode = function(v, depth)
  depth = (depth or 0) + 1
  if depth > 20 then error("JSON nesting too deep") end
  local t = type(v)
  if t == "nil" then return "null" end
  if t == "boolean" then return v and "true" or "false" end
  if t == "number" then
    if v ~= v or v == math.huge or v == -math.huge then return "null" end
    if math.floor(v) == v then return string.format("%d", v) end
    return string.format("%.14g", v)
  end
  if t == "string" then return escapeString(v) end
  if t == "table" then
    local parts = {}
    if next(v) == nil then return "[]" end
    if isArray(v) then
      for i = 1, #v do parts[#parts + 1] = encode(v[i], depth) end
      return "[" .. table.concat(parts, ",") .. "]"
    end
    local keys = {}
    for k in pairs(v) do keys[#keys + 1] = tostring(k) end
    table.sort(keys)
    for _, k in ipairs(keys) do
      parts[#parts + 1] = escapeString(k) .. ":" .. encode(v[k], depth)
    end
    return "{" .. table.concat(parts, ",") .. "}"
  end
  return "null"
end

ns.toJSON = function(v) return encode(v, 0) end

--- Build the normalized ingestion envelope (see docs/ingestion-format.md).
function ns.buildExport(sinceIndex)
  local chars = {}
  for _, c in pairs(ns.db.characters) do chars[#chars + 1] = c end
  local recs = {}
  for i = (sinceIndex or 0) + 1, #ns.db.records do recs[#recs + 1] = ns.db.records[i] end
  return ns.toJSON({
    format = "azeroth-chronicles/v1",
    source = "addon",
    addon_version = ns.VERSION,
    exported_at = ns.now(),
    characters = chars,
    records = recs,
  }), #recs
end
