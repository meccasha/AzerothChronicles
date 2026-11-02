"""Fictional demo group, generated through the real ingestion pipeline.

Everything here is FICTIONAL: people, characters, realm, raids, bosses, items and achievements.
Three members "run the addon" (their simulated exports are ingested and de-duplicated against each
other); two do not, so they only appear through group rosters or manual entries — exactly how a
real partially-instrumented group looks.
"""

import random
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import (
    Achievement,
    AdventureEvent,
    AwardNomination,
    AwardVote,
    Character,
    EventComment,
    EventReaction,
    Group,
    GroupMembership,
    Item,
    LootEvent,
    SyncSource,
    User,
)
from app.models import Encounter as EncounterModel
from app.schemas.ingest import IngestEnvelope
from app.security import hash_password, new_token
from app.services.awards.engine import recompute_group, sync_definitions
from app.services.events import add_participant, get_or_create_event
from app.services.group_settings import GroupSettings
from app.services.ingestion import finalize_groups, ingest_envelope

DEMO_GROUP_NAME = "The Emberreach Wayfarers (Demo)"
REALM = "Emberreach"
START = datetime(2026, 5, 4, 19, 0, tzinfo=UTC)
END = datetime(2026, 10, 31, 23, 0, tzinfo=UTC)

MEMBERS = [
    # key, display, color, addon?, joined offset days, characters[(name, race, class, spec, level)]
    ("mira", "Mira Vale", "#c08a2b", True, 0, [("Mirabelle", "Night Elf", "Druid", "Restoration", 80),
                                                ("Mireth", "Void Elf", "Mage", "Frost", 74)]),
    ("tobias", "Tobias Reed", "#3f7cac", True, 0, [("Tobrin", "Dwarf", "Paladin", "Protection", 80)]),
    ("kestrel", "Kestrel Ash", "#8c4fb8", True, 0, [("Kestrix", "Gnome", "Rogue", "Outlaw", 80),
                                                    ("Kessaly", "Draenei", "Shaman", "Elemental", 71)]),
    ("dunstan", "Dunstan Moor", "#b5473a", False, 2, [("Dunhollow", "Human", "Warrior", "Fury", 80)]),
    ("yselle", "Yselle Brook", "#2f8f6b", False, 29, [("Ysolde", "Draenei", "Priest", "Holy", 80)]),
]
REPORTERS = ("mira", "tobias", "kestrel")
ATTENDANCE = {"mira": 0.93, "tobias": 0.97, "kestrel": 0.82, "dunstan": 0.88, "yselle": 0.78}

RAID1 = ("The Gilded Necropolis", [
    (9001, "Warden Ossivar"), (9002, "The Choir of Ash"), (9003, "Mistress Velhanne"),
    (9004, "Gorlath the Unyielding"), (9005, "The Twin Sentinels"), (9006, "Archivist Myrr"),
    (9007, "Sythra, Queen of Thorns"), (9008, "Vael'thas the Ashbound")])
RAID2 = ("Spire of the Sundered Sky", [
    (9101, "Stormcaller Ithrax"), (9102, "The Hollow Engine"), (9103, "Lady Seraphine"),
    (9104, "Aeon, the Sky-Sundered")])
DUNGEONS = [(99001, "Hollowroot Depths"), (99002, "The Brass Observatory"), (99003, "Sunken Reliquary"),
            (99004, "Cinderfall Keep")]
DIFF = {"Normal": 14, "Heroic": 15, "Mythic": 16}

EPICS = [
    (9200101, "Ossivar's Grave-Bound Helm", "Armor", "Plate"), (9200102, "Choirbreaker Pauldrons", "Armor", "Mail"),
    (9200103, "Velhanne's Silken Shroud", "Armor", "Cloth"), (9200104, "Gorlath's Bloodied Girdle", "Armor", "Plate"),
    (9200105, "Sentinel's Twinned Edge", "Weapon", "Dagger"), (9200106, "Myrr's Ink-Stained Codex", "Armor", "Misc"),
    (9200107, "Thornwoven Gloves", "Armor", "Leather"), (9200108, "Crown of the Ashbound", "Armor", "Leather"),
    (9200109, "Sky-Sundered Signet", "Armor", "Misc"), (9200110, "Engine-Core Bulwark", "Armor", "Shield"),
    (9200111, "Seraphine's Gilded Staff", "Weapon", "Staff"), (9200112, "Stormcaller's Mantle", "Armor", "Cloth"),
]
LEGENDARY = (9200001, "Thal'dranath, Ember of the First Flame", "Weapon", "Two-Handed Sword")
MOUNT = (9200501, "Reins of the Gilded Bonewing", "Miscellaneous", "Mount")

ACH = {
    "first_dungeon": (9100001, "Hollowroot Delver", 10, "Complete Hollowroot Depths.", False),
    "keystone_init": (9100002, "Keystone Initiate", 10, "Complete a Mythic+ dungeon at level 2 or higher.", False),
    "keystone_adept": (9100003, "Keystone Adept", 15, "Complete all dungeons at level 7 or higher in time.", False),
    "keystone_master": (9100004, "Keystone Master", 25, "Complete all dungeons at level 12 or higher in time.", False),
    "necro_normal": (9100010, "The Gilded Necropolis", 10, "Defeat Vael'thas the Ashbound on Normal.", False),
    "necro_heroic": (9100011, "Heroic: Vael'thas the Ashbound", 10, "Defeat Vael'thas on Heroic.", False),
    "aotc": (9100012, "Ahead of the Curve: Vael'thas the Ashbound", 0,
             "Defeat Vael'thas on Heroic before the next tier opens.", True),
    "glory": (9100013, "Glory of the Necropolis Raider", 25, "Complete the Necropolis meta-achievement.", False),
    "spire_normal": (9100020, "Spire of the Sundered Sky", 10, "Defeat Aeon on Normal.", False),
    "explorer": (9100030, "Explorer of the Ember Isles", 10, "Explore the Ember Isles.", False),
    "loremaster": (9100031, "Loremaster of the Ember Isles", 25, "Complete the Ember Isles storylines.", False),
    "pet_tamer": (9100040, "Taming the Ember Isles", 5, "Defeat the regional pet tamers.", False),
}


def _ts(dt: datetime) -> int:
    return int(dt.timestamp())


class _Builder:
    def __init__(self, rng: random.Random, chars: dict[str, list[dict]]):
        self.rng = rng
        self.chars = chars
        self.records: dict[str, list[dict]] = {k: [] for k in REPORTERS}
        self.n = 0

    def rid(self, key: str, kind: str) -> str:
        self.n += 1
        return f"demo-{key}-{kind}-{self.n}"

    def main(self, key):
        return self.chars[key][0]

    def roster(self, present, exclude):
        return [{"name": self.main(k)["name"], "realm": REALM} for k in present if k != exclude]

    def encounter(self, present, raid, boss, difficulty, start, end, success, deaths_by):
        for k in present:
            if k not in REPORTERS:
                continue
            jitter = self.rng.randint(-2, 2)
            self.records[k].append({
                "id": self.rid(k, "enc"), "type": "encounter", "character_guid": self.main(k)["guid"],
                "encounter_id": boss[0], "encounter_name": boss[1], "instance_name": raid, "instance_type": "raid",
                "difficulty_id": DIFF[difficulty], "difficulty_name": difficulty, "group_size": 20,
                "success": success, "start_time": _ts(start), "end_time": _ts(end) + jitter,
                "roster": self.roster(present, k), "deaths": deaths_by.get(k, 0)})

    def dungeon(self, present, dungeon, level, on_time, when):
        for k in present:
            if k in REPORTERS:
                self.records[k].append({
                    "id": self.rid(k, "dng"), "type": "dungeon_complete", "character_guid": self.main(k)["guid"],
                    "map_id": dungeon[0], "name": dungeon[1], "keystone_level": level, "on_time": on_time,
                    "completed_at": _ts(when) + self.rng.randint(-3, 3), "duration_ms": 1_800_000,
                    "roster": self.roster(present, k)})

    def loot(self, k, item, quality, when, raid=None, difficulty=None, enc=None, ilvl=None):
        self.records[k].append({
            "id": self.rid(k, "loot"), "type": "loot", "character_guid": self.main(k)["guid"], "item_id": item[0],
            "item_name": item[1], "quality": quality, "item_class": item[2], "item_subclass": item[3],
            "item_level": ilvl, "encounter_id": enc, "instance_name": raid, "difficulty_name": difficulty,
            "looted_at": _ts(when)})

    def achievement(self, k, key, when):
        a = ACH[key]
        self.records[k].append({
            "id": self.rid(k, "ach"), "type": "achievement", "character_guid": self.main(k)["guid"],
            "achievement_id": a[0], "name": a[1], "points": a[2], "description": a[3], "feat_of_strength": a[4],
            "earned_at": _ts(when)})


def _raid_night(b: _Builder, rng, day: datetime, raid, bosses, difficulty, skill, present, achievements):
    """Simulate a raid night. Returns names of bosses killed. skill: dict boss_id -> kill probability."""
    t = day.replace(hour=19, minute=30)
    killed = []
    for boss in bosses:
        if t.hour >= 23:
            break
        pulls = 0
        while t.hour < 23:
            pulls += 1
            dur = timedelta(minutes=rng.randint(3, 8))
            p = min(0.95, skill.get(boss[0], 0.5) + pulls * 0.08)
            success = rng.random() < p
            deaths = {k: (0 if success and rng.random() < 0.8 else rng.randint(1, 2)) for k in present}
            b.encounter(present, raid, boss, difficulty, t, t + dur, success, deaths)
            t += dur + timedelta(minutes=rng.randint(2, 5))
            if success:
                killed.append(boss)
                skill[boss[0]] = min(0.97, skill.get(boss[0], 0.5) + 0.25)
                for k in present:
                    if k in REPORTERS and rng.random() < 0.18:
                        item = rng.choice(EPICS[:9] if raid == RAID1[0] else EPICS[8:])
                        ilvl = {"Normal": 636, "Heroic": 649, "Mythic": 662}[difficulty]
                        b.loot(k, item, 4, t + timedelta(seconds=40), raid, difficulty, boss[0], ilvl)
                break
            if pulls >= 9:
                break
    return killed


def demo_exists(db: Session) -> bool:
    return db.scalar(select(Group.id).where(Group.name == DEMO_GROUP_NAME)) is not None


def purge_demo(db: Session) -> None:
    db.execute(delete(Group).where(Group.is_demo.is_(True)))
    db.execute(delete(User).where(User.is_demo.is_(True)))
    db.execute(delete(Achievement).where(Achievement.is_demo.is_(True)))
    db.execute(delete(Item).where(Item.is_demo.is_(True)))
    db.execute(delete(EncounterModel).where(EncounterModel.is_demo.is_(True)))
    db.commit()


def seed_demo(db: Session, seed: int = 7) -> Group:
    if demo_exists(db):
        purge_demo(db)
    rng = random.Random(seed)
    users: dict[str, User] = {}
    chars: dict[str, list[dict]] = {}
    group = Group(id=uuid.uuid4(), name=DEMO_GROUP_NAME, slug="emberreach-wayfarers-demo", is_demo=True,
                  description=("A fictional group of five friends used to demonstrate Azeroth Chronicles. "
                               "Every person, character, raid, boss and item here is made up."),
                  settings=GroupSettings().model_dump(), visibility="private")
    group.created_at = START
    db.add(group)
    db.flush()
    for i, (key, display, color, addon, offset, clist) in enumerate(MEMBERS):
        u = User(id=uuid.uuid4(), email=f"{key}@demo.azeroth-chronicles.invalid", display_name=display,
                 password_hash=hash_password(new_token()), avatar_color=color, is_demo=True)
        db.add(u)
        db.flush()
        users[key] = u
        db.add(GroupMembership(id=uuid.uuid4(), group_id=group.id, user_id=u.id,
                               role="owner" if key == "mira" else ("admin" if key == "tobias" else "member"),
                               joined_at=START + timedelta(days=offset)))
        chars[key] = []
        for j, (name, race, cls, spec, lvl) in enumerate(clist):
            guid = f"Player-9999-{i:02d}{j:02d}DE30"
            db.add(Character(id=uuid.uuid4(), owner_user_id=u.id, region="us", realm_slug="emberreach",
                             realm_name=REALM, name=name, player_guid=guid, faction="Alliance", race=race,
                             character_class=cls, specialization=spec, level=lvl, is_main=j == 0,
                             verification="addon_reported" if addon else "manual"))
            chars[key].append({"guid": guid, "name": name, "realm": REALM, "region": "us", "class": cls,
                               "race": race, "faction": "Alliance", "level": lvl, "spec": spec})
    db.flush()

    b = _Builder(rng, chars)
    skill: dict[tuple, dict] = {}
    day = START
    week = 0
    first_normal_clear = first_heroic_clear = None
    while day < END:
        weekday = day.weekday()
        present_base = [k for k, *_ in MEMBERS if not (k == "yselle" and day < START + timedelta(days=29))]
        # Raid nights: Tuesday and Thursday from week 1
        if weekday in (1, 3) and day >= START + timedelta(days=7):
            present = [k for k in present_base if rng.random() < ATTENDANCE[k]]
            if len(present) >= 3:
                week = (day - START).days // 7
                if week < 4:
                    diff = "Normal"
                elif week < 13 or weekday == 1:
                    diff = "Heroic"
                else:
                    diff = "Mythic"
                raid, bosses = RAID1
                if day >= datetime(2026, 8, 18, tzinfo=UTC) and weekday == 3:
                    raid, bosses = RAID2
                    diff = "Normal" if day < datetime(2026, 9, 10, tzinfo=UTC) else "Heroic"
                base = {"Normal": 0.55, "Heroic": 0.3, "Mythic": 0.08}[diff]
                sk = skill.setdefault((raid, diff), {bid: base - i * 0.03 for i, (bid, _) in enumerate(bosses)})
                killed = _raid_night(b, rng, day, raid, bosses, diff, sk, present, None)
                final = bosses[-1]
                end_t = day.replace(hour=23)
                if final in killed and raid == RAID1[0]:
                    if diff == "Normal" and first_normal_clear is None:
                        first_normal_clear = end_t
                        for k in present:
                            if k in REPORTERS:
                                b.achievement(k, "necro_normal", end_t - timedelta(minutes=50))
                    if diff == "Heroic" and first_heroic_clear is None:
                        first_heroic_clear = end_t
                        for k in present:
                            if k in REPORTERS:
                                b.achievement(k, "necro_heroic", end_t - timedelta(minutes=50))
                                b.achievement(k, "aotc", end_t - timedelta(minutes=50))
                        lucky = next((k for k in ("tobias", "mira", "kestrel") if k in present), None)
                        if lucky:
                            b.loot(lucky, LEGENDARY, 5, end_t - timedelta(minutes=48), raid, diff, final[0], 671)
                if final in killed and raid == RAID2[0] and diff == "Normal" and \
                        not any(r.get("achievement_id") == ACH["spire_normal"][0] for r in b.records["mira"]):
                    for k in present:
                        if k in REPORTERS:
                            b.achievement(k, "spire_normal", end_t - timedelta(minutes=45))
                mount_owner = next((k for k in ("kestrel", "mira", "tobias") if k in present), None)
                if final in killed and raid == RAID1[0] and day >= datetime(2026, 8, 1, tzinfo=UTC) and mount_owner \
                        and not any(r.get("item_id") == MOUNT[0] for k in REPORTERS for r in b.records[k]):
                    b.loot(mount_owner, MOUNT, 4, end_t - timedelta(minutes=44), raid, diff, final[0])
        # Dungeon evenings: Saturday + Sunday
        if weekday in (5, 6):
            party = rng.sample(present_base, k=min(len(present_base), 5 if rng.random() < 0.5 else 4))
            runs = rng.randint(1, 3)
            t = day.replace(hour=20)
            weeks_in = (day - START).days / 7
            for _ in range(runs):
                dungeon = rng.choice(DUNGEONS)
                level = None if weeks_in < 2 else max(2, min(16, int(2 + weeks_in * 0.6 + rng.randint(-2, 2))))
                on_time = None if level is None else rng.random() < 0.72
                b.dungeon(party, dungeon, level, on_time, t)
                if rng.random() < 0.12:
                    k = rng.choice([p for p in party if p in REPORTERS] or ["mira"])
                    if k in party:
                        b.loot(k, rng.choice(EPICS), 4, t + timedelta(minutes=1), dungeon[1], f"Mythic+ {level}",
                               None, 640)
                t += timedelta(minutes=rng.randint(30, 45))
        day += timedelta(days=1)

    # Solo-ish achievements captured by the addon
    first_dungeon = min((r for k in REPORTERS for r in b.records[k] if r["type"] == "dungeon_complete"),
                        key=lambda r: r["completed_at"])
    for k in REPORTERS:
        b.achievement(k, "first_dungeon", datetime.fromtimestamp(first_dungeon["completed_at"] + 5, UTC))
        b.achievement(k, "explorer", START + timedelta(days=rng.randint(3, 20), hours=2))
        b.achievement(k, "pet_tamer", START + timedelta(days=rng.randint(10, 60), hours=3))
    for k in REPORTERS:
        keys = sorted((r for r in b.records[k] if r["type"] == "dungeon_complete" and r.get("keystone_level")),
                      key=lambda r: r["completed_at"])
        for lvl_needed, ach_key in ((2, "keystone_init"), (7, "keystone_adept"), (12, "keystone_master")):
            hit = next((r for r in keys if r["keystone_level"] >= lvl_needed and r["on_time"]), None)
            if hit:
                b.achievement(k, ach_key, datetime.fromtimestamp(hit["completed_at"] + 10, UTC))
    b.achievement("mira", "loremaster", datetime(2026, 7, 2, 21, 15, tzinfo=UTC))
    b.achievement("kestrel", "glory", datetime(2026, 9, 24, 22, 40, tzinfo=UTC))

    for k in REPORTERS:
        env = IngestEnvelope.model_validate({"format": "azeroth-chronicles/v1", "source": "addon",
                                             "addon_version": "demo", "characters": chars[k],
                                             "records": b.records[k]})
        ingest_envelope(db, users[k], env, is_demo=True, finalize=False)
        db.add(SyncSource(id=uuid.uuid4(), user_id=users[k].id, kind="addon", status="ok",
                          last_attempt_at=END, last_success_at=END, details={"demo": True}))

    # Manual memories (members without the addon contribute here)
    def manual(title, desc, when, etype, who, major=False, author="mira", **extra_fields):
        ev, _ = get_or_create_event(
            db, group.id, f"manual:demo:{title}", event_type=etype, title=title, description=desc,
            occurred_at=when, time_precision="approximate", importance=85 if major else 60,
            highlight="custom_milestone" if etype == "milestone" else None, source="manual",
            provenance="manual", confidence="unconfirmed", is_manual=True, is_demo=True,
            created_by_user_id=users[author].id, extra={"manual": True, **extra_fields})
        for k in who:
            add_participant(db, ev, users[k].id, None, "claimed")
        return ev

    manual("The Wayfarers are founded", "Five friends, five different guilds, one shared adventure log. "
           "Mira creates the group after an impromptu late-night dungeon run.", START, "milestone",
           ["mira", "tobias", "kestrel", "dunstan"], major=True)
    manual("Yselle joins the party", "Our new healer arrives — and immediately out-heals everyone.",
           START + timedelta(days=29, hours=1), "milestone", ["yselle", "mira"], author="mira")
    manual("Dunstan's 4-hour fishing marathon", "Nobody knows why. Dunstan regrets nothing. 212 fish.",
           datetime(2026, 6, 13, 2, 30, tzinfo=UTC), "manual", ["dunstan", "kestrel"], author="kestrel")
    loot_ev = manual("Ysolde's Ember-Touched Censer", "Yselle finally got the trinket she'd been after for weeks. "
                     "Logged manually — Yselle doesn't run the addon.", datetime(2026, 7, 16, 22, 10, tzinfo=UTC),
                     "loot", ["yselle"], author="yselle", quality="epic", category="gear")
    db.add(LootEvent(id=uuid.uuid4(), group_id=group.id, item_name="Ysolde's Ember-Touched Censer", quality="epic",
                     category="gear", user_id=users["yselle"].id, obtained_at=loot_ev.occurred_at,
                     source_instance="The Gilded Necropolis", difficulty="Heroic", notable_reason="manual",
                     source="manual", dedup_key=f"manual-loot:{loot_ev.id}", event_id=loot_ev.id, is_demo=True))
    manual("Group photo at the Necropolis gates", "Screenshot night! Everyone in their best transmog.",
           datetime(2026, 8, 6, 23, 5, tzinfo=UTC), "manual", ["mira", "tobias", "kestrel", "dunstan", "yselle"],
           author="tobias")
    manual("Six months of adventures", "Half a year of Tuesday-Thursday raids and weekend keys. Here's to the next "
           "six.", datetime(2026, 10, 30, 22, 0, tzinfo=UTC), "milestone",
           ["mira", "tobias", "kestrel", "dunstan", "yselle"], major=True, author="tobias")
    db.flush()
    finalize_groups(db, [group.id])

    # Social layer: pins, reactions, comments on highlights
    highlights = db.scalars(select(AdventureEvent).where(AdventureEvent.group_id == group.id,
                                                         AdventureEvent.highlight.is_not(None))
                            .order_by(AdventureEvent.occurred_at)).all()
    lines = ["GG everyone!", "Finally!!", "I can't believe that worked", "Screenshot or it didn't happen",
             "Best night of the tier", "Tobias, your shield was on fire tonight", "Who pulled the extra pack? 👀",
             "Absolutely deserved", "Same time next week?", "My heart rate is still up"]
    keys = list(users)
    now = datetime.now(UTC)
    for ev in highlights:
        if ev.highlight in ("first_raid_kill", "first_heroic_kill", "first_mythic_kill", "first_legendary",
                            "mount", "first_group_dungeon"):
            ev.pinned = ev.highlight in ("first_heroic_kill", "first_legendary")
        for k in rng.sample(keys, k=rng.randint(1, 4)):
            for emoji in rng.sample(["gg", "fire", "trophy", "heart", "laugh", "salute"], k=rng.randint(1, 2)):
                db.add(EventReaction(id=uuid.uuid4(), event_id=ev.id, user_id=users[k].id, emoji=emoji,
                                     created_at=min(now, ev.occurred_at + timedelta(minutes=10))))
        if rng.random() < 0.55 or ev.highlight in ("first_legendary", "first_heroic_kill"):
            for k in rng.sample(keys, k=rng.randint(1, 3)):
                c = EventComment(id=uuid.uuid4(), event_id=ev.id, user_id=users[k].id, body=rng.choice(lines))
                c.created_at = min(now, ev.occurred_at + timedelta(minutes=rng.randint(2, 600)))
                db.add(c)
    # Group MVP (voted award) for the last full demo month
    sync_definitions(db)
    noms = {}
    for nominee, by, reason in (("tobias", "mira", "Tanked every pull of the Mythic push"),
                                ("yselle", "dunstan", "Kept us alive through 40 wipes"),
                                ("kestrel", "tobias", "Interrupt machine")):
        n = AwardNomination(id=uuid.uuid4(), group_id=group.id, award_key="group_mvp", period_label="2026-10",
                            nominee_user_id=users[nominee].id, nominated_by_user_id=users[by].id, reason=reason)
        db.add(n)
        noms[nominee] = n
    db.flush()
    for voter, choice in (("mira", "tobias"), ("tobias", "yselle"), ("kestrel", "tobias"), ("dunstan", "yselle"),
                          ("yselle", "tobias")):
        db.add(AwardVote(id=uuid.uuid4(), group_id=group.id, award_key="group_mvp", period_label="2026-10",
                         nomination_id=noms[choice].id, voter_user_id=users[voter].id, created_at=END))
    db.commit()
    recompute_group(db, group.id)
    return group


def demo_viewer(db: Session) -> User | None:
    return db.scalar(select(User).where(User.email == "mira@demo.azeroth-chronicles.invalid"))
