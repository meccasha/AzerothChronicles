import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import delete, func, select

from app.config import get_settings
from app.deps import DB, CurrentUser
from app.models import (
    ApiToken,
    Character,
    EventComment,
    EventParticipant,
    Group,
    GroupMembership,
    LootEvent,
    User,
    UserSession,
)
from app.schemas.api import ApiTokenIn, ApiTokenOut, DeleteAccountIn, LoginIn, RegisterIn, UserOut
from app.security import hash_password, hash_token, new_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
me_router = APIRouter(prefix="/me", tags=["me"])

AVATAR_COLORS = ["#c08a2b", "#3f7cac", "#8c4fb8", "#2f8f6b", "#b5473a", "#c26d1f", "#5865a8", "#7a8f2f"]
_login_attempts: dict[str, list[datetime]] = {}


def _rate_limit(key: str, limit: int = 10, window: timedelta = timedelta(minutes=10)) -> None:
    now = datetime.now(UTC)
    hits = [t for t in _login_attempts.get(key, []) if now - t < window]
    if len(hits) >= limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts; try again later.")
    hits.append(now)
    _login_attempts[key] = hits


def start_session(db, response: Response, user: User) -> None:
    s = get_settings()
    raw = new_token(nbytes=32)
    now = datetime.now(UTC)
    db.add(UserSession(id=uuid.uuid4(), user_id=user.id, token_hash=hash_token(raw), created_at=now,
                       expires_at=now + timedelta(hours=s.session_ttl_hours)))
    db.execute(delete(UserSession).where(UserSession.user_id == user.id, UserSession.expires_at < now))
    db.commit()
    response.set_cookie(s.session_cookie_name, raw, max_age=s.session_ttl_hours * 3600, httponly=True,
                        secure=s.cookie_secure, samesite="lax", path="/")


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterIn, response: Response, request: Request, db: DB):
    _rate_limit(f"register:{request.client.host if request.client else '?'}", limit=20)
    email = body.email.lower()
    if db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    count = db.scalar(select(func.count(User.id))) or 0
    user = User(id=uuid.uuid4(), email=email, display_name=body.display_name,
                password_hash=hash_password(body.password), avatar_color=AVATAR_COLORS[count % len(AVATAR_COLORS)])
    db.add(user)
    db.commit()
    start_session(db, response, user)
    return user


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, response: Response, request: Request, db: DB):
    _rate_limit(f"login:{body.email.lower()}")
    user = db.scalar(select(User).where(func.lower(User.email) == body.email.lower()))
    if not user or user.is_demo or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    start_session(db, response, user)
    return user


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: DB):
    s = get_settings()
    raw = request.cookies.get(s.session_cookie_name)
    if raw:
        db.execute(delete(UserSession).where(UserSession.token_hash == hash_token(raw)))
        db.commit()
    response.delete_cookie(s.session_cookie_name, path="/")


@me_router.get("", response_model=UserOut)
def me(user: CurrentUser):
    return user


@me_router.get("/export")
def export_my_data(user: CurrentUser, db: DB):
    """GDPR-style export of the caller's own data."""
    chars = db.scalars(select(Character).where(Character.owner_user_id == user.id)).all()
    groups = db.execute(select(Group.name, GroupMembership.role, GroupMembership.joined_at)
                        .join(GroupMembership, GroupMembership.group_id == Group.id)
                        .where(GroupMembership.user_id == user.id)).all()
    comments = db.scalars(select(EventComment).where(EventComment.user_id == user.id)).all()
    loot = db.scalars(select(LootEvent).where(LootEvent.user_id == user.id)).all()
    return {
        "user": {"email": user.email, "display_name": user.display_name, "created_at": user.created_at},
        "groups": [{"name": g, "role": r, "joined_at": j} for g, r, j in groups],
        "characters": [{"name": c.name, "realm": c.realm_name, "region": c.region, "class": c.character_class,
                        "verification": c.verification} for c in chars],
        "comments": [{"event_id": str(c.event_id), "body": c.body, "created_at": c.created_at} for c in comments],
        "loot": [{"item": li.item_name, "quality": li.quality, "obtained_at": li.obtained_at} for li in loot],
        "event_participations": db.scalar(select(func.count(EventParticipant.id))
                                          .where(EventParticipant.user_id == user.id)),
    }


@me_router.delete("", status_code=204)
def delete_account(body: DeleteAccountIn, response: Response, user: CurrentUser, db: DB):
    """Delete the account and all personal data. Owned groups pass to the longest-standing admin/member,
    or are deleted when the owner is the last member."""
    if not user.is_demo and (not body.password or not verify_password(body.password, user.password_hash)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Password confirmation failed")
    for m in db.scalars(select(GroupMembership).where(GroupMembership.user_id == user.id,
                                                      GroupMembership.role == "owner")).all():
        heir = db.scalar(select(GroupMembership).where(GroupMembership.group_id == m.group_id,
                                                       GroupMembership.user_id != user.id)
                         .order_by(GroupMembership.role != "admin", GroupMembership.joined_at))
        if heir:
            heir.role = "owner"
        else:
            db.delete(db.get(Group, m.group_id))
    db.delete(user)
    db.commit()
    response.delete_cookie(get_settings().session_cookie_name, path="/")


@me_router.get("/tokens", response_model=list[ApiTokenOut])
def list_tokens(user: CurrentUser, db: DB):
    return db.scalars(select(ApiToken).where(ApiToken.user_id == user.id).order_by(ApiToken.created_at.desc())).all()


@me_router.post("/tokens", status_code=201)
def create_token(body: ApiTokenIn, user: CurrentUser, db: DB):
    raw = new_token("act_", 24)
    tok = ApiToken(id=uuid.uuid4(), user_id=user.id, name=body.name, token_prefix=raw[:10],
                   token_hash=hash_token(raw))
    db.add(tok)
    db.commit()
    return {"token": raw, "info": ApiTokenOut.model_validate(tok),
            "note": "Copy this token now; it will not be shown again."}


@me_router.delete("/tokens/{token_id}", status_code=204)
def revoke_token(token_id: uuid.UUID, user: CurrentUser, db: DB):
    tok = db.get(ApiToken, token_id)
    if not tok or tok.user_id != user.id:
        raise HTTPException(404, "Token not found")
    tok.revoked_at = datetime.now(UTC)
    db.commit()
