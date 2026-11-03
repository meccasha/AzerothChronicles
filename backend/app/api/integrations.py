import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.deps import DB, CurrentUser
from app.integrations.blizzard.adapter import get_adapter
from app.integrations.blizzard.types import BlizzardError
from app.models import ApiToken, Character, ExternalAccount, IngestionRecord, OAuthState, SyncJob, SyncSource, User
from app.security import hash_token, new_token
from app.services import blizzard_sync, game_media

router = APIRouter(prefix="/integrations", tags=["integrations"])


def _adapter():
    try:
        return get_adapter()
    except BlizzardError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.get("/status")
def integration_status(user: CurrentUser, db: DB):
    s = get_settings()
    acct = db.scalar(select(ExternalAccount).where(ExternalAccount.user_id == user.id,
                                                   ExternalAccount.provider == "battlenet"))
    sources = {src.kind: src for src in db.scalars(select(SyncSource).where(SyncSource.user_id == user.id))}
    chars = db.scalars(select(Character).where(Character.owner_user_id == user.id)).all()
    jobs = db.scalars(select(SyncJob).where(SyncJob.user_id == user.id).order_by(SyncJob.created_at.desc())
                      .limit(10)).all()
    rejected = db.scalars(select(IngestionRecord).where(IngestionRecord.user_id == user.id,
                                                        IngestionRecord.status == "rejected")
                          .order_by(IngestionRecord.received_at.desc()).limit(10)).all()
    tokens = db.scalars(select(ApiToken).where(ApiToken.user_id == user.id, ApiToken.revoked_at.is_(None))).all()

    def src_out(kind):
        src = sources.get(kind)
        return None if not src else {"status": src.status, "last_attempt_at": src.last_attempt_at,
                                     "last_success_at": src.last_success_at, "last_error": src.last_error,
                                     "details": src.details}
    token_expired = bool(acct and acct.credential and acct.credential.expires_at
                         and acct.credential.expires_at < datetime.now(UTC))
    return {
        "blizzard": {
            "adapter_mode": s.blizzard_adapter,
            "configured": s.blizzard_configured or s.blizzard_adapter == "mock",
            "linked": acct is not None,
            "battletag": acct.display_name if acct else None,
            "region": acct.region if acct else None,
            "authorization_expired": token_expired,
            "source": src_out("blizzard_api"),
            "characters": [{"id": str(c.id), "name": c.name, "realm": c.realm_name, "verification": c.verification,
                            "last_synced_at": c.last_synced_at, "last_sync_error": c.last_sync_error,
                            "backfilled": c.achievements_backfilled_at is not None} for c in chars],
        },
        "addon": {"source": src_out("addon"), "active_tokens": len(tokens)},
        "jobs": [{"id": str(j.id), "kind": j.kind, "status": j.status, "started_at": j.started_at,
                  "finished_at": j.finished_at, "stats": j.stats, "error": j.error} for j in jobs],
        "recent_errors": [{"id": str(r.id), "record_type": r.record_type, "detail": r.status_detail,
                           "received_at": r.received_at} for r in rejected],
    }


_last_media_refresh: list[datetime] = []


@router.get("/media")
def media_status(user: CurrentUser, db: DB):
    """Game artwork (icons, boss portraits, dungeon art) coverage and whether it can be fetched."""
    from sqlalchemy import func

    from app.models import Achievement, Encounter, GameInstance, Item

    def cov(model, col):
        total = db.scalar(select(func.count()).select_from(model).where(model.is_demo.is_(False))) or 0
        have = db.scalar(select(func.count()).select_from(model).where(model.is_demo.is_(False), col.is_not(None))) or 0
        return {"total": total, "with_art": have}

    s = get_settings()
    return {
        "enabled": game_media.media_enabled(),
        "mode": s.blizzard_adapter,
        "pending": game_media.pending_counts(db),
        "coverage": {
            "items": cov(Item, Item.icon_url), "achievements": cov(Achievement, Achievement.icon_url),
            "bosses": cov(Encounter, Encounter.image_url), "instances": cov(GameInstance, GameInstance.image_url),
        },
    }


@router.post("/media/refresh")
def refresh_media(user: CurrentUser, background: BackgroundTasks):
    if not game_media.media_enabled():
        raise HTTPException(503, "Game artwork needs Battle.net API credentials (BLIZZARD_CLIENT_ID/SECRET).")
    now = datetime.now(UTC)
    if _last_media_refresh and now - _last_media_refresh[-1] < timedelta(seconds=60):
        raise HTTPException(429, "Artwork refresh already requested in the last minute")
    _last_media_refresh[:] = [now]
    background.add_task(game_media.run_in_background)
    return {"status": "started"}


@router.get("/blizzard/authorize")
def blizzard_authorize(user: CurrentUser, db: DB, region: str = Query("us", pattern="^(us|eu|kr|tw)$")):
    if user.is_demo:
        raise HTTPException(403, "The demo account cannot link Battle.net")
    adapter = _adapter()
    state = new_token(nbytes=24)
    db.add(OAuthState(id=uuid.uuid4(), state_hash=hash_token(state), user_id=user.id, region=region,
                      expires_at=datetime.now(UTC) + timedelta(minutes=10)))
    db.commit()
    redirect_uri = f"{get_settings().public_api_url}/integrations/blizzard/callback"
    return {"url": adapter.authorize_url(state=state, redirect_uri=redirect_uri, region=region),
            "mode": adapter.mode}


@router.get("/blizzard/mock-authorize", response_class=HTMLResponse)
def mock_authorize(state: str, redirect_uri: str):
    """Development-only stand-in for the Battle.net consent screen (mock adapter)."""
    if get_settings().blizzard_adapter != "mock":
        raise HTTPException(404)
    expected = f"{get_settings().public_api_url}/integrations/blizzard/callback"
    if redirect_uri != expected:
        raise HTTPException(400, "Invalid redirect_uri")
    approve = f"{redirect_uri}?{urlencode({'code': 'mock-code', 'state': state})}"
    deny = f"{redirect_uri}?{urlencode({'error': 'access_denied', 'state': state})}"
    return f"""<!doctype html><html><body style="font-family:sans-serif;background:#111827;color:#e5e7eb;
    display:grid;place-items:center;height:100vh"><div style="max-width:420px;text-align:center">
    <h2>Mock Battle.net (development)</h2><p>This is a simulated consent page. No real Battle.net account is
    involved. Approving links the fictional account <b>MockHero#1234</b>.</p>
    <p><a style="color:#fbbf24" href="{approve}">Approve</a> &nbsp; · &nbsp;
    <a style="color:#9ca3af" href="{deny}">Deny</a></p></div></body></html>"""


@router.get("/blizzard/callback")
def blizzard_callback(user: CurrentUser, db: DB, state: str, code: str | None = None, error: str | None = None):
    web = get_settings().public_web_url
    row = db.scalar(select(OAuthState).where(OAuthState.state_hash == hash_token(state)))
    if row is None or row.user_id != user.id or row.expires_at < datetime.now(UTC):
        return RedirectResponse(f"{web}/integrations?blizzard=invalid_state", status_code=303)
    region = row.region
    db.delete(row)  # single use
    db.commit()
    if error or not code:
        return RedirectResponse(f"{web}/integrations?blizzard=denied", status_code=303)
    try:
        blizzard_sync.store_link(db, user, _adapter(), code=code,
                                 redirect_uri=f"{get_settings().public_api_url}/integrations/blizzard/callback",
                                 region=region)
    except BlizzardError as exc:
        return RedirectResponse(f"{web}/integrations?{urlencode({'blizzard': 'error', 'message': str(exc)})}",
                                status_code=303)
    return RedirectResponse(f"{web}/integrations?blizzard=linked", status_code=303)


@router.get("/blizzard/account-characters")
def account_characters(user: CurrentUser, db: DB):
    try:
        chars = blizzard_sync.list_account_characters(db, user, _adapter())
    except BlizzardError as exc:
        raise HTTPException(400, str(exc)) from exc
    linked = {c.blizzard_character_id for c in db.scalars(select(Character).where(Character.owner_user_id == user.id))}
    return [{**c.__dict__, "linked": c.blizzard_id in linked} for c in sorted(chars, key=lambda c: -(c.level or 0))]


class LinkIn(BaseModel):
    blizzard_ids: list[int] = Field(min_length=1, max_length=50)


@router.post("/blizzard/characters")
def link_blizzard_characters(body: LinkIn, user: CurrentUser, db: DB, background: BackgroundTasks):
    try:
        chars = blizzard_sync.link_characters(db, user, _adapter(), body.blizzard_ids)
    except BlizzardError as exc:
        raise HTTPException(400, str(exc)) from exc
    background.add_task(_run_sync, user.id)
    return {"linked": [c.name for c in chars], "sync": "started"}


def _run_sync(user_id: uuid.UUID) -> None:
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user:
            try:
                blizzard_sync.run_user_sync(db, user, get_adapter())
            except BlizzardError:
                pass  # recorded on the job/source rows
    game_media.run_in_background()


@router.post("/blizzard/sync")
def trigger_sync(user: CurrentUser, db: DB, background: BackgroundTasks):
    running = db.scalar(select(SyncJob).where(SyncJob.user_id == user.id, SyncJob.kind == "blizzard_achievements",
                                              SyncJob.status == "running",
                                              SyncJob.started_at > datetime.now(UTC) - timedelta(minutes=10)))
    if running:
        raise HTTPException(409, "A sync is already running")
    recent = db.scalar(select(SyncJob).where(SyncJob.user_id == user.id, SyncJob.kind == "blizzard_achievements",
                                             SyncJob.started_at > datetime.now(UTC) - timedelta(minutes=2)))
    if recent:
        raise HTTPException(429, "Please wait a couple of minutes between manual syncs")
    _adapter()
    background.add_task(_run_sync, user.id)
    return {"status": "started"}


@router.delete("/blizzard", status_code=204)
def unlink_blizzard(user: CurrentUser, db: DB):
    blizzard_sync.unlink(db, user)
