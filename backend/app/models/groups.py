import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin, uuid_pk

ROLES = ("owner", "admin", "member")


class Group(TimestampMixin, Base):
    __tablename__ = "groups"
    __table_args__ = (CheckConstraint("visibility in ('private','invite_preview')", name="ck_group_visibility"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(80), unique=True)
    slug: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    banner_url: Mapped[str | None] = mapped_column(String(512))
    # private: invite links reveal nothing but the name. invite_preview: invite links show description + size.
    visibility: Mapped[str] = mapped_column(String(32), default="private", server_default="private")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    # Event filters, loot rules, award toggles. Validated by app.services.group_settings.
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")

    memberships = relationship("GroupMembership", back_populates="group", cascade="all, delete-orphan")


class GroupMembership(TimestampMixin, Base):
    __tablename__ = "group_memberships"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_membership"),
        CheckConstraint("role in ('owner','admin','member')", name="ck_membership_role"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16), default="member")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    group = relationship("Group", back_populates="memberships")
    user = relationship("User", back_populates="memberships")


class GroupInvite(TimestampMixin, Base):
    __tablename__ = "group_invites"

    id: Mapped[uuid.UUID] = uuid_pk()
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(32), unique=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    role: Mapped[str] = mapped_column(String(16), default="member")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    max_uses: Mapped[int | None] = mapped_column(Integer)
    uses: Mapped[int] = mapped_column(Integer, default=0)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GroupItemRule(TimestampMixin, Base):
    """Per-group favourite / wishlist / excluded items for the loot importance system."""

    __tablename__ = "group_item_rules"
    __table_args__ = (UniqueConstraint("group_id", "item_id", name="uq_group_item_rule"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[int] = mapped_column(Integer)
    item_name: Mapped[str] = mapped_column(String(160))
    rule: Mapped[str] = mapped_column(String(16))  # "favorite" | "wishlist" | "exclude"
    note: Mapped[str | None] = mapped_column(String(280))
