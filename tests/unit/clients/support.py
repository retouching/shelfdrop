"""Jellyfin as the tests play it: an `httpx.MockTransport` handler in the shape of its API
(the OpenAPI document of Jellyfin, `AuthenticationResult` and `UserDto`). No real Jellyfin is
ever asked."""

import base64
import json
import re
from dataclasses import dataclass, field
from email.parser import BytesParser
from email.policy import HTTP
from typing import Any, Final

import httpx

from shelfdrop.utils.torrent import magnet_id, torrent_id

URL: Final = "http://jellyfin.test"
API_KEY: Final = "jellyfin-api-key"
ADMIN_ID: Final = "admin-of-the-api-key"
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
    items: dict[str, dict[str, Any]] = field(default_factory=dict)
    """Every item (a `BaseItemDto`) by id, with the id of its library in `ParentId`."""
    images: dict[str, bytes] = field(default_factory=dict)
    files: dict[str, bytes] = field(default_factory=dict)
    """The file of a book or an audiobook (`/Items/{id}/Download`), by id; `Range: bytes=0-0`
    gets its first byte and its size (`206`, `Content-Range`), as `PhysicalFile` sends it."""
    refreshed: list[tuple[str, dict[str, str]]] = field(default_factory=list)
    """The items refreshed (`/Library/Refresh`: `library`) and the parameters of each."""
    refresh_fails: bool = False
    """`POST /Items/{id}/Refresh` answers `500`."""
    administrator: bool = True
    """`GET /Users` lists, after the accounts, the administrator `ADMIN_ID`."""

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
        if path == "/Users":
            users = [account[1] for account in self.accounts.values()]
            if self.administrator:
                users.append(user_dto(ADMIN_ID, "Admin", admin=True))
            return httpx.Response(200, json=users, request=request)
        return self.library(request)

    def library(self, request: httpx.Request) -> httpx.Response:
        """The items of the libraries, their images and their scans."""
        path = request.url.path
        params = dict(request.url.params)
        if path == "/Library/Refresh":
            self.refreshed.append(("library", params))
            return httpx.Response(204, request=request)
        if path == "/Items":
            types = params.get("includeItemTypes", "").split(",")
            found = [
                item
                for item in self.items.values()
                if item.get("LibraryId") == params.get("parentId") and item.get("Type") in types
            ]
            return httpx.Response(200, json={"Items": found}, request=request)
        found_path = re.fullmatch(r"/Items/([^/]+)(/Images/Primary|/Refresh|/Download)?", path)
        if found_path is None or found_path.group(1) not in self.items:
            return httpx.Response(404, request=request)
        item_id, rest = found_path.group(1), found_path.group(2)
        if rest == "/Download":
            return self.download(request, item_id)
        if rest == "/Refresh":
            if self.refresh_fails:
                return httpx.Response(500, request=request)
            self.refreshed.append((item_id, params))
            return httpx.Response(204, request=request)
        if rest == "/Images/Primary":
            if request.method == "POST":
                self.images[item_id] = base64.b64decode(request.content)
                # A new image, a new tag (the path of the item and the date of the image).
                self.items[item_id]["ImageTags"] = {"Primary": f"tag-{len(self.requests)}"}
                return httpx.Response(204, request=request)
            if item_id not in self.images:
                return httpx.Response(404, request=request)
            return httpx.Response(
                200,
                content=self.images[item_id],
                headers={"Content-Type": "image/jpeg"},
                request=request,
            )
        if request.method == "POST":
            self.items[item_id] = {**json.loads(request.content), "Id": item_id}
            return httpx.Response(204, request=request)
        if not params.get("userId"):
            # Jellyfin 12 with an API key: "Guid can't be empty" (F26).
            return httpx.Response(400, request=request)
        return httpx.Response(200, json=self.items[item_id], request=request)

    def download(self, request: httpx.Request, item_id: str) -> httpx.Response:
        if item_id not in self.files:
            return httpx.Response(404, request=request)
        data = self.files[item_id]
        name = self.items[item_id].get("Path", "").rsplit("/", 1)[-1]
        headers = {
            "Content-Type": "application/octet-stream",
            "Content-Disposition": f'attachment; filename="{name}"',
        }
        if request.headers.get("Range") == "bytes=0-0":
            headers["Content-Range"] = f"bytes 0-0/{len(data)}"
            return httpx.Response(206, content=data[:1], headers=headers, request=request)
        return httpx.Response(200, content=data, headers=headers, request=request)

    def paths(self) -> list[str]:
        return [request.url.path for request in self.requests]


@dataclass
class FakeQui:
    """qBittorrent behind the client proxy of qui: `/proxy/<key>/api/v2/...` (the
    documentation of qui and the WebUI API of qBittorrent 5.0); another key gets a 401.

    `torrents`: what `torrents/info` lists, by hash. A torrent added is listed once `lost` adds
    have been lost (accepted, then never listed: the trap of the lost sends), with the state
    `added_as`; `refuse` answers `Fails.` to every add."""

    KEY = "qui-client-key"
    categories: list[str] = field(default_factory=list)
    requests: list[httpx.Request] = field(default_factory=list)
    torrents: dict[str, dict[str, Any]] = field(default_factory=dict)
    added: list[dict[str, bytes]] = field(default_factory=list)
    lost: int = 0
    refuse: bool = False
    down: bool = False
    added_as: dict[str, Any] = field(
        default_factory=lambda: {"state": "downloading", "progress": 0.0, "dlspeed": 0, "eta": 0}
    )

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.down:
            return httpx.Response(502, request=request)
        prefix = f"/proxy/{self.KEY}"
        if request.url.path == f"{prefix}/api/v2/torrents/info":
            wanted = str(request.url.params.get("hashes", "")).split("|")
            body = [t for h, t in self.torrents.items() if h in wanted]
            return httpx.Response(200, json=body, request=request)
        if request.url.path == f"{prefix}/api/v2/torrents/add":
            return self.add(request)
        if request.url.path == f"{prefix}/api/v2/torrents/addTags":
            form = dict(httpx.QueryParams(request.read().decode()))
            for digest in form["hashes"].split("|"):
                if digest in self.torrents:
                    tags = self.torrents[digest].get("tags") or ""
                    self.torrents[digest]["tags"] = ", ".join(x for x in (tags, form["tags"]) if x)
            return httpx.Response(200, request=request)
        return self.answer(request)

    def add(self, request: httpx.Request) -> httpx.Response:
        """Keeps the fields of the multipart body; qBittorrent names the torrent by its id."""
        fields = multipart_fields(request)
        self.added.append(fields)
        if self.refuse:
            return httpx.Response(200, text="Fails.", request=request)
        if self.lost > 0:
            self.lost -= 1
            return httpx.Response(200, text="Ok.", request=request)
        if "torrents" in fields:
            digest = torrent_id(fields["torrents"])
        else:
            digest = magnet_id(fields.get("urls", b"").decode())
        if digest is None:
            return httpx.Response(415, request=request)
        self.torrents[digest] = {
            "hash": digest,
            "name": digest,
            "category": fields.get("category", b"").decode(),
            **self.added_as,
        }
        return httpx.Response(200, text="Ok.", request=request)

    def answer(self, request: httpx.Request) -> httpx.Response:
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


def multipart_fields(request: httpx.Request) -> dict[str, bytes]:
    """The fields of a `multipart/form-data` body, by name."""
    head = f"Content-Type: {request.headers['Content-Type']}\r\n\r\n".encode()
    message = BytesParser(policy=HTTP).parsebytes(head + request.read())
    fields: dict[str, bytes] = {}
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        payload = part.get_payload(decode=True)
        if isinstance(name, str) and isinstance(payload, bytes):
            fields[name] = payload
    return fields


@dataclass
class FakeDiscord:
    """A webhook of Discord (`POST /api/webhooks/<id>/<token>?wait=true`): the messages it took,
    each with its `payload_json` and its file; `limited` answers a 429 that many times, `fails`
    a 500 that many times."""

    WEBHOOK = "https://discord.test/api/webhooks/1/token-of-the-tests"
    messages: list[tuple[dict[str, Any], bytes | None]] = field(default_factory=list)
    requests: list[httpx.Request] = field(default_factory=list)
    limited: int = 0
    fails: int = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.limited > 0:
            self.limited -= 1
            return httpx.Response(429, json={"retry_after": 0.01, "global": False})
        if self.fails > 0:
            self.fails -= 1
            return httpx.Response(500)
        if request.headers["Content-Type"].startswith("multipart/"):
            fields = multipart_fields(request)
            self.messages.append((json.loads(fields["payload_json"]), fields.get("files[0]")))
        else:
            self.messages.append((json.loads(request.content), None))
        return httpx.Response(200, json={"id": str(len(self.messages))})
