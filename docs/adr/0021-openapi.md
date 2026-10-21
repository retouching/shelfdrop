# 0021. The OpenAPI document of the API
Status: Accepted
Date: 2026-10-22

## Context
Decided by the user on 2026-10-21 (plan section 3 quater): the routes of the page are documented in OpenAPI, at `/api/docs`, for the sessions of the administrators; a program reaches them with the session or an access token ([ADR 0020](0020-access-tokens.md)). The pages and the API load nothing from another origin, and the API answers carry `Content-Security-Policy: default-src 'none'`.

## Decision
- **The document** is the schema FastAPI builds from the routes and their Pydantic models (`shelfdrop.http.openapi.DocumentedApi.openapi`), with:
  - the security schemes `session` (the cookie `__Host-shelfdrop`) and `token` (`Authorization: Bearer`);
  - on each operation, `x-access` and its `security`: `public`, `session` (the cookie alone), `read` (the cookie or any token), `write` (the cookie or a token `write`), taken from the guard `build_app()` puts on its router (`DocumentedApi.include`) or the one the route asks for itself;
  - the refusals of its access (`401`, `403`, `429`) and the `422` with the body of every error (`ErrorResponse`, its codes listed), instead of the validation error of FastAPI, which the API never answers;
  - examples on the bodies a program sends: a search of releases, a download, a waiting search, a token.
- **Served** to the session alone (`require_session`), out of the document itself: `GET /api/v1/openapi.json` and `GET /api/docs`, a page of plain HTML (each operation, its access, its parameters, its body and its answers, then the schemas), without a script nor a style, under the policy of the API.
- **In the repository**: `docs/openapi.json`, written by `uv run python -m shelfdrop.openapi` from the application built on invented settings; `tests/unit/test_openapi.py` fails when it differs from the application, and the integration suite compares it with the document served.

## Rejected alternatives
- Swagger UI or ReDoc: their pages load scripts and styles, inline or from a CDN, which the policy of the API refuses; bundling them would add a front-end of its own for a page of reference.
- The document open to every token: it names every route of the administrators; a program reads `docs/openapi.json` or asks the session that created its token.
- `docs/api.md` alone: it describes the contract for a human, the document the shapes for a program; both stay, `api.md` links to the document.

## Consequences
- A change of a route, of a schema or of the version writes `docs/openapi.json` again in the same commit.
