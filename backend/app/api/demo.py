from fastapi import APIRouter, HTTPException, Response

from app.api.auth import start_session
from app.config import get_settings
from app.deps import DB
from app.schemas.api import UserOut
from app.services.demo_seed import demo_viewer

router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/status")
def demo_status(db: DB):
    enabled = get_settings().demo_mode
    return {"enabled": enabled, "available": enabled and demo_viewer(db) is not None}


@router.post("/login", response_model=UserOut)
def demo_login(response: Response, db: DB):
    """Sign in as the fictional demo member 'Mira Vale' (only when DEMO_MODE=true)."""
    if not get_settings().demo_mode:
        raise HTTPException(404, "Demo mode is disabled")
    user = demo_viewer(db)
    if user is None:
        raise HTTPException(503, "Demo data has not been seeded. Run: python -m app.cli seed-demo")
    start_session(db, response, user)
    return user
