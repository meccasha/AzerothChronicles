"""Server-side aggregation for the statistics dashboard.

Every number here is a count of *recorded* rows. Nothing is extrapolated. Coverage information is
returned alongside so the UI can explain gaps (e.g. members without a connected source).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import and_, case, distinct, func, literal, or_, select
from sqlalchemy.orm import Session

from app.models import (
    ActivitySession,
    AdventureEvent,
    Encounter,
    EncounterAttempt,
    EncounterAttemptParticipant,
    EventParticipant,
    ExternalAccount,
    GroupMembership,
    LootEvent,
    SyncSource,
    User,
)

OBSERVED = ("confirmed", "roster")  # participation backed by game data


@dataclass
class Range:
    start: datetime | None
    end: datetime | None

    def on(self, col):
        conds = []
        if self.start is not None:
            conds.append(col >= self.start)
        if self.end is not None:
            conds.append(col < self.end)
        return and_(*conds) if conds else literal(True)


def _visible(group_id: uuid.UUID):
    return and_(AdventureEvent.group_id == group_id, AdventureEvent.deleted_at.is_(None),
                AdventureEvent.hidden.is_(False))


def loot_visible(group_id: uuid.UUID):
    """Loot rows belong to the group and are not attached to a hidden/deleted timeline event."""
    hidden = select(AdventureEvent.id).where(AdventureEvent.group_id == group_id,
                                             or_(AdventureEvent.hidden, AdventureEvent.deleted_at.is_not(None)))
    return and_(LootEvent.group_id == group_id, or_(LootEvent.event_id.is_(None), LootEvent.event_id.not_in(hidden)))


def overview(db: Session, group_id: uuid.UUID, rng: Range) -> dict[str, Any]:
    ev = db.execute(
        select(
            func.count(AdventureEvent.id),
            func.count(case((AdventureEvent.event_type == "achievement", 1))),
            func.count(case((and_(AdventureEvent.event_type == "boss_kill", AdventureEvent.is_manual), 1))),
            func.count(case((AdventureEvent.event_type == "dungeon_complete", 1))),
            func.count(case((AdventureEvent.is_manual, 1))),
            func.min(AdventureEvent.occurred_at),
        ).where(_visible(group_id), rng.on(AdventureEvent.occurred_at))
    ).one()
    att = db.execute(
        select(func.count(case((EncounterAttempt.success, 1))), func.count(case((~EncounterAttempt.success, 1))))
        .where(EncounterAttempt.group_id == group_id, rng.on(EncounterAttempt.ended_at))
    ).one()
    loot = db.execute(
        select(func.count(LootEvent.id), func.count(case((LootEvent.quality == "legendary", 1))),
               func.count(case((LootEvent.category == "mount", 1))))
        .where(loot_visible(group_id), rng.on(LootEvent.obtained_at))
    ).one()
    sessions = db.scalar(select(func.count(ActivitySession.id)).where(
        ActivitySession.group_id == group_id, rng.on(ActivitySession.started_at)))
    first_ever = db.scalar(select(func.min(AdventureEvent.occurred_at)).where(
        _visible(group_id), AdventureEvent.provenance != "backfill"))
    return {
        "tracked_events": ev[0],
        "achievements_recorded": ev[1],
        "boss_kills_confirmed": att[0],
        "boss_kills_manual": ev[2],
        "wipes_recorded": att[1],
        "dungeons_recorded": ev[3],
        "manual_events": ev[4],
        "notable_loot": loot[0],
        "legendary_loot": loot[1],
        "mounts": loot[2],
        "play_sessions": sessions or 0,
        "first_event_in_range": ev[5],
        "first_recorded_activity": first_ever,
        "most_active": member_activity(db, group_id, rng, limit=5),
    }


def member_activity(db: Session, group_id: uuid.UUID, rng: Range, limit: int | None = None) -> list[dict]:
    q = (
        select(User.id, User.display_name, User.avatar_color, func.count(EventParticipant.id).label("n"))
        .join(EventParticipant, EventParticipant.user_id == User.id)
        .join(AdventureEvent, AdventureEvent.id == EventParticipant.event_id)
        .where(_visible(group_id), rng.on(AdventureEvent.occurred_at))
        .group_by(User.id).order_by(func.count(EventParticipant.id).desc(), User.display_name)
    )
    if limit:
        q = q.limit(limit)
    return [{"user_id": str(r[0]), "display_name": r[1], "avatar_color": r[2], "events": r[3]}
            for r in db.execute(q).all()]


def timeseries(db: Session, group_id: uuid.UUID, rng: Range, bucket: str = "month") -> list[dict]:
    if bucket not in ("week", "month"):
        raise ValueError("bucket must be week or month")

    def trunc(col):
        return func.date_trunc(bucket, func.timezone("UTC", col))

    rows: dict[str, dict] = {}

    def slot(key) -> dict:
        k = key.date().isoformat()
        return rows.setdefault(k, {"bucket": k, "events": 0, "achievements": 0, "boss_kills": 0, "wipes": 0,
                                   "loot": 0, "dungeons": 0, "active_members": 0})

    b = trunc(AdventureEvent.occurred_at).label("b")
    for key, total, ach, dun in db.execute(
        select(b, func.count(AdventureEvent.id),
               func.count(case((AdventureEvent.event_type == "achievement", 1))),
               func.count(case((AdventureEvent.event_type == "dungeon_complete", 1))))
        .where(_visible(group_id), rng.on(AdventureEvent.occurred_at)).group_by(b)
    ).all():
        s = slot(key)
        s["events"], s["achievements"], s["dungeons"] = total, ach, dun
    ba = trunc(EncounterAttempt.ended_at).label("b")
    for key, kills, wipes in db.execute(
        select(ba, func.count(case((EncounterAttempt.success, 1))), func.count(case((~EncounterAttempt.success, 1))))
        .where(EncounterAttempt.group_id == group_id, rng.on(EncounterAttempt.ended_at)).group_by(ba)
    ).all():
        s = slot(key)
        s["boss_kills"], s["wipes"] = kills, wipes
    bl = trunc(LootEvent.obtained_at).label("b")
    for key, n in db.execute(select(bl, func.count(LootEvent.id)).where(
            loot_visible(group_id), rng.on(LootEvent.obtained_at)).group_by(bl)).all():
        slot(key)["loot"] = n
    for key, n in db.execute(
        select(b, func.count(distinct(EventParticipant.user_id)))
        .join(EventParticipant, EventParticipant.event_id == AdventureEvent.id)
        .where(_visible(group_id), rng.on(AdventureEvent.occurred_at)).group_by(b)
    ).all():
        slot(key)["active_members"] = n
    return [rows[k] for k in sorted(rows)]


def by_period(db: Session, group_id: uuid.UUID) -> list[dict]:
    """Event counts grouped by expansion and season (as stamped from app/data/periods.json)."""
    rows = db.execute(
        select(AdventureEvent.expansion, AdventureEvent.season, AdventureEvent.event_type,
               func.count(AdventureEvent.id))
        .where(_visible(group_id)).group_by(AdventureEvent.expansion, AdventureEvent.season,
                                            AdventureEvent.event_type)
    ).all()
    out: dict[tuple, dict] = {}
    for exp, sea, et, n in rows:
        d = out.setdefault((exp, sea), {"expansion": exp, "season": sea, "total": 0})
        d[et] = d.get(et, 0) + n
        d["total"] += n
    return sorted(out.values(), key=lambda d: (d["expansion"] or "", d["season"] or ""))


def member_table(db: Session, group_id: uuid.UUID, rng: Range) -> list[dict]:
    members = db.execute(
        select(User.id, User.display_name, User.avatar_color, GroupMembership.role, GroupMembership.joined_at)
        .join(GroupMembership, GroupMembership.user_id == User.id).where(GroupMembership.group_id == group_id)
    ).all()
    part = (
        select(EventParticipant.user_id,
               func.count(EventParticipant.id),
               func.count(case((AdventureEvent.event_type == "achievement", 1))),
               func.count(case((and_(AdventureEvent.event_type == "boss_kill",
                                     EventParticipant.confirmation.in_(OBSERVED)), 1))),
               func.count(case((and_(AdventureEvent.event_type == "dungeon_complete",
                                     EventParticipant.confirmation.in_(OBSERVED)), 1))))
        .join(AdventureEvent, AdventureEvent.id == EventParticipant.event_id)
        .where(_visible(group_id), rng.on(AdventureEvent.occurred_at)).group_by(EventParticipant.user_id)
    )
    p = {r[0]: r[1:] for r in db.execute(part).all()}
    loot = {r[0]: r[1:] for r in db.execute(
        select(LootEvent.user_id, func.count(LootEvent.id), func.count(case((LootEvent.quality == "legendary", 1))))
        .where(loot_visible(group_id), rng.on(LootEvent.obtained_at)).group_by(LootEvent.user_id)).all()}
    deaths = {r[0]: r[1:] for r in db.execute(
        select(EncounterAttemptParticipant.user_id, func.sum(EncounterAttemptParticipant.deaths),
               func.count(EncounterAttemptParticipant.deaths),
               func.count(case((~EncounterAttempt.success, 1))))
        .join(EncounterAttempt, EncounterAttempt.id == EncounterAttemptParticipant.attempt_id)
        .where(EncounterAttempt.group_id == group_id, rng.on(EncounterAttempt.ended_at))
        .group_by(EncounterAttemptParticipant.user_id)).all()}
    out = []
    for uid, name, color, role, joined in members:
        pp = p.get(uid, (0, 0, 0, 0))
        ll = loot.get(uid, (0, 0))
        dd = deaths.get(uid, (None, 0, 0))
        out.append({
            "user_id": str(uid), "display_name": name, "avatar_color": color, "role": role, "joined_at": joined,
            "events": pp[0], "achievements": pp[1], "boss_kills": pp[2], "dungeons": pp[3],
            "loot": ll[0], "legendaries": ll[1], "wipes": dd[2],
            # deaths only meaningful when the member's addon reported death data
            "deaths": int(dd[0]) if dd[1] else None, "attempts_with_death_data": dd[1],
        })
    return sorted(out, key=lambda r: (-r["events"], r["display_name"]))


def progression(db: Session, group_id: uuid.UUID) -> list[dict]:
    rows = db.execute(
        select(Encounter.id, Encounter.name, Encounter.instance_name, Encounter.instance_type,
               EncounterAttempt.difficulty,
               func.count(case((EncounterAttempt.success, 1))), func.count(case((~EncounterAttempt.success, 1))),
               func.min(case((EncounterAttempt.success, EncounterAttempt.ended_at))),
               func.min(EncounterAttempt.ended_at))
        .join(EncounterAttempt, EncounterAttempt.encounter_id == Encounter.id)
        .where(EncounterAttempt.group_id == group_id)
        .group_by(Encounter.id, EncounterAttempt.difficulty)
        .order_by(Encounter.instance_name, func.min(EncounterAttempt.ended_at))
    ).all()
    return [{"encounter_id": r[0], "name": r[1], "instance_name": r[2], "instance_type": r[3], "difficulty": r[4],
             "kills": r[5], "wipes": r[6], "first_kill_at": r[7], "first_attempt_at": r[8]} for r in rows]


def coverage(db: Session, group_id: uuid.UUID) -> dict[str, Any]:
    member_ids = list(db.scalars(select(GroupMembership.user_id).where(GroupMembership.group_id == group_id)))
    bnet = set(db.scalars(select(ExternalAccount.user_id).where(ExternalAccount.user_id.in_(member_ids))))
    addon = set(db.scalars(select(SyncSource.user_id).where(SyncSource.user_id.in_(member_ids),
                                                             SyncSource.kind == "addon",
                                                             SyncSource.last_success_at.is_not(None))))
    death_rows = db.scalar(
        select(func.count(EncounterAttemptParticipant.id))
        .join(EncounterAttempt, EncounterAttempt.id == EncounterAttemptParticipant.attempt_id)
        .where(EncounterAttempt.group_id == group_id, EncounterAttemptParticipant.deaths.is_not(None)))
    notes = []
    if len(addon) < len(member_ids):
        notes.append(f"{len(member_ids) - len(addon)} of {len(member_ids)} members have not uploaded addon data; "
                     "boss kills, wipes and loot are only recorded from members who do.")
    if len(bnet) < len(member_ids):
        notes.append(f"{len(member_ids) - len(bnet)} of {len(member_ids)} members have not linked Battle.net; "
                     "their achievements are only captured by the addon or manual entries.")
    if not death_rows:
        notes.append("No death data has been recorded yet, so death-based awards are not calculated.")
    notes.append("All counts are recorded/tracked activity, not a complete history of everything played.")
    return {"members": len(member_ids), "battlenet_linked": len(bnet), "addon_reporting": len(addon),
            "attempts_with_death_data": death_rows or 0, "notes": notes}
