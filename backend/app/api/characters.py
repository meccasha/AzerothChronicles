import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app.deps import DB, CurrentUser
from app.models import Character, CharacterIdentityHistory
from app.schemas.api import CharacterIn, CharacterOut, CharacterPatch
from app.services.characters import realm_slug, record_identity

router = APIRouter(prefix="/me/characters", tags=["characters"])


@router.get("", response_model=list[CharacterOut])
def my_characters(user: CurrentUser, db: DB):
    return db.scalars(select(Character).where(Character.owner_user_id == user.id)
                      .order_by(Character.is_main.desc(), Character.name)).all()


@router.post("", response_model=CharacterOut, status_code=201)
def add_character(body: CharacterIn, user: CurrentUser, db: DB):
    """Manually declared character (unverified). Prefer Battle.net linking for verified ownership."""
    name = body.name.strip().capitalize()
    slug = realm_slug(body.realm)
    if db.scalar(select(Character.id).where(Character.owner_user_id == user.id, Character.region == body.region,
                                            Character.realm_slug == slug, func.lower(Character.name) == name.lower())):
        raise HTTPException(409, "You already have this character")
    ch = Character(id=uuid.uuid4(), owner_user_id=user.id, name=name, realm_name=body.realm.strip(),
                   realm_slug=slug, region=body.region, character_class=body.character_class, race=body.race,
                   faction=body.faction, level=body.level, specialization=body.specialization,
                   verification="manual")
    has_any = db.scalar(select(Character.id).where(Character.owner_user_id == user.id))
    ch.is_main = has_any is None
    db.add(ch)
    db.flush()
    record_identity(db, ch, "created", "manual")
    db.commit()
    return ch


@router.patch("/{character_id}", response_model=CharacterOut)
def update_character(character_id: uuid.UUID, body: CharacterPatch, user: CurrentUser, db: DB):
    ch = db.get(Character, character_id)
    if not ch or ch.owner_user_id != user.id:
        raise HTTPException(404, "Character not found")
    if body.is_main:
        for other in db.scalars(select(Character).where(Character.owner_user_id == user.id)):
            other.is_main = False
    for field in ("is_main", "is_active", "specialization"):
        v = getattr(body, field)
        if v is not None:
            setattr(ch, field, v)
    ch.updated_at = datetime.now(UTC)
    db.commit()
    return ch


@router.delete("/{character_id}", status_code=204)
def remove_character(character_id: uuid.UUID, user: CurrentUser, db: DB):
    """Removing a character keeps historic events (participation shows the member without the character)."""
    ch = db.get(Character, character_id)
    if not ch or ch.owner_user_id != user.id:
        raise HTTPException(404, "Character not found")
    db.delete(ch)
    db.commit()


@router.get("/{character_id}/history")
def character_history(character_id: uuid.UUID, user: CurrentUser, db: DB):
    ch = db.get(Character, character_id)
    if not ch or ch.owner_user_id != user.id:
        raise HTTPException(404, "Character not found")
    rows = db.scalars(select(CharacterIdentityHistory).where(CharacterIdentityHistory.character_id == ch.id)
                      .order_by(CharacterIdentityHistory.observed_at)).all()
    return [{"name": r.name, "realm_slug": r.realm_slug, "region": r.region, "faction": r.faction,
             "change_type": r.change_type, "source": r.source, "observed_at": r.observed_at} for r in rows]
