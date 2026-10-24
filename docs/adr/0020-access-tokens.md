# 0020. Access tokens of the API
Status: Accepted
Date: 2026-10-22

## Context
Decided on 2026-10-21: a program (an agent, a script) reaches the API and the MCP server with an access token, created from the page Paramètres › API et MCP. A token has a name, a scope (**Lecture**, or **Lecture et téléchargement**) and a lifetime (30 days, 90 days, a year, or without end); it is shown once, the database keeps its SHA-256 alone; its last use is shown and it is revoked at once. A token never reads nor changes the settings, and never makes another token: those stay with the session of an administrator of Jellyfin. 60 requests a minute for each token.

## Decision
- **The token** (`shelfdrop/tokens/`, `TokenService`): `sd_` and 32 random bytes in base64url, given once in the answer of `POST /api/v1/tokens`. The table `api_tokens` keeps its name, the SHA-256 of the secret (unique), its scope (`read` or `write`), who created it and when, its expiry, its last use (written again once a minute at most) and its revocation. A token revoked stays in the table, out of the list; one expired stays in the list, refused.
- **The header**: `Authorization: Bearer <secret>`. A request that carries it is judged by its token alone, the cookie never read (`shelfdrop/http/dependencies.py`). A token refused, whatever is wrong with it (unknown, expired, revoked, another scheme), gets the `401 not_signed_in` of a request without a session; the 61st request of a minute gets `429 too_many_requests` (`TokenThrottle`, in memory: one process).
- **What a token reaches** (`build_app()`):
  - the settings, the trackers, the filters, the tokens, the logs ([ADR 0023](0023-logs.md)) and the session: never (`require_session`, `403 token_forbidden`), even with a cookie next to the token;
  - the searches of releases, the torrent of a release, and the public OpenAPI document and its page (`require_reader`, [ADR 0021](0021-openapi.md)): every token, a search reads;
  - the works, the downloads, the page Jellyfin, the waiting searches, Ranger and the uploads (`require_access`): every token for a `GET`, a `write` token for a write, else `403 token_forbidden`.
- **The origin**: a write with an `Authorization` header needs no `Origin` (`OriginMiddleware`): no page of another site can set that header without CORS, which the API never grants, and the cookie is then not read; a write with the cookie alone still needs the `Origin` of its host (ADR 0013).
- **The author**: what a token does is done under its name (`Account(user_id="token:<id>", username=<name>)`): the downloads it sends, the journal.
- **The audit**: the creation and the revocation of a token (`created`, `revoked`, target `token.<id>`, the account of the session), never its secret.

## Rejected alternatives
- Keeping the secret sealed (AES-GCM) to show it again: a token shown twice is a token copied twice; the SHA-256 suffices to check a random secret of 256 bits.
- A token that reads the settings: they hold the addresses of the services, and the page that changes them is the one place of the administrators.
- A per-route scope list: three groups of routers say it in one place (`build_app()`), and a new router has to pick one.
- The `401` telling an expired token from a revoked one: a refusal never says what is wrong ([ADR 0013](0013-sign-in-and-sessions.md)).

## Consequences
- A restart forgets the counts of the minute (`TokenThrottle` in memory, as `LoginThrottle`).
- The secret cannot be found again: a token lost is revoked and another made.
