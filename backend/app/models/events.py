"""Canonical adventure events and everything hanging off them."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin, uuid_pk

EVENT_TYPES = ("achievement", "boss_kill", "dungeon_complete", "loot", "milestone", "manual")
CONFIRMATIONS = ("confirmed", "roster", "claimed")


class AdventureEvent(TimestampMixin, Base):
    """A normalized, de-duplicated timeline entry for one group.

    Several raw ingestion records (from different members / sources) can map onto one
    canonical event via ``dedup_key``.
    """

    __tablename__ = "adventure_events"
    __table_args__ = (
        UniqueConstraint("group_id", "dedup_key", name="uq_event_dedup"),
        CheckConstraint(
            "event_type in ('achievement','boss_kill','dungeon_complete','loot','milestone','manual')",
            name="ck_event_type",
        ),
        CheckConstraint("time_precision in ('exact','observed','approximate')", name="ck_time_precision"),
        Index("ix_event_group_time", "group_id", "occurred_at"),
        Index("ix_event_group_type", "group_id", "event_type"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(24))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # exact: real completion time. observed: first time a sync saw it. approximate: user-entered.
    time_precision: Mapped[str] = mapped_column(String(16), default="exact")
    importance: Mapped[int] = mapped_column(Integer, default=50)
    # Distinctive presentation, e.g. first_raid_kill, legendary, first_group_dungeon, mythic_kill
    highlight: Mapped[str | None] = mapped_column(String(40))

    achievement_id: Mapped[int | None] = mapped_column(ForeignKey("achievements.id", ondelete="SET NULL"))
    encounter_id: Mapped[int | None] = mapped_column(ForeignKey("encounters.id", ondelete="SET NULL"))
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id", ondelete="SET NULL"))
    difficulty: Mapped[str | None] = mapped_column(String(32))
    instance_name: Mapped[str | None] = mapped_column(String(160))
    game_instance_id: Mapped[int | None] = mapped_column(ForeignKey("game_instances.id", ondelete="SET NULL"))
    expansion: Mapped[str | None] = mapped_column(String(64))
    season: Mapped[str | None] = mapped_column(String(64))

    # Provenance
    source: Mapped[str] = mapped_column(String(24))  # blizzard_api | addon | manual | demo | import
    provenance: Mapped[str] = mapped_column(String(16), default="live")  # live | backfill | manual
    confidence: Mapped[str] = mapped_column(String(16), default="confirmed")  # confirmed | unconfirmed
    dedup_key: Mapped[str] = mapped_column(String(200))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    is_manual: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")

    participants = relationship("EventParticipant", back_populates="event", cascade="all, delete-orphan")
    comments = relationship("EventComment", back_populates="event", cascade="all, delete-orphan")
    reactions = relationship("EventReaction", back_populates="event", cascade="all, delete-orphan")
    media = relationship("EventMedia", back_populates="event", cascade="all, delete-orphan")
    achievement = relationship("Achievement")
    encounter = relationship("Encounter")
    item = relationship("Item")
    game_instance = relationship("GameInstance")


class EventParticipant(Base):
    __tablename__ = "event_participants"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_participant"),
        CheckConstraint("confirmation in ('confirmed','roster','claimed')", name="ck_participant_confirmation"),
        Index("ix_participant_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("adventure_events.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    character_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id", ondelete="SET NULL")
    )
    # confirmed: reported by the member's own client / Blizzard data for their character.
    # roster: seen in another member's group roster at the time of the event.
    # claimed: added manually; not verified by any game data source.
    confirmation: Mapped[str] = mapped_column(String(16), default="confirmed")

    event = relationship("AdventureEvent", back_populates="participants")
    user = relationship("User")
    character = relationship("Character")


class EventComment(TimestampMixin, Base):
    __tablename__ = "event_comments"

    id: Mapped[uuid.UUID] = uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("adventure_events.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    event = relationship("AdventureEvent", back_populates="comments")
    user = relationship("User")


class EventReaction(Base):
    __tablename__ = "event_reactions"
    __table_args__ = (UniqueConstraint("event_id", "user_id", "emoji", name="uq_event_reaction"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("adventure_events.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    emoji: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    event = relationship("AdventureEvent", back_populates="reactions")


class EventFavorite(Base):
    __tablename__ = "event_favorites"
    __table_args__ = (UniqueConstraint("event_id", "user_id", name="uq_event_favorite"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("adventure_events.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EventMedia(Base):
    __tablename__ = "event_media"

    id: Mapped[uuid.UUID] = uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("adventure_events.id", ondelete="CASCADE"), index=True
    )
    uploader_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    caption: Mapped[str | None] = mapped_column(String(280))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    event = relationship("AdventureEvent", back_populates="media")


class CharacterAchievement(Base):
    """Snapshot of which achievements each character has been observed to have."""

    __tablename__ = "character_achievements"
    __table_args__ = (UniqueConstraint("character_id", "achievement_id", name="uq_character_achievement"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), index=True
    )
    achievement_id: Mapped[int] = mapped_column(ForeignKey("achievements.id", ondelete="CASCADE"), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # blizzard_backfill | blizzard_sync | addon | manual | demo
    source: Mapped[str] = mapped_column(String(24))


class EncounterAttempt(TimestampMixin, Base):
    """One pull of a boss by the group (kill or wipe), merged across reporters."""

    __tablename__ = "encounter_attempts"
    __table_args__ = (
        UniqueConstraint("group_id", "dedup_key", name="uq_attempt_dedup"),
        Index("ix_attempt_group_encounter", "group_id", "encounter_id", "difficulty_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"))
    encounter_id: Mapped[int] = mapped_column(ForeignKey("encounters.id", ondelete="CASCADE"))
    difficulty_id: Mapped[int | None] = mapped_column(Integer)
    difficulty: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    success: Mapped[bool] = mapped_column(Boolean)
    group_size: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(24))
    dedup_key: Mapped[str] = mapped_column(String(200))
    reporter_count: Mapped[int] = mapped_column(Integer, default=1)
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("adventure_events.id", ondelete="SET NULL")
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    encounter = relationship("Encounter")
    participants = relationship(
        "EncounterAttemptParticipant", back_populates="attempt", cascade="all, delete-orphan"
    )


class EncounterAttemptParticipant(Base):
    __tablename__ = "encounter_attempt_participants"
    __table_args__ = (UniqueConstraint("attempt_id", "user_id", name="uq_attempt_participant"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounter_attempts.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    character_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id", ondelete="SET NULL")
    )
    confirmation: Mapped[str] = mapped_column(String(16), default="confirmed")
    # Personal death count during the attempt; NULL means "unknown" (no reliable data from this member).
    deaths: Mapped[int | None] = mapped_column(Integer)

    attempt = relationship("EncounterAttempt", back_populates="participants")


class LootEvent(TimestampMixin, Base):
    __tablename__ = "loot_events"
    __table_args__ = (
        UniqueConstraint("group_id", "dedup_key", name="uq_loot_dedup"),
        Index("ix_loot_group_time", "group_id", "obtained_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"))
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id", ondelete="SET NULL"))
    item_name: Mapped[str] = mapped_column(String(200))
    quality: Mapped[str] = mapped_column(String(16))
    category: Mapped[str] = mapped_column(String(24))  # gear | mount | pet | toy | collectible | other
    icon_url: Mapped[str | None] = mapped_column(String(512))
    collectible_id: Mapped[int | None] = mapped_column(Integer)  # mount / toy id for collectibles
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    character_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id", ondelete="SET NULL")
    )
    obtained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_instance: Mapped[str | None] = mapped_column(String(160))
    source_encounter_id: Mapped[int | None] = mapped_column(ForeignKey("encounters.id", ondelete="SET NULL"))
    difficulty: Mapped[str | None] = mapped_column(String(32))
    notable_reason: Mapped[str] = mapped_column(String(32))  # legendary | epic | mount | favorite | wishlist | manual
    is_group_first: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(24))
    dedup_key: Mapped[str] = mapped_column(String(200))
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("adventure_events.id", ondelete="SET NULL")
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    user = relationship("User")
    character = relationship("Character")


class ActivitySession(Base):
    """A derived play session: a cluster of group events with a gap of < 3h between them."""

    __tablename__ = "activity_sessions"
    __table_args__ = (Index("ix_session_group_start", "group_id", "started_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    event_count: Mapped[int] = mapped_column(Integer)
    participant_user_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
