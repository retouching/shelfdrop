# Installation

shelfdrop runs in Docker. What stands around it (a reverse proxy, a tunnel, a firewall) is the choice of each installation: this page says only what shelfdrop expects of it. The paths and the addresses given as examples are examples: use those of your machine.

## Image
`docker/api.Dockerfile` builds `shelfdrop-api:local` from the repository root: the front-end (Node 24, pnpm), then the Python environment from `uv.lock`, then an image on `python:3.13-slim-trixie` with ffmpeg and poppler (the placement worker merges MP3 tracks and reads the first page of a PDF) that runs as the user `shelfdrop` (uid 10001). The plain Docker builder builds it: no BuildKit mount.

At each start the container applies the pending migrations (`shelfdrop db upgrade`), then serves on port 8000 with uvicorn (`--no-server-header`).

## Compose
`docker/compose.yaml` holds two services of the same image, both `restart: unless-stopped`:
- `api`: the pages, the API and the MCP server, a healthcheck on `/health`, the named volume `data` on `/data/shelfdrop` and its port on the loopback alone (`127.0.0.1:${SHELFDROP_API_PORT:-8000}`);
- `placement`: the placement worker (`shelfdrop placement run`, [ADR 0016](adr/0016-placement.md)), the one process that writes in the libraries; started once the API is healthy (the API applies the migrations).

Every command runs from the repository root:

```bash
docker compose --env-file .env -f docker/compose.yaml up -d --build --wait
docker compose --env-file .env -f docker/compose.yaml logs -f api
docker compose --env-file .env -f docker/compose.yaml down
```

`down --volumes` also deletes the database.

## Logs
Both services write their records to stderr, read by `docker compose ... logs`, and to a file of the volume `data`: `logs/api.jsonl` and `logs/placement.jsonl` (`/data/shelfdrop/logs` in the API, `/var/lib/shelfdrop/logs` in the worker), 5 MiB each and two older copies (`.1`, `.2`), 30 MiB at most in all ([ADR 0023](adr/0023-logs.md)). The API reads both for the tab Journaux of the settings: the worker must mount the same volume as the API, as `docker/compose.yaml` does; a worker on another volume leaves its tab empty.

The `.env` file (mode 600: it holds the key of the secrets) sets `SHELFDROP_CONTACT` and `SHELFDROP_SECRET_KEY`, and the variables Compose reads: `SHELFDROP_MEDIA_DIR`, `SHELFDROP_LIBRARY_GID`, `SHELFDROP_API_PORT`, `SHELFDROP_PROXY_ADDRESS`. The other settings are changed on the settings page ([configuration](configuration.md)).

## The first launch
The pages of a new installation open on the set-up ([ADR 0024](adr/0024-first-launch-setup.md)), and the API answers its steps alone (`409 setup_required` to the others):
1. **The internal account**: a name and a password (10 characters at least), the administrator of shelfdrop; its session opens. Anyone who reaches the pages can create it while it does not exist: do this step before the site is published.
2. **Prowlarr**: its address and its API key, and their test.
3. **qBittorrent**: the address of qui and the key of its client proxy, and their test.
4. **Jellyfin**: its address and an API key; its test must pass to go on.
5. **The libraries and the folder of the uploads**: the folders as the placement worker sees them ([the placement worker](#the-placement-worker)).
6. **Terminer**: Jellyfin is tested again, and the site opens.

Each step saves its settings: a set-up stopped and taken again starts at the first service without an address, and Précédent goes back. The settings stay on the settings page afterwards. An installation whose first start had `SHELFDROP_JELLYFIN_URL` skips the set-up: the administrators of Jellyfin sign in, and the internal account is created on the page Paramètres › Accès.

## The placement worker
What the worker needs, on the machine of the libraries:
- **One mount for the torrents and the libraries**: `${SHELFDROP_MEDIA_DIR}:/data` (for example `SHELFDROP_MEDIA_DIR=/srv/media`), with the torrents of qBittorrent in `/data/torrents` (the `content_path` qBittorrent gives must be the path the worker sees: qBittorrent mounts the same folder on `/data`) and the libraries in `/data/files/comics`, `/data/files/ebooks`, `/data/files/audiobooks` (the settings `placement.library.<kind>`). Two mounts would put the torrents and the libraries on two mount points, where a hardlink fails (`EXDEV`).
- **The database of the API under another path**: the volume `data` of the API, mounted on `/var/lib/shelfdrop`, with `SHELFDROP_DATA_DIR=/var/lib/shelfdrop`: nothing is mounted inside the libraries. Both processes open the same SQLite file (WAL), on one machine.
- **The user**: `10001:${SHELFDROP_LIBRARY_GID}`, the group that owns the files of qBittorrent and the libraries (`1000` by default). The kernel lets a process hardlink a file it does not own only when it can read and write it (`fs.protected_hardlinks=1`): the files of qBittorrent must be writable by that group (a umask `002` in qBittorrent), and the folders of the libraries too. The worker writes with the umask `002`: its folders `775`, its files `664`, in the group. Its uid stays 10001, the owner of the database.
- **The environment**: `SHELFDROP_CONTACT`, `SHELFDROP_SECRET_KEY` (the same key as the API), `SHELFDROP_DATA_DIR=/var/lib/shelfdrop`; a network that reaches qBittorrent (or qui), Jellyfin and the metadata sources (the covers of the audiobooks without a picture).
- **The image** holds ffmpeg and ffprobe. The worker runs read-only (`read_only: true`) with a `tmpfs` on `/tmp` (the lists of a merge), `cap_drop: [ALL]`, `no-new-privileges`.
- **The time zone**: the daily scan of the files misplaced runs at `placement.scan_time` in the local time of the worker: `TZ` in its environment (for example `Europe/Paris`; the image must hold the zoneinfo of the zone), else UTC.
- **Jellyfin**: the folders of its libraries have the names of those of the worker (for example `/files/comics` in the container of Jellyfin, `/data/files/comics` in the worker): a library is found by that name, and its items by their path.
- **The folder of the uploads**: the files sent from the page Manuel wait in `uploads.folder` (`/data/envois` by default, [ADR 0019](adr/0019-uploads.md)), on the mount of the libraries but out of them. It must exist, owned by the group of the libraries and group-writable; with the example above (`/srv/media`, the group 1000): `mkdir -p /srv/media/envois && chown 10001:1000 /srv/media/envois && chmod 2775 /srv/media/envois`. Without it, a file sent stays out of Ranger (`lost`).
- **The API** needs no mount of the libraries: it reads them through Jellyfin, and asks the worker for the `cover.jpg` it writes, the files of Ranger it places and the scans.

## The chunks of the uploads
The page sends a file in chunks of 50 MiB ([ADR 0019](adr/0019-uploads.md)). The API writes them, then the whole file put together, in `uploads/<id>/` of its data directory (`/data/shelfdrop/uploads` in the image), the volume of the database; the placement worker reads them there through its own mount of that volume (`/var/lib/shelfdrop/uploads`), moves the file into `uploads.folder`, and removes them. The API never writes them in `/tmp`: it can run read-only (`read_only: true`) with a `tmpfs` on `/tmp`, the volume of `/data/shelfdrop` its one writable place. The volume needs room for the uploads in progress: 5 GiB a file at most, kept 7 days when stopped (`uploads.keep_days`). To keep them off the disk of the volume, mount another folder on `/data/shelfdrop/uploads` of the API and on `/var/lib/shelfdrop/uploads` of the worker (the same folder for both, owned by uid 10001).

## The MCP server and the access tokens
The API serves the MCP server at `/mcp` on its own port ([ADR 0022](adr/0022-mcp-server.md)): no variable, mount nor service of its own. A program reaches the API (`/api/...`) and `/mcp` with `Authorization: Bearer <token>`, a token created on the page Paramètres, Accès; the configuration of a client: [an MCP client](mcp-client.md). The client is a program, not a browser: a challenge page or a cache in front of `/mcp` and `/api/` breaks it.

## Database and upgrades
The database is one SQLite file, `shelfdrop.db`, in `SHELFDROP_DATA_DIR` (`/data/shelfdrop` in the image), in WAL mode. It holds the internal account (the scrypt of its password), the uploads in progress (their chunks next to it, in `uploads/`), the caches (the answers of the metadata sources and of Prowlarr, the works found), the trackers and the filters, and the settings with their sealed secrets and their audit. Deleting it loses the settings too; the secrets cannot be read without `SHELFDROP_SECRET_KEY`.

`docker compose --env-file .env -f docker/compose.yaml exec api shelfdrop db check` compares the database with the models of the image.

An upgrade is a new image: `up -d --build --wait` applies its migrations at start. A database migrated by a newer image stops an older one (`Can't locate revision`): go back to the newer image.

## Reverse proxy
The API serves the pages, the API and the MCP server on one port, bound to the loopback. Whatever proxy stands in front of it, shelfdrop expects:
- **TLS**: the pages served over HTTPS, with HSTS: the session cookie is `__Host-` and `Secure` ([ADR 0013](adr/0013-sign-in-and-sessions.md));
- **One origin**: every path forwarded to the port of the API, the `Host` of the request kept (a write with the session checks that its `Origin` names it) and the header `Authorization` passed as it is;
- **The address of the client**: the proxy sets `X-Forwarded-For`, and its own address is `SHELFDROP_PROXY_ADDRESS`, the one uvicorn trusts (`FORWARDED_ALLOW_IPS`); the limits of the sign-in count by that address;
- **Request bodies**: up to 60 MiB on `PUT /api/v1/uploads/{id}/chunks/{n}` (a chunk of 50 MiB and a little more), passed on without being buffered on the disk of the proxy;
- **Timeouts**: a read timeout of 3 minutes at least on `/mcp` (a call of `search_releases` holds its request until the search of Prowlarr ends: 60 seconds at most a name, the names queued two at a time), and on the event stream of a release search (`GET /api/v1/searches/{id}/events`, Server-Sent Events), passed on without buffering;
- **A limit of requests**, if the proxy has one: room for 60 requests a minute for each token on `/mcp` and `/api/`, the limit shelfdrop applies itself;
- **The country of a sign-in** (optional): a proxy that knows the country of the client sends it as a two-letter code in the header `CF-IPCountry`; the journal names it for a sign-in ([how it works](how-it-works.md#journal)). Without the header, no country is named.
