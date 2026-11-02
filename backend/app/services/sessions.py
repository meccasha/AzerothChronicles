"""Derive play sessions from recorded events (gap-based clustering)."""

import uuid
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import ActivitySession, AdventureEvent, EventParticipant

SESSION_GAP = timedelta(hours=3)


def rebuild_activity_sessions(db: Session, group_id: uuid.UUID) -> int:
    rows = db.execute(
        select(AdventureEvent.id, AdventureEvent.occurred_at, EventParticipant.user_id)
        .join(EventParticipant, EventParticipant.event_id == AdventureEvent.id)
        .where(
            AdventureEvent.group_id == group_id,
            AdventureEvent.deleted_at.is_(None),
            AdventureEvent.provenance != "backfill",
        )
        .order_by(AdventureEvent.occurred_at)
    ).all()
    db.execute(delete(ActivitySession).where(ActivitySession.group_id == group_id))
    sessions: list[ActivitySession] = []
    current: ActivitySession | None = None
    seen_events: set[uuid.UUID] = set()
    users: set[str] = set()
    for event_id, ts, user_id in rows:
        if current is None or ts - current.ended_at > SESSION_GAP:
            if current is not None:
                current.participant_user_ids = sorted(users)
            current = ActivitySession(id=uuid.uuid4(), group_id=group_id, started_at=ts, ended_at=ts, event_count=0)
            sessions.append(current)
            users = set()
        current.ended_at = max(current.ended_at, ts)
        if event_id not in seen_events:
            seen_events.add(event_id)
            current.event_count += 1
        users.add(str(user_id))
    if current is not None:
        current.participant_user_ids = sorted(users)
    db.add_all(sessions)
    db.flush()
    return len(sessions)
