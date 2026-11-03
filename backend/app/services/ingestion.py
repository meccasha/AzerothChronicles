"""Ingestion: raw source records -> immutable IngestionRecord rows -> canonical events.

Guarantees:
* Idempotent per (user, source, record id): re-uploading the same export is a no-op.
* Cross-reporter dedup: two members reporting the same boss pull produce one attempt/event.
* Participation is attributed only from evidence: the reporter's own client ("confirmed") or the
  reporter's group roster matched to a group member's known character ("roster").
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Achievement,
    AdventureEvent,
    Character,
    CharacterAchievement,
    Encounter,
    EncounterAttempt,
    EncounterAttemptParticipant,
    GameInstance,
    Group,
    GroupItemRule,
    GroupMembership,
    IngestionRecord,
    Item,
    LootEvent,
    SyncJob,
    SyncSource,
    User,
)
from app.schemas.ingest import (
    AchievementRecord,
    CharacterInfo,
    CollectibleRecord,
    DungeonRecord,
    EncounterRecord,
    IngestEnvelope,
    IngestResult,
    LootRecord,
)
from app.services import importance
from app.services.characters import (
    apply_identity,
    find_group_character,
    realm_key,
    realm_slug,
    record_identity,
)
from app.services.events import add_participant, get_or_create_event, lock_group, recompute_highlights
from app.services.game_media import icon_url_from_name, name_key
from app.services.group_settings import GroupSettings, load_settings
from app.services.sessions import rebuild_activity_sessions

QUALITY_NAMES = {0: "poor", 1: "common", 2: "uncommon", 3: "rare", 4: "epic", 5: "legendary",
                 6: "artifact", 7: "heirloom", 8: "token"}
# Fallback names for common DifficultyIDs; the addon normally sends the localized name itself.
DIFFICULTY_NAMES = {1: "Normal", 2: "Heroic", 8: "Mythic Keystone", 14: "Normal", 15: "Heroic", 16: "Mythic",
                    17: "Looking For Raid", 23: "Mythic", 24: "Timewalking", 33: "Timewalking", 220: "Story"}
ATTEMPT_MATCH_WINDOW = timedelta(seconds=180)
DUNGEON_MATCH_WINDOW = timedelta(seconds=300)


class RecordRejected(Exception):
    pass


class RecordIgnored(Exception):
    pass


@dataclass
class _Ctx:
    db: Session
    user: User
    source: str
    is_demo: bool
    groups: list[tuple[Group, GroupMembership, GroupSettings]]
    chars: dict[str, Character]
    stats: dict[str, int] = field(default_factory=lambda: dict(
        received=0, normalized=0, duplicates=0, ignored=0, rejected=0, events_created=0, events_merged=0))
    messages: list[str] = field(default_factory=list)


def ts(value: int) -> datetime:
    return datetime.fromtimestamp(value, UTC)


# ---------------------------------------------------------------------------------------------
# Characters
# ---------------------------------------------------------------------------------------------

def resolve_characters(db: Session, user: User, infos: list[CharacterInfo], source: str) -> dict[str, Character]:
    out: dict[str, Character] = {}
    for info in infos:
        ch = db.scalar(select(Character).where(Character.player_guid == info.guid))
        if ch is not None and ch.owner_user_id != user.id:
            continue  # GUID belongs to someone else's character -> never hijack; records will be rejected
        if ch is None:
            # Adopt an existing (e.g. Blizzard-verified or manual) character by name + realm.
            for cand in db.scalars(
                select(Character).where(Character.owner_user_id == user.id,
                                        func.lower(Character.name) == info.name.lower())
            ):
                if realm_key(cand.realm_name) == realm_key(info.realm) or realm_key(cand.realm_slug) == realm_key(
                    info.realm
                ):
                    ch = cand
                    break
        if ch is None:
            ch = Character(
                id=uuid.uuid4(), owner_user_id=user.id, region=info.region.lower(), realm_slug=realm_slug(info.realm),
                realm_name=info.realm, name=info.name, verification="addon_reported",
            )
            db.add(ch)
            db.flush()
            record_identity(db, ch, "created", source)
        else:
            apply_identity(db, ch, name=info.name, realm_name=info.realm, region=info.region.lower(),
                           faction=info.faction, source=source)
        ch.player_guid = info.guid
        ch.character_class = info.class_name or ch.character_class
        ch.race = info.race or ch.race
        ch.faction = info.faction or ch.faction
        ch.level = info.level or ch.level
        ch.specialization = info.spec or ch.specialization
        out[info.guid] = ch
    db.flush()
    return out


def _record_character(ctx: _Ctx, rec) -> Character:
    if rec.character_guid:
        ch = ctx.chars.get(rec.character_guid)
        if ch is None:
            raise RecordRejected("character GUID not declared in export or belongs to another user")
        return ch
    if len(ctx.chars) == 1:
        return next(iter(ctx.chars.values()))
    raise RecordRejected("record has no character_guid and export declares several characters")


# ---------------------------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------------------------

def get_instance(db: Session, *, name: str | None, map_id: int | None, journal_instance_id: int | None,
                 instance_type: str | None, is_demo: bool) -> GameInstance | None:
    """Find or create the dungeon/raid row: journal id > map id > normalized name."""
    if not name and not journal_instance_id and not map_id:
        return None
    inst = None
    if journal_instance_id:
        inst = db.scalar(select(GameInstance).where(GameInstance.journal_instance_id == journal_instance_id))
    if inst is None and map_id:
        inst = db.scalar(select(GameInstance).where(GameInstance.map_id == map_id).limit(1))
    if inst is None and name:
        inst = db.scalar(select(GameInstance).where(func.lower(GameInstance.name) == name.lower()).limit(1))
        if inst is None:  # tolerant match ("The Stonevault" vs "Stonevault"); only a few hundred rows exist
            key = name_key(name)
            inst = next((c for c in db.scalars(select(GameInstance)) if name_key(c.name) == key), None)
    if inst is None:
        inst = GameInstance(name=name or f"Instance {map_id or journal_instance_id}", map_id=map_id,
                            journal_instance_id=journal_instance_id, instance_type=instance_type, is_demo=is_demo)
        db.add(inst)
        db.flush()
        return inst
    if journal_instance_id and inst.journal_instance_id is None and not db.scalar(
            select(GameInstance.id).where(GameInstance.journal_instance_id == journal_instance_id)):
        inst.journal_instance_id = journal_instance_id
        inst.media_fetched_at = None  # exact id now known: (re)fetch artwork
    inst.map_id = inst.map_id or map_id
    inst.instance_type = inst.instance_type or instance_type
    return inst


def _get_encounter(db: Session, rec: EncounterRecord, is_demo: bool) -> Encounter:
    itype = "raid" if rec.instance_type == "raid" else "dungeon"
    enc = db.scalar(select(Encounter).where(Encounter.dungeon_encounter_id == rec.encounter_id))
    if enc is None:
        enc = Encounter(
            dungeon_encounter_id=rec.encounter_id, name=rec.encounter_name, instance_name=rec.instance_name,
            instance_id=rec.instance_id, instance_type=itype, is_demo=is_demo,
        )
        db.add(enc)
        db.flush()
    if enc.game_instance_id is None or rec.journal_instance_id:
        inst = get_instance(db, name=rec.instance_name, map_id=rec.instance_id,
                            journal_instance_id=rec.journal_instance_id, instance_type=itype, is_demo=is_demo)
        if inst is not None:
            enc.game_instance_id = inst.id
    if rec.journal_encounter_id and enc.journal_encounter_id is None and not db.scalar(
            select(Encounter.id).where(Encounter.journal_encounter_id == rec.journal_encounter_id)):
        enc.journal_encounter_id = rec.journal_encounter_id
        enc.media_fetched_at = None
    return enc


def _attempt_participant(db: Session, attempt: EncounterAttempt, user_id: uuid.UUID, character_id, confirmation,
                         deaths: int | None) -> None:
    p = db.scalar(select(EncounterAttemptParticipant).where(
        EncounterAttemptParticipant.attempt_id == attempt.id, EncounterAttemptParticipant.user_id == user_id))
    if p is None:
        db.add(EncounterAttemptParticipant(id=uuid.uuid4(), attempt_id=attempt.id, user_id=user_id,
                                           character_id=character_id, confirmation=confirmation, deaths=deaths))
    else:
        if confirmation == "confirmed":
            p.confirmation = "confirmed"
            p.character_id = character_id
            if deaths is not None:
                p.deaths = deaths
    db.flush()


def handle_encounter(ctx: _Ctx, rec: EncounterRecord, ch: Character) -> dict:
    if rec.instance_type not in ("raid", "party"):
        raise RecordIgnored(f"instance type '{rec.instance_type}' is not tracked")
    db = ctx.db
    enc = _get_encounter(db, rec, ctx.is_demo)
    difficulty = rec.difficulty_name or DIFFICULTY_NAMES.get(rec.difficulty_id or -1, "Unknown")
    ended = ts(rec.end_time)
    refs: dict = {"encounter_id": enc.id, "attempts": [], "events": []}
    for group, _membership, settings in ctx.groups:
        lock_group(db, group.id)
        attempt = db.scalar(
            select(EncounterAttempt).where(
                EncounterAttempt.group_id == group.id,
                EncounterAttempt.encounter_id == enc.id,
                EncounterAttempt.difficulty == difficulty,
                EncounterAttempt.success.is_(rec.success),
                EncounterAttempt.ended_at.between(ended - ATTEMPT_MATCH_WINDOW, ended + ATTEMPT_MATCH_WINDOW),
            )
        )
        if attempt is None:
            attempt = EncounterAttempt(
                id=uuid.uuid4(), group_id=group.id, encounter_id=enc.id, difficulty_id=rec.difficulty_id,
                difficulty=difficulty, started_at=ts(rec.start_time) if rec.start_time else None, ended_at=ended,
                success=rec.success, group_size=rec.group_size, source=ctx.source, is_demo=ctx.is_demo,
                dedup_key=f"enc:{rec.encounter_id}:{difficulty.lower()}:{rec.end_time}:{'k' if rec.success else 'w'}",
            )
            db.add(attempt)
            db.flush()
        else:
            already = db.scalar(select(EncounterAttemptParticipant).where(
                EncounterAttemptParticipant.attempt_id == attempt.id,
                EncounterAttemptParticipant.user_id == ctx.user.id,
                EncounterAttemptParticipant.confirmation == "confirmed"))
            if already is None:
                attempt.reporter_count += 1
        _attempt_participant(db, attempt, ctx.user.id, ch.id, "confirmed", rec.deaths)
        for entry in rec.roster:
            match = find_group_character(db, group.id, entry.name, entry.realm, ch.realm_name)
            if match and match.owner_user_id != ctx.user.id:
                _attempt_participant(db, attempt, match.owner_user_id, match.id, "roster", None)
        refs["attempts"].append(str(attempt.id))

        if not rec.success:
            continue
        parts = db.scalars(select(EncounterAttemptParticipant).where(
            EncounterAttemptParticipant.attempt_id == attempt.id)).all()
        if len(parts) < settings.events.encounter_min_members:
            ctx.messages.append(f"{enc.name}: below the group's minimum member count; kill recorded, not posted")
            continue
        event, created = get_or_create_event(
            db, group.id, f"boss:{attempt.dedup_key}",
            event_type="boss_kill", title=f"{enc.name} defeated",
            description=f"{difficulty} {enc.instance_name or ''}".strip(),
            occurred_at=ended, time_precision="exact",
            importance=importance.boss_kill_importance(enc.instance_type, difficulty, False, len(parts)),
            encounter_id=enc.id, difficulty=difficulty, instance_name=enc.instance_name,
            game_instance_id=enc.game_instance_id,
            source=ctx.source, provenance="live", confidence="confirmed", is_demo=ctx.is_demo,
            extra={"group_size": rec.group_size,
                   "duration_s": (rec.end_time - rec.start_time) if rec.start_time else None},
        )
        attempt.event_id = event.id
        for p in parts:
            add_participant(db, event, p.user_id, p.character_id, p.confirmation)
        ctx.stats["events_created" if created else "events_merged"] += 1
        refs["events"].append(str(event.id))
    return refs


def handle_achievement(ctx: _Ctx, rec: AchievementRecord, ch: Character) -> dict:
    db = ctx.db
    ach = db.get(Achievement, rec.achievement_id)
    if ach is None:
        ach = Achievement(id=rec.achievement_id, name=rec.name, points=rec.points, description=rec.description,
                          is_feat_of_strength=rec.feat_of_strength, is_demo=ctx.is_demo)
        db.add(ach)
        db.flush()
    earned = ts(rec.earned_at)
    known = db.scalar(select(CharacterAchievement).where(
        CharacterAchievement.character_id == ch.id, CharacterAchievement.achievement_id == ach.id))
    if known is None:
        db.add(CharacterAchievement(id=uuid.uuid4(), character_id=ch.id, achievement_id=ach.id,
                                    completed_at=earned, observed_at=datetime.now(UTC),
                                    source="demo" if ctx.is_demo else "addon"))
        db.flush()
    elif known.completed_at is None:
        known.completed_at = earned
    refs: dict = {"achievement_id": ach.id, "events": []}
    for group, _m, settings in ctx.groups:
        if not importance.should_post_achievement(ach.points, ach.is_feat_of_strength,
                                                  settings.events.achievement_min_points):
            continue
        lock_group(db, group.id)
        window = timedelta(hours=settings.events.achievement_merge_hours)
        event = db.scalar(select(AdventureEvent).where(
            AdventureEvent.group_id == group.id, AdventureEvent.event_type == "achievement",
            AdventureEvent.achievement_id == ach.id, AdventureEvent.deleted_at.is_(None),
            AdventureEvent.occurred_at.between(earned - window, earned + window)))
        created = False
        if event is None:
            event, created = get_or_create_event(
                db, group.id, f"ach:{ach.id}:{rec.earned_at}:{ctx.user.id}",
                event_type="achievement", title=ach.name, description=ach.description or "",
                occurred_at=earned, time_precision="exact",
                importance=importance.achievement_importance(ach.points, ach.is_feat_of_strength, 1),
                achievement_id=ach.id, source=ctx.source, provenance="live", confidence="confirmed",
                is_demo=ctx.is_demo, extra={"points": ach.points, "feat_of_strength": ach.is_feat_of_strength},
            )
        add_participant(db, event, ctx.user.id, ch.id, "confirmed")
        ctx.stats["events_created" if created else "events_merged"] += 1
        refs["events"].append(str(event.id))
    return refs


def _loot_category(item_class: str | None, item_subclass: str | None) -> str:
    c, s = (item_class or "").lower(), (item_subclass or "").lower()
    if "mount" in s or "mount" in c:
        return "mount"
    if "pet" in s or "companion" in s or "battle pet" in c:
        return "pet"
    if "toy" in s or "toy" in c:
        return "toy"
    if c in ("armor", "weapon") or "armor" in c or "weapon" in c:
        return "gear"
    return "other"


def _notable_reason(settings: GroupSettings, rule: str | None, quality: str, category: str,
                    item_level: int | None) -> str | None:
    if rule == "exclude":
        return None
    if rule in ("favorite", "wishlist"):
        return rule
    lr = settings.loot
    if quality == "legendary" and lr.record_legendary:
        return "legendary"
    if category == "mount" and lr.record_mounts:
        return "mount"
    if category in ("pet", "toy") and lr.record_collectibles:
        return "collectible"
    if quality == "epic" and lr.record_epic:
        if lr.epic_min_item_level and (item_level or 0) < lr.epic_min_item_level:
            return None
        return "epic"
    if quality == "rare" and lr.record_rare:
        return "rare"
    return None


def _record_loot(ctx: _Ctx, ch: Character, *, item_id: int | None, name: str, quality: str, category: str,
                 icon: str | None, when: datetime, dedup: str, instance: str | None, difficulty: str | None,
                 encounter_db_id: int | None, item_level: int | None, collectible_id: int | None = None) -> dict:
    db = ctx.db
    refs: dict = {"loot_events": [], "events": []}
    any_notable = False
    for group, _m, settings in ctx.groups:
        rule = None
        if item_id is not None:
            rule = db.scalar(select(GroupItemRule.rule).where(GroupItemRule.group_id == group.id,
                                                              GroupItemRule.item_id == item_id))
        reason = _notable_reason(settings, rule, quality, category, item_level)
        if reason is None:
            continue
        any_notable = True
        lock_group(db, group.id)
        loot = db.scalar(select(LootEvent).where(LootEvent.group_id == group.id, LootEvent.dedup_key == dedup))
        if loot is not None:
            ctx.stats["events_merged"] += 1
            continue
        event = None
        if "loot" in settings.events.enabled_categories:
            event, _ = get_or_create_event(
                db, group.id, dedup, event_type="loot", title=name,
                description=" · ".join(x for x in [difficulty, instance] if x),
                occurred_at=when, time_precision="exact",
                importance=importance.loot_importance(quality, category, reason),
                item_id=item_id, difficulty=difficulty, instance_name=instance, encounter_id=encounter_db_id,
                source=ctx.source, provenance="live", confidence="confirmed", is_demo=ctx.is_demo,
                extra={"quality": quality, "category": category, "notable_reason": reason,
                       "item_level": item_level},
            )
            add_participant(db, event, ctx.user.id, ch.id, "confirmed")
            refs["events"].append(str(event.id))
        loot = LootEvent(
            id=uuid.uuid4(), group_id=group.id, item_id=item_id, item_name=name, quality=quality,
            category=category, icon_url=icon, user_id=ctx.user.id, character_id=ch.id, obtained_at=when,
            source_instance=instance, source_encounter_id=encounter_db_id, difficulty=difficulty,
            notable_reason=reason, source=ctx.source, dedup_key=dedup, collectible_id=collectible_id,
            event_id=event.id if event else None, is_demo=ctx.is_demo,
        )
        db.add(loot)
        db.flush()
        refs["loot_events"].append(str(loot.id))
        ctx.stats["events_created"] += 1
    if not any_notable:
        raise RecordIgnored("item does not meet any group's notable-loot rules")
    return refs


def _icon_fields(icon_file_id: int | None, legacy: str | None) -> tuple[int | None, str | None]:
    """Addon icons are FileDataIDs (numbers); only texture *names* can be turned into CDN URLs."""
    if legacy and legacy.strip().isdigit():
        return icon_file_id or int(legacy.strip()), None
    return icon_file_id, icon_url_from_name(legacy)


def _upsert_item(db: Session, item_id: int, name: str, quality: str, item_class, item_subclass,
                 icon_file_id: int | None, icon_url: str | None, is_demo: bool) -> Item:
    item = db.get(Item, item_id)
    if item is None:
        item = Item(id=item_id, name=name, quality=quality, item_class=item_class, item_subclass=item_subclass,
                    icon_file_id=icon_file_id, icon_url=icon_url, metadata_source="addon", is_demo=is_demo)
        db.add(item)
        db.flush()
    else:
        item.icon_file_id = item.icon_file_id or icon_file_id
        item.icon_url = item.icon_url or icon_url
    return item


def handle_loot(ctx: _Ctx, rec: LootRecord, ch: Character) -> dict:
    quality = QUALITY_NAMES.get(rec.quality, "unknown")
    category = _loot_category(rec.item_class, rec.item_subclass)
    file_id, icon_url = _icon_fields(rec.icon_file_id, rec.icon)
    item = _upsert_item(ctx.db, rec.item_id, rec.item_name, quality, rec.item_class, rec.item_subclass, file_id,
                        icon_url, ctx.is_demo)
    enc_id = None
    if rec.encounter_id:
        enc_id = ctx.db.scalar(select(Encounter.id).where(Encounter.dungeon_encounter_id == rec.encounter_id))
    return _record_loot(
        ctx, ch, item_id=rec.item_id, name=rec.item_name, quality=quality, category=category, icon=item.icon_url,
        when=ts(rec.looted_at), dedup=f"loot:{ch.id}:{rec.item_id}:{rec.looted_at // 60}",
        instance=rec.instance_name, difficulty=rec.difficulty_name, encounter_db_id=enc_id,
        item_level=rec.item_level,
    )


def handle_collectible(ctx: _Ctx, rec: CollectibleRecord, ch: Character) -> dict:
    quality = "unknown"
    item = ctx.db.get(Item, rec.item_id) if rec.item_id else None
    if item:
        quality = item.quality
    return _record_loot(
        ctx, ch, item_id=item.id if item else None,
        name=rec.name, quality=quality, category=rec.type, icon=item.icon_url if item else None,
        when=ts(rec.learned_at),
        dedup=f"{rec.type}:{ctx.user.id}:{rec.collectible_id}", instance=None, difficulty=None,
        encounter_db_id=None, item_level=None, collectible_id=rec.collectible_id,
    )


def handle_dungeon(ctx: _Ctx, rec: DungeonRecord, ch: Character) -> dict:
    db = ctx.db
    when = ts(rec.completed_at)
    refs: dict = {"events": []}
    title = f"{rec.name} +{rec.keystone_level}" if rec.keystone_level else rec.name
    inst = get_instance(db, name=rec.name, map_id=rec.instance_id, journal_instance_id=rec.journal_instance_id,
                        instance_type="dungeon", is_demo=ctx.is_demo)
    for group, _m, settings in ctx.groups:
        if "dungeon_complete" not in settings.events.enabled_categories:
            continue
        lock_group(db, group.id)
        candidates = db.scalars(select(AdventureEvent).where(
            AdventureEvent.group_id == group.id, AdventureEvent.event_type == "dungeon_complete",
            AdventureEvent.deleted_at.is_(None),
            AdventureEvent.occurred_at.between(when - DUNGEON_MATCH_WINDOW, when + DUNGEON_MATCH_WINDOW))).all()
        event = next((e for e in candidates if e.extra.get("map_id") == rec.map_id
                      and e.extra.get("keystone_level") == rec.keystone_level), None)
        created = False
        if event is None:
            event, created = get_or_create_event(
                db, group.id, f"dungeon:{rec.map_id}:{rec.keystone_level or 0}:{rec.completed_at}",
                event_type="dungeon_complete", title=title,
                description=("Completed in time" if rec.on_time else "Completed (over time)")
                if rec.on_time is not None else "Dungeon completed",
                occurred_at=when, time_precision="exact",
                importance=importance.dungeon_importance(rec.keystone_level, 1 + len(rec.roster)),
                instance_name=rec.name, difficulty=f"Mythic+ {rec.keystone_level}" if rec.keystone_level else None,
                game_instance_id=inst.id if inst else None,
                source=ctx.source, provenance="live", confidence="confirmed", is_demo=ctx.is_demo,
                extra={"map_id": rec.map_id, "keystone_level": rec.keystone_level, "on_time": rec.on_time,
                       "duration_ms": rec.duration_ms},
            )
        if event.game_instance_id is None and inst is not None:
            event.game_instance_id = inst.id
        add_participant(db, event, ctx.user.id, ch.id, "confirmed")
        for entry in rec.roster:
            match = find_group_character(db, group.id, entry.name, entry.realm, ch.realm_name)
            if match and match.owner_user_id != ctx.user.id:
                add_participant(db, event, match.owner_user_id, match.id, "roster")
        ctx.stats["events_created" if created else "events_merged"] += 1
        refs["events"].append(str(event.id))
    return refs


HANDLERS = {
    "encounter": handle_encounter,
    "achievement": handle_achievement,
    "loot": handle_loot,
    "mount": handle_collectible,
    "pet": handle_collectible,
    "toy": handle_collectible,
    "dungeon_complete": handle_dungeon,
}


# ---------------------------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------------------------

def recompute_wipe_streaks(db: Session, group_id: uuid.UUID) -> None:
    attempts = db.scalars(
        select(EncounterAttempt).where(EncounterAttempt.group_id == group_id)
        .order_by(EncounterAttempt.encounter_id, EncounterAttempt.difficulty, EncounterAttempt.ended_at)
    ).all()
    streak: dict[tuple, int] = {}
    for a in attempts:
        key = (a.encounter_id, a.difficulty)
        if not a.success:
            streak[key] = streak.get(key, 0) + 1
            continue
        wipes = streak.pop(key, 0)
        if a.event_id:
            ev = db.get(AdventureEvent, a.event_id)
            if ev is not None:
                extra = dict(ev.extra or {})
                extra["wipes_before_kill"] = wipes
                ev.extra = extra
    db.flush()


def finalize_groups(db: Session, group_ids: list[uuid.UUID]) -> None:
    for gid in group_ids:
        recompute_wipe_streaks(db, gid)
        recompute_highlights(db, gid)
        rebuild_activity_sessions(db, gid)


def ingest_envelope(db: Session, user: User, env: IngestEnvelope, *, is_demo: bool = False,
                    finalize: bool = True) -> IngestResult:
    now = datetime.now(UTC)
    job = SyncJob(id=uuid.uuid4(), user_id=user.id, kind=f"{env.source}_import", status="running",
                  started_at=now)
    db.add(job)
    rows = db.execute(
        select(Group, GroupMembership).join(GroupMembership, GroupMembership.group_id == Group.id)
        .where(GroupMembership.user_id == user.id)
    ).all()
    groups = [(g, m, load_settings(g.settings)) for g, m in rows]
    ctx = _Ctx(db=db, user=user, source="demo" if is_demo else ("addon" if env.source != "simulated" else "simulated"),
               is_demo=is_demo, groups=groups, chars=resolve_characters(db, user, env.characters, env.source))
    if not groups:
        ctx.messages.append("You are not in any group yet; records are stored and will not appear on a timeline.")

    for rec in env.records:
        ctx.stats["received"] += 1
        key = f"{env.source}:{rec.type}:{rec.id}"
        if db.scalar(select(IngestionRecord.id).where(IngestionRecord.user_id == user.id,
                                                      IngestionRecord.idempotency_key == key)):
            ctx.stats["duplicates"] += 1
            continue
        raw = IngestionRecord(id=uuid.uuid4(), user_id=user.id, sync_job_id=job.id, source=env.source,
                              record_type=rec.type, idempotency_key=key, payload=rec.model_dump(mode="json"),
                              received_at=now, status="normalized")
        try:
            with db.begin_nested():
                ch = _record_character(ctx, rec)
                raw.canonical_refs = HANDLERS[rec.type](ctx, rec, ch)
            ctx.stats["normalized"] += 1
        except RecordIgnored as exc:
            raw.status, raw.status_detail = "ignored", str(exc)
            ctx.stats["ignored"] += 1
        except RecordRejected as exc:
            raw.status, raw.status_detail = "rejected", str(exc)
            ctx.stats["rejected"] += 1
        except Exception as exc:  # keep the batch going; record the failure for troubleshooting
            raw.status, raw.status_detail = "rejected", f"processing error: {exc.__class__.__name__}: {exc}"[:500]
            ctx.stats["rejected"] += 1
        db.add(raw)
        db.flush()

    if finalize:
        finalize_groups(db, [g.id for g, _, _ in groups])

    job.status = "succeeded" if ctx.stats["rejected"] == 0 else "partial"
    job.finished_at = datetime.now(UTC)
    job.stats = dict(ctx.stats)
    if not is_demo:
        src = db.scalar(select(SyncSource).where(SyncSource.user_id == user.id, SyncSource.kind == "addon"))
        if src is None:
            src = SyncSource(id=uuid.uuid4(), user_id=user.id, kind="addon")
            db.add(src)
        src.last_attempt_at = job.finished_at
        src.last_success_at = job.finished_at
        src.status = "ok" if ctx.stats["rejected"] == 0 else "error"
        src.last_error = None if ctx.stats["rejected"] == 0 else f"{ctx.stats['rejected']} record(s) rejected"
        src.details = {"addon_version": env.addon_version, "exported_at": env.exported_at,
                       "last_job_id": str(job.id)}
    db.commit()
    return IngestResult(**ctx.stats, groups=[g.name for g, _, _ in groups], messages=ctx.messages,
                        sync_job_id=str(job.id))
