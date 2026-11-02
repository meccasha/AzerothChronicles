"""Typed, validated per-group configuration stored in groups.settings (JSONB)."""

from typing import Any

from pydantic import BaseModel, Field


class LootRules(BaseModel):
    record_legendary: bool = True
    record_epic: bool = True
    record_rare: bool = False
    record_mounts: bool = True
    record_collectibles: bool = True  # pets / toys
    epic_min_item_level: int | None = Field(default=None, ge=0, le=2000)


class EventRules(BaseModel):
    # Default importance cut-off for the timeline; lower-importance events are stored but collapsed.
    timeline_min_importance: int = Field(default=30, ge=0, le=100)
    # Achievements worth fewer points (and not Feats of Strength) are tracked but not posted to the timeline.
    achievement_min_points: int = Field(default=10, ge=0, le=100)
    # Window used to merge the same achievement earned by several members into one event.
    achievement_merge_hours: int = Field(default=6, ge=0, le=72)
    # Minimum number of group members that must be present for a boss kill to be posted.
    encounter_min_members: int = Field(default=1, ge=1, le=40)
    enabled_categories: list[str] = Field(
        default_factory=lambda: ["achievement", "boss_kill", "dungeon_complete", "loot", "milestone", "manual"]
    )


class AwardSettings(BaseModel):
    disabled: list[str] = Field(default_factory=list)


class GroupSettings(BaseModel):
    loot: LootRules = Field(default_factory=LootRules)
    events: EventRules = Field(default_factory=EventRules)
    awards: AwardSettings = Field(default_factory=AwardSettings)


def load_settings(raw: dict[str, Any] | None) -> GroupSettings:
    return GroupSettings.model_validate(raw or {})


def merge_settings(raw: dict[str, Any] | None, patch: dict[str, Any]) -> GroupSettings:
    current = load_settings(raw).model_dump()
    for section, values in patch.items():
        if isinstance(values, dict) and isinstance(current.get(section), dict):
            current[section].update(values)
        else:
            current[section] = values
    return GroupSettings.model_validate(current)
