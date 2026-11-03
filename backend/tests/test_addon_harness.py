"""Executes the real addon Lua under Lua 5.1 with a mocked WoW API, then checks that its output is
accepted by the backend's SavedVariables parser and ingestion schema."""

import json
from pathlib import Path

import pytest

from app.schemas.ingest import IngestEnvelope
from app.services.lua_savedvariables import parse_savedvariables, savedvariables_to_envelope
from tests.conftest import create_group

lua51 = pytest.importorskip("lupa.lua51")

ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / "addon" / "AzerothChronicles"
MOCK = Path(__file__).parent / "wow_mock.lua"


def boot():
    lua = lua51.LuaRuntime(unpack_returned_tuples=True)
    lua.execute(MOCK.read_text())
    ns = lua.table()
    loader = lua.eval("function(src, name, ns) local f = assert(loadstring(src, name)); f('AzerothChronicles', ns) end")
    toc = (ADDON / "AzerothChronicles.toc").read_text().splitlines()
    for fname in [ln.strip() for ln in toc if ln.strip().endswith(".lua")]:
        loader((ADDON / fname).read_text(), fname, ns)
    g = lua.globals()
    fire = g.T.fire
    fire("ADDON_LOADED", "AzerothChronicles")
    fire("PLAYER_LOGIN")
    return lua, g, ns, fire


def play_session(lua, g, fire):
    t = g.T
    lua.execute('T.group = { party1 = { "Groupmate", "Area52" }, party2 = { "Secretive", nil } }')
    lua.execute('T.secret["Secretive"] = true')  # secret values must be dropped, not stored
    fire("ENCOUNTER_START", 3009, "Test Colossus", 15, 20)
    fire("PLAYER_DEAD")
    t.now = t.now + 300
    fire("ENCOUNTER_END", 3009, "Test Colossus", 15, 20, 0)
    t.now = t.now + 600
    fire("ENCOUNTER_START", 3009, "Test Colossus", 15, 20)
    t.now = t.now + 300
    fire("ENCOUNTER_END", 3009, "Test Colossus", 15, 20, 1)
    link = "|cffa335ee|Hitem:212400::::::::80:::::|h[Item 212400]|h|r"
    fire("ENCOUNTER_LOOT_RECEIVED", 3009, 212400, link, 1, "Thalindra-Area52", "HUNTER")
    fire("CHAT_MSG_LOOT", f"You receive loot: {link}.")  # same drop again -> deduplicated
    fire("CHAT_MSG_LOOT", "You receive loot: |cff1eff00|Hitem:1::::|h[Item 1]|h|r.")  # uncommon -> ignored
    fire("CHAT_MSG_LOOT", f"Groupmate receives loot: {link}.")  # someone else's -> ignored
    fire("ACHIEVEMENT_EARNED", 40000, False)
    fire("ACHIEVEMENT_EARNED", 40001, True)  # already earned account-wide -> ignored
    fire("NEW_MOUNT_ADDED", 2001)
    t.now = t.now + 3600
    lua.execute('T.instance = { "Fixture Depths", "party", 8, "Mythic Keystone", 5, 0, false, 2600 }')
    lua.execute("T.uiMap = 2600")
    fire("CHALLENGE_MODE_COMPLETED")
    fire("ENCOUNTER_END", 9999, "Ignored scenario boss", 1, 5, 1)  # no START -> deaths unknown


def test_addon_records_expected_events():
    lua, g, ns, fire = boot()
    play_session(lua, g, fire)
    db = g.AzerothChroniclesDB
    records = [db.records[i] for i in range(1, len(db.records) + 1)]
    types = [r.type for r in records]
    assert types == ["encounter", "encounter", "loot", "achievement", "mount", "dungeon_complete", "encounter"]
    wipe, kill = records[0], records[1]
    assert wipe.success is False and wipe.deaths == 1 and kill.success is True and kill.deaths == 0
    assert kill.difficulty_name == "Heroic" and kill.start_time is not None
    assert kill.journal_instance_id == 9901 and kill.journal_encounter_id == 99011  # exact artwork lookups
    mplus = records[5]
    assert mplus.instance_id == 2600 and mplus.journal_instance_id == 9902
    assert records[4].icon_file_id == 132265  # mount icon FileDataID
    roster = [kill.roster[i] for i in range(1, len(kill.roster) + 1)]
    assert [(r.name, r.realm) for r in roster] == [("Groupmate", "Area52")]
    assert records[2].quality == 4 and records[2].item_level == 639 and records[2].icon_file_id == 12345
    assert records[2].icon is None
    assert records[-1].deaths is None and records[-1].start_time is None
    assert db.lastError is None
    char = db.characters["Player-3676-0ABC1234"]
    assert (char["class"], char.race, char.region, char.spec) == ("Hunter", "Night Elf", "us", "Marksmanship")


def test_reloading_keeps_dedup_index():
    lua, g, ns, fire = boot()
    play_session(lua, g, fire)
    n = len(g.AzerothChroniclesDB.records)
    fire("ADDON_LOADED", "AzerothChronicles")  # simulate /reload: seen-index rebuilt from SavedVariables
    fire("NEW_MOUNT_ADDED", 2001)  # same stable id as before the reload
    fire("ACHIEVEMENT_EARNED", 40000, False)
    assert len(g.AzerothChroniclesDB.records) == n


def test_outputs_are_accepted_by_backend(alice):
    lua, g, ns, fire = boot()
    play_session(lua, g, fire)
    sv = g.T.serialize("AzerothChroniclesDB", g.AzerothChroniclesDB)
    env = IngestEnvelope.model_validate(savedvariables_to_envelope(parse_savedvariables(sv)))
    assert len(env.records) == 7
    exported = ns.buildExport(0)
    exported = exported[0] if isinstance(exported, tuple) else exported
    env2 = IngestEnvelope.model_validate(json.loads(exported))
    assert [r.id for r in env2.records] == [r.id for r in env.records]

    gid = create_group(alice)["id"]
    r = alice.post("/api/ingest/savedvariables", content=sv.encode()).json()
    assert r["normalized"] == 7 and r["rejected"] == 0, r
    ov = alice.get(f"/api/groups/{gid}/stats/overview").json()
    # two raid pulls of the same boss (1 wipe, 1 kill) + one dungeon boss kill
    assert ov["boss_kills_confirmed"] == 2 and ov["wipes_recorded"] == 1 and ov["mounts"] == 1
    assert ov["dungeons_recorded"] == 1 and ov["notable_loot"] == 2  # epic + mount
    # the in-game JSON export of the same data is recognised as duplicates
    again = alice.post("/api/ingest/envelope", content=exported, headers={"content-type": "application/json"}).json()
    assert again["duplicates"] == 7 and again["normalized"] == 0


def test_export_json_escaping():
    lua, g, ns, fire = boot()
    rec = '{ id = "x", type = "achievement", name = "Quote \\" and \\n newline" }'
    g.AzerothChroniclesDB.records[1] = lua.eval(rec)
    out = ns.buildExport(0)
    out = out[0] if isinstance(out, tuple) else out
    assert json.loads(out)["records"][0]["name"] == 'Quote " and \n newline'
