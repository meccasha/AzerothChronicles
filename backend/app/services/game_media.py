"""Game artwork: item/achievement icons, dungeon & raid artwork, boss portraits and mount renders.

All images come from Blizzard's official Game Data API, which returns URLs on Blizzard's render CDN
(render.worldofwarcraft.com). The browser loads them directly from Blizzard; we store only the URL.

Resolution is best-effort and incremental:
* items           -> /data/wow/item/{id} + /data/wow/media/item/{id}             (icon)
* achievements    -> /data/wow/media/achievement/{id}                            (icon)
* instances       -> /data/wow/journal-instance/{id} + media                     (tile artwork)
                     (journal id from the addon, else matched by name via the journal index)
* encounters      -> /data/wow/journal-encounter/{id} -> creature display media  (boss portrait)
                     (journal id from the addon, else matched by name within the resolved instance)
* mounts          -> /data/wow/mount/{id} -> creature display media              (mount render)

Anything Blizzard does not know (404) is marked unavailable and not retried; transient errors are retried
on the next run. Without Battle.net credentials (and outside mock mode) nothing is fetched and the UI
shows generic icons.
"""

import re
import unicodedata
from datetime import UTC, datetime

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.integrations.blizzard.adapter import BlizzardAdapter
from app.integrations.blizzard.types import BlizzardError, CharacterNotFound, JournalInstanceInfo
from app.models import Achievement, AdventureEvent, Encounter, GameInstance, Item, LootEvent

SAFE_URL_RE = re.compile(r"^https://render(-[a-z]{2})?\.worldofwarcraft\.com/[A-Za-z0-9_\-./]+$")
ICON_NAME_RE = re.compile(r"^[a-z0-9_\-]{2,100}$")
ICON_BASE = "https://render.worldofwarcraft.com/us/icons/56/"
LOCK_KEY = "game-media-resolution"


def safe_media_url(url: str | None) -> str | None:
    """Only Blizzard render-CDN URLs are ever stored or shown (no arbitrary hosts / tracking pixels)."""
    if url and SAFE_URL_RE.match(url):
        return url
    return None


def icon_url_from_name(name: str | None) -> str | None:
    """Icon texture name (e.g. "inv_sword_39") -> Blizzard CDN URL."""
    if not name:
        return None
    n = name.strip().lower()
    if n.startswith("interface\\icons\\"):
        n = n.split("\\")[-1]
    return f"{ICON_BASE}{n}.jpg" if ICON_NAME_RE.match(n) else None


def media_kind(url: str | None) -> str | None:
    """icon (56px square), portrait (creature render) or scene (wide journal artwork)."""
    if not url:
        return None
    if "/icons/" in url:
        return "icon"
    if "/npcs/" in url or "creature-display" in url:
        return "portrait"
    return "scene"


def name_key(name: str | None) -> str:
    """Normalize names for matching ("The Stonevault" == "stonevault", accents and punctuation ignored)."""
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"^(the|mock:)\s+", "", s.replace("mock: ", ""))
    return re.sub(r"[^a-z0-9]", "", s)


def media_enabled() -> bool:
    s = get_settings()
    return s.blizzard_adapter == "mock" or s.blizzard_configured


def _now() -> datetime:
    return datetime.now(UTC)


def _transient(exc: BlizzardError) -> bool:
    return exc.retryable and not isinstance(exc, CharacterNotFound)


class _Resolver:
    def __init__(self, db: Session, adapter: BlizzardAdapter, region: str, limit: int):
        self.db, self.adapter, self.region, self.limit = db, adapter, region, limit
        self.counts = {"items": 0, "achievements": 0, "instances": 0, "encounters": 0, "mounts": 0,
                       "unavailable": 0, "deferred": 0}
        self._index: dict[str, int] | None = None
        self._instances: dict[int, JournalInstanceInfo] = {}

    # ---------------------------------------------------------------- helpers
    def journal_index(self) -> dict[str, int]:
        if self._index is None:
            self._index = {name_key(n): i for i, n in self.adapter.journal_instance_index(region=self.region)}
        return self._index

    def journal_instance(self, jid: int) -> JournalInstanceInfo:
        if jid not in self._instances:
            self._instances[jid] = self.adapter.journal_instance(region=self.region, journal_instance_id=jid)
        return self._instances[jid]

    def unavailable(self, row) -> None:
        if hasattr(row, "media_status"):
            row.media_status = "unavailable"
        self.counts["unavailable"] += 1

    # ---------------------------------------------------------------- items
    def items(self) -> None:
        for item in self.db.scalars(select(Item).where(Item.metadata_fetched_at.is_(None), Item.is_demo.is_(False))
                                    .limit(self.limit)):
            try:
                info = self.adapter.item(region=self.region, item_id=item.id)
            except BlizzardError as exc:
                if _transient(exc):
                    self.counts["deferred"] += 1
                    continue
                item.metadata_fetched_at = _now()
                self.unavailable(item)
                continue
            item.icon_url = safe_media_url(info.icon_url) or item.icon_url
            item.item_class = info.item_class or item.item_class
            item.item_subclass = info.item_subclass or item.item_subclass
            item.inventory_type = info.inventory_type or item.inventory_type
            item.metadata_source, item.metadata_fetched_at = "blizzard_api", _now()
            self.counts["items"] += 1
        # every museum entry of an item shares its icon (flush first: the session does not autoflush)
        self.db.flush()
        self.db.execute(
            update(LootEvent).where(LootEvent.item_id == Item.id, LootEvent.icon_url.is_(None),
                                    Item.icon_url.is_not(None)).values(icon_url=Item.icon_url)
            .execution_options(synchronize_session=False))

    # ---------------------------------------------------------------- achievements
    def achievements(self) -> None:
        for ach in self.db.scalars(select(Achievement).where(Achievement.icon_fetched_at.is_(None),
                                                             Achievement.is_demo.is_(False)).limit(self.limit)):
            try:
                ach.icon_url = safe_media_url(self.adapter.achievement_icon(region=self.region,
                                                                            achievement_id=ach.id))
            except BlizzardError as exc:
                if _transient(exc):
                    self.counts["deferred"] += 1
                    continue
                self.unavailable(ach)
            else:
                self.counts["achievements"] += 1
            ach.icon_fetched_at = _now()

    # ---------------------------------------------------------------- instances
    def instances(self) -> None:
        rows = self.db.scalars(select(GameInstance).where(GameInstance.media_fetched_at.is_(None),
                                                          GameInstance.is_demo.is_(False)).limit(self.limit)).all()
        for inst in rows:
            try:
                jid = inst.journal_instance_id or self.journal_index().get(name_key(inst.name))
                if jid is None:
                    inst.media_fetched_at = _now()
                    self.unavailable(inst)
                    continue
                info = self.journal_instance(jid)
            except BlizzardError as exc:
                if _transient(exc):
                    self.counts["deferred"] += 1
                    continue
                inst.media_fetched_at = _now()
                self.unavailable(inst)
                continue
            if inst.journal_instance_id is None:
                owner = self.db.scalar(select(GameInstance).where(GameInstance.journal_instance_id == jid))
                if owner is not None and owner.id != inst.id:
                    inst = self._merge(inst, owner)
                inst.journal_instance_id = jid
            inst.image_url = safe_media_url(info.image_url) or inst.image_url
            inst.map_id = inst.map_id or info.map_id
            if info.category:
                inst.instance_type = "raid" if info.category.upper() == "RAID" else "dungeon"
            inst.media_status, inst.media_fetched_at = "resolved", _now()
            self.counts["instances"] += 1
            self.db.flush()

    def _merge(self, dup: GameInstance, keep: GameInstance) -> GameInstance:
        """Two rows turned out to be the same journal instance (e.g. name vs. map id): keep one."""
        self.db.execute(update(Encounter).where(Encounter.game_instance_id == dup.id).values(game_instance_id=keep.id))
        self.db.execute(update(AdventureEvent).where(AdventureEvent.game_instance_id == dup.id)
                        .values(game_instance_id=keep.id))
        self.db.delete(dup)
        self.db.flush()
        return keep

    # ---------------------------------------------------------------- encounters
    def encounters(self) -> None:
        rows = self.db.scalars(select(Encounter).where(Encounter.media_fetched_at.is_(None),
                                                       Encounter.is_demo.is_(False)).limit(self.limit)).all()
        for enc in rows:
            jid = enc.journal_encounter_id
            try:
                if jid is None:
                    inst = enc.game_instance
                    if inst is None or inst.media_status == "unavailable" or inst.journal_instance_id is None:
                        if inst is not None and inst.media_fetched_at is None:
                            self.counts["deferred"] += 1  # resolve the instance first
                            continue
                        enc.media_fetched_at = _now()
                        self.unavailable(enc)
                        continue
                    wanted = name_key(enc.name)
                    jid = next((i for i, n in self.journal_instance(inst.journal_instance_id).encounters
                                if name_key(n) == wanted), None)
                    if jid is None:
                        enc.media_fetched_at = _now()
                        self.unavailable(enc)
                        continue
                info = self.adapter.journal_encounter(region=self.region, journal_encounter_id=jid)
            except BlizzardError as exc:
                if _transient(exc):
                    self.counts["deferred"] += 1
                    continue
                enc.media_fetched_at = _now()
                self.unavailable(enc)
                continue
            if enc.journal_encounter_id is None and not self.db.scalar(
                    select(Encounter.id).where(Encounter.journal_encounter_id == jid)):
                enc.journal_encounter_id = jid
            enc.image_url = safe_media_url(info.image_url) or enc.image_url
            enc.media_status, enc.media_fetched_at = "resolved", _now()
            self.counts["encounters"] += 1

    # ---------------------------------------------------------------- mounts
    def mounts(self) -> None:
        ids = self.db.scalars(select(LootEvent.collectible_id).where(
            LootEvent.category == "mount", LootEvent.collectible_id.is_not(None), LootEvent.icon_url.is_(None),
            LootEvent.is_demo.is_(False)).distinct().limit(self.limit)).all()
        for mount_id in ids:
            try:
                url = safe_media_url(self.adapter.mount_image(region=self.region, mount_id=mount_id))
            except BlizzardError as exc:
                if _transient(exc):
                    self.counts["deferred"] += 1
                else:
                    self.unavailable(None)
                continue
            if url:
                self.db.execute(update(LootEvent).where(LootEvent.category == "mount",
                                                        LootEvent.collectible_id == mount_id,
                                                        LootEvent.icon_url.is_(None)).values(icon_url=url))
                self.counts["mounts"] += 1


def resolve_media(db: Session, adapter: BlizzardAdapter, region: str | None = None, limit: int = 200) -> dict:
    """Fetch missing artwork in one transaction, serialized across processes by a transaction-scoped
    advisory lock (released automatically on commit/rollback, whichever pooled connection is used)."""
    db.commit()  # start from a clean transaction so the lock covers exactly this run
    if not db.scalar(text("SELECT pg_try_advisory_xact_lock(hashtext(:k))"), {"k": LOCK_KEY}):
        db.rollback()
        return {"skipped": "another media resolution is running"}
    try:
        r = _Resolver(db, adapter, region or get_settings().blizzard_default_region, limit)
        r.items()
        r.achievements()
        r.instances()
        r.encounters()
        r.mounts()
        db.commit()
        return r.counts
    except Exception:
        db.rollback()
        raise


def pending_counts(db: Session) -> dict:
    from sqlalchemy import func

    return {
        "items": db.scalar(select(func.count(Item.id)).where(Item.metadata_fetched_at.is_(None),
                                                             Item.is_demo.is_(False))),
        "achievements": db.scalar(select(func.count(Achievement.id)).where(Achievement.icon_fetched_at.is_(None),
                                                                           Achievement.is_demo.is_(False))),
        "instances": db.scalar(select(func.count(GameInstance.id)).where(GameInstance.media_fetched_at.is_(None),
                                                                         GameInstance.is_demo.is_(False))),
        "encounters": db.scalar(select(func.count(Encounter.id)).where(Encounter.media_fetched_at.is_(None),
                                                                       Encounter.is_demo.is_(False))),
    }


def run_in_background() -> None:
    """Entry point for FastAPI BackgroundTasks / the worker: own session, never raises."""
    from app.db import SessionLocal
    from app.integrations.blizzard.adapter import get_adapter

    if not media_enabled():
        return
    try:
        adapter = get_adapter()
    except BlizzardError:
        return
    with SessionLocal() as db:
        try:
            resolve_media(db, adapter)
        except BlizzardError:
            pass


__all__ = ["safe_media_url", "icon_url_from_name", "media_kind", "resolve_media", "run_in_background",
           "pending_counts", "media_enabled", "name_key"]
