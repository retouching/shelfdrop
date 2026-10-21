# 0013. Sign-in with Jellyfin, sessions in a cookie
Status: Accepted
Date: 2026-10-21

## Context
Decided by the user on 2026-10-21 (plan section 5): shelfdrop is for the administrators of Jellyfin alone, without accounts of its own. Credentials are never kept nor logged; a refusal never says what is missing. The API is reached through Cloudflare from anywhere: every route but the sign-in, the liveness probe and the pages needs a session, and the writes must come from the pages themselves.

## Decision
- `POST /api/v1/session` sends the name and the password to `POST /Users/AuthenticateByName` of Jellyfin (its address is the setting `jellyfin.url`), with a device id drawn for this sign-in. The account must have `Policy.IsAdministrator` and not `Policy.IsDisabled`; otherwise the session Jellyfin opened is closed at once (`POST /Sessions/Logout`) and the answer is the same `401 login_refused` as for wrong credentials.
- A session is a random token of 256 bits (`secrets.token_urlsafe(32)`) in the cookie `__Host-shelfdrop` (`Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/`, 30 days). The table `sessions` keeps its SHA-256 alone, the account, and the access token of Jellyfin, sealed under the fingerprint of the session ([ADR 0012](0012-settings-and-secrets.md)).
- `shelfdrop.http.dependencies.require_session`, on every router but the one of the session: a session Jellyfin confirmed less than 5 minutes ago is taken; otherwise `GET /Users/Me` with its access token must give the same account, still an administrator. A token Jellyfin refuses, or an account no longer administrator, ends the session; a Jellyfin that does not answer refuses the request and keeps the session for later.
- `shelfdrop.http.middleware.origin.OriginMiddleware`: a write under the prefix of the API (`POST`, `PUT`, `PATCH`, `DELETE`) needs an `Origin` that names the host of the request, otherwise `403 origin_refused`.
- `shelfdrop.auth.throttle.LoginThrottle`, in memory: 5 attempts a minute from one address (`request.client.host`, as uvicorn resolves it behind the proxy), 30 an hour in all; past them `429 too_many_attempts`, and Jellyfin is not asked.
- A sign-out removes the session and closes the one of Jellyfin.

## Rejected alternatives
- The API key of Jellyfin to check an account again (`GET /Users/{id}`): nobody could sign in before the key is set on the page, and a session would outlive its revocation in Jellyfin.
- A token signed by shelfdrop (JWT) instead of a row: it cannot be revoked before it expires.
- A CSRF token: the cookie is `SameSite=Strict` and every write checks its `Origin`.

## Consequences
- Jellyfin down: nobody signs in, and a session older than 5 minutes waits for it.
- A restart forgets the attempts counted; the sessions survive it.
- Over plain HTTP outside localhost, a browser keeps no `Secure` cookie: the API is served behind TLS.
