import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin, uuid_pk


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(String(255))
    avatar_color: Mapped[str | None] = mapped_column(String(16))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    memberships = relationship("GroupMembership", back_populates="user", cascade="all, delete-orphan")
    characters = relationship("Character", back_populates="owner", cascade="all, delete-orphan")


class UserSession(Base):
    """Opaque server-side sessions; only a SHA-256 of the cookie value is stored."""

    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ApiToken(TimestampMixin, Base):
    """Personal tokens used by the companion app to upload addon exports."""

    __tablename__ = "api_tokens"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(64))
    token_prefix: Mapped[str] = mapped_column(String(12))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExternalAccount(TimestampMixin, Base):
    __tablename__ = "external_accounts"
    __table_args__ = (UniqueConstraint("provider", "external_id", name="uq_external_account"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(32))  # "battlenet"
    external_id: Mapped[str] = mapped_column(String(64))
    display_name: Mapped[str | None] = mapped_column(String(128))  # BattleTag
    region: Mapped[str] = mapped_column(String(8))

    credential = relationship(
        "IntegrationCredential", back_populates="account", uselist=False, cascade="all, delete-orphan"
    )


class IntegrationCredential(TimestampMixin, Base):
    """Encrypted OAuth tokens. Never serialized to API responses."""

    __tablename__ = "integration_credentials"

    id: Mapped[uuid.UUID] = uuid_pk()
    external_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("external_accounts.id", ondelete="CASCADE"), unique=True
    )
    access_token_encrypted: Mapped[str] = mapped_column(String(4096))
    refresh_token_encrypted: Mapped[str | None] = mapped_column(String(4096))
    scopes: Mapped[str] = mapped_column(String(255), default="")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    account = relationship("ExternalAccount", back_populates="credential")


class OAuthState(Base):
    __tablename__ = "oauth_states"

    id: Mapped[uuid.UUID] = uuid_pk()
    state_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    region: Mapped[str] = mapped_column(String(8))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
