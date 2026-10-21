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
- **The API** needs no new mount: it reads the libraries through Jellyfin, and asks the worker for the `cover.jpg` it writes, the files of Ranger it places and the scans.

## Database and upgrades
The database is one SQLite file, `shelfdrop.db`, in `SHELFDROP_DATA_DIR` (`/data/shelfdrop` in the image), in WAL mode. It holds the caches (the answers of the metadata sources and of Prowlarr, the works found), the trackers and the filters, and the settings with their sealed secrets and their audit. Deleting it loses the settings too; the secrets cannot be read without `SHELFDROP_SECRET_KEY`.

`docker compose --env-file .env -f docker/compose.yaml exec api shelfdrop db check` compares the database with the models of the image.

An upgrade is a new image: `up -d --build --wait` applies its migrations at start. A database migrated by a newer image stops an older one (`Can't locate revision`): go back to the newer image.

## Reverse proxy
The API serves the pages and the API on one port. The proxy in front of it:
- terminates TLS and sets HSTS;
- forwards every path to the port of the API;
- is the address of `SHELFDROP_PROXY_ADDRESS`, whose `X-Forwarded-For` uvicorn trusts (`FORWARDED_ALLOW_IPS`).
