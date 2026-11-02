import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin, uuid_pk


class SyncSource(TimestampMixin, Base):
    """A configured data source for a user (Battle.net link, addon/companion uploads)."""

    __tablename__ = "sync_sources"
    __table_args__ = (UniqueConstraint("user_id", "kind", name="uq_sync_source"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(24))  # blizzard_api | addon
    status: Mapped[str] = mapped_column(String(16), default="idle")  # idle | ok | error | disabled
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")


class SyncJob(TimestampMixin, Base):
    __tablename__ = "sync_jobs"
    __table_args__ = (Index("ix_sync_job_user", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued|running|succeeded|partial|failed
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    error: Mapped[str | None] = mapped_column(Text)


class IngestionRecord(Base):
    """Raw, immutable record of something a source reported, kept for audit and reprocessing."""

    __tablename__ = "ingestion_records"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_ingestion_idempotency"),
        Index("ix_ingestion_status", "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    sync_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sync_jobs.id", ondelete="SET NULL"), index=True
    )
    source: Mapped[str] = mapped_column(String(24))  # addon | blizzard_api | simulated
    record_type: Mapped[str] = mapped_column(String(24))  # encounter | achievement | loot | character | ...
    idempotency_key: Mapped[str] = mapped_column(String(200))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # normalized | duplicate | ignored | rejected
    status: Mapped[str] = mapped_column(String(16))
    status_detail: Mapped[str | None] = mapped_column(String(500))
    canonical_refs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
