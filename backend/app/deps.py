"""FastAPI dependencies: authentication and group-scoped authorization."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import ApiToken, Group, GroupMembership, User, UserSession
from app.security import hash_token

DB = Annotated[Session, Depends(get_db)]

ROLE_RANK = {"member": 1, "admin": 2, "owner": 3}


def _user_from_session(request: Request, db: Session) -> User | None:
    raw = request.cookies.get(get_settings().session_cookie_name)
    if not raw:
        return None
    sess = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(raw)))
    if not sess or sess.expires_at < datetime.now(UTC):
        return None
    return db.get(User, sess.user_id)


def _user_from_api_token(request: Request, db: Session) -> User | None:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    token = db.scalar(select(ApiToken).where(ApiToken.token_hash == hash_token(header[7:].strip())))
    if not token or token.revoked_at is not None:
        return None
    token.last_used_at = datetime.now(UTC)
    db.commit()
    return db.get(User, token.user_id)


def current_user(request: Request, db: DB) -> User:
    user = _user_from_session(request, db)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    return user


def current_user_or_token(request: Request, db: DB) -> User:
    """Session cookie or personal API token (used by the companion uploader)."""
    user = _user_from_session(request, db) or _user_from_api_token(request, db)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


@dataclass
class GroupAccess:
    group: Group
    membership: GroupMembership
    user: User

    @property
    def is_admin(self) -> bool:
        return ROLE_RANK[self.membership.role] >= ROLE_RANK["admin"]

    def require(self, role: str) -> None:
        if ROLE_RANK[self.membership.role] < ROLE_RANK[role]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires {role} role in this group")


def group_access(group_id: uuid.UUID, user: CurrentUser, db: DB) -> GroupAccess:
    """Resolve the group *only* if the caller is a member. Non-members get 404 (no existence leak)."""
    row = db.execute(
        select(Group, GroupMembership)
        .join(GroupMembership, GroupMembership.group_id == Group.id)
        .where(Group.id == group_id, GroupMembership.user_id == user.id)
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")
    return GroupAccess(group=row[0], membership=row[1], user=user)


Access = Annotated[GroupAccess, Depends(group_access)]


def member_user_ids(db: Session, group_id: uuid.UUID) -> set[uuid.UUID]:
    return set(db.scalars(select(GroupMembership.user_id).where(GroupMembership.group_id == group_id)))
