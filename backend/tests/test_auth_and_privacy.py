from datetime import UTC, datetime, timedelta

from sqlalchemy import update

from app.models import GroupInvite
from tests.conftest import Api, create_group, join, make_user


def test_register_login_logout_me():
    api = Api()
    r = api.post("/api/auth/register", json={"email": "Hero@Example.com", "display_name": "Hero",
                                             "password": "a-long-password"})
    assert r.status_code == 201
    assert r.json()["email"] == "hero@example.com"
    assert api.get("/api/me").status_code == 200
    assert api.post("/api/auth/logout").status_code == 204
    assert api.get("/api/me").status_code == 401
    bad = api.post("/api/auth/login", json={"email": "hero@example.com", "password": "wrong-password"})
    assert bad.status_code == 401
    good = api.post("/api/auth/login", json={"email": "HERO@example.com", "password": "a-long-password"})
    assert good.status_code == 200


def test_register_validation_and_duplicates(alice):
    api = Api()
    assert api.post("/api/auth/register", json={"email": "x@example.com", "display_name": "X",
                                                "password": "short"}).status_code == 422
    assert api.post("/api/auth/register", json={"email": "not-an-email", "display_name": "Xy",
                                                "password": "long-enough-pw"}).status_code == 422
    assert api.post("/api/auth/register", json={"email": alice.user["email"], "display_name": "Dup",
                                                "password": "long-enough-pw"}).status_code == 409


def test_csrf_header_required_for_cookie_requests(alice):
    r = alice.c.post("/api/groups", json={"name": "No Header Group"})
    assert r.status_code == 403
    r = alice.c.post("/api/groups", json={"name": "Evil Group"},
                     headers={"x-ac-client": "web", "origin": "https://evil.example"})
    assert r.status_code == 403


def test_non_members_cannot_see_group_or_its_data(alice, bob):
    g = create_group(alice, "Secret Society")
    gid = g["id"]
    for path in ("", "/members", "/events", "/stats/overview", "/loot", "/awards", "/dashboard"):
        assert bob.get(f"/api/groups/{gid}{path}").status_code == 404, path
    assert [x["id"] for x in bob.get("/api/groups").json()] == []
    anon = Api()
    assert anon.get(f"/api/groups/{gid}").status_code == 401


def test_invite_flow_roles_and_expiry(alice, bob, carol, db):
    g = create_group(alice)
    gid = g["id"]
    inv = alice.post(f"/api/groups/{gid}/invites", json={"expires_in_hours": 1, "max_uses": 1}).json()
    preview = bob.get(f"/api/invites/{inv['code']}").json()
    assert preview["valid"] and preview["description"] is None  # private group hides details
    assert bob.post(f"/api/invites/{inv['code']}/accept").status_code == 200
    # max_uses reached
    assert carol.post(f"/api/invites/{inv['code']}/accept").status_code == 410
    # members cannot administer
    assert bob.patch(f"/api/groups/{gid}", json={"description": "hacked"}).status_code == 403
    assert bob.post(f"/api/groups/{gid}/invites", json={}).status_code == 403
    # expired invite
    inv2 = alice.post(f"/api/groups/{gid}/invites", json={}).json()
    db.execute(update(GroupInvite).where(GroupInvite.code == inv2["code"])
               .values(expires_at=datetime.now(UTC) - timedelta(minutes=1)))
    db.commit()
    assert carol.post(f"/api/invites/{inv2['code']}/accept").status_code == 410
    # revoked invite
    inv3 = alice.post(f"/api/groups/{gid}/invites", json={}).json()
    alice.delete(f"/api/groups/{gid}/invites/{inv3['id']}")
    assert carol.post(f"/api/invites/{inv3['code']}/accept").status_code == 410


def test_role_management_and_leaving(alice, bob, carol):
    gid = create_group(alice)["id"]
    join(alice, bob, gid)
    join(alice, carol, gid)
    assert alice.patch(f"/api/groups/{gid}/members/{bob.user['id']}", json={"role": "admin"}).status_code == 204
    # admin cannot remove the owner, can remove a member
    assert bob.delete(f"/api/groups/{gid}/members/{alice.user['id']}").status_code == 403
    assert bob.delete(f"/api/groups/{gid}/members/{carol.user['id']}").status_code == 204
    # owner cannot leave without transfer
    assert alice.delete(f"/api/groups/{gid}/members/{alice.user['id']}").status_code == 400
    assert alice.patch(f"/api/groups/{gid}/members/{bob.user['id']}", json={"role": "owner"}).status_code == 204
    assert alice.delete(f"/api/groups/{gid}/members/{alice.user['id']}").status_code == 204
    assert alice.get(f"/api/groups/{gid}").status_code == 404


def test_groups_are_isolated(alice, bob):
    g1 = create_group(alice, "Group One")["id"]
    g2 = create_group(bob, "Group Two")["id"]
    ev = alice.post(f"/api/groups/{g1}/events", json={"title": "Secret night", "occurred_at": "2026-01-01T20:00:00Z"})
    assert ev.status_code == 201
    eid = ev.json()["id"]
    assert bob.get(f"/api/groups/{g2}/events/{eid}").status_code == 404
    assert bob.get(f"/api/groups/{g1}/events/{eid}").status_code == 404
    assert bob.post(f"/api/groups/{g2}/events/{eid}/comments", json={"body": "hi"}).status_code == 404
    assert bob.get(f"/api/groups/{g2}/stats/overview").json()["tracked_events"] == 0


def test_account_export_and_deletion_transfers_ownership(alice, bob):
    gid = create_group(alice)["id"]
    join(alice, bob, gid)
    exp = alice.get("/api/me/export").json()
    assert exp["user"]["email"] == alice.user["email"] and len(exp["groups"]) == 1
    assert alice.delete("/api/me", json={"confirm": "DELETE", "password": "wrong"}).status_code == 403
    assert alice.delete("/api/me", json={"confirm": "DELETE", "password": "correct horse battery"}).status_code == 204
    g = bob.get(f"/api/groups/{gid}").json()
    assert g["my_role"] == "owner"


def test_demo_login_is_read_only_for_group_creation(db):
    from app.services.demo_seed import seed_demo

    seed_demo(db)
    api = Api()
    assert api.post("/api/demo/login").status_code == 200
    groups = api.get("/api/groups").json()
    assert len(groups) == 1 and groups[0]["is_demo"]
    assert api.post("/api/groups", json={"name": "Demo hack"}).status_code == 403
    other = make_user("Outsider")
    assert other.get(f"/api/groups/{groups[0]['id']}").status_code == 404
