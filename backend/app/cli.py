"""Management commands: python -m app.cli <command>"""

import argparse
import time

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.integrations.blizzard.adapter import get_adapter
from app.integrations.blizzard.types import BlizzardError
from app.models import ExternalAccount, Group, User
from app.services import blizzard_sync, game_media
from app.services.awards.engine import recompute_group
from app.services.demo_seed import apply_demo_media, demo_exists, purge_demo, seed_demo


def sync_all() -> None:
    with SessionLocal() as db:
        adapter = get_adapter()
        for (uid,) in db.execute(select(ExternalAccount.user_id).distinct()).all():
            user = db.get(User, uid)
            try:
                job = blizzard_sync.run_user_sync(db, user, adapter)
                print(f"[sync] {user.display_name}: {job.status} {job.stats}")
            except BlizzardError as exc:
                print(f"[sync] {user.display_name}: failed: {exc}")
        try:
            print(f"[sync] game artwork: {game_media.resolve_media(db, adapter)}")
        except BlizzardError as exc:
            print(f"[sync] game artwork skipped: {exc}")
        for (gid,) in db.execute(select(Group.id)).all():
            recompute_group(db, gid, only_open=True)


def main() -> None:
    p = argparse.ArgumentParser(prog="app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("seed-demo", help="(re)create the fictional demo group")
    s.add_argument("--if-missing", action="store_true")
    sub.add_parser("purge-demo", help="delete all demo data")
    sub.add_parser("recompute-awards", help="recompute awards for every group")
    sub.add_parser("sync", help="run one Battle.net sync pass for all linked users")
    sub.add_parser("resolve-media", help="fetch missing item/achievement icons, boss portraits and dungeon art")
    sub.add_parser("worker", help="loop: sync + award recompute every SYNC_INTERVAL_MINUTES")
    args = p.parse_args()

    if args.cmd == "seed-demo":
        with SessionLocal() as db:
            if args.if_missing and (demo_exists(db) or not get_settings().demo_mode):
                if demo_exists(db):
                    apply_demo_media(db)  # keeps older demo installs up to date with artwork
                print("demo: skipped (exists or DEMO_MODE=false)")
                return
            t = time.time()
            g = seed_demo(db)
            print(f"demo: seeded '{g.name}' in {time.time() - t:.1f}s")
    elif args.cmd == "purge-demo":
        with SessionLocal() as db:
            purge_demo(db)
            print("demo: purged")
    elif args.cmd == "recompute-awards":
        with SessionLocal() as db:
            for (gid,) in db.execute(select(Group.id)).all():
                print(gid, recompute_group(db, gid))
    elif args.cmd == "sync":
        sync_all()
    elif args.cmd == "resolve-media":
        if not game_media.media_enabled():
            print("game artwork: disabled (set BLIZZARD_CLIENT_ID/BLIZZARD_CLIENT_SECRET, or BLIZZARD_ADAPTER=mock)")
            return
        with SessionLocal() as db:
            print(f"game artwork: {game_media.resolve_media(db, get_adapter())}")
    elif args.cmd == "worker":
        interval = get_settings().sync_interval_minutes * 60
        while True:
            try:
                sync_all()
            except Exception as exc:  # keep the worker alive; errors are also recorded on sync_jobs
                print(f"[worker] error: {exc}")
            time.sleep(interval)


if __name__ == "__main__":
    main()
