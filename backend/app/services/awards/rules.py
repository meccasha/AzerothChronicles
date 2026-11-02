"""Award rules. To add an award: subclass AwardRule, implement ``scores``, append to REGISTRY.

Each rule maps members -> a numeric score for a period using only recorded rows. Returning ``None``
means the data needed to judge the award does not exist (result status ``insufficient_data``).
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models import (
    AdventureEvent,
    AwardNomination,
    AwardVote,
    Encounter,
    EncounterAttempt,
    EncounterAttemptParticipant,
    EventParticipant,
    GroupMembership,
    LootEvent,
)
from app.services.stats import loot_visible

OBSERVED = ("confirmed", "roster")


@dataclass(frozen=True)
class Period:
    type: str  # week | month | season | all_time
    label: str
    start: datetime
    end: datetime


def _in(col, p: Period):
    return and_(col >= p.start, col < p.end)


def _visible(group_id):
    return and_(AdventureEvent.group_id == group_id, AdventureEvent.deleted_at.is_(None),
                AdventureEvent.hidden.is_(False))


class AwardRule(ABC):
    key: str
    title: str
    description: str
    icon: str
    rules: str
    kind: str = "auto"
    requires: str | None = None
    version: str = "1"
    unit: str = ""
    period_types: tuple[str, ...] = ("week", "month", "season", "all_time")

    @abstractmethod
    def scores(self, db: Session, group_id: uuid.UUID, p: Period) -> dict[uuid.UUID, float] | None: ...


def _participation_counts(db, group_id, p, *conds, confirmations=None) -> dict[uuid.UUID, float]:
    q = (select(EventParticipant.user_id, func.count(EventParticipant.id))
         .join(AdventureEvent, AdventureEvent.id == EventParticipant.event_id)
         .where(_visible(group_id), _in(AdventureEvent.occurred_at, p), *conds)
         .group_by(EventParticipant.user_id))
    if confirmations:
        q = q.where(EventParticipant.confirmation.in_(confirmations))
    return {u: float(n) for u, n in db.execute(q).all()}


class AchievementHunter(AwardRule):
    key, title, icon, unit = "achievement_hunter", "Achievement Hunter", "trophy", "achievements"
    description = "Most recorded achievements earned."
    rules = ("Counts achievement timeline events the member participated in during the period, including "
             "Blizzard-backfilled achievements dated after they joined the group. Achievements shared by several "
             "members count once per member.")

    def scores(self, db, group_id, p):
        return _participation_counts(db, group_id, p, AdventureEvent.event_type == "achievement")


class LootGoblin(AwardRule):
    key, title, icon, unit = "loot_goblin", "Loot Goblin", "gem", "notable items"
    description = "Most notable loot acquisitions."
    rules = "Counts Loot Museum entries (items that met the group's notable-loot rules) obtained in the period."

    def scores(self, db, group_id, p):
        rows = db.execute(select(LootEvent.user_id, func.count(LootEvent.id))
                          .where(loot_visible(group_id), _in(LootEvent.obtained_at, p))
                          .group_by(LootEvent.user_id)).all()
        return {u: float(n) for u, n in rows}


class LegendaryCollector(AwardRule):
    key, title, icon, unit = "legendary_collector", "Legendary Collector", "sparkles", "legendaries"
    description = "Most recorded legendary items obtained."
    rules = "Counts Loot Museum entries of legendary quality obtained in the period."

    def scores(self, db, group_id, p):
        rows = db.execute(select(LootEvent.user_id, func.count(LootEvent.id))
                          .where(loot_visible(group_id), LootEvent.quality == "legendary",
                                 _in(LootEvent.obtained_at, p)).group_by(LootEvent.user_id)).all()
        return {u: float(n) for u, n in rows}


class RaidVeteran(AwardRule):
    key, title, icon, unit = "raid_veteran", "Raid Veteran", "swords", "raid boss kills"
    description = "Most confirmed raid boss victories participated in."
    rules = ("Counts raid boss-kill events where the member's participation is backed by game data (reported by "
             "their own addon, or seen in another member's group roster). Manually tagged participation is "
             "excluded.")

    def scores(self, db, group_id, p):
        return _participation_counts(
            db, group_id, p, AdventureEvent.event_type == "boss_kill",
            AdventureEvent.encounter_id.in_(select(Encounter.id).where(Encounter.instance_type == "raid")),
            confirmations=OBSERVED)


class DungeonExplorer(AwardRule):
    key, title, icon, unit = "dungeon_explorer", "Dungeon Explorer", "compass", "dungeons"
    description = "Most confirmed dungeon completions."
    rules = "Counts dungeon-completion events with game-data-backed participation (addon or roster)."

    def scores(self, db, group_id, p):
        return _participation_counts(db, group_id, p, AdventureEvent.event_type == "dungeon_complete",
                                     confirmations=OBSERVED)


class ProgressionPioneer(AwardRule):
    key, title, icon, unit = "progression_pioneer", "Progression Pioneer", "flag", "first kills"
    description = "Most first-time group kills participated in."
    rules = ("Counts boss kills that were the group's first recorded kill of that boss on that difficulty, "
             "with game-data-backed participation.")

    def scores(self, db, group_id, p):
        return _participation_counts(db, group_id, p, AdventureEvent.event_type == "boss_kill",
                                     AdventureEvent.extra["first_kill"].as_boolean().is_(True),
                                     confirmations=OBSERVED)


def _death_rows(db, group_id, p):
    return db.execute(
        select(EncounterAttemptParticipant.user_id, EncounterAttempt.success, EncounterAttemptParticipant.deaths)
        .join(EncounterAttempt, EncounterAttempt.id == EncounterAttemptParticipant.attempt_id)
        .where(EncounterAttempt.group_id == group_id, _in(EncounterAttempt.ended_at, p),
               EncounterAttemptParticipant.deaths.is_not(None))).all()


class Unbreakable(AwardRule):
    key, title, icon, unit = "unbreakable", "Unbreakable", "shield", "deathless kills"
    description = "Most successful recorded boss encounters without a recorded personal death."
    requires = "death_data"
    rules = ("Counts successful boss attempts where the member's own addon reported zero deaths. Attempts "
             "without death data for that member are ignored. Not awarded if no death data exists in the period.")

    def scores(self, db, group_id, p):
        rows = _death_rows(db, group_id, p)
        if not rows:
            return None
        out: dict[uuid.UUID, float] = {}
        for user_id, success, deaths in rows:
            out.setdefault(user_id, 0.0)
            if success and deaths == 0:
                out[user_id] += 1
        return out


class FloorInspector(AwardRule):
    key, title, icon, unit = "floor_inspector", "The Floor Inspector", "skull", "recorded deaths"
    description = "Most recorded deaths (with love)."
    requires = "death_data"
    rules = ("Sums personal deaths reported by each member's own addon during boss encounters. Members without "
             "death data are not ranked. Not awarded if no death data exists in the period.")

    def scores(self, db, group_id, p):
        rows = _death_rows(db, group_id, p)
        if not rows:
            return None
        out: dict[uuid.UUID, float] = {}
        for user_id, _s, deaths in rows:
            out[user_id] = out.get(user_id, 0.0) + deaths
        return out


class DayOneAdventurer(AwardRule):
    key, title, icon, unit = "day_one", "Day One Adventurer", "sunrise", "days"
    description = "Member with the longest recorded group history."
    period_types = ("all_time",)
    rules = ("Days between the member's earliest recorded activity in the group (first event participation or "
             "membership date, whichever is earlier) and the end of the period.")

    def scores(self, db, group_id, p):
        joined = dict(db.execute(select(GroupMembership.user_id, GroupMembership.joined_at)
                                 .where(GroupMembership.group_id == group_id)).all())
        first = dict(db.execute(
            select(EventParticipant.user_id, func.min(AdventureEvent.occurred_at))
            .join(AdventureEvent, AdventureEvent.id == EventParticipant.event_id)
            .where(_visible(group_id), AdventureEvent.provenance != "backfill")
            .group_by(EventParticipant.user_id)).all())
        out = {}
        for uid, j in joined.items():
            start = min(x for x in (j, first.get(uid)) if x is not None)
            if start < p.end:
                out[uid] = float(max((p.end - start).days, 0))
        return out


class MostActive(AwardRule):
    key, title, icon, unit = "most_active", "Most Active Adventurer", "flame", "activities"
    description = "Most recorded group activities participated in."
    rules = "Counts every visible timeline event the member participated in, including manually logged events."

    def scores(self, db, group_id, p):
        return _participation_counts(db, group_id, p)


class GroupMVP(AwardRule):
    key, title, icon, unit = "group_mvp", "Group MVP", "crown", "votes"
    kind = "vote"
    description = "Voted by the group: who carried us this month?"
    period_types = ("month",)
    rules = ("Members nominate each other during the month and each member casts one vote. Most votes wins; ties "
             "are shown as ties.")

    def scores(self, db, group_id, p):
        rows = db.execute(
            select(AwardNomination.nominee_user_id, func.count(AwardVote.id))
            .join(AwardVote, AwardVote.nomination_id == AwardNomination.id, isouter=True)
            .where(AwardNomination.group_id == group_id, AwardNomination.award_key == self.key,
                   AwardNomination.period_label == p.label)
            .group_by(AwardNomination.nominee_user_id)).all()
        return {u: float(n) for u, n in rows}


REGISTRY: list[AwardRule] = [
    AchievementHunter(), LootGoblin(), LegendaryCollector(), RaidVeteran(), DungeonExplorer(),
    ProgressionPioneer(), Unbreakable(), FloorInspector(), DayOneAdventurer(), MostActive(), GroupMVP(),
]
RULES = {r.key: r for r in REGISTRY}
