"""Loot Museum, statistics, Hall of Fame, dashboard and member profiles."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import and_, func, or_, select

from app.api.serializers import events_out, load_events
from app.deps import DB, Access
from app.models import (
    AdventureEvent,
    AwardDefinition,
    AwardNomination,
    AwardResult,
    AwardVote,
    Character,
    EventComment,
    EventParticipant,
    EventReaction,
    GroupMembership,
    LootEvent,
    User,
)
from app.schemas.api import CharacterOut, NominationIn, UserBrief, VoteIn
from app.services import periods, stats
from app.services.awards import engine
from app.services.awards.rules import RULES

router = APIRouter(prefix="/groups/{group_id}", tags=["insights"])


def _range(period: str, start: datetime | None, end: datetime | None) -> tuple[stats.Range, str]:
    try:
        s, e, label = periods.resolve_period(period, start, end)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return stats.Range(s, e), label


# ----------------------------------------------------------------------------- loot museum
def _loot_row(row: LootEvent, user: User, ch: Character | None, celebration: int) -> dict:
    return {
        "id": str(row.id), "event_id": str(row.event_id) if row.event_id else None, "item_id": row.item_id,
        "item_name": row.item_name, "quality": row.quality, "category": row.category, "icon_url": row.icon_url,
        "obtained_at": row.obtained_at, "source_instance": row.source_instance, "difficulty": row.difficulty,
        "notable_reason": row.notable_reason, "is_group_first": row.is_group_first, "source": row.source,
        "is_demo": row.is_demo, "celebration": celebration,
        "user": UserBrief.model_validate(user).model_dump(mode="json"),
        "character": {"id": str(ch.id), "name": ch.name, "character_class": ch.character_class} if ch else None,
    }


def _celebration_scores(db, event_ids: list) -> dict:
    ids = [i for i in event_ids if i]
    if not ids:
        return {}
    r = dict(db.execute(select(EventReaction.event_id, func.count(EventReaction.id))
                        .where(EventReaction.event_id.in_(ids)).group_by(EventReaction.event_id)).all())
    c = dict(db.execute(select(EventComment.event_id, func.count(EventComment.id))
                        .where(EventComment.event_id.in_(ids), EventComment.deleted_at.is_(None))
                        .group_by(EventComment.event_id)).all())
    return {i: r.get(i, 0) + c.get(i, 0) for i in ids}


@router.get("/loot")
def loot_museum(
    access: Access, db: DB, q: str | None = Query(None, max_length=100), quality: str | None = None,
    member: uuid.UUID | None = None, category: str | None = None,
    sort: str = Query("recent", pattern="^(recent|oldest|celebrated)$"),
    limit: int = Query(60, ge=1, le=200), offset: int = Query(0, ge=0),
):
    gid = access.group.id
    conds = [stats.loot_visible(gid)]
    if q:
        conds.append(LootEvent.item_name.ilike(f"%{q.replace('%', '')}%"))
    if quality:
        conds.append(LootEvent.quality.in_(quality.split(",")))
    if member:
        conds.append(LootEvent.user_id == member)
    if category:
        conds.append(LootEvent.category.in_(category.split(",")))
    total = db.scalar(select(func.count(LootEvent.id)).where(*conds))
    base = (select(LootEvent, User, Character).join(User, User.id == LootEvent.user_id)
            .outerjoin(Character, Character.id == LootEvent.character_id).where(*conds))
    if sort == "celebrated":
        score = (select(func.count(EventReaction.id)).where(EventReaction.event_id == LootEvent.event_id)
                 .correlate(LootEvent).scalar_subquery())
        base = base.order_by(score.desc(), LootEvent.obtained_at.desc())
    else:
        base = base.order_by(LootEvent.obtained_at.desc() if sort == "recent" else LootEvent.obtained_at.asc())
    rows = db.execute(base.limit(limit).offset(offset)).all()
    scores = _celebration_scores(db, [r[0].event_id for r in rows])
    return {"total": total, "items": [_loot_row(lo, u, c, scores.get(lo.event_id, 0)) for lo, u, c in rows]}


@router.get("/loot/highlights")
def loot_highlights(access: Access, db: DB):
    gid = access.group.id
    vis = stats.loot_visible(gid)

    def one(*conds, order):
        r = db.execute(select(LootEvent, User, Character).join(User, User.id == LootEvent.user_id)
                       .outerjoin(Character, Character.id == LootEvent.character_id)
                       .where(vis, *conds).order_by(order).limit(1)).first()
        return _loot_row(r[0], r[1], r[2], 0) if r else None

    first_legendary = one(LootEvent.quality == "legendary", order=LootEvent.obtained_at.asc())
    latest_mount = one(LootEvent.category == "mount", order=LootEvent.obtained_at.desc())
    rows = db.execute(select(LootEvent, User, Character).join(User, User.id == LootEvent.user_id)
                      .outerjoin(Character, Character.id == LootEvent.character_id)
                      .where(vis, LootEvent.event_id.is_not(None))).all()
    scores = _celebration_scores(db, [r[0].event_id for r in rows])
    celebrated = sorted(rows, key=lambda r: (-scores.get(r[0].event_id, 0), -r[0].obtained_at.timestamp()))[:4]
    by_quality = dict(db.execute(select(LootEvent.quality, func.count(LootEvent.id)).where(vis)
                                 .group_by(LootEvent.quality)).all())
    by_category = dict(db.execute(select(LootEvent.category, func.count(LootEvent.id)).where(vis)
                                  .group_by(LootEvent.category)).all())
    return {"first_legendary": first_legendary, "latest_mount": latest_mount,
            "most_celebrated": [_loot_row(lo, u, c, scores.get(lo.event_id, 0))
                                for lo, u, c in celebrated if scores.get(lo.event_id, 0) > 0],
            "by_quality": by_quality, "by_category": by_category}


# ----------------------------------------------------------------------------- statistics
@router.get("/stats/overview")
def stats_overview(access: Access, db: DB, period: str = "all_time", start: datetime | None = None,
                   end: datetime | None = None):
    rng, label = _range(period, start, end)
    return {"period": period, "label": label, "start": rng.start, "end": rng.end,
            **stats.overview(db, access.group.id, rng), "coverage": stats.coverage(db, access.group.id)}


@router.get("/stats/timeseries")
def stats_timeseries(access: Access, db: DB, period: str = "all_time", start: datetime | None = None,
                     end: datetime | None = None, bucket: str = Query("month", pattern="^(week|month)$")):
    rng, label = _range(period, start, end)
    return {"label": label, "bucket": bucket, "series": stats.timeseries(db, access.group.id, rng, bucket)}


@router.get("/stats/members")
def stats_members(access: Access, db: DB, period: str = "all_time", start: datetime | None = None,
                  end: datetime | None = None):
    rng, label = _range(period, start, end)
    return {"label": label, "members": stats.member_table(db, access.group.id, rng)}


@router.get("/stats/progression")
def stats_progression(access: Access, db: DB):
    return {"encounters": stats.progression(db, access.group.id), "by_period": stats.by_period(db, access.group.id),
            "expansions": [{"key": w.key, "name": w.name} for w in periods.expansions()],
            "seasons": [{"key": w.key, "name": w.name} for w in periods.seasons()]}


# ----------------------------------------------------------------------------- hall of fame
def _result_out(r: AwardResult, users: dict) -> dict:
    w = users.get(r.winner_user_id)
    return {"award_key": r.award_key, "period_type": r.period_type, "period_label": r.period_label,
            "period_start": r.period_start, "period_end": r.period_end, "status": r.status,
            "winner": UserBrief.model_validate(w).model_dump(mode="json") if w else None,
            "winning_value": float(r.winning_value) if r.winning_value is not None else None,
            "standings": r.standings, "is_final": r.is_final, "computed_at": r.computed_at,
            "calculation_version": r.calculation_version}


@router.get("/awards")
def hall_of_fame(access: Access, db: DB):
    gid = access.group.id
    if not db.scalar(select(func.count(AwardResult.id)).where(AwardResult.group_id == gid)):
        engine.recompute_group(db, gid)
    defs = {d.key: d for d in db.scalars(select(AwardDefinition))}
    results = db.scalars(select(AwardResult).where(AwardResult.group_id == gid)
                         .order_by(AwardResult.period_start.desc())).all()
    users = {u.id: u for u in db.scalars(select(User).join(GroupMembership, GroupMembership.user_id == User.id)
                                         .where(GroupMembership.group_id == gid))}
    now = datetime.now(UTC)
    current = {pt: engine.current_period(pt, now).label for pt in ("week", "month", "season", "all_time")}
    disabled = set((access.group.settings or {}).get("awards", {}).get("disabled", []))
    awards = []
    for rule in RULES.values():
        d = defs.get(rule.key)
        mine = [r for r in results if r.award_key == rule.key]
        cur = {pt: next((_result_out(r, users) for r in mine if r.period_type == pt and r.period_label == lbl), None)
               for pt, lbl in current.items() if pt in rule.period_types}
        history = [_result_out(r, users) for r in mine if r.is_final and r.status in ("awarded", "tied")]
        awards.append({
            "key": rule.key, "title": rule.title, "description": rule.description, "icon": rule.icon,
            "kind": rule.kind, "rules": d.rules if d else rule.rules, "requires": rule.requires, "unit": rule.unit,
            "period_types": list(rule.period_types), "enabled": rule.key not in disabled,
            "current": cur, "history": history[:24],
        })
    # Trophy cabinet: count of finalized wins per member
    cabinet: dict[str, int] = {}
    for r in results:
        if r.is_final and r.winner_user_id and r.status == "awarded":
            cabinet[str(r.winner_user_id)] = cabinet.get(str(r.winner_user_id), 0) + 1
    return {"awards": awards, "current_labels": current, "trophy_cabinet": cabinet,
            "last_computed_at": max((r.computed_at for r in results), default=None)}


@router.post("/awards/recompute")
def recompute_awards(access: Access, db: DB):
    access.require("admin")
    n = engine.recompute_group(db, access.group.id)
    return {"computed": n}


@router.get("/awards/{award_key}/nominations")
def list_nominations(award_key: str, access: Access, db: DB):
    rule = RULES.get(award_key)
    if not rule or rule.kind != "vote":
        raise HTTPException(404, "Not a voted award")
    label = engine.current_period("month").label
    noms = db.execute(select(AwardNomination, User).join(User, User.id == AwardNomination.nominee_user_id)
                      .where(AwardNomination.group_id == access.group.id, AwardNomination.award_key == award_key,
                             AwardNomination.period_label == label)).all()
    votes = dict(db.execute(select(AwardVote.nomination_id, func.count(AwardVote.id))
                            .where(AwardVote.group_id == access.group.id, AwardVote.period_label == label)
                            .group_by(AwardVote.nomination_id)).all())
    my_vote = db.scalar(select(AwardVote.nomination_id).where(
        AwardVote.group_id == access.group.id, AwardVote.award_key == award_key, AwardVote.period_label == label,
        AwardVote.voter_user_id == access.user.id))
    return {"period_label": label, "my_vote": str(my_vote) if my_vote else None,
            "nominations": [{"id": str(n.id), "nominee": UserBrief.model_validate(u).model_dump(mode="json"),
                             "reason": n.reason, "votes": votes.get(n.id, 0)} for n, u in noms]}


@router.post("/awards/{award_key}/nominations", status_code=201)
def nominate(award_key: str, body: NominationIn, access: Access, db: DB):
    rule = RULES.get(award_key)
    if not rule or rule.kind != "vote":
        raise HTTPException(404, "Not a voted award")
    if not db.scalar(select(GroupMembership.id).where(GroupMembership.group_id == access.group.id,
                                                      GroupMembership.user_id == body.nominee_user_id)):
        raise HTTPException(422, "Nominee must be a group member")
    label = engine.current_period("month").label
    engine.sync_definitions(db)
    existing = db.scalar(select(AwardNomination).where(
        AwardNomination.group_id == access.group.id, AwardNomination.award_key == award_key,
        AwardNomination.period_label == label, AwardNomination.nominee_user_id == body.nominee_user_id))
    if existing:
        return {"id": str(existing.id)}
    n = AwardNomination(id=uuid.uuid4(), group_id=access.group.id, award_key=award_key, period_label=label,
                        nominee_user_id=body.nominee_user_id, nominated_by_user_id=access.user.id, reason=body.reason)
    db.add(n)
    db.commit()
    return {"id": str(n.id)}


@router.put("/awards/{award_key}/vote")
def vote(award_key: str, body: VoteIn, access: Access, db: DB):
    label = engine.current_period("month").label
    nom = db.get(AwardNomination, body.nomination_id)
    if not nom or nom.group_id != access.group.id or nom.award_key != award_key or nom.period_label != label:
        raise HTTPException(404, "Nomination not found for the current period")
    v = db.scalar(select(AwardVote).where(AwardVote.group_id == access.group.id, AwardVote.award_key == award_key,
                                          AwardVote.period_label == label, AwardVote.voter_user_id == access.user.id))
    if v is None:
        v = AwardVote(id=uuid.uuid4(), group_id=access.group.id, award_key=award_key, period_label=label,
                      voter_user_id=access.user.id, nomination_id=nom.id, created_at=datetime.now(UTC))
        db.add(v)
    else:
        v.nomination_id = nom.id
    db.flush()
    engine.compute(db, access.group.id, RULES[award_key], engine.current_period("month"))
    db.commit()
    return {"ok": True}


# ----------------------------------------------------------------------------- dashboard
@router.get("/dashboard")
def dashboard(access: Access, db: DB):
    gid = access.group.id
    vis = and_(AdventureEvent.group_id == gid, AdventureEvent.deleted_at.is_(None), AdventureEvent.hidden.is_(False))
    threshold = (access.group.settings or {}).get("events", {}).get("timeline_min_importance", 30)
    important = or_(AdventureEvent.importance >= threshold, AdventureEvent.is_manual, AdventureEvent.pinned)

    def recent(*conds, n=5):
        ids = list(db.scalars(select(AdventureEvent.id).where(vis, *conds)
                              .order_by(AdventureEvent.occurred_at.desc()).limit(n)))
        return events_out(db, load_events(db, ids), access)

    featured_id = db.scalar(select(AdventureEvent.id).where(vis, AdventureEvent.pinned)
                            .order_by(AdventureEvent.occurred_at.desc()).limit(1)) or db.scalar(
        select(AdventureEvent.id).where(vis, AdventureEvent.extra["milestone"].as_string().is_not(None))
        .order_by(AdventureEvent.occurred_at.desc()).limit(1)) or db.scalar(
        select(AdventureEvent.id).where(vis, AdventureEvent.highlight.is_not(None))
        .order_by(AdventureEvent.importance.desc(), AdventureEvent.occurred_at.desc()).limit(1))
    featured = events_out(db, load_events(db, [featured_id]), access)[0] if featured_id else None
    rng = stats.Range(None, None)
    ov = stats.overview(db, gid, rng)
    if not db.scalar(select(func.count(AwardResult.id)).where(AwardResult.group_id == gid)):
        engine.recompute_group(db, gid)
    month = engine.current_period("month").label
    has_current = db.scalar(select(func.count(AwardResult.id)).where(
        AwardResult.group_id == gid, AwardResult.period_type == "month", AwardResult.period_label == month,
        AwardResult.winner_user_id.is_not(None)))
    if not has_current:  # early in a month: show the most recent month that has decided awards
        month = db.scalar(select(AwardResult.period_label).where(
            AwardResult.group_id == gid, AwardResult.period_type == "month", AwardResult.winner_user_id.is_not(None))
            .order_by(AwardResult.period_start.desc()).limit(1)) or month
    leaders = db.execute(select(AwardResult, User).outerjoin(User, User.id == AwardResult.winner_user_id)
                         .where(AwardResult.group_id == gid, AwardResult.period_type == "month",
                                AwardResult.period_label == month, AwardResult.winner_user_id.is_not(None))).all()
    return {
        "overview": ov,
        "coverage": stats.coverage(db, gid),
        "recent_activity": recent(important, n=8),
        "recent_boss_kills": recent(AdventureEvent.event_type == "boss_kill", n=4),
        "recent_achievements": recent(AdventureEvent.event_type == "achievement", important, n=4),
        "recent_loot": recent(AdventureEvent.event_type == "loot", n=4),
        "featured": featured,
        "award_leaders": [{"award_key": r.award_key, "title": RULES[r.award_key].title,
                           "icon": RULES[r.award_key].icon, "unit": RULES[r.award_key].unit,
                           "value": float(r.winning_value or 0), "status": r.status,
                           "winner": UserBrief.model_validate(u).model_dump(mode="json")}
                          for r, u in leaders if r.award_key in RULES],
        "award_period_label": month,
    }


# ----------------------------------------------------------------------------- member profile
@router.get("/members/{user_id}/profile")
def member_profile(user_id: uuid.UUID, access: Access, db: DB):
    gid = access.group.id
    m = db.scalar(select(GroupMembership).where(GroupMembership.group_id == gid, GroupMembership.user_id == user_id))
    if m is None:
        raise HTTPException(404, "Member not found")
    user = db.get(User, user_id)
    chars = db.scalars(select(Character).where(Character.owner_user_id == user_id)
                       .order_by(Character.is_main.desc(), Character.name)).all()
    table = {r["user_id"]: r for r in stats.member_table(db, gid, stats.Range(None, None))}
    ids = list(db.scalars(
        select(AdventureEvent.id).join(EventParticipant, EventParticipant.event_id == AdventureEvent.id)
        .where(AdventureEvent.group_id == gid, AdventureEvent.deleted_at.is_(None), AdventureEvent.hidden.is_(False),
               EventParticipant.user_id == user_id)
        .order_by(AdventureEvent.occurred_at.desc()).limit(12)))
    wins = db.execute(select(AwardResult.award_key, func.count(AwardResult.id))
                      .where(AwardResult.group_id == gid, AwardResult.winner_user_id == user_id,
                             AwardResult.is_final, AwardResult.status == "awarded")
                      .group_by(AwardResult.award_key)).all()
    per_char = dict(db.execute(select(EventParticipant.character_id, func.count(EventParticipant.id))
                               .join(AdventureEvent, AdventureEvent.id == EventParticipant.event_id)
                               .where(AdventureEvent.group_id == gid, AdventureEvent.deleted_at.is_(None),
                                      EventParticipant.user_id == user_id)
                               .group_by(EventParticipant.character_id)).all())
    return {
        "user": UserBrief.model_validate(user).model_dump(mode="json"), "role": m.role, "joined_at": m.joined_at,
        "stats": table.get(str(user_id)),
        "characters": [{**CharacterOut.model_validate(c).model_dump(mode="json"), "group_events": per_char.get(c.id, 0)}
                       for c in chars],
        "recent_events": events_out(db, load_events(db, ids), access),
        "award_wins": [{"award_key": k, "title": RULES[k].title if k in RULES else k, "icon": RULES[k].icon
                        if k in RULES else "trophy", "count": n} for k, n in wins],
    }
