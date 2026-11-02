from sqlalchemy import func, select

from app.models import EncounterAttempt, EncounterAttemptParticipant, IngestionRecord, LootEvent
from tests.conftest import char, create_group, encounter, envelope, join, ts

A_GUID, B_GUID, C_GUID = "Player-1-0000000A", "Player-1-0000000B", "Player-1-0000000C"


def setup_group(alice, bob, carol=None):
    gid = create_group(alice)["id"]
    join(alice, bob, gid)
    if carol:
        join(alice, carol, gid)
    return gid


def ingest(api, chars, records, source="addon"):
    r = api.post("/api/ingest/envelope", json=envelope(chars, records, source))
    assert r.status_code == 200, r.text
    return r.json()


def test_same_kill_reported_by_two_members_is_one_event(alice, bob, carol, db):
    gid = setup_group(alice, bob, carol)
    ingest(carol, [char(C_GUID, "Carolyn")], [])  # carol's character becomes known (no addon records)
    end = ts(2026, 3, 10)
    ra = ingest(alice, [char(A_GUID, "Alicia")],
                [encounter("a-1", A_GUID, success=True, end=end,
                           roster=[{"name": "Bobbo", "realm": "Area52"}, {"name": "Carolyn", "realm": "Area52"},
                                   {"name": "Stranger", "realm": "Area52"}])])
    rb = ingest(bob, [char(B_GUID, "Bobbo")],
                [encounter("b-1", B_GUID, success=True, end=end + 2, deaths=1,
                           roster=[{"name": "Alicia", "realm": "Area52"}])])
    assert ra["events_created"] == 1 and rb["events_merged"] == 1 and rb["events_created"] == 0
    assert db.scalar(select(func.count(EncounterAttempt.id))) == 1
    attempt = db.scalar(select(EncounterAttempt))
    assert attempt.reporter_count == 2
    events = alice.get(f"/api/groups/{gid}/events?types=boss_kill").json()["items"]
    assert len(events) == 1
    conf = {p["user"]["display_name"]: p["confirmation"] for p in events[0]["participants"]}
    # alice & bob reported from their own clients; carol only seen in a roster; stranger ignored
    assert conf == {"Alice": "confirmed", "Bob": "confirmed", "Carol": "roster"}
    deaths = {p.user_id: p.deaths for p in db.scalars(select(EncounterAttemptParticipant))}
    assert deaths[__import__("uuid").UUID(bob.user["id"])] == 1
    assert deaths[__import__("uuid").UUID(carol.user["id"])] is None  # unknown, not zero


def test_reupload_is_idempotent(alice, bob):
    setup_group(alice, bob)
    recs = [encounter("a-1", A_GUID, success=True, end=ts(2026, 3, 10))]
    first = ingest(alice, [char(A_GUID, "Alicia")], recs)
    second = ingest(alice, [char(A_GUID, "Alicia")], recs)
    assert first["normalized"] == 1 and second["duplicates"] == 1 and second["normalized"] == 0


def test_wipes_counted_and_first_kill_recomputed_out_of_order(alice, bob, db):
    gid = setup_group(alice, bob)
    c = [char(A_GUID, "Alicia")]
    # later kill imported first
    ingest(alice, c, [encounter("k2", A_GUID, success=True, end=ts(2026, 3, 17))])
    ingest(alice, c, [encounter("w1", A_GUID, success=False, end=ts(2026, 3, 10, 20)),
                      encounter("w2", A_GUID, success=False, end=ts(2026, 3, 10, 20, 10)),
                      encounter("k1", A_GUID, success=True, end=ts(2026, 3, 10, 21))])
    kills = alice.get(f"/api/groups/{gid}/events?types=boss_kill&order=asc&show_all=true").json()["items"]
    assert [k["extra"]["first_kill"] for k in kills] == [True, False]
    assert kills[0]["extra"]["wipes_before_kill"] == 2
    assert kills[1]["extra"]["wipes_before_kill"] == 0
    ov = alice.get(f"/api/groups/{gid}/stats/overview").json()
    assert ov["boss_kills_confirmed"] == 2 and ov["wipes_recorded"] == 2


def test_first_raid_kill_milestone_requires_two_members(alice, bob):
    gid = setup_group(alice, bob)
    ingest(bob, [char(B_GUID, "Bobbo")], [])
    ingest(alice, [char(A_GUID, "Alicia")], [encounter("solo", A_GUID, success=True, end=ts(2026, 3, 1), enc_id=1)])
    ingest(alice, [char(A_GUID, "Alicia")], [encounter("duo", A_GUID, success=True, end=ts(2026, 3, 2), enc_id=2,
                                                       roster=[{"name": "Bobbo"}])])
    evs = alice.get(f"/api/groups/{gid}/events?types=boss_kill&order=asc").json()["items"]
    assert evs[0]["highlight"] == "first_kill"
    assert evs[1]["highlight"] == "first_raid_kill"
    assert evs[1]["extra"]["milestone"] == "First raid boss defeated together"


def test_character_guid_cannot_be_hijacked(alice, bob):
    setup_group(alice, bob)
    ingest(alice, [char(A_GUID, "Alicia")], [])
    r = ingest(bob, [char(A_GUID, "Alicia")], [encounter("x", A_GUID, success=True, end=ts(2026, 3, 1))])
    assert r["rejected"] == 1 and r["events_created"] == 0


def test_validation_errors_are_rejected_with_422(alice):
    bad = envelope([char(A_GUID, "Alicia")], [{"id": "x1", "type": "encounter", "encounter_id": 1}])
    assert alice.post("/api/ingest/envelope", json=bad).status_code == 422
    assert alice.post("/api/ingest/envelope", json={"format": "other/v9"}).status_code == 422


def loot(rid, guid, item_id, name, quality, cls="Armor", sub="Plate", when=None, ilvl=None):
    return {"id": rid, "type": "loot", "character_guid": guid, "item_id": item_id, "item_name": name,
            "quality": quality, "item_class": cls, "item_subclass": sub, "item_level": ilvl,
            "looted_at": when or ts(2026, 3, 5)}


def test_loot_rules(alice, bob, db):
    gid = setup_group(alice, bob)
    c = [char(A_GUID, "Alicia")]
    r = ingest(alice, c, [loot("l1", A_GUID, 1, "Green Boots", 2), loot("l2", A_GUID, 2, "Purple Helm", 4),
                          loot("l3", A_GUID, 3, "Orange Blade", 5, "Weapon", "Sword"),
                          loot("l4", A_GUID, 4, "Reins of Testing", 4, "Miscellaneous", "Mount")])
    assert r["ignored"] == 1 and r["normalized"] == 3
    reasons = {row.item_name: row.notable_reason for row in db.scalars(select(LootEvent))}
    assert reasons == {"Purple Helm": "epic", "Orange Blade": "legendary", "Reins of Testing": "mount"}
    # turn off epics, add a wishlist rare and an excluded legendary
    alice.patch(f"/api/groups/{gid}", json={"settings": {"loot": {"record_epic": False}}})
    alice.post(f"/api/groups/{gid}/item-rules", json={"item_id": 10, "item_name": "Blue Ring", "rule": "wishlist"})
    alice.post(f"/api/groups/{gid}/item-rules", json={"item_id": 11, "item_name": "Meh Legendary", "rule": "exclude"})
    r = ingest(alice, c, [loot("l5", A_GUID, 5, "Another Epic", 4, when=ts(2026, 3, 6)),
                          loot("l6", A_GUID, 10, "Blue Ring", 3, when=ts(2026, 3, 6)),
                          loot("l7", A_GUID, 11, "Meh Legendary", 5, when=ts(2026, 3, 6))])
    assert r["ignored"] == 2 and r["normalized"] == 1
    museum = alice.get(f"/api/groups/{gid}/loot?quality=legendary").json()
    assert museum["total"] == 1 and museum["items"][0]["item_name"] == "Orange Blade"
    hl = alice.get(f"/api/groups/{gid}/loot/highlights").json()
    assert hl["first_legendary"]["item_name"] == "Orange Blade"
    assert hl["latest_mount"]["item_name"] == "Reins of Testing"


def test_epic_item_level_threshold(alice, bob):
    gid = setup_group(alice, bob)
    alice.patch(f"/api/groups/{gid}", json={"settings": {"loot": {"epic_min_item_level": 600}}})
    r = ingest(alice, [char(A_GUID, "Alicia")], [loot("l1", A_GUID, 1, "Old Epic", 4, ilvl=400),
                                                 loot("l2", A_GUID, 2, "New Epic", 4, ilvl=650)])
    assert r["ignored"] == 1 and r["normalized"] == 1


def test_achievement_merge_and_min_points(alice, bob, db):
    gid = setup_group(alice, bob)
    ach = {"type": "achievement", "achievement_id": 500, "name": "Big Deal", "points": 25}
    ingest(alice, [char(A_GUID, "Alicia")], [{**ach, "id": "a1", "character_guid": A_GUID,
                                              "earned_at": ts(2026, 3, 5, 21)},
                                             {"id": "a2", "type": "achievement", "character_guid": A_GUID,
                                              "achievement_id": 501, "name": "Tiny", "points": 5,
                                              "earned_at": ts(2026, 3, 5, 21)}])
    ingest(bob, [char(B_GUID, "Bobbo")], [{**ach, "id": "b1", "character_guid": B_GUID,
                                           "earned_at": ts(2026, 3, 5, 22)}])
    evs = alice.get(f"/api/groups/{gid}/events?types=achievement&show_all=true").json()["items"]
    assert len(evs) == 1  # "Tiny" (5 pts) is tracked but not posted
    assert {p["user"]["display_name"] for p in evs[0]["participants"]} == {"Alice", "Bob"}
    assert evs[0]["highlight"] == "group_achievement"
    assert db.scalar(select(func.count(IngestionRecord.id)).where(IngestionRecord.status == "normalized")) == 3


def test_dungeon_completion_merges_reporters(alice, bob):
    gid = setup_group(alice, bob)
    d = {"type": "dungeon_complete", "map_id": 77, "name": "Test Depths", "keystone_level": 10, "on_time": True}
    ingest(alice, [char(A_GUID, "Alicia")], [{**d, "id": "d1", "character_guid": A_GUID,
                                              "completed_at": ts(2026, 3, 7), "roster": [{"name": "Bobbo"}]}])
    ingest(bob, [char(B_GUID, "Bobbo")], [{**d, "id": "d2", "character_guid": B_GUID,
                                           "completed_at": ts(2026, 3, 7) + 3}])
    evs = alice.get(f"/api/groups/{gid}/events?types=dungeon_complete").json()["items"]
    assert len(evs) == 1 and evs[0]["title"] == "Test Depths +10"
    assert evs[0]["highlight"] == "first_group_dungeon"
    assert {p["confirmation"] for p in evs[0]["participants"]} == {"confirmed"}


def test_scenarios_ignored_and_user_without_group(alice):
    r = ingest(alice, [char(A_GUID, "Alicia")],
               [encounter("s1", A_GUID, success=True, end=ts(2026, 3, 1), itype="scenario")])
    assert r["ignored"] == 1
    assert any("not in any group" in m for m in r["messages"])


def test_rename_is_tracked_in_identity_history(alice):
    ingest(alice, [char(A_GUID, "Alicia")], [])
    ingest(alice, [char(A_GUID, "Alicianna", realm="Area52")], [])
    chars = alice.get("/api/me/characters").json()
    assert len(chars) == 1 and chars[0]["name"] == "Alicianna"
    hist = alice.get(f"/api/me/characters/{chars[0]['id']}/history").json()
    assert [h["change_type"] for h in hist] == ["created", "rename"]  # Area52 == Area 52, no transfer


def test_partial_data_without_deaths_marks_awards_insufficient(alice, bob):
    gid = setup_group(alice, bob)
    ingest(alice, [char(A_GUID, "Alicia")], [encounter("k", A_GUID, success=True, end=ts(2026, 3, 1), deaths=None)])
    alice.post(f"/api/groups/{gid}/awards/recompute")
    awards = {a["key"]: a for a in alice.get(f"/api/groups/{gid}/awards").json()["awards"]}
    assert awards["unbreakable"]["current"]["all_time"]["status"] == "insufficient_data"
    assert awards["floor_inspector"]["current"]["all_time"]["status"] == "insufficient_data"
    assert awards["raid_veteran"]["current"]["all_time"]["winner"]["display_name"] == "Alice"
