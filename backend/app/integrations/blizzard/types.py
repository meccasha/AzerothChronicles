"""Provider-neutral data shapes returned by Blizzard adapters.

Business logic only ever sees these types, never raw Battle.net JSON.
"""

from dataclasses import dataclass, field
from datetime import datetime


class BlizzardError(Exception):
    """Base error with a user-presentable message."""

    def __init__(self, message: str, *, status: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


class BlizzardNotConfigured(BlizzardError):
    pass


class CharacterNotFound(BlizzardError):
    pass


class BlizzardAuthError(BlizzardError):
    pass


@dataclass
class TokenSet:
    access_token: str
    expires_at: datetime | None
    refresh_token: str | None = None
    scopes: str = ""


@dataclass
class AccountIdentity:
    id: str
    battletag: str | None


@dataclass
class CharacterSummary:
    blizzard_id: int
    name: str
    realm_slug: str
    realm_name: str
    region: str
    level: int | None = None
    character_class: str | None = None
    race: str | None = None
    faction: str | None = None


@dataclass
class CharacterProfile(CharacterSummary):
    specialization: str | None = None
    achievement_points: int | None = None


@dataclass
class AchievementCompletion:
    achievement_id: int
    name: str
    completed_at: datetime | None  # None when Blizzard does not report a completion timestamp


@dataclass
class AchievementInfo:
    id: int
    name: str
    description: str | None
    points: int
    category: str | None = None
    icon_url: str | None = None


@dataclass
class ItemInfo:
    id: int
    name: str
    quality: str
    item_class: str | None = None
    item_subclass: str | None = None
    inventory_type: str | None = None
    icon_url: str | None = None


@dataclass
class CharacterAchievements:
    total_points: int | None
    completions: list[AchievementCompletion] = field(default_factory=list)
