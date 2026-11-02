import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.models import AwardResult
from app.services.awards import engine
from app.services.awards.rules import RULES, Period
from tests.conftest import char, create_group, encounter, envelope, join, ts

A, B = "Player-1-AAAA", "Player-1-BBBB"


def _seed(alice, bob):
    gid = create_group(alice)["id"]
    join(alice, bob, gid)
    bob.post("/api/ingest/envelope", json=envelope([char(B, "Bobbo")], []))
    roster_b = [{"name": "Bobbo"}]
    recs = [
        encounter("w1", A, success=False, end=ts(2026, 4, 1, 20), deaths=2, roster=roster_b),
        encounter("k1", A, success=True, end=ts(2026, 4, 1, 21), deaths=0, roster=roster_b),
        encounter("k2", A, success=True, end=ts(2026, 4, 8, 21), deaths=1, enc_id=3002, name="Boss Two"),
        {"id": "l1", "type": "loot", "character_guid": A, "item_id": 1, "item_name": "Shiny", "quality": 5,
         "item_class": "Weapon", "item_subclass": "Mace", "looted_at": ts(2026, 4, 8, 21, 1)},
        {"id": "a1", "type": "achievement", "character_guid": A, "achievement_id": 9, "name": "Cool",
         "points": 20, "earned_at": ts(2026, 5, 2)},
    ]
    alice.post("/api/ingest/envelope", json=envelope([char(A, "Alicia")], recs))
    bob.post("/api/ingest/envelope", json=envelope([char(B, "Bobbo")], [
        encounter("bk1", B, success=True, end=ts(2026, 4, 1, 21) + 1, deaths=1, roster=[{"name": "Alicia"}])]))
    return gid


def test_overview_counts_are_grounded(alice, bob):
    gid = _seed(alice, bob)
    ov = alice.get(f"/api/groups/{gid}/stats/overview").json()
    assert ov["boss_kills_confirmed"] == 2 and ov["wipes_recorded"] == 1
    assert ov["notable_loot"] == 1 and ov["legendary_loot"] == 1 and ov["achievements_recorded"] == 1
    assert ov["tracked_events"] == 4
    assert any("not linked Battle.net" in n for n in ov["coverage"]["notes"])
    custom = alice.get(f"/api/groups/{gid}/stats/overview?period=custom&start=2026-04-05T00:00:00Z"
                       "&end=2026-04-30T00:00:00Z").json()
    assert custom["boss_kills_confirmed"] == 1 and custom["wipes_recorded"] == 0
    assert alice.get(f"/api/groups/{gid}/stats/overview?period=custom").status_code == 422
    assert alice.get(f"/api/groups/{gid}/stats/overview?period=bogus").status_code == 422
    series = alice.get(f"/api/groups/{gid}/stats/timeseries").json()["series"]
    april = next(s for s in series if s["bucket"] == "2026-04-01")
    assert april["boss_kills"] == 2 and april["wipes"] == 1 and april["active_members"] == 2
    members = {m["display_name"]: m for m in alice.get(f"/api/groups/{gid}/stats/members").json()["members"]}
    assert members["Alice"]["boss_kills"] == 2 and members["Bob"]["boss_kills"] == 1
    assert members["Alice"]["deaths"] == 3 and members["Bob"]["deaths"] == 1
    prog = alice.get(f"/api/groups/{gid}/stats/progression").json()["encounters"]
    assert {(p["name"], p["kills"], p["wipes"]) for p in prog} == {("Test Boss", 1, 1), ("Boss Two", 1, 0)}


def test_hidden_events_excluded_from_stats(alice, bob):
    gid = _seed(alice, bob)
    loot_ev = alice.get(f"/api/groups/{gid}/events?types=loot").json()["items"][0]
    alice.patch(f"/api/groups/{gid}/events/{loot_ev['id']}", json={"hidden": True})
    ov = alice.get(f"/api/groups/{gid}/stats/overview").json()
    assert ov["notable_loot"] == 0 and ov["tracked_events"] == 3
    assert alice.get(f"/api/groups/{gid}/loot").json()["total"] == 0


def test_award_rules_and_reproducibility(alice, bob, db):
    gid = uuid.UUID(_seed(alice, bob))
    april = Period("month", "2026-04", datetime(2026, 4, 1, tzinfo=UTC), datetime(2026, 5, 1, tzinfo=UTC))
    now = datetime(2026, 6, 1, tzinfo=UTC)
    a, b = uuid.UUID(alice.user["id"]), uuid.UUID(bob.user["id"])
    assert RULES["raid_veteran"].scores(db, gid, april) == {a: 2.0, b: 1.0}
    assert RULES["unbreakable"].scores(db, gid, april) == {a: 1.0, b: 0.0}
    assert RULES["floor_inspector"].scores(db, gid, april) == {a: 3.0, b: 1.0}
    assert RULES["legendary_collector"].scores(db, gid, april) == {a: 1.0}
    assert RULES["progression_pioneer"].scores(db, gid, april) == {a: 2.0, b: 1.0}
    r1 = engine.compute(db, gid, RULES["raid_veteran"], april, now)
    snapshot = (r1.winner_user_id, float(r1.winning_value), r1.status, r1.standings)
    r2 = engine.compute(db, gid, RULES["raid_veteran"], april, now)
    assert (r2.winner_user_id, float(r2.winning_value), r2.status, r2.standings) == snapshot
    assert r1.winner_user_id == a and r1.is_final
    may = Period("month", "2026-05", datetime(2026, 5, 1, tzinfo=UTC), datetime(2026, 6, 1, tzinfo=UTC))
    assert engine.compute(db, gid, RULES["unbreakable"], may, now).status == "insufficient_data"
    assert engine.compute(db, gid, RULES["loot_goblin"], may, now).status == "no_data"
    db.commit()


def test_ties_are_reported(alice, bob, db):
    gid = create_group(alice)["id"]
    join(alice, bob, gid)
    for api, guid, nm, other in ((alice, A, "Alicia", "Bobbo"), (bob, B, "Bobbo", "Alicia")):
        api.post("/api/ingest/envelope", json=envelope([char(guid, nm)], [
            encounter(f"{guid}-k", guid, success=True, end=ts(2026, 4, 1, 21), roster=[{"name": other}])]))
    p = Period("month", "2026-04", datetime(2026, 4, 1, tzinfo=UTC), datetime(2026, 5, 1, tzinfo=UTC))
    r = engine.compute(db, uuid.UUID(gid), RULES["raid_veteran"], p)
    assert r.status == "tied" and all(s.get("tied") for s in r.standings)


def test_hall_of_fame_and_voting(alice, bob, db):
    gid = _seed(alice, bob)
    hof = alice.get(f"/api/groups/{gid}/awards").json()
    keys = {a["key"] for a in hof["awards"]}
    assert {"achievement_hunter", "loot_goblin", "legendary_collector", "raid_veteran", "dungeon_explorer",
            "progression_pioneer", "unbreakable", "floor_inspector", "day_one", "most_active",
            "group_mvp"} <= keys
    assert all(a["rules"] for a in hof["awards"])
    n = alice.post(f"/api/groups/{gid}/awards/group_mvp/nominations",
                   json={"nominee_user_id": bob.user["id"], "reason": "carried"}).json()
    assert bob.put(f"/api/groups/{gid}/awards/group_mvp/vote", json={"nomination_id": n["id"]}).status_code == 200
    assert alice.put(f"/api/groups/{gid}/awards/group_mvp/vote", json={"nomination_id": n["id"]}).status_code == 200
    noms = alice.get(f"/api/groups/{gid}/awards/group_mvp/nominations").json()
    assert noms["nominations"][0]["votes"] == 2
    res = db.scalar(select(AwardResult).where(AwardResult.award_key == "group_mvp",
                                              AwardResult.period_label == noms["period_label"]))
    assert str(res.winner_user_id) == bob.user["id"]
    assert bob.post(f"/api/groups/{gid}/awards/recompute").status_code == 403
    dash = alice.get(f"/api/groups/{gid}/dashboard").json()
    assert dash["overview"]["boss_kills_confirmed"] == 2 and dash["featured"] is not None


def test_award_disable_setting(alice, bob, db):
    gid = _seed(alice, bob)
    alice.patch(f"/api/groups/{gid}", json={"settings": {"awards": {"disabled": ["loot_goblin"]}}})
    alice.post(f"/api/groups/{gid}/awards/recompute")
    assert db.scalar(select(AwardResult).where(AwardResult.award_key == "loot_goblin")) is None
