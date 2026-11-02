import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.schemas.ingest import IngestEnvelope
from app.services import importance, periods
from app.services.characters import realm_key, realm_slug
from app.services.lua_savedvariables import LuaParseError, parse_savedvariables, savedvariables_to_envelope
from tests.conftest import create_group, join

FIX = Path(__file__).parent / "fixtures"


def test_parse_fixture_into_valid_envelope():
    env = IngestEnvelope.model_validate(savedvariables_to_envelope(
        parse_savedvariables((FIX / "AzerothChronicles.lua").read_text())))
    assert env.addon_version == "1.0.0" and len(env.characters) == 1
    assert [r.type for r in env.records] == ["encounter", "encounter", "loot", "achievement", "mount"]
    assert env.records[2].item_name == 'Fixture Longbow of "Testing"'
    assert env.records[0].roster[0].name == "Groupmate"


@pytest.mark.parametrize("src", [
    "AzerothChroniclesDB = { os.execute('rm -rf /') }",
    "AzerothChroniclesDB = function() end",
    "AzerothChroniclesDB = {",
    "x = 1 + 2",
])
def test_parser_rejects_code(src):
    with pytest.raises(LuaParseError):
        parse_savedvariables(src)


def test_parser_requires_our_table():
    with pytest.raises(LuaParseError):
        savedvariables_to_envelope(parse_savedvariables("OtherAddonDB = {}"))


def test_upload_savedvariables_and_json_export_merge(alice, bob):
    gid = create_group(alice)["id"]
    join(alice, bob, gid)
    # bob's character must be known for roster matching -> bob uploads the JSON export first
    rb = bob.post("/api/ingest/envelope", json=json.loads((FIX / "addon_export.json").read_text()))
    assert rb.status_code == 200
    ra = alice.post("/api/ingest/savedvariables", content=(FIX / "AzerothChronicles.lua").read_bytes(),
                    headers={"content-type": "text/plain"})
    assert ra.status_code == 200, ra.text
    body = ra.json()
    assert body["normalized"] == 5 and body["rejected"] == 0
    ov = alice.get(f"/api/groups/{gid}/stats/overview").json()
    assert ov["wipes_recorded"] == 1  # alice's and bob's reports of the same wipe were merged
    assert ov["boss_kills_confirmed"] == 1 and ov["mounts"] == 1
    bad = alice.post("/api/ingest/savedvariables", content=b"print('hi')")
    assert bad.status_code == 422


def test_api_token_upload_for_companion(alice):
    tok = alice.post("/api/me/tokens", json={"name": "Companion"}).json()["token"]
    assert tok.startswith("act_")
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    data = (FIX / "AzerothChronicles.lua").read_bytes()
    assert c.post("/api/ingest/savedvariables", content=data, headers={"authorization": f"Bearer {tok}"}
                  ).status_code == 200
    assert c.post("/api/ingest/savedvariables", content=data, headers={"authorization": "Bearer act_wrong"}
                  ).status_code == 401
    # tokens cannot be used for normal (cookie-only) endpoints
    assert c.get("/api/groups", headers={"authorization": f"Bearer {tok}"}).status_code == 401
    tid = alice.get("/api/me/tokens").json()[0]["id"]
    alice.delete(f"/api/me/tokens/{tid}")
    assert c.post("/api/ingest/savedvariables", content=data, headers={"authorization": f"Bearer {tok}"}
                  ).status_code == 401


def test_importance_rules():
    assert importance.boss_kill_importance("raid", "Mythic", True, 5) == 100
    assert importance.boss_kill_importance("raid", "Normal", False, 1) == 65
    assert importance.loot_importance("legendary", "gear", "legendary") == 92
    assert importance.loot_importance("epic", "gear", "wishlist") == 65
    assert not importance.should_post_achievement(5, False, 10)
    assert importance.should_post_achievement(0, True, 10)


def test_periods_and_realms():
    mid = datetime(2026, 6, 1, tzinfo=UTC)
    assert periods.expansion_for(mid).key == "midnight"
    s, e, _ = periods.resolve_period("current_season", now=mid)
    assert s == datetime(2026, 3, 17, tzinfo=UTC) and e is None
    with pytest.raises(ValueError):
        periods.resolve_period("custom", datetime(2026, 2, 1, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC))
    assert realm_slug("Area 52") == "area-52" and realm_key("Area52") == realm_key("Area 52")
    assert realm_slug("Kel'Thuzad") == "kelthuzad"
