"""Deterministic award computation.

compute(rule, period) is a pure function of database rows, so results are reproducible: recomputing
an already-final period yields the same winner. Ties are broken by earliest membership, then name,
and flagged in standings.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import AdventureEvent, AwardDefinition, AwardResult, Group, GroupMembership, User
from app.services import periods as P
from app.services.awards.rules import REGISTRY, RULES, AwardRule, Period
from app.services.group_settings import load_settings

WEEKS_OF_HISTORY = 26


def sync_definitions(db: Session) -> None:
    for r in REGISTRY:
        stmt = insert(AwardDefinition).values(
            key=r.key, title=r.title, description=r.description, icon=r.icon, kind=r.kind, rules=r.rules,
            requires=r.requires, enabled_by_default=True)
        db.execute(stmt.on_conflict_do_update(index_elements=["key"], set_={
            "title": r.title, "description": r.description, "icon": r.icon, "kind": r.kind, "rules": r.rules,
            "requires": r.requires}))
    db.flush()


def month_label(start: datetime) -> str:
    return start.strftime("%Y-%m")


def week_label(start: datetime) -> str:
    y, w, _ = start.isocalendar()
    return f"{y}-W{w:02d}"


def periods_for_group(db: Session, group_id: uuid.UUID, now: datetime | None = None) -> list[Period]:
    now = now or datetime.now(UTC)
    first = db.scalar(select(func.min(AdventureEvent.occurred_at)).where(
        AdventureEvent.group_id == group_id, AdventureEvent.deleted_at.is_(None)))
    group = db.get(Group, group_id)
    origin = min(x for x in (first, group.created_at if group else None, now) if x is not None)
    out = [Period("all_time", "All time", datetime(2004, 11, 23, tzinfo=UTC), now + timedelta(seconds=1))]
    m = P.month_start(origin)
    while m <= now:
        out.append(Period("month", month_label(m), m, P.next_month(m)))
        m = P.next_month(m)
    w = max(P.week_start(origin), P.week_start(now) - timedelta(weeks=WEEKS_OF_HISTORY))
    while w <= now:
        out.append(Period("week", week_label(w), w, w + timedelta(weeks=1)))
        w += timedelta(weeks=1)
    for s in P.seasons():
        if s.start <= now and (s.end is None or s.end > origin):
            out.append(Period("season", s.name, s.start, s.end or now + timedelta(seconds=1)))
    return out


def compute(db: Session, group_id: uuid.UUID, rule: AwardRule, period: Period,
            now: datetime | None = None) -> AwardResult:
    now = now or datetime.now(UTC)
    if db.get(AwardDefinition, rule.key) is None:
        sync_definitions(db)
    members = db.execute(
        select(User.id, User.display_name, GroupMembership.joined_at)
        .join(GroupMembership, GroupMembership.user_id == User.id).where(GroupMembership.group_id == group_id)
    ).all()
    member_info = {uid: (name, joined) for uid, name, joined in members}
    scores = rule.scores(db, group_id, period)
    standings: list[dict] = []
    status = "no_data"
    winner = None
    value = None
    if scores is None:
        status = "insufficient_data"
    else:
        ranked = sorted(
            ((uid, v) for uid, v in scores.items() if uid in member_info),
            key=lambda kv: (-kv[1], member_info[kv[0]][1], member_info[kv[0]][0].lower()),
        )
        top = ranked[0][1] if ranked else 0
        rank = 0
        prev = None
        for i, (uid, v) in enumerate(ranked):
            if v != prev:
                rank, prev = i + 1, v
            standings.append({"user_id": str(uid), "display_name": member_info[uid][0], "value": v, "rank": rank})
        if ranked and top > 0:
            winner, value = ranked[0][0], top
            tied = [s for s in standings if s["value"] == top]
            status = "tied" if len(tied) > 1 else "awarded"
            for s in tied:
                s["tied"] = len(tied) > 1
    values = dict(
        group_id=group_id, award_key=rule.key, period_type=period.type, period_label=period.label,
        period_start=period.start, period_end=period.end, winner_user_id=winner, winning_value=value,
        status=status, standings=standings[:10], calculation_version=rule.version, computed_at=now,
        is_final=period.end <= now and period.type != "all_time",
    )
    stmt = insert(AwardResult).values(id=uuid.uuid4(), **values).on_conflict_do_update(
        constraint="uq_award_result", set_={k: v for k, v in values.items()
                                             if k not in ("group_id", "award_key", "period_type", "period_start")})
    db.execute(stmt)
    return db.scalar(select(AwardResult).where(
        AwardResult.group_id == group_id, AwardResult.award_key == rule.key,
        AwardResult.period_type == period.type, AwardResult.period_start == period.start))


def recompute_group(db: Session, group_id: uuid.UUID, now: datetime | None = None,
                    only_open: bool = False) -> int:
    """Recompute all awards for a group. With only_open, finalized periods are left untouched."""
    sync_definitions(db)
    group = db.get(Group, group_id)
    disabled = set(load_settings(group.settings).awards.disabled) if group else set()
    n = 0
    for period in periods_for_group(db, group_id, now):
        for rule in REGISTRY:
            if rule.key in disabled or period.type not in rule.period_types:
                continue
            if only_open:
                existing = db.scalar(select(AwardResult.is_final).where(
                    AwardResult.group_id == group_id, AwardResult.award_key == rule.key,
                    AwardResult.period_type == period.type, AwardResult.period_start == period.start))
                if existing:
                    continue
            compute(db, group_id, rule, period, now)
            n += 1
    db.commit()
    return n


def current_period(period_type: str, now: datetime | None = None) -> Period:
    now = now or datetime.now(UTC)
    if period_type == "week":
        s = P.week_start(now)
        return Period("week", week_label(s), s, s + timedelta(weeks=1))
    if period_type == "month":
        s = P.month_start(now)
        return Period("month", month_label(s), s, P.next_month(s))
    if period_type == "season":
        w = P.season_for(now)
        if w:
            return Period("season", w.name, w.start, w.end or now + timedelta(seconds=1))
    return Period("all_time", "All time", datetime(2004, 11, 23, tzinfo=UTC), now + timedelta(seconds=1))


__all__ = ["RULES", "REGISTRY", "compute", "recompute_group", "periods_for_group", "current_period"]
