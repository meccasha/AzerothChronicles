import json
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import ValidationError
from sqlalchemy import func, select

from app.deps import DB, CurrentUser, current_user_or_token
from app.models import Character, GroupMembership, IngestionRecord, User
from app.schemas.ingest import IngestEnvelope, IngestResult
from app.services.ingestion import ingest_envelope
from app.services.lua_savedvariables import LuaParseError, parse_savedvariables, savedvariables_to_envelope

router = APIRouter(prefix="/ingest", tags=["ingestion"])
MAX_BODY = 20 * 1024 * 1024


def _user(request: Request, db: DB) -> User:
    return current_user_or_token(request, db)


def _check_demo(user: User) -> None:
    if user.is_demo:
        raise HTTPException(403, "The demo account is read-only for ingestion; register an account to import data.")


@router.post("/envelope", response_model=IngestResult)
def ingest_json(env: IngestEnvelope, db: DB, user: User = Depends(_user)):
    """Import normalized events (addon JSON export, companion uploads, or simulated events)."""
    _check_demo(user)
    return ingest_envelope(db, user, env)


@router.post("/savedvariables", response_model=IngestResult)
async def ingest_savedvariables(request: Request, db: DB, user: User = Depends(_user)):
    """Upload the raw WTF/Account/<ACCOUNT>/SavedVariables/AzerothChronicles.lua file (text body)."""
    _check_demo(user)
    body = await request.body()
    if len(body) > MAX_BODY:
        raise HTTPException(413, "File too large")
    try:
        text = body.decode("utf-8", errors="replace")
        env = IngestEnvelope.model_validate(savedvariables_to_envelope(parse_savedvariables(text)))
    except LuaParseError as exc:
        raise HTTPException(422, f"Could not read SavedVariables: {exc}") from exc
    except ValidationError as exc:
        raise HTTPException(422, f"SavedVariables content is not in the expected format: {exc.errors()[:3]}") from exc
    return ingest_envelope(db, user, env)


@router.get("/records")
def list_records(user: CurrentUser, db: DB, status: str | None = Query(None, pattern="^(normalized|ignored|rejected)$"),
                 limit: int = Query(50, ge=1, le=200)):
    q = select(IngestionRecord).where(IngestionRecord.user_id == user.id)
    if status:
        q = q.where(IngestionRecord.status == status)
    rows = db.scalars(q.order_by(IngestionRecord.received_at.desc()).limit(limit)).all()
    counts = dict(db.execute(select(IngestionRecord.status, func.count(IngestionRecord.id))
                             .where(IngestionRecord.user_id == user.id).group_by(IngestionRecord.status)).all())
    return {"counts": counts, "items": [
        {"id": str(r.id), "record_type": r.record_type, "status": r.status, "detail": r.status_detail,
         "source": r.source, "received_at": r.received_at, "idempotency_key": r.idempotency_key,
         "payload": r.payload} for r in rows]}


@router.get("/sample")
def sample_envelope(user: CurrentUser, db: DB, group_id: uuid.UUID | None = None):
    """Build a *simulated* envelope for the caller so the pipeline can be exercised without the game.

    Uses the caller's first character (or a placeholder) and real group-mate character names for the
    roster so participation matching can be observed. Clearly marked source="simulated".
    """
    ch = db.scalar(select(Character).where(Character.owner_user_id == user.id).order_by(Character.is_main.desc()))
    roster = []
    if group_id:
        if not db.scalar(select(GroupMembership.id).where(GroupMembership.group_id == group_id,
                                                          GroupMembership.user_id == user.id)):
            raise HTTPException(404, "Group not found")
        mates = db.scalars(select(Character).join(GroupMembership, GroupMembership.user_id == Character.owner_user_id)
                           .where(GroupMembership.group_id == group_id, Character.owner_user_id != user.id).limit(4))
        roster = [{"name": c.name, "realm": c.realm_name} for c in mates]
    guid = (ch.player_guid if ch and ch.player_guid else f"Player-0000-{user.id.hex[:8].upper()}")
    me = {"guid": guid, "name": ch.name if ch else "Simtester", "realm": ch.realm_name if ch else "Simulation",
          "region": ch.region if ch else "us", "class": ch.character_class if ch else "Paladin",
          "race": ch.race if ch else "Human", "faction": ch.faction if ch else "Alliance", "level": 80}
    now = datetime.now(UTC).replace(microsecond=0)
    t = int((now - timedelta(hours=2)).timestamp())
    nonce = uuid.uuid4().hex[:8]
    recs = [
        {"id": f"sim-{nonce}-w1", "type": "encounter", "character_guid": guid, "encounter_id": 990001,
         "encounter_name": "Simulated Sentinel", "instance_name": "Simulation Spire", "instance_type": "raid",
         "difficulty_id": 15, "difficulty_name": "Heroic", "group_size": 10, "success": False, "start_time": t,
         "end_time": t + 240, "roster": roster, "deaths": 1},
        {"id": f"sim-{nonce}-k1", "type": "encounter", "character_guid": guid, "encounter_id": 990001,
         "encounter_name": "Simulated Sentinel", "instance_name": "Simulation Spire", "instance_type": "raid",
         "difficulty_id": 15, "difficulty_name": "Heroic", "group_size": 10, "success": True, "start_time": t + 600,
         "end_time": t + 900, "roster": roster, "deaths": 0},
        {"id": f"sim-{nonce}-l1", "type": "loot", "character_guid": guid, "item_id": 990101,
         "item_name": "Simulated Blade of Testing", "quality": 4, "item_class": "Weapon", "item_subclass": "Sword",
         "item_level": 650, "encounter_id": 990001, "instance_name": "Simulation Spire",
         "difficulty_name": "Heroic", "looted_at": t + 920},
        {"id": f"sim-{nonce}-a1", "type": "achievement", "character_guid": guid, "achievement_id": 990201,
         "name": "Simulated: Sentinel Slayer", "points": 10, "earned_at": t + 905},
    ]
    return {"format": "azeroth-chronicles/v1", "source": "simulated", "addon_version": "simulated",
            "exported_at": int(now.timestamp()), "characters": [me], "records": recs,
            "_note": "Simulated data generated for pipeline testing. Edit freely before importing."}


def envelope_from_text(text: str) -> IngestEnvelope:
    """Accept either JSON (in-game export string) or SavedVariables Lua."""
    text = text.strip()
    if text.startswith("{"):
        return IngestEnvelope.model_validate(json.loads(text))
    return IngestEnvelope.model_validate(savedvariables_to_envelope(parse_savedvariables(text)))
