# Installation

## Image
`docker/api.Dockerfile` builds `shelfdrop-api:local` from the repository root: the front-end (Node 24, pnpm), then the Python environment from `uv.lock`, then an image on `python:3.13-slim-trixie` with ffmpeg and poppler (the placement worker merges MP3 tracks and reads the first page of a PDF) that runs as the user `shelfdrop` (uid 10001). The plain Docker builder builds it: no BuildKit mount.

At each start the container applies the pending migrations (`shelfdrop db upgrade`), then serves on port 8000 with uvicorn (`--no-server-header`).

## Compose
`docker/compose.yaml` holds two services of the same image, both `restart: unless-stopped`:
- `api`: the pages and the API, a healthcheck on `/health`, the named volume `data` on `/data/shelfdrop` and its port on the loopback alone (`127.0.0.1:${SHELFDROP_API_PORT:-8000}`);
- `placement`: the placement worker (`shelfdrop placement run`, [ADR 0016](adr/0016-placement.md)), the one process that writes in the libraries; started once the API is healthy (the API applies the migrations).

Every command runs from the repository root:

```bash
docker compose --env-file .env -f docker/compose.yaml up -d --build --wait
docker compose --env-file .env -f docker/compose.yaml logs -f api
docker compose --env-file .env -f docker/compose.yaml down
```

`down --volumes` also deletes the database.

The `.env` file sets `SHELFDROP_CONTACT` and `SHELFDROP_SECRET_KEY` (mode 600: it holds the key of the secrets); the other settings are changed on the settings page ([configuration](configuration.md)).

## The placement worker
What the worker needs, on the machine of the libraries (NAMI: `/mnt/storage/data`):
- **One mount for the torrents and the libraries**: `${SHELFDROP_MEDIA_DIR}:/data`, with the torrents of qBittorrent in `/data/torrents` (the `content_path` qBittorrent gives must be the path the worker sees: qBittorrent mounts the same folder on `/data`) and the libraries in `/data/files/comics`, `/data/files/ebooks`, `/data/files/audiobooks` (the settings `placement.library.<kind>`). Two mounts would put the torrents and the libraries on two mount points, where a hardlink fails (`EXDEV`).
- **The database of the API under another path**: the same volume or folder as `/data/shelfdrop` of the API, mounted on `/var/lib/shelfdrop`, with `SHELFDROP_DATA_DIR=/var/lib/shelfdrop`: nothing is mounted inside the libraries. Both processes open the same SQLite file (WAL), on one machine.
- **The user**: `10001:${SHELFDROP_LIBRARY_GID}` (1000, the group of the files of qBittorrent and of the libraries on NAMI). The kernel lets a process hardlink a file it does not own only when it can read and write it (`fs.protected_hardlinks=1`): the files of qBittorrent must be writable by that group (its umask `002`), and the folders of the libraries too. The worker writes with the umask `002`: its folders `775`, its files `664`, in the group. Its uid stays 10001, the owner of the database.
- **The environment**: `SHELFDROP_CONTACT`, `SHELFDROP_SECRET_KEY` (the same key as the API), `SHELFDROP_DATA_DIR=/var/lib/shelfdrop`; the network of qBittorrent (qui), of Jellyfin and of the metadata sources (the covers of the audiobooks without a picture).
- **The image** holds ffmpeg and ffprobe: the worker no longer runs `docker exec jellyfin`. It runs read-only (`read_only: true`) with a `tmpfs` on `/tmp` (the lists of a merge), `cap_drop: [ALL]`, `no-new-privileges`.
- **The time zone**: the daily scan of the files misplaced runs at `placement.scan_time` in the local time of the worker: `TZ` (`Europe/Paris`) in its environment (the image must hold the zoneinfo of the zone), else UTC.
- **Jellyfin**: the folders of its libraries have the names of those of the worker (`/files/comics` there, `/data/files/comics` here): a library is found by that name, and its items by their path.
- **The folder of the uploads**: the files sent from the page Manuel wait in `uploads.folder` (`/data/envois` by default, [ADR 0019](adr/0019-uploads.md)), on the mount of the libraries but out of them (NAMI: `/mnt/storage/data/envois`). It must exist, owned by the group of the libraries and group-writable (`mkdir -p /mnt/storage/data/envois && chown 10001:1000 /mnt/storage/data/envois && chmod 2775 /mnt/storage/data/envois`); without it, a file sent stays out of Ranger (`lost`).
- **The API** needs no new mount: it reads the libraries through Jellyfin, and asks the worker for the `cover.jpg` it writes, the files of Ranger it places and the scans.

## The chunks of the uploads
The page sends a file in chunks of 50 MiB ([ADR 0019](adr/0019-uploads.md)). The API writes them, then the whole file put together, in `uploads/<id>/` of its data directory (`/data/shelfdrop/uploads` in the image), the volume of the database; the placement worker reads them there through its own mount of that volume (`/var/lib/shelfdrop/uploads`), moves the file into `uploads.folder`, and removes them. The API never writes them in `/tmp`: in production the API can run read-only (`read_only: true`) with a `tmpfs` on `/tmp`, and the volume of `/data/shelfdrop` stays its one writable place, as today; no new mount is needed, and the container starts as before. The volume needs room for the uploads in progress: 5 GiB a file at most, kept 7 days when stopped (`uploads.keep_days`). To keep them off the disk of the volume, mount another folder on `/data/shelfdrop/uploads` of the API and on `/var/lib/shelfdrop/uploads` of the worker (the same folder for both, owned by uid 10001).

The proxy in front of the API takes requests of 50 MiB and a little more on `PUT /api/v1/uploads/{id}/chunks/{n}` (nginx: `client_max_body_size 60m` there), and must not buffer them on its disk (`proxy_request_buffering off`).

## The MCP server and the access tokens
The API serves the MCP server at `/mcp` on its own port ([ADR 0022](adr/0022-mcp-server.md)); it needs no new variable, mount nor service, and the container starts with the configuration of today. The table `api_tokens` comes with a migration, applied at start. A program reaches the API (`/api/...`) and `/mcp` with `Authorization: Bearer <token>`, a token created on the page Paramètres, API et MCP.

What the proxy in front of it needs for `/mcp`:
- the same proxy as the pages, the header `Authorization` passed as it is;
- a read timeout of 2 minutes at least (`proxy_read_timeout`): a call of `search_releases` holds its request until the search of Prowlarr ends (60 seconds at most a name, the names queued two at a time). The plan asks for `proxy_buffering off` and 1 hour: harmless, but the answers are single JSON documents (no event stream);
- no cache, no challenge page: the client is a program, not a browser.

Where a program comes from is a choice of the deployment, to make before it; three ways, none of them changes the code:
1. **The public name, through Cloudflare** (`https://shelfdrop.maigo.party/mcp`): the same vhost as the pages. Authenticated Origin Pulls checks Cloudflare towards the proxy, not the client: a token passes it. But the pages of challenge (bocchi) and `limit_req` of the vhost must not apply to `/mcp` nor to the requests with `Authorization: Bearer` (a location `/mcp` without them, and a `limit_req` of its own around 60 a minute, the limit of a token), and Cloudflare must not challenge them (a rule of the WAF that skips `/mcp` and `/api/` with that header, or a bot fight mode off for them).
2. **Another name, without Cloudflare**, on the proxy alone (a vhost `shelfdrop-api` reachable from the machine of the client alone, by IP or by its WireGuard address): no AOP nor challenge there; the client verifies the certificate of `*.maigo.party`.
3. **The tunnel**: a client on the proxy machine (maomao) reaches `http://10.66.0.2:8485/mcp` directly, through WireGuard, without TLS nor Cloudflare; the port stays closed to the LAN (ufw `wg0` from 10.66.0.1 alone).

Default proposed: 1 if the client runs outside maomao, 3 if it runs on maomao; to decide when deploying.

## Database and upgrades
The database is one SQLite file, `shelfdrop.db`, in `SHELFDROP_DATA_DIR` (`/data/shelfdrop` in the image), in WAL mode. It holds the uploads in progress (their chunks next to it, in `uploads/`), the caches (the answers of the metadata sources and of Prowlarr, the works found), the trackers and the filters, and the settings with their sealed secrets and their audit. Deleting it loses the settings too; the secrets cannot be read without `SHELFDROP_SECRET_KEY`.

`docker compose --env-file .env -f docker/compose.yaml exec api shelfdrop db check` compares the database with the models of the image.

An upgrade is a new image: `up -d --build --wait` applies its migrations at start. A database migrated by a newer image stops an older one (`Can't locate revision`): go back to the newer image.

## Reverse proxy
The API serves the pages and the API on one port. The proxy in front of it:
- terminates TLS and sets HSTS;
- forwards every path to the port of the API;
- is the address of `SHELFDROP_PROXY_ADDRESS`, whose `X-Forwarded-For` uvicorn trusts (`FORWARDED_ALLOW_IPS`).
