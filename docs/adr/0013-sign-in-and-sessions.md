# 0013. Sign-in with the internal account or Jellyfin, sessions in a cookie
Status: Accepted
Date: 2026-10-24

## Context
Decided on 2026-10-21: shelfdrop is for the administrators of Jellyfin alone. Decided on 2026-10-24: one account of its own besides them, the internal account, to sign in before Jellyfin is connected (the set-up of the first launch, [ADR 0023](0023-first-launch-setup.md)) and while Jellyfin is down; it stays once Jellyfin is connected. Credentials are never kept nor logged (the internal password is kept as its scrypt alone); a refusal never says what is missing. The API is reached from anywhere, through a reverse proxy: every route but the sign-in, the liveness probe and the pages needs a session, and the writes must come from the pages themselves.

## Decision
- The internal account: one at most, the table `internal_account` (`shelfdrop.accounts`): its name (1 to 64 characters) and the scrypt of its password (`shelfdrop.utils.passwords`: N=2^15, r=8, p=1, a random salt of 16 bytes, the parameters written with the hash, compared in constant time; 10 characters at least). It is created by the first step of the set-up, or from the page Paramètres › Accès (`POST /api/v1/account`) by an installation signed in through Jellyfin; its password changes with the current one given (`PUT /api/v1/account/password`), and every other session of the internal account ends.
- `POST /api/v1/session` takes the internal account when the name typed is its own (without regard to case): its password is checked against its scrypt, Jellyfin is not asked, and a wrong password is the same `401 login_refused`. A Jellyfin account of the same name cannot sign in. Any other name goes to Jellyfin: `POST /api/v1/session` sends the name and the password to `POST /Users/AuthenticateByName` of Jellyfin (its address is the setting `jellyfin.url`), with a device id drawn for this sign-in. The account must have `Policy.IsAdministrator` and not `Policy.IsDisabled`; otherwise the session Jellyfin opened is closed at once (`POST /Sessions/Logout`) and the answer is the same `401 login_refused` as for wrong credentials.
- A session is a random token of 256 bits (`secrets.token_urlsafe(32)`) in the cookie `__Host-shelfdrop` (`Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/`, 30 days). The table `sessions` keeps its SHA-256 alone, the account, and the access token of Jellyfin, sealed under the fingerprint of the session ([ADR 0012](0012-settings-and-secrets.md)); a session of the internal account has the id `internal` (`shelfdrop.auth.types.INTERNAL_USER_ID`) and no token of Jellyfin. What an account does is signed with its name (the downloads, the audit, the journal).
- `shelfdrop.http.dependencies.require_session`, on every router but the one of the session: a session Jellyfin confirmed less than 5 minutes ago is taken; otherwise `GET /Users/Me` with its access token must give the same account, still an administrator. A token Jellyfin refuses, or an account no longer administrator, ends the session; a Jellyfin that does not answer refuses the request and keeps the session for later. A session of the internal account is confirmed when the internal account still has its name.
- `shelfdrop.http.middleware.origin.OriginMiddleware`: a write under the prefix of the API (`POST`, `PUT`, `PATCH`, `DELETE`) needs an `Origin` that names the host of the request, otherwise `403 origin_refused`.
- `shelfdrop.auth.throttle.LoginThrottle`, in memory: 5 attempts a minute from one address (`request.client.host`, as uvicorn resolves it behind the proxy), 30 an hour in all; past them `429 too_many_attempts`, and Jellyfin is not asked.
- A sign-out removes the session and closes the one of Jellyfin (none for the internal account).

## Rejected alternatives
- The API key of Jellyfin to check an account again (`GET /Users/{id}`): nobody could sign in before the key is set on the page, and a session would outlive its revocation in Jellyfin.
- A token signed by shelfdrop (JWT) instead of a row: it cannot be revoked before it expires.
- A CSRF token: the cookie is `SameSite=Strict` and every write checks its `Origin`.
- Several internal accounts, or roles: one administrator of shelfdrop is enough beside those of Jellyfin.
- The internal account tried after Jellyfin, or Jellyfin after a wrong internal password: one name gives one account, and a wrong password costs one attempt alone.
- bcrypt or Argon2: a dependency; `hashlib.scrypt` is in the standard library.

## Consequences
- Jellyfin down: the administrators of Jellyfin do not sign in, and their sessions older than 5 minutes wait for it; the internal account signs in.
- A restart forgets the attempts counted; the sessions survive it.
- Over plain HTTP outside localhost, a browser keeps no `Secure` cookie: the API is served behind TLS.
