"""End-to-end API workflow: sign up -> group -> invite -> characters -> ingest -> timeline/stats/awards."""

from tests.conftest import Api, char, encounter, envelope


def test_full_group_workflow():
    owner, friend = Api(), Api()
    owner.post("/api/auth/register", json={"email": "owner@example.com", "display_name": "Owner",
                                          "password": "a very long password"})
    friend.post("/api/auth/register", json={"email": "friend@example.com", "display_name": "Friend",
                                           "password": "another long password"})
    g = owner.post("/api/groups", json={"name": "Weekend Warriors", "description": "Friends across guilds"}).json()
    gid = g["id"]
    inv = owner.post(f"/api/groups/{gid}/invites", json={"expires_in_hours": 48}).json()
    assert inv["url"].endswith(inv["code"])
    assert friend.post(f"/api/invites/{inv['code']}/accept").status_code == 200

    # characters: one manual (unverified), one via addon export
    assert owner.post("/api/me/characters", json={"name": "Ownerella", "realm": "Stormrage", "region": "us",
                                                  "character_class": "Mage"}).status_code == 201
    members = owner.get(f"/api/groups/{gid}/members").json()
    assert {m["user"]["display_name"] for m in members} == {"Owner", "Friend"}

    friend.post("/api/ingest/envelope", json=envelope([char("P-F", "Friendo", realm="Stormrage")], []))
    sim = owner.get(f"/api/ingest/sample?group_id={gid}").json()
    assert sim["source"] == "simulated" and sim["records"][0]["roster"][0]["name"] == "Friendo"
    res = owner.post("/api/ingest/envelope", json=sim).json()
    assert res["normalized"] == 4 and res["rejected"] == 0
    friend.post("/api/ingest/envelope", json=envelope([char("P-F", "Friendo", realm="Stormrage")], [
        {**encounter("f-1", "P-F", success=True, end=sim["records"][1]["end_time"] + 1, enc_id=990001,
                     name="Simulated Sentinel"), "instance_name": "Simulation Spire"}]))

    tl = owner.get(f"/api/groups/{gid}/events").json()
    kills = [e for e in tl["items"] if e["event_type"] == "boss_kill"]
    assert len(kills) == 1
    assert {p["confirmation"] for p in kills[0]["participants"]} == {"confirmed"}
    assert kills[0]["extra"]["wipes_before_kill"] == 1
    assert kills[0]["highlight"] == "first_raid_kill"

    ov = owner.get(f"/api/groups/{gid}/stats/overview").json()
    assert ov["boss_kills_confirmed"] == 1 and ov["wipes_recorded"] == 1 and ov["notable_loot"] == 1
    owner.post(f"/api/groups/{gid}/awards/recompute")
    hof = {a["key"]: a for a in owner.get(f"/api/groups/{gid}/awards").json()["awards"]}
    assert hof["loot_goblin"]["current"]["all_time"]["winner"]["display_name"] == "Owner"
    assert hof["raid_veteran"]["current"]["all_time"]["status"] == "tied"
    dash = owner.get(f"/api/groups/{gid}/dashboard").json()
    assert dash["featured"]["highlight"] == "first_raid_kill"
    assert owner.get("/api/integrations/status").json()["addon"]["source"]["status"] == "ok"
