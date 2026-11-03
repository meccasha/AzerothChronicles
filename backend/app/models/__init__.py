"""All ORM models; importing this package registers them on Base.metadata."""

from app.models.awards import AwardDefinition, AwardNomination, AwardResult, AwardVote
from app.models.catalog import Achievement, Encounter, GameInstance, Item
from app.models.characters import Character, CharacterIdentityHistory
from app.models.events import (
    ActivitySession,
    AdventureEvent,
    CharacterAchievement,
    EncounterAttempt,
    EncounterAttemptParticipant,
    EventComment,
    EventFavorite,
    EventMedia,
    EventParticipant,
    EventReaction,
    LootEvent,
)
from app.models.groups import Group, GroupInvite, GroupItemRule, GroupMembership
from app.models.sync import IngestionRecord, SyncJob, SyncSource
from app.models.users import ApiToken, ExternalAccount, IntegrationCredential, OAuthState, User, UserSession

__all__ = [
    "Achievement", "ActivitySession", "AdventureEvent", "ApiToken", "AwardDefinition", "AwardNomination",
    "AwardResult", "AwardVote", "Character", "CharacterAchievement", "CharacterIdentityHistory", "Encounter",
    "EncounterAttempt", "EncounterAttemptParticipant", "EventComment", "EventFavorite", "EventMedia",
    "EventParticipant", "EventReaction", "ExternalAccount", "GameInstance", "Group", "GroupInvite", "GroupItemRule",
    "GroupMembership", "IngestionRecord", "IntegrationCredential", "Item", "LootEvent", "OAuthState",
    "SyncJob", "SyncSource", "User", "UserSession",
]
