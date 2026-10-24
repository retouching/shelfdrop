# 0021. The OpenAPI document of the API
Status: Accepted
Date: 2026-10-24

## Context
Decided by the user on 2026-10-21 (plan section 3 quater): the routes of the page are documented in OpenAPI, at `/api/docs`; a program reaches them with the session or an access token ([ADR 0020](0020-access-tokens.md)). The pages and the API load nothing from another origin, and the API answers carry `Content-Security-Policy: default-src 'none'`. Decided by the user on 2026-10-24: `/api/docs` is the real documentation an OpenAPI tool shows, Swagger UI or ReDoc, and describes the public API alone, the one of the access tokens; nothing of the part of the session.

## Decision
- **The document** is the schema FastAPI builds from the routes and their Pydantic models (`shelfdrop.http.openapi.DocumentedApi.openapi`), with:
  - the security schemes `session` (the cookie `__Host-shelfdrop`) and `token` (`Authorization: Bearer sd_...`);
  - on each operation, `x-access` and its `security`: `public`, `session` (the cookie alone), `read` (the cookie or any token), `write` (the cookie or a token `write`), taken from the guard `build_app()` puts on its router (`DocumentedApi.include`) or the one the route asks for itself;
  - the refusals of its access (`401`, `403`, `429`) and the `422` with the body of every error (`ErrorResponse`, its codes in `ErrorCode`, beside it), instead of the validation error of FastAPI, which the API never answers;
  - examples on the bodies a program sends: a search of releases, a download, a waiting search, a token.
- **The public document** (`shelfdrop.http.openapi.public_document`, `DocumentedApi.public_openapi`): the operations `read` and `write` of the document alone, the schemas they use (followed through their references), the scheme `token` alone, each operation behind it, its refusals told for a token; no route of the session (the sign-in, the settings, the trackers, the filters, the tokens) nor `/health`.
- **Served** to a session or any token (`require_reader`: the document of the token API is for the programs that hold one), out of the document itself:
  - `GET /api/v1/openapi.json`: the public document; the whole one is never served;
  - `GET /api/docs`: Swagger UI on it (`swagger-ui-dist`, its bundle and its CSS built by Vite into `assets/`: the second entry of the front-end, `web/swagger/index.html` and `web/src/docs.ts`), the page `swagger/index.html` of the build read by `shelfdrop.modules.docs.router.docs_router` (`404` without the build). Authorize takes a token, and Try it out sends it as `Authorization: Bearer`: the API then reads the token alone, and a write needs no `Origin` (ADR 0020). The token stays in the page (`persistAuthorization` off), no validator of swagger.io is called.
  - The page has a policy of its own (`DOCS_CONTENT_SECURITY_POLICY` of `SecurityHeadersMiddleware`): `default-src 'none'`, scripts, styles and requests (`connect-src`) from the same origin, images from it or `data:` (the icons of the CSS of Swagger UI), never `unsafe-inline` nor `unsafe-eval`; `Cache-Control: no-store` as the API. The bundle of Swagger UI 5 adds no `<style>`, sets no `style` attribute in text and calls no `eval` (its `Function("return this")` is reached only without `globalThis`); its React sets its styles through the DOM, which the policy lets through.
- **In the repository**: `docs/openapi.json` (every route, for the developers and the test of the accesses) and `docs/openapi.public.json` (the one served), written by `uv run python -m shelfdrop.openapi` from the application built on invented settings; `tests/unit/test_openapi.py` fails when one differs from the application; the integration suite compares the second with the document served and calls every operation of the first as its `x-access` says.

## Rejected alternatives
- ReDoc: it injects `<style>` elements at run time, which the policy of the page refuses without `unsafe-inline`.
- Swagger UI or ReDoc from a CDN, or the page of FastAPI (`docs_url`): scripts from another origin and an inline script, which the policies of the pages and of the API refuse.
- The page of plain HTML, without a script nor a style, that listed the operations: it could not try an operation, and it described the part of the session too.
- The whole document served, to the session alone: it names every route of the administrators, which a program never calls; the public one is what a token needs, and the whole one stays in the repository.
- Serving the public document at a second URL, the whole one staying at `/api/v1/openapi.json`: a second route for a document no client of the API uses.
- `docs/api.md` alone: it describes the contract for a human, the document the shapes for a program; both stay, `api.md` links to the document.

## Consequences
- A change of a route, of a schema or of the version writes `docs/openapi.json` and `docs/openapi.public.json` again in the same commit.
- `swagger-ui-dist` is a dependency of `web/` (its install script, `@scarf/scarf`, never runs: `web/pnpm-workspace.yaml`); its bundle, about 1.5 MB, is loaded by `/api/docs` alone. A new version of it is read again for inline styles and `eval` before it is taken.
- The pages and `/api/docs` share `assets/` of the build; `/swagger/index.html` is not served at the top of the site (`web_router` serves the files at the top of the build alone).
