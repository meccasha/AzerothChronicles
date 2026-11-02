"""Live Battle.net adapter.

Endpoint shapes follow the official Battle.net documentation (develop.battle.net):
  OAuth:     https://oauth.battle.net/authorize, /token, /userinfo
  API host:  https://{region}.api.blizzard.com   (us, eu, kr, tw)
  Namespaces: profile-{region} (character/account profile), static-{region} (game data)
  Account:   GET /profile/user/wow                                (user token, scope wow.profile)
  Character: GET /profile/wow/character/{realmSlug}/{name}
             GET /profile/wow/character/{realmSlug}/{name}/achievements
             GET /profile/wow/character/{realmSlug}/{name}/character-media
  Game data: GET /data/wow/achievement/{id}, /data/wow/item/{id}, /data/wow/media/item/{id}
Tokens are sent as an Authorization: Bearer header (the access_token query parameter is deprecated).
See docs/blizzard-integration.md for the verification checklist; field access is defensive so that a
changed response shape degrades to a clear error instead of fabricated data.
"""

import threading
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import Settings
from app.integrations.blizzard.types import (
    AccountIdentity,
    AchievementCompletion,
    AchievementInfo,
    BlizzardAuthError,
    BlizzardError,
    BlizzardNotConfigured,
    CharacterAchievements,
    CharacterNotFound,
    CharacterProfile,
    CharacterSummary,
    ItemInfo,
    TokenSet,
)

OAUTH_HOST = "https://oauth.battle.net"
REGIONS = ("us", "eu", "kr", "tw")
MAX_RETRIES = 4


def _api_host(region: str) -> str:
    if region not in REGIONS:
        raise BlizzardError(f"Unsupported region '{region}'")
    return f"https://{region}.api.blizzard.com"


def _ms_to_dt(value: Any) -> datetime | None:
    if isinstance(value, int | float) and value > 0:
        return datetime.fromtimestamp(value / 1000, UTC)
    return None


def _name(obj: Any) -> str | None:
    """Blizzard returns localized names either as a string (with locale param) or a dict of locales."""
    if isinstance(obj, dict):
        n = obj.get("name")
        if isinstance(n, dict):
            return n.get("en_US") or next(iter(n.values()), None)
        return n
    return None


class _RateLimiter:
    """Simple spacing limiter: stays well under the documented 100 req/s ceiling."""

    def __init__(self, per_second: float = 20.0):
        self.interval = 1.0 / per_second
        self.lock = threading.Lock()
        self.next_at = 0.0

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            delay = self.next_at - now
            self.next_at = max(now, self.next_at) + self.interval
        if delay > 0:
            time.sleep(delay)


class LiveBlizzardAdapter:
    mode = "live"
    _limiter = _RateLimiter()
    _app_tokens: dict[str, tuple[str, datetime]] = {}
    _cache: dict[str, tuple[float, Any]] = {}
    CACHE_TTL = 3600.0

    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        if not settings.blizzard_configured:
            raise BlizzardNotConfigured(
                "Battle.net is not configured: set BLIZZARD_CLIENT_ID and BLIZZARD_CLIENT_SECRET."
            )
        self.settings = settings
        self.client = client or httpx.Client(timeout=15.0)

    # ------------------------------------------------------------------ HTTP helpers
    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            self._limiter.wait()
            try:
                resp = self.client.request(method, url, **kwargs)
            except httpx.TransportError as exc:
                last_exc = exc
                time.sleep(min(2**attempt, 8))
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                retry_after = resp.headers.get("retry-after")
                wait = float(retry_after) if retry_after and retry_after.isdigit() else min(2**attempt, 8)
                last_exc = BlizzardError(f"Battle.net returned {resp.status_code}", status=resp.status_code,
                                         retryable=True)
                time.sleep(wait)
                continue
            return resp
        if isinstance(last_exc, BlizzardError):
            raise last_exc
        raise BlizzardError(f"Battle.net unreachable: {last_exc}", retryable=True)

    def _app_token(self, region: str) -> str:
        cached = self._app_tokens.get(region)
        if cached and cached[1] > datetime.now(UTC) + timedelta(minutes=5):
            return cached[0]
        resp = self._request(
            "POST", f"{OAUTH_HOST}/token", data={"grant_type": "client_credentials"},
            auth=(self.settings.blizzard_client_id, self.settings.blizzard_client_secret),
        )
        if resp.status_code != 200:
            raise BlizzardAuthError("Battle.net rejected the client credentials (check client id/secret).",
                                    status=resp.status_code)
        body = resp.json()
        token = body["access_token"]
        self._app_tokens[region] = (token, datetime.now(UTC) + timedelta(seconds=int(body.get("expires_in", 3600))))
        return token

    def _get(self, region: str, path: str, namespace: str, *, token: str | None = None, cache: bool = True) -> Any:
        params = {"namespace": f"{namespace}-{region}", "locale": self.settings.blizzard_locale}
        url = f"{_api_host(region)}{path}?{urlencode(params)}"
        if cache and token is None and url in self._cache and self._cache[url][0] > time.monotonic():
            return self._cache[url][1]
        bearer = token or self._app_token(region)
        resp = self._request("GET", url, headers={"Authorization": f"Bearer {bearer}"})
        if resp.status_code == 404:
            raise CharacterNotFound(
                "Not found on Battle.net (the character may be renamed, transferred, inactive, or hidden).",
                status=404)
        if resp.status_code in (401, 403):
            raise BlizzardAuthError("Battle.net denied access (token expired or permission missing).",
                                    status=resp.status_code)
        if resp.status_code != 200:
            raise BlizzardError(f"Unexpected Battle.net response {resp.status_code}", status=resp.status_code)
        data = resp.json()
        if cache and token is None:
            self._cache[url] = (time.monotonic() + self.CACHE_TTL, data)
        return data

    # ------------------------------------------------------------------ OAuth
    def authorize_url(self, *, state: str, redirect_uri: str, region: str) -> str:
        q = urlencode({"client_id": self.settings.blizzard_client_id, "scope": "openid wow.profile",
                       "state": state, "redirect_uri": redirect_uri, "response_type": "code"})
        return f"{OAUTH_HOST}/authorize?{q}"

    def exchange_code(self, *, code: str, redirect_uri: str, region: str) -> TokenSet:
        resp = self._request(
            "POST", f"{OAUTH_HOST}/token",
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
            auth=(self.settings.blizzard_client_id, self.settings.blizzard_client_secret),
        )
        if resp.status_code != 200:
            raise BlizzardAuthError("Battle.net authorization failed; please try linking again.",
                                    status=resp.status_code)
        body = resp.json()
        return TokenSet(
            access_token=body["access_token"],
            expires_at=datetime.now(UTC) + timedelta(seconds=int(body.get("expires_in", 86400))),
            refresh_token=body.get("refresh_token"),
            scopes=body.get("scope", ""),
        )

    def userinfo(self, *, access_token: str, region: str) -> AccountIdentity:
        resp = self._request("GET", f"{OAUTH_HOST}/userinfo", headers={"Authorization": f"Bearer {access_token}"})
        if resp.status_code != 200:
            raise BlizzardAuthError("Could not read Battle.net account identity.", status=resp.status_code)
        body = resp.json()
        return AccountIdentity(id=str(body.get("id") or body.get("sub")), battletag=body.get("battletag"))

    # ------------------------------------------------------------------ Profile
    def account_characters(self, *, access_token: str, region: str) -> list[CharacterSummary]:
        data = self._get(region, "/profile/user/wow", "profile", token=access_token, cache=False)
        out: list[CharacterSummary] = []
        for account in data.get("wow_accounts", []) or []:
            for c in account.get("characters", []) or []:
                realm = c.get("realm") or {}
                out.append(CharacterSummary(
                    blizzard_id=int(c["id"]), name=c.get("name", "?"), realm_slug=realm.get("slug", ""),
                    realm_name=_name(realm) or realm.get("slug", ""), region=region, level=c.get("level"),
                    character_class=_name(c.get("playable_class")), race=_name(c.get("playable_race")),
                    faction=_name(c.get("faction")),
                ))
        return out

    def character_profile(self, *, region: str, realm_slug: str, name: str) -> CharacterProfile:
        d = self._get(region, f"/profile/wow/character/{realm_slug}/{name.lower()}", "profile", cache=False)
        realm = d.get("realm") or {}
        return CharacterProfile(
            blizzard_id=int(d["id"]), name=d.get("name", name), realm_slug=realm.get("slug", realm_slug),
            realm_name=_name(realm) or realm_slug, region=region, level=d.get("level"),
            character_class=_name(d.get("character_class")), race=_name(d.get("race")),
            faction=_name(d.get("faction")), specialization=_name(d.get("active_spec")),
            achievement_points=d.get("achievement_points"),
        )

    def character_achievements(self, *, region: str, realm_slug: str, name: str) -> CharacterAchievements:
        d = self._get(region, f"/profile/wow/character/{realm_slug}/{name.lower()}/achievements", "profile",
                      cache=False)
        completions = []
        for a in d.get("achievements", []) or []:
            ach = a.get("achievement") or {}
            completed = _ms_to_dt(a.get("completed_timestamp"))
            criteria = a.get("criteria") or {}
            # Entries without a completion timestamp and with incomplete criteria are in-progress.
            if completed is None and criteria and not criteria.get("is_completed", False):
                continue
            completions.append(AchievementCompletion(
                achievement_id=int(a.get("id") or ach.get("id")), name=_name(ach) or "Unknown achievement",
                completed_at=completed))
        return CharacterAchievements(total_points=d.get("total_points"), completions=completions)

    def character_avatar(self, *, region: str, realm_slug: str, name: str) -> str | None:
        try:
            d = self._get(region, f"/profile/wow/character/{realm_slug}/{name.lower()}/character-media", "profile")
        except CharacterNotFound:
            return None
        for asset in d.get("assets", []) or []:
            if asset.get("key") == "avatar":
                return asset.get("value")
        return None

    # ------------------------------------------------------------------ Game data
    def achievement(self, *, region: str, achievement_id: int) -> AchievementInfo:
        d = self._get(region, f"/data/wow/achievement/{achievement_id}", "static")
        return AchievementInfo(id=achievement_id, name=_name(d) or str(achievement_id),
                               description=d.get("description"), points=int(d.get("points") or 0),
                               category=_name(d.get("category")))

    def item(self, *, region: str, item_id: int) -> ItemInfo:
        d = self._get(region, f"/data/wow/item/{item_id}", "static")
        icon = None
        try:
            media = self._get(region, f"/data/wow/media/item/{item_id}", "static")
            icon = next((a.get("value") for a in media.get("assets", []) if a.get("key") == "icon"), None)
        except BlizzardError:
            pass
        quality = ((d.get("quality") or {}).get("type") or "unknown").lower()
        return ItemInfo(id=item_id, name=_name(d) or str(item_id), quality=quality,
                        item_class=_name(d.get("item_class")), item_subclass=_name(d.get("item_subclass")),
                        inventory_type=_name(d.get("inventory_type")), icon_url=icon)
