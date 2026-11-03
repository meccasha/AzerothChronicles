"""game media: instances, boss portraits, achievement/item icons, mount ids

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-03
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SAFE_URL = r"^https://render(-[a-z]{2})?\.worldofwarcraft\.com/"


def upgrade() -> None:
    op.create_table(
        "game_instances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("journal_instance_id", sa.Integer(), nullable=True),
        sa.Column("map_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("instance_type", sa.String(length=16), nullable=True),
        sa.Column("image_url", sa.String(length=512), nullable=True),
        sa.Column("media_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("media_status", sa.String(length=24), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("journal_instance_id"),
    )
    op.create_index("ix_game_instances_map_id", "game_instances", ["map_id"])
    op.create_index("ix_game_instances_name", "game_instances", ["name"])
    op.add_column("achievements", sa.Column("icon_fetched_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("adventure_events", sa.Column("game_instance_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_adventure_events_game_instance", "adventure_events", "game_instances",
                          ["game_instance_id"], ["id"], ondelete="SET NULL")
    op.add_column("encounters", sa.Column("game_instance_id", sa.Integer(), nullable=True))
    op.add_column("encounters", sa.Column("image_url", sa.String(length=512), nullable=True))
    op.add_column("encounters", sa.Column("media_fetched_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("encounters", sa.Column("media_status", sa.String(length=24), nullable=True))
    op.create_foreign_key("fk_encounters_game_instance", "encounters", "game_instances",
                          ["game_instance_id"], ["id"], ondelete="SET NULL")
    op.add_column("items", sa.Column("icon_file_id", sa.Integer(), nullable=True))
    op.add_column("loot_events", sa.Column("collectible_id", sa.Integer(), nullable=True))

    # --- backfill existing data -------------------------------------------------------------
    # Instances from encounters (raids and dungeon bosses) ...
    op.execute("""
        INSERT INTO game_instances (name, map_id, instance_type, is_demo)
        SELECT instance_name, max(instance_id), max(instance_type), bool_or(is_demo)
        FROM encounters WHERE instance_name IS NOT NULL GROUP BY instance_name
    """)
    # ... and from Mythic+ / manual dungeon completions not already known.
    op.execute("""
        INSERT INTO game_instances (name, instance_type, is_demo)
        SELECT instance_name, 'dungeon', bool_or(is_demo) FROM adventure_events
        WHERE event_type = 'dungeon_complete' AND instance_name IS NOT NULL
          AND instance_name NOT IN (SELECT name FROM game_instances)
        GROUP BY instance_name
    """)
    op.execute("UPDATE encounters e SET game_instance_id = gi.id FROM game_instances gi WHERE gi.name = e.instance_name")
    op.execute("""
        UPDATE adventure_events ae SET game_instance_id = gi.id FROM game_instances gi
        WHERE ae.instance_name = gi.name AND ae.event_type IN ('boss_kill', 'dungeon_complete')
    """)
    # Collectible ids were only kept in the dedup key ("mount:<user>:<id>").
    op.execute(r"""
        UPDATE loot_events SET collectible_id = split_part(dedup_key, ':', 3)::int
        WHERE dedup_key ~ '^(mount|pet|toy):[^:]+:[0-9]+$'
    """)
    # Earlier versions stored the client's numeric icon FileDataID in icon_url; move it, and drop any
    # icon URL that does not point at Blizzard's render CDN.
    op.execute(r"UPDATE items SET icon_file_id = icon_url::int, icon_url = NULL WHERE icon_url ~ '^[0-9]{1,9}$'")
    op.execute(f"UPDATE items SET icon_url = NULL WHERE icon_url IS NOT NULL AND icon_url !~ '{SAFE_URL}'")
    op.execute(f"UPDATE loot_events SET icon_url = NULL WHERE icon_url IS NOT NULL AND icon_url !~ '{SAFE_URL}'")
    op.execute(f"UPDATE achievements SET icon_url = NULL WHERE icon_url IS NOT NULL AND icon_url !~ '{SAFE_URL}'")


def downgrade() -> None:
    op.drop_column("loot_events", "collectible_id")
    op.drop_column("items", "icon_file_id")
    op.drop_constraint("fk_encounters_game_instance", "encounters", type_="foreignkey")
    op.drop_column("encounters", "media_status")
    op.drop_column("encounters", "media_fetched_at")
    op.drop_column("encounters", "image_url")
    op.drop_column("encounters", "game_instance_id")
    op.drop_constraint("fk_adventure_events_game_instance", "adventure_events", type_="foreignkey")
    op.drop_column("adventure_events", "game_instance_id")
    op.drop_column("achievements", "icon_fetched_at")
    op.drop_index("ix_game_instances_name", table_name="game_instances")
    op.drop_index("ix_game_instances_map_id", table_name="game_instances")
    op.drop_table("game_instances")
