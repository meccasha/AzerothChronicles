import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.deps import DB, ROLE_RANK, Access, CurrentUser
from app.models import Character, Group, GroupInvite, GroupItemRule, GroupMembership, User
from app.schemas.api import (
    AddMemberIn,
    CharacterOut,
    GroupIn,
    GroupOut,
    GroupPatch,
    InviteIn,
    InviteOut,
    InvitePreview,
    ItemRuleIn,
    ItemRuleOut,
    MemberOut,
    RoleIn,
    UserBrief,
)
from app.services.group_settings import GroupSettings, merge_settings

router = APIRouter(prefix="/groups", tags=["groups"])
invite_router = APIRouter(prefix="/invites", tags=["invites"])


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80] or "group"


def _group_out(db, g: Group, role: str | None) -> GroupOut:
    out = GroupOut.model_validate(g)
    out.my_role = role
    out.member_count = db.scalar(select(func.count(GroupMembership.id)).where(GroupMembership.group_id == g.id))
    out.settings = GroupSettings.model_validate(g.settings or {}).model_dump()
    return out


@router.get("", response_model=list[GroupOut])
def my_groups(user: CurrentUser, db: DB):
    rows = db.execute(select(Group, GroupMembership.role).join(GroupMembership, GroupMembership.group_id == Group.id)
                      .where(GroupMembership.user_id == user.id).order_by(Group.is_demo, Group.name)).all()
    return [_group_out(db, g, r) for g, r in rows]


@router.post("", response_model=GroupOut, status_code=201)
def create_group(body: GroupIn, user: CurrentUser, db: DB):
    if user.is_demo:
        raise HTTPException(403, "The demo account cannot create groups; register a free account instead.")
    slug = _slugify(body.name)
    if db.scalar(select(Group.id).where((func.lower(Group.name) == body.name.lower()) | (Group.slug == slug))):
        raise HTTPException(status.HTTP_409_CONFLICT, "A group with this name already exists")
    g = Group(id=uuid.uuid4(), name=body.name.strip(), slug=slug, description=body.description,
              banner_url=body.banner_url, created_by_user_id=user.id, settings=GroupSettings().model_dump())
    db.add(g)
    db.flush()
    db.add(GroupMembership(id=uuid.uuid4(), group_id=g.id, user_id=user.id, role="owner",
                           joined_at=datetime.now(UTC)))
    db.commit()
    return _group_out(db, g, "owner")


@router.get("/{group_id}", response_model=GroupOut)
def get_group(access: Access, db: DB):
    return _group_out(db, access.group, access.membership.role)


@router.patch("/{group_id}", response_model=GroupOut)
def update_group(body: GroupPatch, access: Access, db: DB):
    access.require("admin")
    g = access.group
    if body.name is not None and body.name != g.name:
        if db.scalar(select(Group.id).where(func.lower(Group.name) == body.name.lower(), Group.id != g.id)):
            raise HTTPException(409, "A group with this name already exists")
        g.name = body.name
    if body.description is not None:
        g.description = body.description
    if "banner_url" in body.model_fields_set:
        g.banner_url = body.banner_url
    if body.visibility is not None:
        g.visibility = body.visibility
    if body.settings is not None:
        try:
            g.settings = merge_settings(g.settings, body.settings).model_dump()
        except ValueError as exc:
            raise HTTPException(422, f"Invalid settings: {exc}") from exc
    db.commit()
    return _group_out(db, g, access.membership.role)


@router.delete("/{group_id}", status_code=204)
def delete_group(access: Access, db: DB):
    access.require("owner")
    db.delete(access.group)
    db.commit()


# ----------------------------------------------------------------------------- members
@router.get("/{group_id}/members", response_model=list[MemberOut])
def list_members(access: Access, db: DB):
    rows = db.execute(select(GroupMembership, User).join(User, User.id == GroupMembership.user_id)
                      .where(GroupMembership.group_id == access.group.id).order_by(GroupMembership.joined_at)).all()
    chars = db.scalars(select(Character).where(Character.owner_user_id.in_([u.id for _, u in rows]))
                       .order_by(Character.is_main.desc(), Character.level.desc().nulls_last(), Character.name)).all()
    by_user: dict[uuid.UUID, list] = {}
    for c in chars:
        by_user.setdefault(c.owner_user_id, []).append(CharacterOut.model_validate(c))
    return [MemberOut(user=UserBrief.model_validate(u), role=m.role, joined_at=m.joined_at,
                      characters=by_user.get(u.id, [])) for m, u in rows]


@router.post("/{group_id}/members", response_model=MemberOut, status_code=201)
def add_member(body: AddMemberIn, access: Access, db: DB):
    """Admins can add an already-registered friend directly by email."""
    access.require("admin")
    user = db.scalar(select(User).where(func.lower(User.email) == body.email.lower(), User.is_demo.is_(False)))
    if user is None:
        raise HTTPException(404, "No registered user with that email. Send them an invite link instead.")
    m = GroupMembership(id=uuid.uuid4(), group_id=access.group.id, user_id=user.id, role="member",
                        joined_at=datetime.now(UTC))
    db.add(m)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Already a member") from exc
    return MemberOut(user=UserBrief.model_validate(user), role="member", joined_at=m.joined_at)


@router.patch("/{group_id}/members/{user_id}", status_code=204)
def change_role(user_id: uuid.UUID, body: RoleIn, access: Access, db: DB):
    access.require("admin")
    target = db.scalar(select(GroupMembership).where(GroupMembership.group_id == access.group.id,
                                                     GroupMembership.user_id == user_id))
    if target is None:
        raise HTTPException(404, "Member not found")
    if body.role == "owner":
        access.require("owner")
        access.membership.role = "admin"  # ownership transfer
    elif ROLE_RANK[target.role] >= ROLE_RANK[access.membership.role] and target.user_id != access.user.id:
        raise HTTPException(403, "You cannot change the role of someone at or above your rank")
    if target.role == "owner" and body.role != "owner":
        raise HTTPException(400, "Transfer ownership to another member first")
    target.role = body.role
    db.commit()


@router.delete("/{group_id}/members/{user_id}", status_code=204)
def remove_member(user_id: uuid.UUID, access: Access, db: DB):
    target = db.scalar(select(GroupMembership).where(GroupMembership.group_id == access.group.id,
                                                     GroupMembership.user_id == user_id))
    if target is None:
        raise HTTPException(404, "Member not found")
    if user_id != access.user.id:
        access.require("admin")
        if ROLE_RANK[target.role] >= ROLE_RANK[access.membership.role]:
            raise HTTPException(403, "You cannot remove someone at or above your rank")
    if target.role == "owner":
        raise HTTPException(400, "The owner must transfer ownership (or delete the group) before leaving")
    db.delete(target)
    db.commit()


# ----------------------------------------------------------------------------- invites
def _invite_out(i: GroupInvite) -> InviteOut:
    out = InviteOut.model_validate(i)
    out.url = f"{get_settings().public_web_url}/invite/{i.code}"
    return out


@router.get("/{group_id}/invites", response_model=list[InviteOut])
def list_invites(access: Access, db: DB):
    access.require("admin")
    rows = db.scalars(select(GroupInvite).where(GroupInvite.group_id == access.group.id)
                      .order_by(GroupInvite.created_at.desc())).all()
    return [_invite_out(i) for i in rows]


@router.post("/{group_id}/invites", response_model=InviteOut, status_code=201)
def create_invite(body: InviteIn, access: Access, db: DB):
    access.require("admin")
    if access.user.is_demo:
        raise HTTPException(403, "Invites are disabled for the demo account")
    inv = GroupInvite(id=uuid.uuid4(), group_id=access.group.id, code=secrets.token_urlsafe(12),
                      created_by_user_id=access.user.id, role=body.role, max_uses=body.max_uses, uses=0,
                      expires_at=datetime.now(UTC) + timedelta(hours=body.expires_in_hours))
    db.add(inv)
    db.commit()
    return _invite_out(inv)


@router.delete("/{group_id}/invites/{invite_id}", status_code=204)
def revoke_invite(invite_id: uuid.UUID, access: Access, db: DB):
    access.require("admin")
    inv = db.get(GroupInvite, invite_id)
    if not inv or inv.group_id != access.group.id:
        raise HTTPException(404, "Invite not found")
    inv.revoked_at = datetime.now(UTC)
    db.commit()


def _valid_invite(inv: GroupInvite | None) -> bool:
    return bool(inv and inv.revoked_at is None and inv.expires_at > datetime.now(UTC)
                and (inv.max_uses is None or inv.uses < inv.max_uses))


@invite_router.get("/{code}", response_model=InvitePreview)
def preview_invite(code: str, user: CurrentUser, db: DB):
    inv = db.scalar(select(GroupInvite).where(GroupInvite.code == code))
    if inv is None:
        raise HTTPException(404, "Invite not found")
    g = db.get(Group, inv.group_id)
    preview = g.visibility == "invite_preview"
    count = db.scalar(select(func.count(GroupMembership.id)).where(GroupMembership.group_id == g.id))
    return InvitePreview(group_name=g.name, description=g.description if preview else None,
                         member_count=count if preview else None, expires_at=inv.expires_at,
                         valid=_valid_invite(inv))


@invite_router.post("/{code}/accept")
def accept_invite(code: str, user: CurrentUser, db: DB):
    if user.is_demo:
        raise HTTPException(403, "The demo account cannot join groups")
    inv = db.scalar(select(GroupInvite).where(GroupInvite.code == code).with_for_update())
    if not _valid_invite(inv):
        raise HTTPException(410, "This invite has expired or been revoked")
    existing = db.scalar(select(GroupMembership).where(GroupMembership.group_id == inv.group_id,
                                                       GroupMembership.user_id == user.id))
    if existing is None:
        db.add(GroupMembership(id=uuid.uuid4(), group_id=inv.group_id, user_id=user.id, role=inv.role,
                               joined_at=datetime.now(UTC)))
        inv.uses += 1
    db.commit()
    return {"group_id": str(inv.group_id)}


# ----------------------------------------------------------------------------- item rules
@router.get("/{group_id}/item-rules", response_model=list[ItemRuleOut])
def list_item_rules(access: Access, db: DB):
    return db.scalars(select(GroupItemRule).where(GroupItemRule.group_id == access.group.id)
                      .order_by(GroupItemRule.item_name)).all()


@router.post("/{group_id}/item-rules", response_model=ItemRuleOut, status_code=201)
def upsert_item_rule(body: ItemRuleIn, access: Access, db: DB):
    access.require("admin")
    rule = db.scalar(select(GroupItemRule).where(GroupItemRule.group_id == access.group.id,
                                                 GroupItemRule.item_id == body.item_id))
    if rule is None:
        rule = GroupItemRule(id=uuid.uuid4(), group_id=access.group.id, **body.model_dump())
        db.add(rule)
    else:
        for k, v in body.model_dump().items():
            setattr(rule, k, v)
    db.commit()
    return rule


@router.delete("/{group_id}/item-rules/{rule_id}", status_code=204)
def delete_item_rule(rule_id: uuid.UUID, access: Access, db: DB):
    access.require("admin")
    rule = db.get(GroupItemRule, rule_id)
    if not rule or rule.group_id != access.group.id:
        raise HTTPException(404, "Rule not found")
    db.delete(rule)
    db.commit()
