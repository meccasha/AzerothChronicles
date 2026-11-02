"""Character identity resolution and history tracking."""

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Character, CharacterIdentityHistory, GroupMembership


def realm_slug(realm: str) -> str:
    """Approximation of Blizzard realm slugs ("Area 52" -> "area-52"). The Blizzard API's own slug
    is preferred whenever a character is verified through it."""
    s = realm.strip().lower().replace("'", "")
    s = re.sub(r"[\s_]+", "-", s)
    return re.sub(r"[^a-z0-9\-]", "", s)


def realm_key(realm: str) -> str:
    """Comparison key tolerant of the in-game normalized form ("Area52") vs display ("Area 52")."""
    return re.sub(r"[^a-z0-9]", "", realm.lower())


def record_identity(db: Session, ch: Character, change_type: str, source: str) -> None:
    db.add(
        CharacterIdentityHistory(
            id=uuid.uuid4(), character_id=ch.id, name=ch.name, realm_slug=ch.realm_slug, region=ch.region,
            faction=ch.faction, change_type=change_type, source=source, observed_at=datetime.now(UTC),
        )
    )


def apply_identity(db: Session, ch: Character, *, name: str, realm_name: str, region: str,
                   faction: str | None, source: str) -> None:
    """Update display identity, appending to history when it changes (rename/transfer/faction)."""
    changes = []
    if ch.name != name:
        changes.append("rename")
    moved = realm_key(ch.realm_name) != realm_key(realm_name) and realm_key(ch.realm_slug) != realm_key(realm_name)
    if moved or ch.region != region:
        changes.append("realm_transfer")
        ch.realm_name, ch.realm_slug = realm_name, realm_slug(realm_name)
    if faction and ch.faction and ch.faction != faction:
        changes.append("faction_change")
    ch.name, ch.region = name, region
    if faction:
        ch.faction = faction
    for c in changes:
        record_identity(db, ch, c, source)


def find_group_character(db: Session, group_id: uuid.UUID, name: str, realm: str | None,
                         default_realm: str | None) -> Character | None:
    """Match a roster entry (name + realm as shown in game) to a group member's character."""
    key = realm_key(realm or default_realm or "")
    q = (
        select(Character)
        .join(GroupMembership, GroupMembership.user_id == Character.owner_user_id)
        .where(GroupMembership.group_id == group_id, func.lower(Character.name) == name.lower())
    )
    candidates = db.scalars(q).all()
    exact = [c for c in candidates if realm_key(c.realm_slug) == key or realm_key(c.realm_name) == key]
    if len(exact) == 1:
        return exact[0]
    return None  # ambiguous or unknown -> do not attribute
