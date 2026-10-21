# Installation

## Image
`docker/api.Dockerfile` builds `shelfdrop-api:local` from the repository root: the front-end (Node 24, pnpm), then the Python environment from `uv.lock`, then an image on `python:3.13-slim-trixie` that runs as the user `shelfdrop` (uid 10001). The plain Docker builder builds it: no BuildKit mount.

At each start the container applies the pending migrations (`shelfdrop db upgrade`), then serves on port 8000 with uvicorn (`--no-server-header`).

## Compose
`docker/compose.yaml` holds one service, `api`, with `restart: unless-stopped`, a healthcheck on `/health`, the named volume `data` on `/data/shelfdrop` and its port on the loopback alone (`127.0.0.1:${SHELFDROP_API_PORT:-8000}`). Every command runs from the repository root:

```bash
docker compose --env-file .env -f docker/compose.yaml up -d --build --wait
docker compose --env-file .env -f docker/compose.yaml logs -f api
docker compose --env-file .env -f docker/compose.yaml down
```

`down --volumes` also deletes the database.

The `.env` file sets `SHELFDROP_CONTACT` and `SHELFDROP_SECRET_KEY` (mode 600: it holds the key of the secrets); the other settings are changed on the settings page ([configuration](configuration.md)).

## Database and upgrades
The database is one SQLite file, `shelfdrop.db`, in `SHELFDROP_DATA_DIR` (`/data/shelfdrop` in the image), in WAL mode. It holds the caches (the answers of the metadata sources and of Prowlarr, the works found), the trackers and the filters, and the settings with their sealed secrets and their audit. Deleting it loses the settings too; the secrets cannot be read without `SHELFDROP_SECRET_KEY`.

`docker compose --env-file .env -f docker/compose.yaml exec api shelfdrop db check` compares the database with the models of the image.

An upgrade is a new image: `up -d --build --wait` applies its migrations at start. A database migrated by a newer image stops an older one (`Can't locate revision`): go back to the newer image.

## Reverse proxy
The API serves the pages and the API on one port. The proxy in front of it:
- terminates TLS and sets HSTS;
- forwards every path to the port of the API;
- is the address of `SHELFDROP_PROXY_ADDRESS`, whose `X-Forwarded-For` uvicorn trusts (`FORWARDED_ALLOW_IPS`).
