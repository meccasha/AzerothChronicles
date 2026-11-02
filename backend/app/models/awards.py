import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin, uuid_pk


class AwardDefinition(TimestampMixin, Base):
    """Registry mirror of award types (code is the source of truth for calculation)."""

    __tablename__ = "award_definitions"

    key: Mapped[str] = mapped_column(String(48), primary_key=True)
    title: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    icon: Mapped[str] = mapped_column(String(48))
    kind: Mapped[str] = mapped_column(String(16))  # auto | vote
    rules: Mapped[str] = mapped_column(Text)
    requires: Mapped[str | None] = mapped_column(String(48))
    enabled_by_default: Mapped[bool] = mapped_column(Boolean, default=True)


class AwardResult(Base):
    __tablename__ = "award_results"
    __table_args__ = (
        UniqueConstraint("group_id", "award_key", "period_type", "period_start", name="uq_award_result"),
        Index("ix_award_result_group", "group_id", "award_key"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"))
    award_key: Mapped[str] = mapped_column(ForeignKey("award_definitions.key", ondelete="CASCADE"))
    period_type: Mapped[str] = mapped_column(String(16))  # week | month | season | all_time
    period_label: Mapped[str] = mapped_column(String(64))
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    winner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    winning_value: Mapped[float | None] = mapped_column(Numeric(12, 2))
    # status: awarded | no_data | insufficient_data | tie_unresolved
    status: Mapped[str] = mapped_column(String(24))
    standings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    calculation_version: Mapped[str] = mapped_column(String(16))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_final: Mapped[bool] = mapped_column(Boolean, default=False)


class AwardNomination(TimestampMixin, Base):
    __tablename__ = "award_nominations"
    __table_args__ = (
        UniqueConstraint("group_id", "award_key", "period_label", "nominee_user_id", name="uq_nomination"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"))
    award_key: Mapped[str] = mapped_column(ForeignKey("award_definitions.key", ondelete="CASCADE"))
    period_label: Mapped[str] = mapped_column(String(64))
    nominee_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    nominated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    reason: Mapped[str] = mapped_column(String(280), default="")


class AwardVote(Base):
    __tablename__ = "award_votes"
    __table_args__ = (UniqueConstraint("group_id", "award_key", "period_label", "voter_user_id", name="uq_vote"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"))
    award_key: Mapped[str] = mapped_column(ForeignKey("award_definitions.key", ondelete="CASCADE"))
    period_label: Mapped[str] = mapped_column(String(64))
    nomination_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("award_nominations.id", ondelete="CASCADE")
    )
    voter_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
