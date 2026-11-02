import os
import uuid
from datetime import UTC, datetime

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://azeroth:azeroth@localhost:5432/azeroth_test")
os.environ["BLIZZARD_ADAPTER"] = "mock"
os.environ["DEMO_MODE"] = "true"
os.environ["UPLOAD_DIR"] = "/tmp/azeroth-test-uploads"

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from alembic import command  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402

BACKEND = os.path.dirname(os.path.dirname(__file__))


@pytest.fixture(scope="session", autouse=True)
def _migrate():
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    cfg = Config(os.path.join(BACKEND, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND, "alembic"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _clean():
    from app.api import auth

    auth._login_attempts.clear()
    yield
    names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {names} CASCADE"))


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


class Api:
    """TestClient wrapper that behaves like the web frontend (sends the CSRF header)."""

    def __init__(self):
        self.c = TestClient(app)
        self.user: dict | None = None

    def _h(self, kw):
        kw.setdefault("headers", {})["x-ac-client"] = "web"
        return kw

    def get(self, url, **kw):
        return self.c.get(url, **kw)

    def post(self, url, **kw):
        return self.c.post(url, **self._h(kw))

    def put(self, url, **kw):
        return self.c.put(url, **self._h(kw))

    def patch(self, url, **kw):
        return self.c.patch(url, **self._h(kw))

    def delete(self, url, **kw):
        return self.c.request("DELETE", url, **self._h(kw))


def make_user(name: str = "Alice") -> Api:
    api = Api()
    r = api.post("/api/auth/register", json={"email": f"{name.lower()}-{uuid.uuid4().hex[:6]}@example.com",
                                             "display_name": name, "password": "correct horse battery"})
    assert r.status_code == 201, r.text
    api.user = r.json()
    return api


@pytest.fixture
def alice() -> Api:
    return make_user("Alice")


@pytest.fixture
def bob() -> Api:
    return make_user("Bob")


@pytest.fixture
def carol() -> Api:
    return make_user("Carol")


def create_group(api: Api, name: str | None = None) -> dict:
    r = api.post("/api/groups", json={"name": name or f"Group {uuid.uuid4().hex[:6]}", "description": "test"})
    assert r.status_code == 201, r.text
    return r.json()


def join(owner: Api, member: Api, group_id: str) -> None:
    inv = owner.post(f"/api/groups/{group_id}/invites", json={"expires_in_hours": 24}).json()
    r = member.post(f"/api/invites/{inv['code']}/accept")
    assert r.status_code == 200, r.text


def ts(y, m, d, h=20, mi=0, s=0) -> int:
    return int(datetime(y, m, d, h, mi, s, tzinfo=UTC).timestamp())


def char(guid: str, name: str, realm: str = "Area 52", cls: str = "Warrior") -> dict:
    return {"guid": guid, "name": name, "realm": realm, "region": "us", "class": cls, "race": "Human",
            "faction": "Alliance", "level": 80}


def envelope(characters: list[dict], records: list[dict], source: str = "addon") -> dict:
    return {"format": "azeroth-chronicles/v1", "source": source, "addon_version": "test",
            "characters": characters, "records": records}


def encounter(rid: str, guid: str, *, success: bool, end: int, enc_id: int = 3001, name: str = "Test Boss",
              diff: str = "Heroic", roster: list | None = None, deaths: int | None = 0, itype: str = "raid") -> dict:
    return {"id": rid, "type": "encounter", "character_guid": guid, "encounter_id": enc_id, "encounter_name": name,
            "instance_name": "Test Raid", "instance_type": itype, "difficulty_id": 15, "difficulty_name": diff,
            "group_size": 10, "success": success, "start_time": end - 300, "end_time": end,
            "roster": roster or [], "deaths": deaths}
