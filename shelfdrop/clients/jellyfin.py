"""Jellyfin (its REST API): the sign-in of an account, its session, the server and its
libraries.

Every request carries the header `Authorization: MediaBrowser Client=..., Device=...,
DeviceId=..., Version=...`, with `Token=...` once signed in (an access token or an API key).
The password goes in the body of `POST /Users/AuthenticateByName` alone, never in a log.
"""

from typing import Any, Final

import httpx

from shelfdrop.clients.exceptions import ServiceError, ServiceNotConfiguredError
from shelfdrop.clients.types import JellyfinLibrary, JellyfinLogin, JellyfinUser

CLIENT: Final = "shelfdrop"


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
        return [
            JellyfinLibrary(
                name=str(item["Name"]), collection_type=item.get("CollectionType") or None
            )
            for item in body
            if isinstance(item, dict) and item.get("Name")
        ]

    def key_header(self, api_key: str | None) -> str:
        if not api_key:
            raise ServiceNotConfiguredError("no key")
        return authorization(self.version, CLIENT, api_key)

    async def call(
        self,
        method: str,
        url: str | None,
        path: str,
        header: str,
        *,
        json: dict[str, str] | None = None,
    ) -> Any:
        if not url:
            raise ServiceNotConfiguredError("no address")
        try:
            response = await self.http.request(
                method, f"{url.rstrip('/')}{path}", json=json, headers={"Authorization": header}
            )
        except httpx.HTTPError as exc:
            raise ServiceError(type(exc).__name__) from exc
        if response.status_code == 204:
            return None
        if response.status_code != 200:
            raise ServiceError(f"HTTP {response.status_code}", status=response.status_code)
        try:
            return response.json()
        except ValueError as exc:
            raise ServiceError("invalid JSON") from exc
