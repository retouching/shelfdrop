"""Jellyfin as the tests play it: an `httpx.MockTransport` handler in the shape of its API
(the OpenAPI document of Jellyfin, `AuthenticationResult` and `UserDto`). No real Jellyfin is
ever asked."""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Final

import httpx

URL: Final = "http://jellyfin.test"
API_KEY: Final = "jellyfin-api-key"
TOKEN_FIELD: Final = re.compile(r'Token="([^"]+)"')


def user_dto(user_id: str, name: str, *, admin: bool, disabled: bool = False) -> dict[str, Any]:
    return {
        "Name": name,
        "Id": user_id,
        "HasPassword": True,
        "Policy": {
            "IsAdministrator": admin,
            "IsDisabled": disabled,
            "SyncPlayAccess": "CreateAndJoinGroups",
        },
    }


@dataclass
class FakeJellyfin:
    """Accounts by name: (password, UserDto). An access token is given at each sign-in; a
    token signed out, or `revoked`, is refused."""

    accounts: dict[str, tuple[str, dict[str, Any]]] = field(default_factory=dict)
    tokens: dict[str, str] = field(default_factory=dict)
    requests: list[httpx.Request] = field(default_factory=list)
    down: bool = False
    libraries: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.down:
            return httpx.Response(503, request=request)
        header = request.headers.get("Authorization", "")
        found = TOKEN_FIELD.search(header)
        token = found.group(1) if found else None
        path = request.url.path
        if path == "/Users/AuthenticateByName":
            body = json.loads(request.content)
            account = self.accounts.get(body["Username"])
            if account is None or account[0] != body["Pw"]:
                return httpx.Response(401, request=request)
            token = f"token-{len(self.tokens) + 1}"
            self.tokens[token] = body["Username"]
            return httpx.Response(
                200,
                json={"User": account[1], "AccessToken": token, "ServerId": "s1"},
                request=request,
            )
        if path == "/Users/Me":
            name = self.tokens.get(token or "")
            if name is None:
                return httpx.Response(401, request=request)
            return httpx.Response(200, json=self.accounts[name][1], request=request)
        if path == "/Sessions/Logout":
            self.tokens.pop(token or "", None)
            return httpx.Response(204, request=request)
        if token != API_KEY:
            return httpx.Response(401, request=request)
        if path == "/System/Info":
            return httpx.Response(200, json={"Version": "10.11.2", "ServerName": "nami"})
        if path == "/Library/VirtualFolders":
            return httpx.Response(200, json=self.libraries, request=request)
        return httpx.Response(404, request=request)

    def paths(self) -> list[str]:
        return [request.url.path for request in self.requests]


@dataclass
class FakeQui:
    """qBittorrent behind the client proxy of qui: `/proxy/<key>/api/v2/...` (the
    documentation of qui and the WebUI API of qBittorrent 5.0); another key gets a 401."""

    KEY = "qui-client-key"
    categories: list[str] = field(default_factory=list)
    requests: list[httpx.Request] = field(default_factory=list)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        prefix = f"/proxy/{self.KEY}"
        path = request.url.path
        if not path.startswith(prefix + "/"):
            return httpx.Response(401, request=request)
        path = path.removeprefix(prefix)
        if path == "/api/v2/app/version":
            return httpx.Response(200, text="v5.1.2", request=request)
        if path == "/api/v2/torrents/categories":
            body = {name: {"name": name, "savePath": f"/data/{name}"} for name in self.categories}
            return httpx.Response(200, json=body, request=request)
        return httpx.Response(404, request=request)
