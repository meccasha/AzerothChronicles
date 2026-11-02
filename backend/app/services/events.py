"""Creation and maintenance of canonical adventure events."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import Session

from app.models import AdventureEvent, Encounter, EventParticipant, Group, LootEvent
from app.services import periods

CONFIRMATION_RANK = {"claimed": 1, "roster": 2, "confirmed": 3}


def lock_group(db: Session, group_id: uuid.UUID) -> None:
    """Serialize ingestion per group (transaction-scoped advisory lock) to make dedup race-free."""
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"group:{group_id}"})


def stamp_periods(event: AdventureEvent) -> None:
    exp = periods.expansion_for(event.occurred_at)
    sea = periods.season_for(event.occurred_at)
    event.expansion = exp.key if exp else None
    event.season = sea.key if sea else None


def get_or_create_event(db: Session, group_id: uuid.UUID, dedup_key: str, **fields) -> tuple[AdventureEvent, bool]:
    existing = db.scalar(
        select(AdventureEvent).where(AdventureEvent.group_id == group_id, AdventureEvent.dedup_key == dedup_key)
    )
    if existing:
        return existing, False
    event = AdventureEvent(id=uuid.uuid4(), group_id=group_id, dedup_key=dedup_key, **fields)
    stamp_periods(event)
    db.add(event)
    db.flush()
    return event, True


def add_participant(
    db: Session,
    event: AdventureEvent,
    user_id: uuid.UUID,
    character_id: uuid.UUID | None,
    confirmation: str,
) -> EventParticipant:
    """Attach a member to an event, upgrading confirmation if stronger evidence arrives."""
    existing = db.scalar(
        select(EventParticipant).where(EventParticipant.event_id == event.id, EventParticipant.user_id == user_id)
    )
    if existing:
        if CONFIRMATION_RANK[confirmation] > CONFIRMATION_RANK[existing.confirmation]:
            existing.confirmation = confirmation
            if character_id:
                existing.character_id = character_id
        elif existing.character_id is None and character_id:
            existing.character_id = character_id
        return existing
    p = EventParticipant(
        id=uuid.uuid4(), event_id=event.id, user_id=user_id, character_id=character_id, confirmation=confirmation
    )
    db.add(p)
    db.flush()
    return p


def participant_count(db: Session, event_id: uuid.UUID) -> int:
    return len(db.scalars(select(EventParticipant.id).where(EventParticipant.event_id == event_id)).all())


# --------------------------------------------------------------------------------------------
# "Firsts": recomputed deterministically from all data so out-of-order imports stay correct.
# --------------------------------------------------------------------------------------------

AUTO_HIGHLIGHTS = {
    "first_raid_kill", "first_kill", "first_group_dungeon", "first_mythic_kill", "first_heroic_kill",
    "legendary", "first_legendary", "mount", "group_achievement", "feat_of_strength",
}

MILESTONE_LABELS = {
    "first_raid_kill": "First raid boss defeated together",
    "first_group_dungeon": "First dungeon completed together",
    "first_heroic_kill": "First heroic raid victory",
    "first_mythic_kill": "First mythic raid victory",
    "first_legendary": "First group legendary",
}


def recompute_highlights(db: Session, group_id: uuid.UUID) -> None:
    events = db.scalars(
        select(AdventureEvent)
        .where(
            AdventureEvent.group_id == group_id,
            AdventureEvent.deleted_at.is_(None),
            AdventureEvent.event_type.in_(["boss_kill", "dungeon_complete", "loot", "achievement"]),
        )
        .order_by(AdventureEvent.occurred_at, AdventureEvent.created_at)
    ).all()
    counts: dict[uuid.UUID, int] = dict(_participant_counts(db, group_id))
    encounters = {e.id: e for e in db.scalars(select(Encounter)).all()}
    seen_kill: set[tuple[int | None, str | None]] = set()
    flags = {"first_raid_kill": False, "first_group_dungeon": False, "first_heroic_kill": False,
             "first_mythic_kill": False, "first_legendary": False}

    for ev in events:
        if ev.highlight and ev.highlight not in AUTO_HIGHLIGHTS:
            continue  # user-defined highlight, leave alone
        extra = dict(ev.extra or {})
        extra.pop("milestone", None)
        extra["first_kill"] = False
        together = counts.get(ev.id, 0) >= 2
        highlight: str | None = None

        if ev.event_type == "boss_kill":
            enc = encounters.get(ev.encounter_id) if ev.encounter_id else None
            key = (ev.encounter_id, (ev.difficulty or "").lower())
            if key not in seen_kill:
                seen_kill.add(key)
                extra["first_kill"] = True
                highlight = "first_kill"
            is_raid = enc is not None and enc.instance_type == "raid"
            diff = (ev.difficulty or "").lower()
            if is_raid and together:
                if not flags["first_raid_kill"]:
                    flags["first_raid_kill"] = True
                    highlight = "first_raid_kill"
                elif "mythic" in diff and not flags["first_mythic_kill"]:
                    flags["first_mythic_kill"] = True
                    highlight = "first_mythic_kill"
                elif "heroic" in diff and not flags["first_heroic_kill"]:
                    flags["first_heroic_kill"] = True
                    highlight = "first_heroic_kill"
        elif ev.event_type == "dungeon_complete":
            if together and not flags["first_group_dungeon"]:
                flags["first_group_dungeon"] = True
                highlight = "first_group_dungeon"
        elif ev.event_type == "loot":
            quality = extra.get("quality")
            if quality == "legendary":
                highlight = "legendary"
                if not flags["first_legendary"]:
                    flags["first_legendary"] = True
                    highlight = "first_legendary"
            elif extra.get("category") == "mount":
                highlight = "mount"
        elif ev.event_type == "achievement":
            if extra.get("feat_of_strength"):
                highlight = "feat_of_strength"
            elif together:
                highlight = "group_achievement"

        if highlight in MILESTONE_LABELS:
            extra["milestone"] = MILESTONE_LABELS[highlight]
        ev.highlight = highlight
        ev.extra = extra

    # Loot table mirror of "group first" for the museum.
    loot_rows = db.scalars(
        select(LootEvent).where(LootEvent.group_id == group_id).order_by(LootEvent.obtained_at)
    ).all()
    seen_items: set[str] = set()
    for row in loot_rows:
        k = str(row.item_id) if row.item_id else row.item_name.lower()
        row.is_group_first = k not in seen_items
        seen_items.add(k)
    db.flush()


def _participant_counts(db: Session, group_id: uuid.UUID) -> list[tuple[uuid.UUID, int]]:
    return db.execute(
        select(EventParticipant.event_id, func.count(EventParticipant.id))
        .join(AdventureEvent, AdventureEvent.id == EventParticipant.event_id)
        .where(AdventureEvent.group_id == group_id)
        .group_by(EventParticipant.event_id)
    ).all()


def visible_events_clause(group_id: uuid.UUID):
    return and_(
        AdventureEvent.group_id == group_id,
        AdventureEvent.deleted_at.is_(None),
        AdventureEvent.hidden.is_(False),
    )


def now() -> datetime:
    return datetime.now(UTC)


def groups_for_user(db: Session, user_id: uuid.UUID) -> list[Group]:
    from app.models import GroupMembership

    return list(
        db.scalars(
            select(Group).join(GroupMembership, GroupMembership.group_id == Group.id).where(
                GroupMembership.user_id == user_id
            )
        )
    )
