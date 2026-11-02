# Awards

Code: `backend/app/services/awards/` — `rules.py` (one class per award) and `engine.py` (periods,
ranking, persistence). Rules text shown in the UI comes from the same classes.

## Periods

| Type | Window (UTC) | Computed |
|---|---|---|
| `week` | ISO week, Monday 00:00 → next Monday | last 26 weeks |
| `month` | calendar month | every month since the group's first event |
| `season` | windows in `backend/app/data/periods.json` (editable config) | every season overlapping group history |
| `all_time` | everything | always |

A result is `is_final` once its period has ended (all-time never is). The worker recomputes open periods;
admins can recompute everything from the Hall of Fame.

## Ranking

Members are ranked by score (descending). Ties share a rank and the result status is `tied`; the listed
winner breaks the tie by earliest membership, then display name — deterministic, so recomputation always
returns the same result. A score of 0 never wins (`no_data`). If the data an award needs does not exist at
all, the result is `insufficient_data` instead of a guess.

## Award rules

| Award | Score | Periods |
|---|---|---|
| Achievement Hunter | Achievement timeline events participated in (incl. Battle.net backfill dated after joining) | all |
| Loot Goblin | Loot Museum entries obtained | all |
| Legendary Collector | Legendary-quality Loot Museum entries | all |
| Raid Veteran | Raid boss-kill events with `confirmed` or `roster` participation | all |
| Dungeon Explorer | Dungeon completions with `confirmed` or `roster` participation | all |
| Progression Pioneer | Boss kills that were the group's first recorded kill of that boss + difficulty (`confirmed`/`roster`) | all |
| Unbreakable | Successful attempts where the member's **own addon** reported 0 deaths; needs death data | all |
| The Floor Inspector | Sum of deaths reported by the member's own addon; needs death data | all |
| Day One Adventurer | Days from earliest of (membership date, first live event participation) to period end | all-time |
| Most Active Adventurer | All visible timeline events participated in (including manual `claimed` ones) | all |
| Group MVP *(voted)* | Votes on the month's nominations, one vote per member (changeable) | month |

Hidden and deleted events never count. Manual (`claimed`) participation counts only for Most Active.

## Adding an award

```python
class Explorer(AwardRule):
    key, title, icon, unit = "explorer", "Explorer", "compass", "instances"
    description = "Most distinct instances visited."
    rules = "Counts distinct instance names across the member's visible events."

    def scores(self, db, group_id, p):
        ...  # return {user_id: float} or None when data is unavailable

REGISTRY.append(Explorer())
```

Definitions are upserted into `award_definitions` on startup, and the frontend renders new awards
automatically (add an icon mapping in `frontend/src/components/common/award-icon.tsx` if needed).
Add a unit test next to `backend/tests/test_stats_awards.py`.
