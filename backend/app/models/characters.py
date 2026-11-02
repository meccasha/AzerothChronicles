import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin, uuid_pk


class Character(TimestampMixin, Base):
    """A WoW character with a stable internal id.

    Identity is anchored on Blizzard's numeric character id when verified through the API
    (it survives renames and realm transfers), and secondarily on the in-game player GUID
    reported by the addon. Name/realm are mutable display attributes with history.
    """

    __tablename__ = "characters"
    __table_args__ = (
        UniqueConstraint("region", "blizzard_character_id", name="uq_character_blizzard_id"),
        Index("ix_character_name_realm", "region", "realm_slug", "name"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    region: Mapped[str] = mapped_column(String(8))
    realm_slug: Mapped[str] = mapped_column(String(64))
    realm_name: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(32))
    blizzard_character_id: Mapped[int | None] = mapped_column(BigInteger)
    player_guid: Mapped[str | None] = mapped_column(String(64), unique=True)
    faction: Mapped[str | None] = mapped_column(String(16))
    race: Mapped[str | None] = mapped_column(String(32))
    character_class: Mapped[str | None] = mapped_column(String(32))
    specialization: Mapped[str | None] = mapped_column(String(32))
    level: Mapped[int | None] = mapped_column(Integer)
    achievement_points: Mapped[int | None] = mapped_column(Integer)
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    # "blizzard_verified" | "addon_reported" | "manual"
    verification: Mapped[str] = mapped_column(String(24), default="manual")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_main: Mapped[bool] = mapped_column(Boolean, default=False)
    achievements_backfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_error: Mapped[str | None] = mapped_column(String(500))

    owner = relationship("User", back_populates="characters")
    identity_history = relationship(
        "CharacterIdentityHistory", back_populates="character", cascade="all, delete-orphan"
    )


class CharacterIdentityHistory(Base):
    __tablename__ = "character_identity_history"

    id: Mapped[uuid.UUID] = uuid_pk()
    character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(32))
    realm_slug: Mapped[str] = mapped_column(String(64))
    region: Mapped[str] = mapped_column(String(8))
    faction: Mapped[str | None] = mapped_column(String(16))
    change_type: Mapped[str] = mapped_column(String(24))  # created | rename | realm_transfer | faction_change
    source: Mapped[str] = mapped_column(String(24))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    character = relationship("Character", back_populates="identity_history")
