"""ORM -> API conversion helpers (batch-friendly to avoid N+1 queries)."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.deps import GroupAccess
from app.models import AdventureEvent, Encounter, EventComment, EventFavorite, EventParticipant, LootEvent, User
from app.schemas.api import (
    CharacterOut,
    EventOut,
    MediaOut,
    ParticipantOut,
    ReactionSummary,
    UserBrief,
)

EVENT_LOAD = (
    selectinload(AdventureEvent.participants).selectinload(EventParticipant.user),
    selectinload(AdventureEvent.participants).selectinload(EventParticipant.character),
    selectinload(AdventureEvent.reactions),
    selectinload(AdventureEvent.media),
    selectinload(AdventureEvent.achievement),
    selectinload(AdventureEvent.encounter).selectinload(Encounter.game_instance),
    selectinload(AdventureEvent.item),
    selectinload(AdventureEvent.game_instance),
)


def event_artwork(e: AdventureEvent, loot_icon: str | None) -> tuple[str | None, str | None, str | None]:
    """Best game image for an event -> (image_url, image_kind, scene_url)."""
    from app.services.game_media import media_kind

    instance = e.game_instance or (e.encounter.game_instance if e.encounter else None)
    scene = instance.image_url if instance and media_kind(instance.image_url) == "scene" else None
    image = None
    if e.event_type == "loot":
        image = (e.item.icon_url if e.item else None) or loot_icon
    elif e.event_type == "achievement" or (e.achievement and not e.item):
        image = e.achievement.icon_url if e.achievement else None
    if image is None and e.item and e.item.icon_url:
        image = e.item.icon_url
    if image is None and e.event_type in ("boss_kill", "dungeon_complete"):
        image = (e.encounter.image_url if e.encounter else None) or (instance.image_url if instance else None)
    return image, media_kind(image), scene


def media_url(storage_key: str) -> str:
    return f"/api/media/{storage_key}"


def events_out(db: Session, events: list[AdventureEvent], access: GroupAccess) -> list[EventOut]:
    ids = [e.id for e in events]
    if not ids:
        return []
    comment_counts = dict(db.execute(
        select(EventComment.event_id, func.count(EventComment.id))
        .where(EventComment.event_id.in_(ids), EventComment.deleted_at.is_(None))
        .group_by(EventComment.event_id)).all())
    favorites = set(db.scalars(select(EventFavorite.event_id).where(
        EventFavorite.event_id.in_(ids), EventFavorite.user_id == access.user.id)))
    creator_ids = {e.created_by_user_id for e in events if e.created_by_user_id}
    creators = {u.id: u for u in db.scalars(select(User).where(User.id.in_(creator_ids)))} if creator_ids else {}
    loot_icons = dict(db.execute(select(LootEvent.event_id, LootEvent.icon_url).where(
        LootEvent.event_id.in_(ids), LootEvent.icon_url.is_not(None))).all())
    out = []
    for e in events:
        reactions: dict[str, ReactionSummary] = {}
        for r in e.reactions:
            s = reactions.setdefault(r.emoji, ReactionSummary(emoji=r.emoji, count=0, mine=False))
            s.count += 1
            s.mine = s.mine or r.user_id == access.user.id
        parts = sorted(e.participants, key=lambda p: p.user.display_name.lower())
        can_edit = e.is_manual and (e.created_by_user_id == access.user.id or access.is_admin)
        image_url, image_kind, scene_url = event_artwork(e, loot_icons.get(e.id))
        out.append(EventOut(
            id=e.id, event_type=e.event_type, title=e.title, description=e.description,
            occurred_at=e.occurred_at, time_precision=e.time_precision, importance=e.importance,
            highlight=e.highlight, difficulty=e.difficulty, instance_name=e.instance_name,
            expansion=e.expansion, season=e.season, source=e.source, provenance=e.provenance,
            confidence=e.confidence, is_manual=e.is_manual, is_demo=e.is_demo, hidden=e.hidden, pinned=e.pinned,
            favorite=e.id in favorites,
            achievement={"id": e.achievement.id, "name": e.achievement.name, "points": e.achievement.points,
                         "icon_url": e.achievement.icon_url} if e.achievement else None,
            encounter={"id": e.encounter.id, "name": e.encounter.name, "instance_name": e.encounter.instance_name,
                       "instance_type": e.encounter.instance_type, "image_url": e.encounter.image_url}
            if e.encounter else None,
            item={"id": e.item.id, "name": e.item.name, "quality": e.item.quality, "icon_url": e.item.icon_url,
                  "item_class": e.item.item_class} if e.item else None,
            extra=e.extra or {},
            image_url=image_url, image_kind=image_kind, scene_url=scene_url,
            participants=[ParticipantOut(user=UserBrief.model_validate(p.user),
                                         character=CharacterOut.model_validate(p.character) if p.character else None,
                                         confirmation=p.confirmation) for p in parts],
            reactions=sorted(reactions.values(), key=lambda r: -r.count),
            comment_count=comment_counts.get(e.id, 0),
            media=[MediaOut(id=m.id, url=media_url(m.storage_key), content_type=m.content_type, width=m.width,
                            height=m.height, caption=m.caption) for m in e.media],
            created_by=UserBrief.model_validate(creators[e.created_by_user_id])
            if e.created_by_user_id in creators else None,
            can_edit=can_edit,
            can_moderate=access.is_admin or (e.is_manual and e.created_by_user_id == access.user.id),
        ))
    return out


def load_events(db: Session, ids: list[uuid.UUID]) -> list[AdventureEvent]:
    if not ids:
        return []
    rows = {e.id: e for e in db.scalars(select(AdventureEvent).where(AdventureEvent.id.in_(ids)).options(*EVENT_LOAD))}
    return [rows[i] for i in ids if i in rows]
