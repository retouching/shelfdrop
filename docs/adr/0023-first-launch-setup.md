# 0023. The set-up of the first launch
Status: Accepted
Date: 2026-10-24

## Context
Decided on 2026-10-24: a new installation is set up from the pages, step by step, before the rest of the site opens: the internal account first ([ADR 0013](0013-sign-in-and-sessions.md)), then Prowlarr, qBittorrent (qui) and Jellyfin, each with its test, then the libraries and the folder of the uploads. Jellyfin is required: the set-up does not end without it. An installation already set up (signed in through Jellyfin) never sees it.

## Decision
- **The rule** (`shelfdrop.accounts.rules.setup_needed`): without an internal account, the set-up is needed while `jellyfin.url` is not set; with one, while its `setup_finished_at` is empty. An account created from the page Paramètres › Accès is finished at its creation; the one of the first step is not, until the end. So an installation with the address of Jellyfin, saved or imported from `SHELFDROP_JELLYFIN_URL` ([ADR 0012](0012-settings-and-secrets.md)), keeps signing in through Jellyfin, and a set-up started stays open across restarts until its end.
- **The gate**: `shelfdrop.http.middleware.setup.SetupMiddleware`, while the set-up is needed, answers `409 setup_required` to every request of the API and of `/mcp`, but `/api/v1/setup`, `/api/v1/session` and `/api/v1/settings` (the steps save and test through the settings, behind the session); `/health` and the pages stay open. Once the set-up is known finished, `SetupGate` (a container singleton) keeps it in memory: the database is no longer read for it.
- **The steps** (`shelfdrop.modules.setup`): `GET /api/v1/setup` gives `{"needed", "account"}` to anyone. `POST /api/v1/setup/account`, open to anyone while the set-up is needed and no account exists, creates the internal account and opens its session; the account is one row of key 1, so the first request wins and the next gets `409 account_exists`; once the set-up is not needed, `409 setup_done`. The services, the libraries and the folder of the uploads are saved by `PUT /api/v1/settings` and tested by `POST /api/v1/settings/test`, as on the page Paramètres: what is saved is the progress, and a set-up taken again starts at the first service without an address. `POST /api/v1/setup/finish`, with the session, tests the Jellyfin saved (`ConnectionProbes`, its address and its key): connected, the set-up ends; otherwise `409 jellyfin_not_connected`.
- **The page** (`web/src/components/SetupPanel.tsx`): while the set-up is needed, it shows the panel alone: the account (or the sign-in, once the account exists), then one step at a time, Précédent to go back; the step Jellyfin goes on only once its test passes; Terminer opens the site.

## Rejected alternatives
- A flag of the settings set at the end: an installation set up before it would see the panel, unless a revision guessed it from the settings.
- Steps of their own to save the services: they would copy the settings and their tests.
- The set-up skipped without Jellyfin: nobody would sign in through Jellyfin, and the libraries are read there.

## Consequences
- A new installation is reached by anyone until the first step is done: the account is created at the first launch, before the site is published.
- An installation without an internal account whose address of Jellyfin is cleared sees the set-up again (nobody could sign in there).
- The access tokens, the MCP server and the document of the API wait for the end of the set-up.
