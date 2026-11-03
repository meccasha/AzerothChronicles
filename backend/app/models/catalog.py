"""Reference data about game objects (achievements, encounters, instances, items).

Image URLs are only ever taken from Blizzard's render CDN (see app.services.game_media.safe_media_url),
never from user uploads, so the browser only loads game artwork from Blizzard.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin


class Achievement(TimestampMixin, Base):
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)  # Blizzard achievement id
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    points: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[str | None] = mapped_column(String(120))
    icon_url: Mapped[str | None] = mapped_column(String(512))
    is_feat_of_strength: Mapped[bool] = mapped_column(Boolean, default=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    icon_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GameInstance(TimestampMixin, Base):
    """A dungeon or raid. Identified by Blizzard's Encounter Journal instance id when known,
    otherwise by the in-game map id or name until media resolution links it."""

    __tablename__ = "game_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    journal_instance_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    map_id: Mapped[int | None] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    instance_type: Mapped[str | None] = mapped_column(String(16))  # raid | dungeon
    image_url: Mapped[str | None] = mapped_column(String(512))  # journal "tile" artwork
    media_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    media_status: Mapped[str | None] = mapped_column(String(24))  # resolved | unavailable
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Encounter(TimestampMixin, Base):
    """A boss encounter. The addon reports DungeonEncounterIDs; the web API uses journal ids."""

    __tablename__ = "encounters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dungeon_encounter_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    journal_encounter_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String(160))
    instance_name: Mapped[str | None] = mapped_column(String(160))
    instance_id: Mapped[int | None] = mapped_column(Integer)
    instance_type: Mapped[str] = mapped_column(String(16), default="raid")  # raid | dungeon
    expansion: Mapped[str | None] = mapped_column(String(64))
    is_final_boss: Mapped[bool] = mapped_column(Boolean, default=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    game_instance_id: Mapped[int | None] = mapped_column(ForeignKey("game_instances.id", ondelete="SET NULL"))
    image_url: Mapped[str | None] = mapped_column(String(512))  # boss portrait (creature display "zoom")
    media_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    media_status: Mapped[str | None] = mapped_column(String(24))

    game_instance = relationship("GameInstance")


class Item(TimestampMixin, Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)  # game item id
    name: Mapped[str] = mapped_column(String(200))
    quality: Mapped[str] = mapped_column(String(16))  # poor..legendary, artifact, heirloom
    item_class: Mapped[str | None] = mapped_column(String(64))
    item_subclass: Mapped[str | None] = mapped_column(String(64))
    inventory_type: Mapped[str | None] = mapped_column(String(64))
    icon_url: Mapped[str | None] = mapped_column(String(512))
    icon_file_id: Mapped[int | None] = mapped_column(Integer)  # FileDataID reported by the game client
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_source: Mapped[str] = mapped_column(String(24), default="addon")
    metadata_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
