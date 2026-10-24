"""Jellyfin (its REST API): the sign-in of an account, its session, the server and its
libraries, their items, their images and their scans.

Every request carries the header `Authorization: MediaBrowser Client=..., Device=...,
DeviceId=..., Version=...`, with `Token=...` once signed in (an access token or an API key).
The password goes in the body of `POST /Users/AuthenticateByName` alone, never in a log.
"""

import base64
from collections.abc import Mapping, Sequence
from typing import Any, Final

import httpx

from shelfdrop.clients.exceptions import ServiceError, ServiceNotConfiguredError
from shelfdrop.clients.types import JellyfinItem, JellyfinLibrary, JellyfinLogin, JellyfinUser

CLIENT: Final = "shelfdrop"
# The fields `GET /Items` adds to each item.
ITEM_FIELDS: Final = "Path,Overview,Genres,People,ProductionYear,OriginalTitle"
# The refresh modes of `POST /Items/{id}/Refresh` for each scan mode: the new and changed files,
# the missing metadata, everything replaced.
REFRESH_MODES: Final[Mapping[str, dict[str, str]]] = {
    "new": {"metadataRefreshMode": "Default", "imageRefreshMode": "Default"},
    "missing": {
        "metadataRefreshMode": "FullRefresh",
        "imageRefreshMode": "FullRefresh",
        "replaceAllMetadata": "false",
        "replaceAllImages": "false",
    },
    "all": {
        "metadataRefreshMode": "FullRefresh",
        "imageRefreshMode": "FullRefresh",
        "replaceAllMetadata": "true",
        "replaceAllImages": "true",
    },
}


def authorization(version: str, device_id: str, token: str | None) -> str:
    """The `Authorization` header of Jellyfin; the values hold no quote (a version, a hex id,
    a token)."""
    fields = [
        f'Client="{CLIENT}"',
        f'Device="{CLIENT}"',
        f'DeviceId="{device_id}"',
        f'Version="{version}"',
    ]
    if token is not None:
        fields.append(f'Token="{token}"')
    return "MediaBrowser " + ", ".join(fields)


def number(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def item_of(body: object) -> JellyfinItem | None:
    """An item of `GET /Items`, or None without its id."""
    if not isinstance(body, dict) or not body.get("Id"):
        return None
    people = body.get("People")
    images = body.get("ImageTags")
    genres = body.get("Genres")
    return JellyfinItem(
        id=str(body["Id"]),
        type=str(body.get("Type") or ""),
        name=str(body.get("Name") or ""),
        path=str(body.get("Path") or ""),
        overview=str(body.get("Overview") or ""),
        genres=tuple(str(g) for g in genres) if isinstance(genres, list) else (),
        authors=tuple(
            str(p["Name"])
            for p in (people if isinstance(people, list) else [])
            if isinstance(p, dict) and p.get("Type") == "Author" and p.get("Name")
        ),
        year=number(body.get("ProductionYear")),
        original_title=str(body.get("OriginalTitle") or ""),
        has_image=isinstance(images, dict) and bool(images.get("Primary")),
        index_number=number(body.get("IndexNumber")),
    )


def library_of(item: dict[str, Any]) -> JellyfinLibrary:
    locations = item.get("Locations")
    progress = item.get("RefreshProgress")
    running = item.get("RefreshStatus") not in (None, "Idle")
    return JellyfinLibrary(
        name=str(item["Name"]),
        collection_type=item.get("CollectionType") or None,
        item_id=str(item["ItemId"]) if item.get("ItemId") else None,
        locations=tuple(str(x) for x in locations) if isinstance(locations, list) else (),
        refresh_progress=(
            float(progress) if running and isinstance(progress, int | float) else None
        ),
    )


def user_of(body: object) -> JellyfinUser:
    """A `UserDto`. Raises ServiceError when it misses its id or its name."""
    if not isinstance(body, dict) or not body.get("Id") or not body.get("Name"):
        raise ServiceError("unexpected body")
    policy = body.get("Policy")
    return JellyfinUser(
        id=str(body["Id"]),
        name=str(body["Name"]),
        administrator=isinstance(policy, dict) and policy.get("IsAdministrator") is True,
        disabled=isinstance(policy, dict) and policy.get("IsDisabled") is True,
    )


class JellyfinClient:
    def __init__(self, http: httpx.AsyncClient, version: str) -> None:
        self.http = http
        self.version = version

    async def authenticate(
        self, url: str | None, username: str, password: str, device_id: str
    ) -> JellyfinLogin:
        """`POST /Users/AuthenticateByName`. Raises ServiceError (`refused` for wrong
        credentials)."""
        body = await self.call(
            "POST",
            url,
            "/Users/AuthenticateByName",
            authorization(self.version, device_id, None),
            json={"Username": username, "Pw": password},
        )
        if not isinstance(body, dict) or not isinstance(body.get("AccessToken"), str):
            raise ServiceError("unexpected body")
        return JellyfinLogin(user=user_of(body.get("User")), token=body["AccessToken"])

    async def current_user(self, url: str | None, token: str, device_id: str) -> JellyfinUser:
        """`GET /Users/Me` with the access token of a session."""
        body = await self.call(
            "GET", url, "/Users/Me", authorization(self.version, device_id, token)
        )
        return user_of(body)

    async def sign_out(self, url: str | None, token: str, device_id: str) -> None:
        """`POST /Sessions/Logout`: Jellyfin forgets the access token."""
        await self.call(
            "POST", url, "/Sessions/Logout", authorization(self.version, device_id, token)
        )

    async def server_version(self, url: str | None, api_key: str | None) -> str:
        """`GET /System/Info` with an API key: the version of the server."""
        body = await self.call("GET", url, "/System/Info", self.key_header(api_key))
        if not isinstance(body, dict) or not isinstance(body.get("Version"), str):
            raise ServiceError("unexpected body")
        return str(body["Version"])

    async def libraries(self, url: str | None, api_key: str | None) -> list[JellyfinLibrary]:
        """`GET /Library/VirtualFolders` with an API key."""
        body = await self.call("GET", url, "/Library/VirtualFolders", self.key_header(api_key))
        if not isinstance(body, list):
            raise ServiceError("unexpected body")
        return [library_of(item) for item in body if isinstance(item, dict) and item.get("Name")]

    async def items(
        self, url: str | None, api_key: str | None, parent_id: str, types: Sequence[str]
    ) -> list[JellyfinItem]:
        """`GET /Items` of the library `parent_id` and its folders, of the `types` given."""
        body = await self.call(
            "GET",
            url,
            "/Items",
            self.key_header(api_key),
            params={
                "parentId": parent_id,
                "recursive": "true",
                "includeItemTypes": ",".join(types),
                "fields": ITEM_FIELDS,
                "enableImageTypes": "Primary",
            },
        )
        found = body.get("Items") if isinstance(body, dict) else None
        if not isinstance(found, list):
            raise ServiceError("unexpected body")
        return [item for item in (item_of(x) for x in found) if item is not None]

    async def administrator(self, url: str | None, api_key: str | None) -> str:
        """`GET /Users` with an API key: the id of the first administrator not disabled, the user
        `GET /Items/{id}` reads as. Raises ServiceError when there is none."""
        body = await self.call("GET", url, "/Users", self.key_header(api_key))
        if not isinstance(body, list):
            raise ServiceError("unexpected body")
        for entry in body:
            try:
                user = user_of(entry)
            except ServiceError:
                continue
            if user.administrator and not user.disabled:
                return user.id
        raise ServiceError("no administrator")

    async def item(self, url: str | None, api_key: str | None, item_id: str) -> dict[str, Any]:
        """`GET /Items/{id}?userId=`: the whole item, as `POST /Items/{id}` takes it back. With an
        API key, Jellyfin needs the user it reads as (F26): an administrator."""
        user_id = await self.administrator(url, api_key)
        body = await self.call(
            "GET", url, f"/Items/{item_id}", self.key_header(api_key), params={"userId": user_id}
        )
        if not isinstance(body, dict) or not body.get("Id"):
            raise ServiceError("unexpected body")
        return body

    async def update_item(
        self, url: str | None, api_key: str | None, item_id: str, body: dict[str, Any]
    ) -> None:
        """`POST /Items/{id}` with the whole item: the fields it lacks are emptied."""
        await self.call("POST", url, f"/Items/{item_id}", self.key_header(api_key), json=body)

    async def image(
        self, url: str | None, api_key: str | None, item_id: str, max_width: int
    ) -> tuple[bytes, str]:
        """`GET /Items/{id}/Images/Primary`: its bytes and their type."""
        response = await self.send(
            "GET",
            url,
            f"/Items/{item_id}/Images/Primary",
            self.key_header(api_key),
            params={"maxWidth": str(max_width)},
        )
        return response.content, response.headers.get("Content-Type", "image/jpeg")

    async def set_image(
        self, url: str | None, api_key: str | None, item_id: str, data: bytes, content_type: str
    ) -> None:
        """`POST /Items/{id}/Images/Primary`: Jellyfin reads the body in base64."""
        await self.send(
            "POST",
            url,
            f"/Items/{item_id}/Images/Primary",
            self.key_header(api_key),
            content=base64.b64encode(data),
            content_type=content_type,
        )

    async def refresh(self, url: str | None, api_key: str | None, item_id: str, mode: str) -> None:
        """`POST /Items/{id}/Refresh` (a library, a folder or a book, and what it holds) in
        the scan mode `new`, `missing` or `all`."""
        await self.call(
            "POST",
            url,
            f"/Items/{item_id}/Refresh",
            self.key_header(api_key),
            params={"recursive": "true", **REFRESH_MODES[mode]},
        )

    async def refresh_libraries(self, url: str | None, api_key: str | None) -> None:
        """`POST /Library/Refresh`: the scan of every library."""
        await self.call("POST", url, "/Library/Refresh", self.key_header(api_key))

    def key_header(self, api_key: str | None) -> str:
        if not api_key:
            raise ServiceNotConfiguredError("no key")
        return authorization(self.version, CLIENT, api_key)

    async def send(
        self,
        method: str,
        url: str | None,
        path: str,
        header: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        content: bytes | None = None,
        content_type: str | None = None,
    ) -> httpx.Response:
        if not url:
            raise ServiceNotConfiguredError("no address")
        headers = {"Authorization": header}
        if content_type is not None:
            headers["Content-Type"] = content_type
        try:
            response = await self.http.request(
                method,
                f"{url.rstrip('/')}{path}",
                json=json,
                params=params,
                content=content,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise ServiceError(type(exc).__name__) from exc
        if response.status_code not in (200, 204):
            raise ServiceError(f"HTTP {response.status_code}", status=response.status_code)
        return response

    async def call(
        self,
        method: str,
        url: str | None,
        path: str,
        header: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> Any:
        response = await self.send(method, url, path, header, json=json, params=params)
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise ServiceError("invalid JSON") from exc
