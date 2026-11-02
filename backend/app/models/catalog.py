"""Reference data about game objects (achievements, encounters, items)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

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


class Item(TimestampMixin, Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)  # game item id
    name: Mapped[str] = mapped_column(String(200))
    quality: Mapped[str] = mapped_column(String(16))  # poor..legendary, artifact, heirloom
    item_class: Mapped[str | None] = mapped_column(String(64))
    item_subclass: Mapped[str | None] = mapped_column(String(64))
    inventory_type: Mapped[str | None] = mapped_column(String(64))
    icon_url: Mapped[str | None] = mapped_column(String(512))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_source: Mapped[str] = mapped_column(String(24), default="addon")
    metadata_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
