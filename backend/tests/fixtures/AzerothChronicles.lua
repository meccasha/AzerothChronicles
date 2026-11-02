
AzerothChroniclesDB = {
	["schema"] = 1,
	["version"] = "1.0.0",
	["lastWrite"] = 1772665200,
	["settings"] = {
		["minimapButton"] = true,
		["recordEpicLoot"] = true,
	},
	["characters"] = {
		["Player-3676-0ABC1234"] = {
			["guid"] = "Player-3676-0ABC1234",
			["name"] = "Thalindra",
			["realm"] = "Area 52",
			["region"] = "us",
			["class"] = "Hunter",
			["race"] = "Night Elf",
			["faction"] = "Alliance",
			["level"] = 80,
			["spec"] = "Marksmanship",
		},
	},
	["records"] = {
		{
			["id"] = "enc-3676-0ABC1234-3009-15-1772660000",
			["type"] = "encounter",
			["character_guid"] = "Player-3676-0ABC1234",
			["encounter_id"] = 3009,
			["encounter_name"] = "Test Colossus",
			["instance_name"] = "Fixture Citadel",
			["instance_id"] = 2769,
			["instance_type"] = "raid",
			["difficulty_id"] = 15,
			["difficulty_name"] = "Heroic",
			["group_size"] = 18,
			["success"] = false,
			["start_time"] = 1772659700,
			["end_time"] = 1772660000,
			["deaths"] = 1,
			["roster"] = {
				{
					["name"] = "Groupmate",
					["realm"] = "Area52",
				}, -- [1]
			},
		}, -- [1]
		{
			["id"] = "enc-3676-0ABC1234-3009-15-1772661000",
			["type"] = "encounter",
			["character_guid"] = "Player-3676-0ABC1234",
			["encounter_id"] = 3009,
			["encounter_name"] = "Test Colossus",
			["instance_name"] = "Fixture Citadel",
			["instance_type"] = "raid",
			["difficulty_id"] = 15,
			["difficulty_name"] = "Heroic",
			["group_size"] = 18,
			["success"] = true,
			["start_time"] = 1772660600,
			["end_time"] = 1772661000,
			["deaths"] = 0,
			["roster"] = {
			},
		}, -- [2]
		{
			["id"] = "loot-3676-0ABC1234-212400-1772661050",
			["type"] = "loot",
			["character_guid"] = "Player-3676-0ABC1234",
			["item_id"] = 212400,
			["item_name"] = "Fixture Longbow of \"Testing\"",
			["quality"] = 4,
			["item_class"] = "Weapon",
			["item_subclass"] = "Bows",
			["item_level"] = 639,
			["encounter_id"] = 3009,
			["instance_name"] = "Fixture Citadel",
			["difficulty_name"] = "Heroic",
			["looted_at"] = 1772661050,
		}, -- [3]
		{
			["id"] = "ach-3676-0ABC1234-40000",
			["type"] = "achievement",
			["character_guid"] = "Player-3676-0ABC1234",
			["achievement_id"] = 40000,
			["name"] = "Fixture: Colossus Toppler",
			["points"] = 10,
			["earned_at"] = 1772661001,
		}, -- [4]
		{
			["id"] = "mount-3676-0ABC1234-2001",
			["type"] = "mount",
			["character_guid"] = "Player-3676-0ABC1234",
			["collectible_id"] = 2001,
			["name"] = "Fixture Gryphon",
			["learned_at"] = 1772662000,
		}, -- [5]
	},
}
