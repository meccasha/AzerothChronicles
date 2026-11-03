"""Request/response models for the HTTP API."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

ORM = ConfigDict(from_attributes=True)


# ----------------------------------------------------------------------------- auth / users
class RegisterIn(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=40)
    password: str = Field(min_length=10, max_length=200)

    @field_validator("display_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("display name too short")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=200)


class UserOut(BaseModel):
    model_config = ORM
    id: uuid.UUID
    email: str
    display_name: str
    avatar_color: str | None
    is_demo: bool
    created_at: datetime


class UserBrief(BaseModel):
    model_config = ORM
    id: uuid.UUID
    display_name: str
    avatar_color: str | None


class DeleteAccountIn(BaseModel):
    password: str | None = None
    confirm: Literal["DELETE"]


class ApiTokenIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class ApiTokenOut(BaseModel):
    model_config = ORM
    id: uuid.UUID
    name: str
    token_prefix: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


# ----------------------------------------------------------------------------- groups
class GroupIn(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    description: str = Field(default="", max_length=2000)
    banner_url: str | None = Field(default=None, max_length=512)

    @field_validator("banner_url")
    @classmethod
    def https_only(cls, v: str | None) -> str | None:
        if v and not (v.startswith("https://") or v.startswith("/")):
            raise ValueError("banner_url must be https:// or a site-relative path")
        return v or None


class GroupPatch(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=80)
    description: str | None = Field(default=None, max_length=2000)
    banner_url: str | None = Field(default=None, max_length=512)
    visibility: Literal["private", "invite_preview"] | None = None
    settings: dict[str, Any] | None = None

    _https = field_validator("banner_url")(GroupIn.https_only.__func__)


class GroupOut(BaseModel):
    model_config = ORM
    id: uuid.UUID
    name: str
    slug: str
    description: str
    banner_url: str | None
    visibility: str
    is_demo: bool
    created_at: datetime
    settings: dict[str, Any]
    my_role: str | None = None
    member_count: int | None = None


class MemberOut(BaseModel):
    user: UserBrief
    role: str
    joined_at: datetime
    characters: list["CharacterOut"] = []


class RoleIn(BaseModel):
    role: Literal["admin", "member", "owner"]


class AddMemberIn(BaseModel):
    email: EmailStr


class InviteIn(BaseModel):
    expires_in_hours: int = Field(default=72, ge=1, le=24 * 30)
    max_uses: int | None = Field(default=None, ge=1, le=100)
    role: Literal["member", "admin"] = "member"


class InviteOut(BaseModel):
    model_config = ORM
    id: uuid.UUID
    code: str
    role: str
    expires_at: datetime
    max_uses: int | None
    uses: int
    revoked_at: datetime | None
    url: str | None = None


class InvitePreview(BaseModel):
    group_name: str
    description: str | None
    member_count: int | None
    expires_at: datetime
    valid: bool


class ItemRuleIn(BaseModel):
    item_id: int = Field(ge=1)
    item_name: str = Field(min_length=1, max_length=160)
    rule: Literal["favorite", "wishlist", "exclude"]
    note: str | None = Field(default=None, max_length=280)


class ItemRuleOut(ItemRuleIn):
    model_config = ORM
    id: uuid.UUID


# ----------------------------------------------------------------------------- characters
class CharacterIn(BaseModel):
    name: str = Field(min_length=2, max_length=12, pattern=r"^[^\d\s]+$")
    realm: str = Field(min_length=2, max_length=64)
    region: Literal["us", "eu", "kr", "tw"] = "us"
    character_class: str | None = Field(default=None, max_length=32)
    race: str | None = Field(default=None, max_length=32)
    faction: Literal["Alliance", "Horde", "Neutral"] | None = None
    level: int | None = Field(default=None, ge=1, le=90)
    specialization: str | None = Field(default=None, max_length=32)


class CharacterPatch(BaseModel):
    is_main: bool | None = None
    is_active: bool | None = None
    specialization: str | None = Field(default=None, max_length=32)


class CharacterOut(BaseModel):
    model_config = ORM
    id: uuid.UUID
    owner_user_id: uuid.UUID
    name: str
    realm_name: str
    realm_slug: str
    region: str
    faction: str | None
    race: str | None
    character_class: str | None
    specialization: str | None
    level: int | None
    achievement_points: int | None
    avatar_url: str | None
    verification: str
    is_active: bool
    is_main: bool
    last_synced_at: datetime | None
    last_sync_error: str | None


# ----------------------------------------------------------------------------- events
class ParticipantOut(BaseModel):
    user: UserBrief
    character: CharacterOut | None
    confirmation: str


class MediaOut(BaseModel):
    id: uuid.UUID
    url: str
    content_type: str
    width: int | None
    height: int | None
    caption: str | None


class ReactionSummary(BaseModel):
    emoji: str
    count: int
    mine: bool


class EventOut(BaseModel):
    id: uuid.UUID
    event_type: str
    title: str
    description: str
    occurred_at: datetime
    time_precision: str
    importance: int
    highlight: str | None
    difficulty: str | None
    instance_name: str | None
    expansion: str | None
    season: str | None
    source: str
    provenance: str
    confidence: str
    is_manual: bool
    is_demo: bool
    hidden: bool
    pinned: bool
    favorite: bool
    achievement: dict | None
    encounter: dict | None
    item: dict | None
    extra: dict[str, Any]
    # Game artwork (Blizzard render CDN). image_kind: icon | portrait | scene. scene_url: instance artwork.
    image_url: str | None = None
    image_kind: str | None = None
    scene_url: str | None = None
    participants: list[ParticipantOut]
    reactions: list[ReactionSummary]
    comment_count: int
    media: list[MediaOut]
    created_by: UserBrief | None
    can_edit: bool
    can_moderate: bool


class EventPage(BaseModel):
    items: list[EventOut]
    next_cursor: str | None
    total: int
    hidden_below_threshold: int


MANUAL_TYPES = Literal["manual", "milestone", "boss_kill", "dungeon_complete", "achievement", "loot"]


class ManualEventIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=5000)
    occurred_at: datetime
    event_type: MANUAL_TYPES = "manual"
    participant_user_ids: list[uuid.UUID] = Field(default_factory=list, max_length=40)
    achievement_id: int | None = None
    encounter_name: str | None = Field(default=None, max_length=160)
    instance_name: str | None = Field(default=None, max_length=160)
    difficulty: str | None = Field(default=None, max_length=32)
    item_id: int | None = None
    item_name: str | None = Field(default=None, max_length=200)
    item_quality: Literal["rare", "epic", "legendary", "unknown"] | None = None
    item_category: Literal["gear", "mount", "pet", "toy", "collectible", "other"] | None = None
    major: bool = False


class EventPatch(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    hidden: bool | None = None
    pinned: bool | None = None


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class CommentOut(BaseModel):
    id: uuid.UUID
    user: UserBrief
    body: str
    created_at: datetime
    can_delete: bool


ALLOWED_REACTIONS = ("gg", "fire", "skull", "laugh", "heart", "trophy", "gem", "salute")


class ReactionIn(BaseModel):
    emoji: Literal["gg", "fire", "skull", "laugh", "heart", "trophy", "gem", "salute"]


class VoteIn(BaseModel):
    nomination_id: uuid.UUID


class NominationIn(BaseModel):
    nominee_user_id: uuid.UUID
    reason: str = Field(default="", max_length=280)


MemberOut.model_rebuild()
