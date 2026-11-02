"""Azeroth Chronicles API."""

from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import auth, characters, demo, events, groups, ingest, insights, integrations
from app.config import get_settings
from app.db import SessionLocal


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.services.awards.engine import sync_definitions

    try:
        with SessionLocal() as db:
            sync_definitions(db)
            db.commit()
    except Exception as exc:  # DB may not be migrated yet; endpoints will surface the real error
        print(f"[startup] award definitions not synced: {exc}")
    yield

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_EXEMPT_PREFIXES = ("/api/ingest/",)  # token-authenticated uploads from the companion


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Azeroth Chronicles API", version="0.1.0", docs_url="/api/docs",
                  openapi_url="/api/openapi.json", redoc_url=None, lifespan=lifespan)

    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        # CSRF defence for cookie-authenticated requests: browsers cannot send a custom header
        # cross-site without a CORS preflight (which we never grant), and Origin must match.
        has_session = settings.session_cookie_name in request.cookies
        bearer = request.headers.get("authorization", "").lower().startswith("bearer ")
        if request.method in UNSAFE and has_session and not bearer:
            origin = request.headers.get("origin")
            if origin and origin not in settings.allowed_origins:
                return JSONResponse({"detail": "Cross-origin request rejected"}, status_code=403)
            if request.headers.get("x-ac-client") != "web" and not request.url.path.startswith(CSRF_EXEMPT_PREFIXES):
                return JSONResponse({"detail": "Missing X-AC-Client header"}, status_code=403)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    for r in (auth.router, auth.me_router, characters.router, groups.router, groups.invite_router, events.router,
              events.media_router, insights.router, ingest.router, integrations.router, demo.router):
        app.include_router(r, prefix="/api")

    @app.get("/api/health")
    def health():
        return {"ok": True, "demo_mode": settings.demo_mode, "blizzard_adapter": settings.blizzard_adapter,
                "public_web_host": urlparse(settings.public_web_url).netloc}

    return app


app = create_app()
