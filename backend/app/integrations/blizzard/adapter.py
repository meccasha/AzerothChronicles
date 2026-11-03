"""Adapter interface for Battle.net. Implementations: LiveBlizzardAdapter, MockBlizzardAdapter."""

from typing import Protocol

from app.integrations.blizzard.types import (
    AccountIdentity,
    AchievementInfo,
    CharacterAchievements,
    CharacterProfile,
    CharacterSummary,
    ItemInfo,
    JournalEncounterInfo,
    JournalInstanceInfo,
    TokenSet,
)


class BlizzardAdapter(Protocol):
    mode: str

    # --- OAuth (authorization code flow, scope "wow.profile") ---
    def authorize_url(self, *, state: str, redirect_uri: str, region: str) -> str: ...
    def exchange_code(self, *, code: str, redirect_uri: str, region: str) -> TokenSet: ...
    def userinfo(self, *, access_token: str, region: str) -> AccountIdentity: ...

    # --- Account profile (user token) ---
    def account_characters(self, *, access_token: str, region: str) -> list[CharacterSummary]: ...

    # --- Character profile (client-credentials token) ---
    def character_profile(self, *, region: str, realm_slug: str, name: str) -> CharacterProfile: ...
    def character_achievements(self, *, region: str, realm_slug: str, name: str) -> CharacterAchievements: ...
    def character_avatar(self, *, region: str, realm_slug: str, name: str) -> str | None: ...

    # --- Game data (client-credentials token) ---
    def achievement(self, *, region: str, achievement_id: int) -> AchievementInfo: ...
    def item(self, *, region: str, item_id: int) -> ItemInfo: ...

    # --- Game data media (client-credentials token) ---
    def achievement_icon(self, *, region: str, achievement_id: int) -> str | None: ...
    def journal_instance_index(self, *, region: str) -> list[tuple[int, str]]: ...
    def journal_instance(self, *, region: str, journal_instance_id: int) -> JournalInstanceInfo: ...
    def journal_encounter(self, *, region: str, journal_encounter_id: int) -> JournalEncounterInfo: ...
    def mount_image(self, *, region: str, mount_id: int) -> str | None: ...


def get_adapter() -> BlizzardAdapter:
    from app.config import get_settings

    settings = get_settings()
    if settings.blizzard_adapter == "live":
        from app.integrations.blizzard.live import LiveBlizzardAdapter

        return LiveBlizzardAdapter(settings)
    from app.integrations.blizzard.mock import MockBlizzardAdapter

    return MockBlizzardAdapter()
