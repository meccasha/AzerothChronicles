import io

from PIL import Image

from tests.conftest import char, create_group, encounter, envelope, join, ts


def _manual(api, gid, **kw):
    body = {"title": "A memorable night", "occurred_at": "2026-02-01T21:00:00Z", **kw}
    r = api.post(f"/api/groups/{gid}/events", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_manual_event_lifecycle_and_permissions(alice, bob):
    gid = create_group(alice)["id"]
    join(alice, bob, gid)
    ev = _manual(bob, gid, description="We laughed so hard", participant_user_ids=[alice.user["id"],
                                                                                   bob.user["id"]])
    assert ev["is_manual"] and ev["confidence"] == "unconfirmed" and ev["time_precision"] == "approximate"
    assert {p["confirmation"] for p in ev["participants"]} == {"claimed"}
    # author edits; admin edits; future dates rejected; outsiders as participants rejected
    assert bob.patch(f"/api/groups/{gid}/events/{ev['id']}", json={"description": "edited"}).status_code == 200
    assert alice.patch(f"/api/groups/{gid}/events/{ev['id']}", json={"title": "Admin edit"}).status_code == 200
    assert bob.post(f"/api/groups/{gid}/events", json={"title": "Future", "occurred_at": "2999-01-01T00:00:00Z"}
                    ).status_code == 422
    assert bob.post(f"/api/groups/{gid}/events", json={"title": "Who?", "occurred_at": "2026-01-01T00:00:00Z",
                                                       "participant_user_ids": [
                                                           "00000000-0000-0000-0000-000000000000"]}
                    ).status_code == 422
    # members cannot pin/hide; admins can; hidden events disappear for members
    assert bob.patch(f"/api/groups/{gid}/events/{ev['id']}", json={"pinned": True}).status_code == 403
    assert alice.patch(f"/api/groups/{gid}/events/{ev['id']}", json={"hidden": True}).status_code == 200
    assert bob.get(f"/api/groups/{gid}/events/{ev['id']}").status_code == 404
    assert alice.get(f"/api/groups/{gid}/events?include_hidden=true").json()["total"] == 1
    alice.patch(f"/api/groups/{gid}/events/{ev['id']}", json={"hidden": False})
    # author can delete own manual event
    assert bob.delete(f"/api/groups/{gid}/events/{ev['id']}").status_code == 204
    assert alice.get(f"/api/groups/{gid}/events").json()["total"] == 0


def test_automatic_events_cannot_be_edited(alice):
    gid = create_group(alice)["id"]
    alice.post("/api/ingest/envelope", json=envelope([char("P-1", "Alicia")], [
        encounter("k", "P-1", success=True, end=ts(2026, 3, 1))]))
    ev = alice.get(f"/api/groups/{gid}/events").json()["items"][0]
    assert alice.patch(f"/api/groups/{gid}/events/{ev['id']}", json={"title": "Fake"}).status_code == 403


def test_comments_reactions_favorites(alice, bob):
    gid = create_group(alice)["id"]
    join(alice, bob, gid)
    ev = _manual(alice, gid)
    url = f"/api/groups/{gid}/events/{ev['id']}"
    c = bob.post(f"{url}/comments", json={"body": "  GG!  "}).json()
    assert c["body"] == "GG!"
    assert bob.post(f"{url}/comments", json={"body": ""}).status_code == 422
    assert bob.post(f"{url}/reactions", json={"emoji": "fire"}).json()["active"] is True
    assert alice.post(f"{url}/reactions", json={"emoji": "fire"}).json()["active"] is True
    assert bob.post(f"{url}/reactions", json={"emoji": "<script>"}).status_code == 422
    alice.put(f"{url}/favorite")
    got = alice.get(url).json()
    assert got["comment_count"] == 1 and got["favorite"] is True
    assert got["reactions"] == [{"emoji": "fire", "count": 2, "mine": True}]
    assert alice.get(f"/api/groups/{gid}/events?favorites=true").json()["total"] == 1
    assert bob.get(f"/api/groups/{gid}/events?favorites=true").json()["total"] == 0
    # a member cannot delete someone else's comment, admin can
    other = alice.post(f"{url}/comments", json={"body": "mine"}).json()
    assert bob.delete(f"{url}/comments/{other['id']}").status_code == 403
    assert alice.delete(f"{url}/comments/{c['id']}").status_code == 204
    assert bob.post(f"{url}/reactions", json={"emoji": "fire"}).json()["active"] is False


def test_filters_search_pagination_and_importance(alice, bob):
    gid = create_group(alice)["id"]
    join(alice, bob, gid)
    recs = [encounter(f"k{i}", "P-1", success=True, end=ts(2026, 3, 1 + i), enc_id=100 + i, name=f"Boss {i}")
            for i in range(5)]
    recs.append({"id": "tiny", "type": "achievement", "character_guid": "P-1", "achievement_id": 7,
                 "name": "Minor thing", "points": 10, "earned_at": ts(2026, 3, 20)})
    alice.post("/api/ingest/envelope", json=envelope([char("P-1", "Alicia")], recs))
    _manual(bob, gid, title="Bob's fishing trip", participant_user_ids=[bob.user["id"]])
    alice.patch(f"/api/groups/{gid}", json={"settings": {"events": {"timeline_min_importance": 40}}})
    page = alice.get(f"/api/groups/{gid}/events").json()
    assert page["total"] == 6 and page["hidden_below_threshold"] == 1  # 10-pt achievement scores 30 + 0
    assert alice.get(f"/api/groups/{gid}/events?show_all=true").json()["total"] == 7
    assert alice.get(f"/api/groups/{gid}/events?types=manual").json()["total"] == 1
    assert alice.get(f"/api/groups/{gid}/events?member={bob.user['id']}").json()["total"] == 1
    assert alice.get(f"/api/groups/{gid}/events?q=boss%203").json()["items"][0]["title"] == "Boss 3 defeated"
    assert alice.get(f"/api/groups/{gid}/events?start=2026-03-03T00:00:00Z&end=2026-03-05T00:00:00Z"
                     ).json()["total"] == 2
    p1 = alice.get(f"/api/groups/{gid}/events?limit=4").json()
    p2 = alice.get(f"/api/groups/{gid}/events?limit=4&cursor={p1['next_cursor']}").json()
    ids = [e["id"] for e in p1["items"] + p2["items"]]
    assert len(ids) == 6 and len(set(ids)) == 6 and p2["next_cursor"] is None
    dates = [e["occurred_at"] for e in p1["items"] + p2["items"]]
    assert dates == sorted(dates, reverse=True)
    assert alice.get(f"/api/groups/{gid}/events?cursor=garbage").status_code == 400
    facets = alice.get(f"/api/groups/{gid}/events/facets").json()
    assert {m["display_name"] for m in facets["members"]} == {"Alice", "Bob"}


def _png(size=(32, 32)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 150, 50)).save(buf, "PNG")
    return buf.getvalue()


def test_screenshot_upload_validation_and_access(alice, bob, carol):
    gid = create_group(alice)["id"]
    join(alice, bob, gid)
    ev = _manual(alice, gid)
    url = f"/api/groups/{gid}/events/{ev['id']}/media"
    bad = alice.post(url, files={"file": ("evil.png", b"<?php echo 1; ?>", "image/png")})
    assert bad.status_code == 415
    ok = alice.post(url, files={"file": ("shot.png", _png(), "image/png")}, data={"caption": "Group pic"})
    assert ok.status_code == 201
    media_url = ok.json()["url"]
    assert bob.get(media_url).status_code == 200
    assert carol.get(media_url).status_code == 404  # not a member
    from app.config import get_settings

    big = b"\x89PNG" + b"0" * (get_settings().max_upload_bytes + 10)
    assert alice.post(url, files={"file": ("big.png", big, "image/png")}).status_code == 413
    got = alice.get(f"/api/groups/{gid}/events/{ev['id']}").json()
    assert got["media"][0]["caption"] == "Group pic"


def test_manual_loot_appears_in_museum(alice, bob):
    gid = create_group(alice)["id"]
    join(alice, bob, gid)
    _manual(alice, gid, title="Bob got the staff", event_type="loot", item_name="Staff of Wonder",
            item_quality="epic", item_category="gear", participant_user_ids=[bob.user["id"]])
    museum = alice.get(f"/api/groups/{gid}/loot").json()
    assert museum["total"] == 1
    item = museum["items"][0]
    assert item["item_name"] == "Staff of Wonder" and item["user"]["display_name"] == "Bob"
    assert item["notable_reason"] == "manual" and item["source"] == "manual"
