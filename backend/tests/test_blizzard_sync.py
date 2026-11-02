import json
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from sqlalchemy import select, update

from app.integrations.blizzard.live import LiveBlizzardAdapter
from app.integrations.blizzard.mock import FIXTURES, MockBlizzardAdapter, fixture_handler
from app.integrations.blizzard.types import BlizzardError, CharacterNotFound
from app.models import Character, CharacterAchievement, GroupMembership, IntegrationCredential, SyncJob, User
from app.services import blizzard_sync
from tests.conftest import create_group


def link_via_oauth(api):
    r = api.get("/api/integrations/blizzard/authorize?region=us")
    assert r.status_code == 200 and r.json()["mode"] == "mock"
    state = parse_qs(urlparse(r.json()["url"]).query)["state"][0]
    cb = api.get(f"/api/integrations/blizzard/callback?state={state}&code=mock-code", follow_redirects=False)
    assert cb.status_code == 303 and "blizzard=linked" in cb.headers["location"]
    return state


def test_oauth_link_stores_encrypted_token_and_rejects_bad_state(alice, db):
    bad = alice.get("/api/integrations/blizzard/callback?state=forged&code=x", follow_redirects=False)
    assert "invalid_state" in bad.headers["location"]
    state = link_via_oauth(alice)
    cred = db.scalar(select(IntegrationCredential))
    assert cred.access_token_encrypted != "mock-access-token" and "mock-access-token" not in cred.access_token_encrypted
    # state is single-use
    again = alice.get(f"/api/integrations/blizzard/callback?state={state}&code=mock-code", follow_redirects=False)
    assert "invalid_state" in again.headers["location"]
    status = alice.get("/api/integrations/status").json()
    assert status["blizzard"]["linked"] and status["blizzard"]["battletag"] == "MockHero#1234"
    assert "access_token" not in json.dumps(status)


def test_oauth_state_bound_to_user(alice, bob):
    r = alice.get("/api/integrations/blizzard/authorize?region=us")
    state = parse_qs(urlparse(r.json()["url"]).query)["state"][0]
    cb = bob.get(f"/api/integrations/blizzard/callback?state={state}&code=mock-code", follow_redirects=False)
    assert "invalid_state" in cb.headers["location"]


def test_backfill_vs_live_achievements(alice, db):
    gid = create_group(alice)["id"]
    # Joined before the mock achievement 9000101 (2025-10-30) but after "Level 10" (2015)
    db.execute(update(GroupMembership).values(joined_at=datetime(2025, 1, 1, tzinfo=UTC)))
    db.commit()
    link_via_oauth(alice)
    chars = alice.get("/api/integrations/blizzard/account-characters").json()
    assert {c["name"] for c in chars} == {"Aerindel", "Brumgar"}
    user = db.get(User, __import__("uuid").UUID(alice.user["id"]))
    adapter = MockBlizzardAdapter()
    blizzard_sync.link_characters(db, user, adapter, [70000001])
    job = blizzard_sync.run_user_sync(db, user, adapter)
    assert job.status == "succeeded" and job.stats["new_achievements"] == 3  # in-progress one skipped
    sources = {ca.achievement_id: ca.source for ca in db.scalars(select(CharacterAchievement))}
    assert set(sources.values()) == {"blizzard_backfill"}
    events = alice.get(f"/api/groups/{gid}/events?types=achievement&show_all=true").json()["items"]
    # Only the timestamped achievement earned after joining is posted, as a labelled backfill.
    assert [(e["title"], e["provenance"], e["time_precision"]) for e in events] == [
        ("Mock: Ashen Vanguard", "backfill", "exact")]

    # Second sync: Blizzard now reports a new achievement without a timestamp -> observed time, live.
    def handler(request: httpx.Request):
        if request.url.path.endswith("/achievements"):
            data = json.loads((FIXTURES / "achievements_aerindel.json").read_text())
            data["achievements"].append({"id": 9000104, "achievement": {"id": 9000104, "name": "Mock: Fresh Feat"},
                                         "criteria": {"is_completed": True}})
            return httpx.Response(200, json=data)
        if request.url.path == "/data/wow/achievement/9000104":
            return httpx.Response(200, json={"id": 9000104, "name": "Mock: Fresh Feat", "points": 20})
        return fixture_handler(request)

    job2 = blizzard_sync.run_user_sync(db, user, MockBlizzardAdapter(handler))
    assert job2.stats["new_achievements"] == 1
    events = alice.get(f"/api/groups/{gid}/events?types=achievement&show_all=true").json()["items"]
    fresh = next(e for e in events if e["title"] == "Mock: Fresh Feat")
    assert fresh["provenance"] == "live" and fresh["time_precision"] == "observed"
    # Re-running is a no-op (no duplicates)
    job3 = blizzard_sync.run_user_sync(db, user, MockBlizzardAdapter(handler))
    assert job3.stats["new_achievements"] == 0


def test_api_failures_are_recorded_not_raised(alice, db, monkeypatch):
    create_group(alice)
    link_via_oauth(alice)
    user = db.get(User, __import__("uuid").UUID(alice.user["id"]))
    blizzard_sync.link_characters(db, user, MockBlizzardAdapter(), [70000001, 70000002])
    monkeypatch.setattr("time.sleep", lambda s: None)

    def flaky(request: httpx.Request):
        if "brumgar" in request.url.path:
            return httpx.Response(503, json={"detail": "down"})
        return fixture_handler(request)

    job = blizzard_sync.run_user_sync(db, user, MockBlizzardAdapter(flaky))
    assert job.status == "partial" and job.stats == {**job.stats, "ok": 1, "failed": 1}
    brum = db.scalar(select(Character).where(Character.name == "Brumgar"))
    assert "503" in brum.last_sync_error
    status = alice.get("/api/integrations/status").json()
    assert status["blizzard"]["source"]["status"] == "error"
    assert status["jobs"][0]["status"] == "partial"


def test_missing_character_raises_not_found():
    with pytest.raises(CharacterNotFound):
        MockBlizzardAdapter().character_profile(region="us", realm_slug="dawnforge", name="nobody")


def test_retries_on_429_then_succeeds(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    calls = {"n": 0}

    def handler(request):
        if request.url.path == "/data/wow/achievement/6":
            calls["n"] += 1
            if calls["n"] < 3:
                return httpx.Response(429, headers={"retry-after": "1"})
        return fixture_handler(request)

    info = MockBlizzardAdapter(handler).achievement(region="us", achievement_id=6)
    assert info.name == "Level 10" and calls["n"] == 3


def test_live_adapter_requires_credentials():
    from app.config import Settings

    with pytest.raises(BlizzardError):
        LiveBlizzardAdapter(Settings(blizzard_client_id="", blizzard_client_secret=""))


def test_rename_detected_via_stable_blizzard_id(alice, db):
    create_group(alice)
    link_via_oauth(alice)
    user = db.get(User, __import__("uuid").UUID(alice.user["id"]))
    blizzard_sync.link_characters(db, user, MockBlizzardAdapter(), [70000002])
    ch = db.scalar(select(Character).where(Character.name == "Brumgar"))

    # After a rename the old name 404s; the account list maps the stable id to the new name.
    def renamed(request):
        path = request.url.path
        if path == "/profile/user/wow":
            d = json.loads((FIXTURES / "account_profile.json").read_text())
            d["wow_accounts"][0]["characters"][1]["name"] = "Brumgarr"
            return httpx.Response(200, json=d)
        if path.startswith("/profile/wow/character/dawnforge/brumgar/") or path.endswith("/brumgar"):
            return httpx.Response(404, json={"detail": "Not Found"})
        if path.startswith("/profile/wow/character/dawnforge/brumgarr"):
            fixture = "character_brumgar.json" if path.endswith("brumgarr") else "achievements_brumgar.json"
            d = json.loads((FIXTURES / fixture).read_text())
            d["name"] = "Brumgarr"
            return httpx.Response(200, json=d)
        return fixture_handler(request)

    blizzard_sync.run_user_sync(db, user, MockBlizzardAdapter(renamed))
    db.refresh(ch)
    assert ch.name == "Brumgarr" and ch.blizzard_character_id == 70000002
    hist = alice.get(f"/api/me/characters/{ch.id}/history").json()
    assert "rename" in [h["change_type"] for h in hist]


def test_expired_user_token_requires_relink(alice, db):
    link_via_oauth(alice)
    db.execute(update(IntegrationCredential).values(expires_at=datetime.now(UTC) - timedelta(hours=1)))
    db.commit()
    r = alice.get("/api/integrations/blizzard/account-characters")
    assert r.status_code == 400 and "Re-link" in r.json()["detail"]
    assert db.scalar(select(SyncJob)) is None
