import json

import httpx
from sqlalchemy import select

from app.integrations.blizzard.mock import FIXTURES, MockBlizzardAdapter, fixture_handler
from app.models import Achievement, Encounter, GameInstance, Item, LootEvent
from app.services.game_media import icon_url_from_name, media_kind, resolve_media, safe_media_url
from tests.conftest import char, create_group, encounter, envelope, ts

G = "Player-1-MEDIA"


def test_url_safety_and_icon_names():
    assert safe_media_url("https://render.worldofwarcraft.com/us/icons/56/inv_sword_39.jpg")
    assert safe_media_url("https://render-eu.worldofwarcraft.com/icons/56/x.jpg")
    for bad in ("http://render.worldofwarcraft.com/x.jpg", "https://evil.example/x.jpg", "javascript:alert(1)",
                "https://render.worldofwarcraft.com.evil.example/x.jpg", "https://render.worldofwarcraft.com/a b.jpg"):
        assert safe_media_url(bad) is None, bad
    assert icon_url_from_name("INV_Sword_39") == "https://render.worldofwarcraft.com/us/icons/56/inv_sword_39.jpg"
    assert icon_url_from_name("Interface\\Icons\\INV_Misc_Book_09").endswith("/inv_misc_book_09.jpg")
    assert icon_url_from_name("../../etc/passwd") is None and icon_url_from_name("12345").endswith("12345.jpg")
    assert media_kind("https://render.worldofwarcraft.com/us/icons/56/a.jpg") == "icon"
    assert media_kind("https://render.worldofwarcraft.com/us/npcs/zoom/creature-display-1.jpg") == "portrait"
    assert media_kind("https://render.worldofwarcraft.com/us/zones/a-small.jpg") == "scene"


def _kill(rid, end, **kw):
    rec = encounter(rid, G, success=True, end=end, enc_id=kw.pop("enc_id", 5001),
                    name=kw.pop("name", "Mock: Ashen Colossus"))
    rec["instance_name"] = kw.pop("instance_name", "Mock: Dawnforge Citadel")
    rec.update(kw)
    return rec


def test_boss_portrait_and_instance_art_from_journal_ids(alice):
    gid = create_group(alice)["id"]
    r = alice.post("/api/ingest/envelope", json=envelope([char(G, "Medi")], [
        _kill("k1", ts(2026, 3, 1), journal_instance_id=9901, journal_encounter_id=99011)]))
    assert r.json()["normalized"] == 1
    ev = alice.get(f"/api/groups/{gid}/events?types=boss_kill").json()["items"][0]
    assert ev["image_url"].endswith("creature-display-880011.jpg") and ev["image_kind"] == "portrait"
    assert ev["scene_url"].endswith("mock-dawnforge-citadel-small.jpg")
    assert ev["encounter"]["image_url"] == ev["image_url"]
    prog = alice.get(f"/api/groups/{gid}/stats/progression").json()["encounters"][0]
    assert prog["image_url"] == ev["image_url"]


def test_name_matching_without_journal_ids(alice, db):
    gid = create_group(alice)["id"]
    # Older addon: no journal ids, and the boss name differs only by case/punctuation
    alice.post("/api/ingest/envelope", json=envelope([char(G, "Medi")], [
        _kill("k1", ts(2026, 3, 1), name="mock: the LAST warden!", enc_id=5002,
              instance_name="Mock: Dawnforge Citadel")]))
    inst = db.scalar(select(GameInstance).where(GameInstance.name == "Mock: Dawnforge Citadel"))
    assert inst.journal_instance_id == 9901 and inst.media_status == "resolved" and inst.map_id == 2769
    enc = db.scalar(select(Encounter).where(Encounter.dungeon_encounter_id == 5002))
    assert enc.journal_encounter_id == 99012 and enc.image_url.endswith("creature-display-880012.jpg")
    ev = alice.get(f"/api/groups/{gid}/events").json()["items"][0]
    assert ev["image_kind"] == "portrait"


def test_dungeon_completion_art_and_instance_dedup(alice, db):
    gid = create_group(alice)["id"]
    d = {"type": "dungeon_complete", "character_guid": G, "map_id": 501, "keystone_level": 9, "on_time": True}
    alice.post("/api/ingest/envelope", json=envelope([char(G, "Medi")], [
        {**d, "id": "d1", "name": "Mock: Ember Depths", "completed_at": ts(2026, 3, 2)},
        # same dungeon later reported with an exact journal id and a different display name
        {**d, "id": "d2", "name": "Ember Depths", "instance_id": 2600, "journal_instance_id": 9902,
         "completed_at": ts(2026, 3, 9)}]))
    rows = db.scalars(select(GameInstance)).all()
    assert len(rows) == 1 and rows[0].journal_instance_id == 9902
    evs = alice.get(f"/api/groups/{gid}/events?types=dungeon_complete").json()["items"]
    assert len(evs) == 2 and all(e["scene_url"].endswith("mock-ember-depths-small.jpg") for e in evs)


def test_item_icons_achievement_icons_mounts_and_legacy_icon_field(alice, db):
    gid = create_group(alice)["id"]
    alice.post("/api/ingest/envelope", json=envelope([char(G, "Medi")], [
        {"id": "l1", "type": "loot", "character_guid": G, "item_id": 9100001, "item_name": "Echo", "quality": 5,
         "icon": "135274", "looted_at": ts(2026, 3, 3)},  # addon 1.0 stored the FileDataID as a string
        {"id": "l2", "type": "loot", "character_guid": G, "item_id": 777, "item_name": "Named", "quality": 5,
         "icon": "INV_Sword_04", "looted_at": ts(2026, 3, 3)},
        {"id": "l3", "type": "loot", "character_guid": G, "item_id": 778, "item_name": "Sneaky", "quality": 5,
         "icon": "https://evil.example/pixel.gif", "looted_at": ts(2026, 3, 3)},
        {"id": "m1", "type": "mount", "character_guid": G, "collectible_id": 2001, "name": "Fixture Gryphon",
         "learned_at": ts(2026, 3, 4)},
        {"id": "a1", "type": "achievement", "character_guid": G, "achievement_id": 9000101, "name": "Vanguard",
         "points": 25, "earned_at": ts(2026, 3, 5)}]))
    echo = db.get(Item, 9100001)
    assert echo.icon_file_id == 135274 and echo.icon_url.endswith("inv_sword_2h_mock.jpg")  # resolved via Battle.net
    assert db.get(Item, 777).icon_url.endswith("/inv_sword_04.jpg")
    sneaky = db.get(Item, 778)
    assert sneaky.icon_url is None and sneaky.metadata_fetched_at is not None  # unsafe URL dropped; 404 not retried
    mount = db.scalar(select(LootEvent).where(LootEvent.category == "mount"))
    assert mount.collectible_id == 2001 and mount.icon_url.endswith("creature-display-880201.jpg")
    assert db.get(Achievement, 9000101).icon_url.endswith("achievement_mock_vanguard.jpg")
    museum = {r["item_name"]: r["icon_url"] for r in alice.get(f"/api/groups/{gid}/loot").json()["items"]}
    assert museum["Echo"].endswith("inv_sword_2h_mock.jpg") and museum["Sneaky"] is None
    events = {e["title"]: e for e in alice.get(f"/api/groups/{gid}/events?show_all=true").json()["items"]}
    assert events["Echo"]["image_kind"] == "icon" and events["Vanguard"]["image_url"].endswith("vanguard.jpg")
    assert events["Fixture Gryphon"]["image_kind"] == "portrait"


def test_transient_errors_are_retried_unknowns_are_not(alice, db, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    monkeypatch.setattr("app.services.game_media.media_enabled", lambda: False)  # no automatic runs
    create_group(alice)
    alice.post("/api/ingest/envelope", json=envelope([char(G, "Medi")], [
        _kill("k1", ts(2026, 3, 1), name="Unknown Boss", instance_name="Nowhere Keep")]))
    calls = {"n": 0}

    def flaky(request: httpx.Request):
        if request.url.path == "/data/wow/journal-instance/index":
            calls["n"] += 1
            if calls["n"] <= 4:  # outlasts the adapter's own retries
                return httpx.Response(503)
        return fixture_handler(request)

    adapter = MockBlizzardAdapter(flaky)
    first = resolve_media(db, adapter)
    inst = db.scalar(select(GameInstance).where(GameInstance.name == "Nowhere Keep"))
    assert first["deferred"] >= 1 and inst.media_fetched_at is None  # Battle.net hiccup: try again later
    second = resolve_media(db, adapter)
    db.refresh(inst)
    assert inst.media_status == "unavailable" and second["unavailable"] >= 2  # not in the journal: stop asking
    enc = db.scalar(select(Encounter).where(Encounter.name == "Unknown Boss"))
    assert enc.media_status == "unavailable"
    assert resolve_media(db, adapter)["unavailable"] == 0


def test_media_status_endpoint_and_refresh(alice):
    s = alice.get("/api/integrations/media").json()
    assert s["enabled"] is True and s["mode"] == "mock" and "bosses" in s["coverage"]
    assert alice.post("/api/integrations/media/refresh").json()["status"] == "started"
    assert alice.post("/api/integrations/media/refresh").status_code == 429


def test_demo_artwork_is_applied(db):
    from app.services.demo_seed import seed_demo

    seed_demo(db)
    assert db.scalar(select(Item).where(Item.id == 9200001)).icon_url.endswith("/inv_sword_39.jpg")
    assert all(e.image_url for e in db.scalars(select(Encounter).where(Encounter.is_demo.is_(True))))
    assert all(i.image_url for i in db.scalars(select(GameInstance).where(GameInstance.is_demo.is_(True))))
    assert json.loads((FIXTURES / "journal_instance_9901.json").read_text())["id"] == 9901
