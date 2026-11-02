"""Battle.net account linking and achievement synchronization.

Backfill vs live:
* The first successful achievement sync of a character is a *backfill*. Every achievement is stored
  as a snapshot (source=blizzard_backfill). A timeline event is only created when Blizzard reports a
  real completion timestamp that falls after the member joined the group, and it is labelled
  provenance=backfill ("Imported from Blizzard history").
* Later syncs diff against the stored snapshot. Newly observed achievements become live events. If
  Blizzard gives a completion timestamp we use it (time_precision=exact); otherwise we use the
  observation time and label it (time_precision=observed).
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.blizzard.adapter import BlizzardAdapter
from app.integrations.blizzard.types import (
    BlizzardAuthError,
    BlizzardError,
    CharacterNotFound,
    CharacterSummary,
)
from app.models import (
    Achievement,
    AdventureEvent,
    Character,
    CharacterAchievement,
    ExternalAccount,
    Group,
    GroupMembership,
    IntegrationCredential,
    SyncJob,
    SyncSource,
    User,
)
from app.security import decrypt_secret, encrypt_secret
from app.services import importance
from app.services.characters import apply_identity, record_identity
from app.services.events import add_participant, get_or_create_event, lock_group, recompute_highlights
from app.services.group_settings import load_settings
from app.services.sessions import rebuild_activity_sessions


def _now() -> datetime:
    return datetime.now(UTC)


def _source(db: Session, user_id: uuid.UUID) -> SyncSource:
    src = db.scalar(select(SyncSource).where(SyncSource.user_id == user_id, SyncSource.kind == "blizzard_api"))
    if src is None:
        src = SyncSource(id=uuid.uuid4(), user_id=user_id, kind="blizzard_api", status="idle")
        db.add(src)
        db.flush()
    return src


def store_link(db: Session, user: User, adapter: BlizzardAdapter, *, code: str, redirect_uri: str,
               region: str) -> ExternalAccount:
    tokens = adapter.exchange_code(code=code, redirect_uri=redirect_uri, region=region)
    ident = adapter.userinfo(access_token=tokens.access_token, region=region)
    acct = db.scalar(select(ExternalAccount).where(ExternalAccount.provider == "battlenet",
                                                   ExternalAccount.external_id == ident.id))
    if acct is not None and acct.user_id != user.id:
        raise BlizzardError("This Battle.net account is already linked to another Azeroth Chronicles user.")
    if acct is None:
        acct = ExternalAccount(id=uuid.uuid4(), user_id=user.id, provider="battlenet", external_id=ident.id,
                               region=region)
        db.add(acct)
        db.flush()
    acct.display_name, acct.region = ident.battletag, region
    cred = acct.credential or IntegrationCredential(id=uuid.uuid4(), external_account_id=acct.id)
    cred.access_token_encrypted = encrypt_secret(tokens.access_token)
    cred.refresh_token_encrypted = encrypt_secret(tokens.refresh_token) if tokens.refresh_token else None
    cred.expires_at, cred.scopes = tokens.expires_at, tokens.scopes
    db.add(cred)
    src = _source(db, user.id)
    src.status, src.last_error = "ok", None
    db.commit()
    return acct


def user_access_token(db: Session, user_id: uuid.UUID) -> tuple[ExternalAccount, str]:
    acct = db.scalar(select(ExternalAccount).where(ExternalAccount.user_id == user_id,
                                                   ExternalAccount.provider == "battlenet"))
    if acct is None or acct.credential is None:
        raise BlizzardAuthError("No Battle.net account linked.")
    cred = acct.credential
    if cred.expires_at and cred.expires_at < _now() + timedelta(minutes=2):
        # Battle.net user tokens are short-lived and are not refreshable via refresh_token in the
        # documented flow; the user must re-authorize. Character/achievement sync does NOT need the
        # user token (it uses client credentials), so only account character listing is affected.
        raise BlizzardAuthError("Battle.net authorization expired. Re-link to refresh your character list.")
    return acct, decrypt_secret(cred.access_token_encrypted)


def list_account_characters(db: Session, user: User, adapter: BlizzardAdapter) -> list[CharacterSummary]:
    acct, token = user_access_token(db, user.id)
    return adapter.account_characters(access_token=token, region=acct.region)


def link_characters(db: Session, user: User, adapter: BlizzardAdapter, blizzard_ids: list[int]) -> list[Character]:
    """Link selected characters from the user's own Battle.net account (ownership verified by Blizzard)."""
    available = {c.blizzard_id: c for c in list_account_characters(db, user, adapter)}
    linked: list[Character] = []
    for bid in blizzard_ids:
        summary = available.get(bid)
        if summary is None:
            raise BlizzardError(f"Character {bid} is not on your Battle.net account.")
        ch = db.scalar(select(Character).where(Character.region == summary.region,
                                               Character.blizzard_character_id == bid))
        if ch is not None and ch.owner_user_id != user.id:
            raise BlizzardError(f"{summary.name} is already linked by another user.")
        if ch is None:
            # Adopt a manual/addon character with the same name+realm if present.
            ch = db.scalar(select(Character).where(Character.owner_user_id == user.id,
                                                   Character.name == summary.name,
                                                   Character.realm_slug == summary.realm_slug,
                                                   Character.blizzard_character_id.is_(None)))
        if ch is None:
            ch = Character(id=uuid.uuid4(), owner_user_id=user.id, region=summary.region, name=summary.name,
                           realm_slug=summary.realm_slug, realm_name=summary.realm_name)
            db.add(ch)
            db.flush()
            record_identity(db, ch, "created", "blizzard_api")
        ch.blizzard_character_id = bid
        ch.verification = "blizzard_verified"
        ch.realm_slug = summary.realm_slug
        ch.character_class, ch.race, ch.faction, ch.level = (
            summary.character_class, summary.race, summary.faction, summary.level)
        linked.append(ch)
    db.commit()
    return linked


def _post_achievement(db: Session, user: User, ch: Character, ach: Achievement, *, when: datetime,
                      precision: str, provenance: str, source: str) -> int:
    """Create/merge group timeline events for one achievement. Returns number of events touched."""
    touched = 0
    rows = db.execute(select(Group, GroupMembership).join(GroupMembership, GroupMembership.group_id == Group.id)
                      .where(GroupMembership.user_id == user.id)).all()
    for group, membership in rows:
        settings = load_settings(group.settings)
        if "achievement" not in settings.events.enabled_categories:
            continue
        if not importance.should_post_achievement(ach.points, ach.is_feat_of_strength,
                                                  settings.events.achievement_min_points):
            continue
        if provenance == "backfill" and when < membership.joined_at:
            continue  # historical, predates the member's time in this group
        lock_group(db, group.id)
        window = timedelta(hours=settings.events.achievement_merge_hours)
        event = db.scalar(select(AdventureEvent).where(
            AdventureEvent.group_id == group.id, AdventureEvent.event_type == "achievement",
            AdventureEvent.achievement_id == ach.id, AdventureEvent.deleted_at.is_(None),
            AdventureEvent.occurred_at.between(when - window, when + window)))
        if event is None:
            event, _ = get_or_create_event(
                db, group.id, f"ach:{ach.id}:{int(when.timestamp())}:{user.id}",
                event_type="achievement", title=ach.name, description=ach.description or "",
                occurred_at=when, time_precision=precision,
                importance=importance.achievement_importance(ach.points, ach.is_feat_of_strength, 1),
                achievement_id=ach.id, source=source, provenance=provenance, confidence="confirmed",
                extra={"points": ach.points, "feat_of_strength": ach.is_feat_of_strength},
            )
        add_participant(db, event, user.id, ch.id, "confirmed")
        touched += 1
    return touched


def _ensure_achievement(db: Session, adapter: BlizzardAdapter, region: str, ach_id: int, name: str) -> Achievement:
    ach = db.get(Achievement, ach_id)
    if ach is None or ach.metadata_fetched_at is None:
        try:
            info = adapter.achievement(region=region, achievement_id=ach_id)
            if ach is None:
                ach = Achievement(id=ach_id, name=info.name)
                db.add(ach)
            ach.name, ach.description, ach.points, ach.category = info.name, info.description, info.points, \
                info.category
            ach.is_feat_of_strength = (info.category or "").lower().startswith("feats of strength")
            ach.metadata_fetched_at = _now()
        except BlizzardError:
            if ach is None:  # keep the snapshot even when metadata is unavailable
                ach = Achievement(id=ach_id, name=name, points=0)
                db.add(ach)
        db.flush()
    return ach


def sync_character(db: Session, adapter: BlizzardAdapter, ch: Character) -> dict:
    user = db.get(User, ch.owner_user_id)
    stats = {"new_achievements": 0, "events": 0, "backfill": ch.achievements_backfilled_at is None}
    profile = adapter.character_profile(region=ch.region, realm_slug=ch.realm_slug, name=ch.name)
    if ch.blizzard_character_id and profile.blizzard_id != ch.blizzard_character_id:
        raise BlizzardError("Character id mismatch: this name now belongs to a different character "
                            "(possible rename/transfer). Re-link from your Battle.net account.")
    apply_identity(db, ch, name=profile.name, realm_name=profile.realm_name, region=ch.region,
                   faction=profile.faction, source="blizzard_api")
    ch.realm_slug = profile.realm_slug
    ch.level, ch.character_class, ch.race = profile.level, profile.character_class, profile.race
    ch.specialization, ch.achievement_points = profile.specialization, profile.achievement_points
    ch.avatar_url = adapter.character_avatar(region=ch.region, realm_slug=ch.realm_slug, name=ch.name) \
        or ch.avatar_url

    result = adapter.character_achievements(region=ch.region, realm_slug=ch.realm_slug, name=ch.name)
    known = set(db.scalars(select(CharacterAchievement.achievement_id)
                           .where(CharacterAchievement.character_id == ch.id)))
    backfill = ch.achievements_backfilled_at is None
    now = _now()
    for comp in result.completions:
        if comp.achievement_id in known:
            continue
        ach = _ensure_achievement(db, adapter, ch.region, comp.achievement_id, comp.name)
        db.add(CharacterAchievement(id=uuid.uuid4(), character_id=ch.id, achievement_id=ach.id,
                                    completed_at=comp.completed_at, observed_at=now,
                                    source="blizzard_backfill" if backfill else "blizzard_sync"))
        stats["new_achievements"] += 1
        if backfill:
            if comp.completed_at is not None:
                stats["events"] += _post_achievement(db, user, ch, ach, when=comp.completed_at, precision="exact",
                                                     provenance="backfill", source="blizzard_api")
        else:
            when = comp.completed_at or now
            stats["events"] += _post_achievement(db, user, ch, ach, when=when,
                                                 precision="exact" if comp.completed_at else "observed",
                                                 provenance="live", source="blizzard_api")
    if backfill:
        ch.achievements_backfilled_at = now
    ch.last_synced_at, ch.last_sync_error = now, None
    db.flush()
    return stats


def refresh_identities(db: Session, user: User, adapter: BlizzardAdapter) -> str | None:
    """Re-read the account character list (keyed by stable Blizzard id) to pick up renames/transfers.

    Character endpoints are addressed by realm+name, so after a rename the old name 404s; the account
    profile is the authoritative mapping from id to current name. Returns a note when unavailable.
    """
    try:
        summaries = {c.blizzard_id: c for c in list_account_characters(db, user, adapter)}
    except BlizzardError as exc:
        return f"Account character list unavailable ({exc}); renames cannot be detected until re-link."
    for ch in db.scalars(select(Character).where(Character.owner_user_id == user.id,
                                                 Character.blizzard_character_id.is_not(None))):
        s = summaries.get(ch.blizzard_character_id)
        if s is None:
            continue  # deleted or moved to another account: keep the character and its history as-is
        apply_identity(db, ch, name=s.name, realm_name=s.realm_name, region=s.region, faction=s.faction,
                       source="blizzard_api")
        ch.realm_slug = s.realm_slug
    db.flush()
    return None


def run_user_sync(db: Session, user: User, adapter: BlizzardAdapter) -> SyncJob:
    job = SyncJob(id=uuid.uuid4(), user_id=user.id, kind="blizzard_achievements", status="running",
                  started_at=_now(), stats={})
    db.add(job)
    db.commit()
    chars = db.scalars(select(Character).where(Character.owner_user_id == user.id,
                                               Character.verification == "blizzard_verified",
                                               Character.is_active.is_(True))).all()
    totals = {"characters": len(chars), "ok": 0, "failed": 0, "new_achievements": 0, "events": 0}
    errors: list[str] = []
    note = refresh_identities(db, user, adapter)
    if note:
        totals["note"] = note
    for ch in chars:
        try:
            with db.begin_nested():
                s = sync_character(db, adapter, ch)
            totals["ok"] += 1
            totals["new_achievements"] += s["new_achievements"]
            totals["events"] += s["events"]
        except (CharacterNotFound, BlizzardError) as exc:
            ch.last_sync_error = str(exc)[:500]
            totals["failed"] += 1
            errors.append(f"{ch.name}-{ch.realm_slug}: {exc}")
    for (gid,) in db.execute(select(GroupMembership.group_id).where(GroupMembership.user_id == user.id)).all():
        recompute_highlights(db, gid)
        rebuild_activity_sessions(db, gid)
    job.finished_at = _now()
    job.stats = totals
    job.status = "succeeded" if not errors else ("partial" if totals["ok"] else "failed")
    job.error = "\n".join(errors) or None
    src = _source(db, user.id)
    src.last_attempt_at = job.finished_at
    if totals["ok"] or not chars:
        src.last_success_at = job.finished_at
    src.status = "ok" if not errors else "error"
    src.last_error = job.error
    db.commit()
    return job


def unlink(db: Session, user: User) -> None:
    acct = db.scalar(select(ExternalAccount).where(ExternalAccount.user_id == user.id,
                                                   ExternalAccount.provider == "battlenet"))
    if acct:
        db.delete(acct)  # cascades credentials
    src = db.scalar(select(SyncSource).where(SyncSource.user_id == user.id, SyncSource.kind == "blizzard_api"))
    if src:
        src.status = "disabled"
    db.commit()
