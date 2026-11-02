import base64
import io
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from sqlalchemy import and_, delete, func, or_, select

from app.api.serializers import EVENT_LOAD, events_out, load_events
from app.config import get_settings
from app.deps import DB, Access, CurrentUser, member_user_ids
from app.models import (
    Achievement,
    AdventureEvent,
    Character,
    EventComment,
    EventFavorite,
    EventMedia,
    EventParticipant,
    EventReaction,
    GroupMembership,
    Item,
    LootEvent,
    User,
)
from app.schemas.api import (
    CommentIn,
    CommentOut,
    EventOut,
    EventPage,
    EventPatch,
    ManualEventIn,
    ReactionIn,
    UserBrief,
)
from app.services import periods
from app.services.events import add_participant, get_or_create_event, recompute_highlights
from app.services.group_settings import load_settings
from app.services.sessions import rebuild_activity_sessions

router = APIRouter(prefix="/groups/{group_id}/events", tags=["events"])
media_router = APIRouter(prefix="/media", tags=["media"])

ALLOWED_IMAGE_FORMATS = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp", "GIF": "image/gif"}
MAX_DIMENSION = 2560


def _encode_cursor(e: AdventureEvent) -> str:
    return base64.urlsafe_b64encode(f"{e.occurred_at.isoformat()}|{e.id}".encode()).decode()


def _decode_cursor(c: str) -> tuple[datetime, uuid.UUID]:
    try:
        ts, eid = base64.urlsafe_b64decode(c.encode()).decode().split("|")
        return datetime.fromisoformat(ts), uuid.UUID(eid)
    except Exception as exc:
        raise HTTPException(400, "Invalid cursor") from exc


def _get_event(db, access, event_id: uuid.UUID, allow_deleted=False) -> AdventureEvent:
    e = db.get(AdventureEvent, event_id)
    if not e or e.group_id != access.group.id or (e.deleted_at and not allow_deleted):
        raise HTTPException(404, "Event not found")
    if e.hidden and not access.is_admin:
        raise HTTPException(404, "Event not found")
    return e


@router.get("", response_model=EventPage)
def list_events(
    access: Access, db: DB,
    types: str | None = Query(None, description="comma-separated event types"),
    member: uuid.UUID | None = None,
    character: uuid.UUID | None = None,
    expansion: str | None = None,
    season: str | None = None,
    q: str | None = Query(None, max_length=100),
    start: datetime | None = None,
    end: datetime | None = None,
    favorites: bool = False,
    pinned: bool = False,
    highlights: bool = False,
    show_all: bool = False,
    include_hidden: bool = False,
    order: str = Query("desc", pattern="^(asc|desc)$"),
    cursor: str | None = None,
    limit: int = Query(30, ge=1, le=100),
):
    gid = access.group.id
    conds = [AdventureEvent.group_id == gid, AdventureEvent.deleted_at.is_(None)]
    if not (include_hidden and access.is_admin):
        conds.append(AdventureEvent.hidden.is_(False))
    if types:
        conds.append(AdventureEvent.event_type.in_([t.strip() for t in types.split(",") if t.strip()]))
    if member:
        conds.append(AdventureEvent.id.in_(select(EventParticipant.event_id).where(EventParticipant.user_id == member)))
    if character:
        conds.append(AdventureEvent.id.in_(select(EventParticipant.event_id)
                                           .where(EventParticipant.character_id == character)))
    if expansion:
        conds.append(AdventureEvent.expansion == expansion)
    if season:
        conds.append(AdventureEvent.season == season)
    if q:
        like = f"%{q.replace('%', '').replace('_', '')}%"
        conds.append(or_(AdventureEvent.title.ilike(like), AdventureEvent.description.ilike(like),
                         AdventureEvent.instance_name.ilike(like)))
    if start:
        conds.append(AdventureEvent.occurred_at >= start)
    if end:
        conds.append(AdventureEvent.occurred_at < end)
    if favorites:
        conds.append(AdventureEvent.id.in_(select(EventFavorite.event_id)
                                           .where(EventFavorite.user_id == access.user.id)))
    if pinned:
        conds.append(AdventureEvent.pinned.is_(True))
    if highlights:
        conds.append(or_(AdventureEvent.highlight.is_not(None), AdventureEvent.pinned.is_(True)))

    threshold = load_settings(access.group.settings).events.timeline_min_importance
    importance_cond = or_(AdventureEvent.importance >= threshold, AdventureEvent.is_manual.is_(True),
                          AdventureEvent.pinned.is_(True))
    hidden_below = 0
    if not show_all:
        hidden_below = db.scalar(select(func.count(AdventureEvent.id)).where(*conds, ~importance_cond)) or 0
        conds.append(importance_cond)
    total = db.scalar(select(func.count(AdventureEvent.id)).where(*conds)) or 0

    query = select(AdventureEvent.id).where(*conds)
    if cursor:
        ts, eid = _decode_cursor(cursor)
        if order == "desc":
            query = query.where(or_(AdventureEvent.occurred_at < ts,
                                    and_(AdventureEvent.occurred_at == ts, AdventureEvent.id < eid)))
        else:
            query = query.where(or_(AdventureEvent.occurred_at > ts,
                                    and_(AdventureEvent.occurred_at == ts, AdventureEvent.id > eid)))
    if order == "desc":
        query = query.order_by(AdventureEvent.occurred_at.desc(), AdventureEvent.id.desc())
    else:
        query = query.order_by(AdventureEvent.occurred_at.asc(), AdventureEvent.id.asc())
    ids = list(db.scalars(query.limit(limit + 1)))
    has_more = len(ids) > limit
    events = load_events(db, ids[:limit])
    return EventPage(items=events_out(db, events, access),
                     next_cursor=_encode_cursor(events[-1]) if has_more and events else None,
                     total=total, hidden_below_threshold=hidden_below)


@router.get("/facets")
def facets(access: Access, db: DB):
    gid = access.group.id
    members = db.execute(select(User.id, User.display_name, User.avatar_color)
                         .join(GroupMembership, GroupMembership.user_id == User.id)
                         .where(GroupMembership.group_id == gid).order_by(User.display_name)).all()
    chars = db.execute(select(Character.id, Character.name, Character.realm_name, Character.character_class,
                              Character.owner_user_id)
                       .where(Character.owner_user_id.in_([m[0] for m in members])).order_by(Character.name)).all()
    used = db.execute(select(AdventureEvent.expansion, AdventureEvent.season).where(
        AdventureEvent.group_id == gid, AdventureEvent.deleted_at.is_(None)).distinct()).all()
    used_exp = {u[0] for u in used if u[0]}
    used_sea = {u[1] for u in used if u[1]}
    return {
        "members": [{"id": str(m[0]), "display_name": m[1], "avatar_color": m[2]} for m in members],
        "characters": [{"id": str(c[0]), "name": c[1], "realm": c[2], "character_class": c[3],
                        "owner_user_id": str(c[4])} for c in chars],
        "expansions": [{"key": w.key, "name": w.name, "has_events": w.key in used_exp} for w in periods.expansions()],
        "seasons": [{"key": w.key, "name": w.name, "expansion": w.expansion, "has_events": w.key in used_sea}
                    for w in periods.seasons()],
        "types": ["achievement", "boss_kill", "dungeon_complete", "loot", "milestone", "manual"],
        "timeline_min_importance": load_settings(access.group.settings).events.timeline_min_importance,
    }


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: uuid.UUID, access: Access, db: DB):
    _get_event(db, access, event_id)
    return events_out(db, load_events(db, [event_id]), access)[0]


@router.post("", response_model=EventOut, status_code=201)
def create_manual_event(body: ManualEventIn, access: Access, db: DB):
    gid = access.group.id
    members = member_user_ids(db, gid)
    bad = [u for u in body.participant_user_ids if u not in members]
    if bad:
        raise HTTPException(422, "All participants must be members of this group")
    if body.occurred_at.tzinfo is None:
        raise HTTPException(422, "occurred_at must include a timezone (UTC recommended)")
    if body.occurred_at > datetime.now(UTC):
        raise HTTPException(422, "Events cannot be in the future")
    ach = db.get(Achievement, body.achievement_id) if body.achievement_id else None
    item = db.get(Item, body.item_id) if body.item_id else None
    extra: dict = {"manual": True}
    if body.encounter_name:
        extra["encounter_name"] = body.encounter_name
    if body.achievement_id and not ach:
        extra["achievement_ref"] = body.achievement_id
    if body.event_type == "loot":
        extra.update(quality=body.item_quality or (item.quality if item else "unknown"),
                     category=body.item_category or "other")
    event, _ = get_or_create_event(
        db, gid, f"manual:{uuid.uuid4()}", event_type=body.event_type, title=body.title.strip(),
        description=body.description.strip(), occurred_at=body.occurred_at.astimezone(UTC),
        time_precision="approximate", importance=85 if body.major else 60,
        highlight="custom_milestone" if body.event_type == "milestone" else None,
        achievement_id=ach.id if ach else None, item_id=item.id if item else None,
        difficulty=body.difficulty, instance_name=body.instance_name, source="manual", provenance="manual",
        confidence="unconfirmed", is_manual=True, created_by_user_id=access.user.id, extra=extra,
    )
    for uid in dict.fromkeys(body.participant_user_ids):
        add_participant(db, event, uid, None, "claimed")
    if body.event_type == "loot":
        recipient = body.participant_user_ids[0] if body.participant_user_ids else access.user.id
        if not body.participant_user_ids:
            add_participant(db, event, recipient, None, "claimed")
        db.add(LootEvent(
            id=uuid.uuid4(), group_id=gid, item_id=item.id if item else None,
            item_name=body.item_name or (item.name if item else body.title), quality=extra["quality"],
            category=extra["category"], user_id=recipient, obtained_at=event.occurred_at,
            source_instance=body.instance_name, difficulty=body.difficulty, notable_reason="manual",
            source="manual", dedup_key=f"manual-loot:{event.id}", event_id=event.id,
        ))
    db.flush()
    recompute_highlights(db, gid)
    rebuild_activity_sessions(db, gid)
    db.commit()
    return events_out(db, load_events(db, [event.id]), access)[0]


@router.patch("/{event_id}", response_model=EventOut)
def update_event(event_id: uuid.UUID, body: EventPatch, access: Access, db: DB):
    e = _get_event(db, access, event_id)
    if body.title is not None or body.description is not None:
        if not e.is_manual:
            raise HTTPException(403, "Only manually created events can be edited")
        if e.created_by_user_id != access.user.id and not access.is_admin:
            raise HTTPException(403, "Only the author or an admin can edit this event")
        if body.title is not None:
            e.title = body.title.strip()
        if body.description is not None:
            e.description = body.description.strip()
        e.edited_at = datetime.now(UTC)
    if body.hidden is not None or body.pinned is not None:
        access.require("admin")
        if body.hidden is not None:
            e.hidden = body.hidden
        if body.pinned is not None:
            e.pinned = body.pinned
    db.commit()
    return events_out(db, load_events(db, [e.id]), access)[0]


@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: uuid.UUID, access: Access, db: DB):
    e = _get_event(db, access, event_id)
    if not access.is_admin and not (e.is_manual and e.created_by_user_id == access.user.id):
        raise HTTPException(403, "Only admins (or the author of a manual event) can delete events")
    e.deleted_at = datetime.now(UTC)
    db.execute(delete(LootEvent).where(LootEvent.event_id == e.id))
    recompute_highlights(db, access.group.id)
    rebuild_activity_sessions(db, access.group.id)
    db.commit()


@router.put("/{event_id}/favorite", status_code=204)
def favorite(event_id: uuid.UUID, access: Access, db: DB):
    _get_event(db, access, event_id)
    if not db.scalar(select(EventFavorite.id).where(EventFavorite.event_id == event_id,
                                                    EventFavorite.user_id == access.user.id)):
        db.add(EventFavorite(id=uuid.uuid4(), event_id=event_id, user_id=access.user.id, created_at=datetime.now(UTC)))
        db.commit()


@router.delete("/{event_id}/favorite", status_code=204)
def unfavorite(event_id: uuid.UUID, access: Access, db: DB):
    _get_event(db, access, event_id)
    db.execute(delete(EventFavorite).where(EventFavorite.event_id == event_id,
                                           EventFavorite.user_id == access.user.id))
    db.commit()


@router.post("/{event_id}/reactions")
def toggle_reaction(event_id: uuid.UUID, body: ReactionIn, access: Access, db: DB):
    _get_event(db, access, event_id)
    existing = db.scalar(select(EventReaction).where(EventReaction.event_id == event_id,
                                                     EventReaction.user_id == access.user.id,
                                                     EventReaction.emoji == body.emoji))
    if existing:
        db.delete(existing)
        active = False
    else:
        db.add(EventReaction(id=uuid.uuid4(), event_id=event_id, user_id=access.user.id, emoji=body.emoji,
                             created_at=datetime.now(UTC)))
        active = True
    db.commit()
    return {"emoji": body.emoji, "active": active}


@router.get("/{event_id}/comments", response_model=list[CommentOut])
def list_comments(event_id: uuid.UUID, access: Access, db: DB):
    _get_event(db, access, event_id)
    rows = db.execute(select(EventComment, User).join(User, User.id == EventComment.user_id)
                      .where(EventComment.event_id == event_id, EventComment.deleted_at.is_(None))
                      .order_by(EventComment.created_at)).all()
    return [CommentOut(id=c.id, user=UserBrief.model_validate(u), body=c.body, created_at=c.created_at,
                       can_delete=c.user_id == access.user.id or access.is_admin) for c, u in rows]


@router.post("/{event_id}/comments", response_model=CommentOut, status_code=201)
def add_comment(event_id: uuid.UUID, body: CommentIn, access: Access, db: DB):
    _get_event(db, access, event_id)
    c = EventComment(id=uuid.uuid4(), event_id=event_id, user_id=access.user.id, body=body.body.strip())
    db.add(c)
    db.commit()
    return CommentOut(id=c.id, user=UserBrief.model_validate(access.user), body=c.body, created_at=c.created_at,
                      can_delete=True)


@router.delete("/{event_id}/comments/{comment_id}", status_code=204)
def delete_comment(event_id: uuid.UUID, comment_id: uuid.UUID, access: Access, db: DB):
    _get_event(db, access, event_id)
    c = db.get(EventComment, comment_id)
    if not c or c.event_id != event_id or c.deleted_at:
        raise HTTPException(404, "Comment not found")
    if c.user_id != access.user.id and not access.is_admin:
        raise HTTPException(403, "Not allowed")
    c.deleted_at = datetime.now(UTC)
    db.commit()


@router.post("/{event_id}/media", status_code=201)
async def upload_media(event_id: uuid.UUID, access: Access, db: DB, file: UploadFile = File(...),
                       caption: str | None = Form(None, max_length=280)):
    _get_event(db, access, event_id)
    settings = get_settings()
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, f"File too large (max {settings.max_upload_bytes // (1024 * 1024)} MB)")
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
        img = Image.open(io.BytesIO(data))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(415, "Only PNG, JPEG, WEBP or GIF screenshots are accepted") from exc
    if img.format not in ALLOWED_IMAGE_FORMATS:
        raise HTTPException(415, "Only PNG, JPEG, WEBP or GIF screenshots are accepted")
    # Re-encode to strip metadata (EXIF/GPS) and neutralize polyglot payloads.
    img.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
    out = io.BytesIO()
    if img.mode in ("RGBA", "LA", "P"):
        img.convert("RGBA").save(out, "PNG", optimize=True)
        ext, ctype = "png", "image/png"
    else:
        img.convert("RGB").save(out, "JPEG", quality=88)
        ext, ctype = "jpg", "image/jpeg"
    key = f"{uuid.uuid4().hex}.{ext}"
    root = Path(settings.upload_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / key).write_bytes(out.getvalue())
    m = EventMedia(id=uuid.uuid4(), event_id=event_id, uploader_user_id=access.user.id, storage_key=key,
                   content_type=ctype, size_bytes=out.tell(), width=img.width, height=img.height,
                   caption=caption, created_at=datetime.now(UTC))
    db.add(m)
    db.commit()
    return {"id": str(m.id), "url": f"/api/media/{key}"}


@router.delete("/{event_id}/media/{media_id}", status_code=204)
def delete_media(event_id: uuid.UUID, media_id: uuid.UUID, access: Access, db: DB):
    _get_event(db, access, event_id)
    m = db.get(EventMedia, media_id)
    if not m or m.event_id != event_id:
        raise HTTPException(404, "Media not found")
    if m.uploader_user_id != access.user.id and not access.is_admin:
        raise HTTPException(403, "Not allowed")
    path = Path(get_settings().upload_dir) / m.storage_key
    path.unlink(missing_ok=True)
    db.delete(m)
    db.commit()


@media_router.get("/{key}")
def get_media(key: str, user: CurrentUser, db: DB):
    m = db.scalar(select(EventMedia).where(EventMedia.storage_key == key))
    if m is None:
        raise HTTPException(404, "Not found")
    ev = db.get(AdventureEvent, m.event_id)
    if not db.scalar(select(GroupMembership.id).where(GroupMembership.group_id == ev.group_id,
                                                      GroupMembership.user_id == user.id)):
        raise HTTPException(404, "Not found")
    path = Path(get_settings().upload_dir) / m.storage_key
    if not path.is_file():
        raise HTTPException(404, "File missing")
    return FileResponse(path, media_type=m.content_type, headers={"Cache-Control": "private, max-age=3600",
                                                                  "X-Content-Type-Options": "nosniff"})


__all__ = ["router", "media_router", "EVENT_LOAD"]
