# Configuration

`shelfdrop.config.Settings` reads every setting from the environment (`SHELFDROP_*`) and from a `.env` file in the working directory, when there is one. An invalid value stops the process at start.

| Variable | Default | Meaning |
| --- | --- | --- |
| `SHELFDROP_CONTACT` | required | An address where the operator can be reached, written in the User-Agent of every request to a metadata source, as their usage policies ask. |
| `SHELFDROP_MYANIMELIST_CLIENT_ID` | none | The Client ID of the MyAnimeList API (myanimelist.net/apiconfig), sent in a header. Without it, MyAnimeList is not asked. Never logged nor shown. |
| `SHELFDROP_PROWLARR_URL` | none | The address of Prowlarr (`http://prowlarr:9696`). |
| `SHELFDROP_PROWLARR_API_KEY` | none | The API key of Prowlarr, sent in the header `X-Api-Key`. Without it or the address, no release is searched (`prowlarr_unavailable`). Never logged nor shown. |
| `SHELFDROP_DATA_DIR` | `.data` (`/data/shelfdrop` in the image) | The directory of the database, created at start. |
| `SHELFDROP_STATIC_DIR` | `shelfdrop/static` (`/app/static` in the image) | The built front-end. Without an `index.html` there, no page is served. |
| `SHELFDROP_API_PREFIX` | `/api` | The prefix of every route but `/health` and the pages: one or more `/segment`. |
| `SHELFDROP_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL`. SQLAlchemy, httpx and httpcore never log below `WARNING`. |
| `SHELFDROP_LOG_FORMAT` | `json` | `json` (one object per line) or `text`. |

Read by Compose alone (`docker/compose.yaml`):

| Variable | Default | Meaning |
| --- | --- | --- |
| `SHELFDROP_API_PORT` | `8000` | The loopback port of the API on the machine. |
| `SHELFDROP_PROXY_ADDRESS` | `127.0.0.1` | The address of the reverse proxy, given to uvicorn as `FORWARDED_ALLOW_IPS`. |
