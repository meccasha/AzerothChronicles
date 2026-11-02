"""Development/test Battle.net adapter.

It is the *live* adapter wired to an in-process httpx transport that serves Battle.net-shaped JSON
fixtures (app/integrations/blizzard/fixtures). Every byte of parsing logic is shared with live mode.
All mock characters/achievements are fictional and prefixed "Mock:" where shown to users.
"""

import json
import re
from pathlib import Path
from urllib.parse import urlencode

import httpx

from app.config import Settings, get_settings
from app.integrations.blizzard.live import LiveBlizzardAdapter, _RateLimiter

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> httpx.Response:
    path = FIXTURES / f"{name}.json"
    if not path.exists():
        return httpx.Response(404, json={"code": 404, "type": "BLZWEBAPI00000404", "detail": "Not Found"})
    return httpx.Response(200, json=json.loads(path.read_text()))


def fixture_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if request.url.host == "oauth.battle.net":
        if path == "/token":
            return httpx.Response(200, json={"access_token": "mock-access-token", "token_type": "bearer",
                                             "expires_in": 86399, "scope": "openid wow.profile"})
        if path == "/userinfo":
            return httpx.Response(200, json={"sub": "100001", "id": 100001, "battletag": "MockHero#1234"})
    if path == "/profile/user/wow":
        return _fixture("account_profile")
    if m := re.fullmatch(r"/profile/wow/character/([^/]+)/([^/]+)(/[a-z\-]+)?", path):
        _realm, name, sub = m.groups()
        prefix = {None: "character", "/achievements": "achievements", "/character-media": "media"}.get(sub)
        return _fixture(f"{prefix}_{name}") if prefix else _fixture("missing")
    if m := re.fullmatch(r"/data/wow/achievement/(\d+)", path):
        return _fixture(f"achievement_{m.group(1)}")
    if m := re.fullmatch(r"/data/wow/item/(\d+)", path):
        return _fixture(f"item_{m.group(1)}")
    if m := re.fullmatch(r"/data/wow/media/item/(\d+)", path):
        return _fixture(f"item_media_{m.group(1)}")
    return _fixture("missing")


class MockBlizzardAdapter(LiveBlizzardAdapter):
    mode = "mock"

    def __init__(self, handler=fixture_handler, settings: Settings | None = None):
        base = settings or get_settings()
        mock_settings = base.model_copy(update={"blizzard_client_id": "mock", "blizzard_client_secret": "mock"})
        super().__init__(mock_settings, client=httpx.Client(transport=httpx.MockTransport(handler)))
        self._app_tokens = {}
        self._cache = {}
        self._limiter = _RateLimiter(per_second=1e9)

    def authorize_url(self, *, state: str, redirect_uri: str, region: str) -> str:
        # Points at the backend's mock consent page instead of Battle.net.
        return f"{self.settings.public_api_url}/integrations/blizzard/mock-authorize?" + urlencode(
            {"state": state, "redirect_uri": redirect_uri})
