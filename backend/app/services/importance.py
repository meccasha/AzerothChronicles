"""Event importance scoring (0-100). Pure functions so the rules are easy to test and tune.

Importance controls default timeline visibility; it never deletes data.
"""

DIFFICULTY_BONUS = {"mythic": 25, "heroic": 12, "normal": 5, "lfr": 0, "story": 0}


def difficulty_key(name: str | None) -> str:
    n = (name or "").lower()
    if "mythic" in n:
        return "mythic"
    if "heroic" in n:
        return "heroic"
    if "looking for raid" in n or n == "lfr":
        return "lfr"
    if "story" in n:
        return "story"
    return "normal"


def boss_kill_importance(instance_type: str, difficulty: str | None, first_kill: bool, members: int) -> int:
    base = 60 if instance_type == "raid" else 35
    score = base + DIFFICULTY_BONUS[difficulty_key(difficulty)]
    if first_kill:
        score += 15
    if members >= 2:
        score += 5
    return min(score, 100)


def dungeon_importance(keystone_level: int | None, members: int) -> int:
    score = 35
    if keystone_level:
        score += min(keystone_level, 20)
    if members >= 3:
        score += 5
    return min(score, 100)


def achievement_importance(points: int, feat_of_strength: bool, members: int) -> int:
    score = 20 + min(points, 50)
    if feat_of_strength:
        score += 30
    if members >= 2:
        score += 10
    return min(score, 100)


def loot_importance(quality: str, category: str, reason: str) -> int:
    if quality == "legendary":
        score = 92
    elif category == "mount":
        score = 75
    elif quality == "epic":
        score = 45
    else:
        score = 30
    if reason in ("favorite", "wishlist"):
        score += 20
    return min(score, 100)


def should_post_achievement(points: int, feat_of_strength: bool, min_points: int) -> bool:
    return feat_of_strength or points >= min_points
