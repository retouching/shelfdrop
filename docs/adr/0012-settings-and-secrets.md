# 0012. Settings in the database, sealed secrets
Status: Accepted
Date: 2026-10-21

## Context
Decided by the user on 2026-10-21: every setting is changed from the settings page, without a restart: the addresses and the keys of Prowlarr, qBittorrent and Jellyfin, the metadata sources, the search. The `.env` file keeps the bootstrap alone: the key of the secrets and the place of the database. The keys already in a `.env` (taken over from Shelfarr) are imported once. A secret never goes back to the browser, nor to a log, an event or the audit.

## Decision
- The settings live in SQLite: `settings` (a JSON value by key, when and by whom it changed last), `secrets` (a sealed value by key) and `audit` (who changed which setting, and when; never a value). `shelfdrop.settings.catalog` is the one list of their keys, kinds, defaults and bounds.
- A secret is sealed with AES-GCM (`shelfdrop.settings.cipher.SecretBox`): a key of 256 bits derived by HKDF-SHA256 from `SHELFDROP_SECRET_KEY` (32 characters at least), a random nonce of 12 bytes per seal, the name of the secret as associated data. It is opened in memory alone, when a call needs it; a secret that no longer opens (the key changed) reads as unset and is logged by its name.
- The other domains read their settings at each use, through `shelfdrop.settings.reader.SettingsReader` (a singleton on sessions of its own): the address and the key of Prowlarr, the Client ID of MyAnimeList, the sources switched on, the number of names searched and the durations of the caches. They know it through a `Protocol` of their own (`WorkSettings`, `NameLimit`, `AnswerTime`, the `Connection` of `ProwlarrClient`), never by an import.
- At start (the lifespan of the application), `SettingsService.import_environment` imports `SHELFDROP_PROWLARR_URL`, `SHELFDROP_PROWLARR_API_KEY`, `SHELFDROP_JELLYFIN_URL` and `SHELFDROP_MYANIMELIST_CLIENT_ID`: each value the database does not hold yet, once (the keys imported are kept under `settings.imported`); a value cleared on the page later is not imported again, a value the page set is never overwritten. The audit names the actor `environment`.

- `POST /api/v1/settings/test` tests a service or a source with the values typed, before they are saved (`shelfdrop.settings.probes`); `ConnectionMonitor` runs the same tests in the background, at start then every 5 minutes, for the services saved, and logs a failure once. qBittorrent is reached through the client proxy of qui (`<address of qui>/proxy/<key>`): qui signs in to qBittorrent, shelfdrop holds one key.
- Every change of a setting, a secret, the trackers or the filters is audited: who, when, which key; never a value.

## Rejected alternatives
- The settings in the environment: a change needs a restart, and the page could not change them.
- A key of encryption stored next to the database: a copy of the volume would give both.
- Fernet: AES-CBC with HMAC, where AES-GCM gives the same guarantees in one primitive, with the name of the secret bound to its value.

## Consequences
- Losing `SHELFDROP_SECRET_KEY` loses the secrets: they are typed again on the page. The API does not start without it.
- A setting has no variable of its own any more but the four imported; `.env.example` lists the bootstrap.
- The tests of the background forget their results at a restart, and run again at start.
