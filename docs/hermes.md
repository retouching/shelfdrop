# Hermes on the MCP server

What Hermes, the agent of the user, needs to call shelfdrop through its MCP server ([ADR 0022](adr/0022-mcp-server.md)) instead of the scripts it runs today. Nothing here is applied by the repository: the configuration of Hermes changes at the deployment, once the user agreed (plan section 11, « Retrait de Shelfarr »).

## The token
Created by the user on the page Paramètres, API et MCP: name `Hermes`, rights **Lecture et téléchargement** (`write`: Hermes sends releases and places files), duration **Sans expiration** or **1 an**. The secret (`sd_...`) is shown once; it goes to `~/.hermes/.env` (mode 600), never in `config.yaml`:

```bash
SHELFDROP_MCP_TOKEN=sd_...
```

## The entry of `~/.hermes/config.yaml`
Under `mcp_servers`, next to the existing servers. Hermes resolves `${VAR}` in `url` and `headers` from its environment, `~/.hermes/.env` included:

```yaml
mcp_servers:
  shelfdrop:
    url: https://shelfdrop.maigo.party/mcp
    headers:
      Authorization: "Bearer ${SHELFDROP_MCP_TOKEN}"
    # search_releases waits for the search of Prowlarr (60 seconds a name stuck, two names at
    # a time): more than the 30 seconds by default.
    timeout: 180
    connect_timeout: 30
```

The URL depends on the way chosen at the deployment ([installation](installation.md#the-mcp-server-and-the-access-tokens)): `https://shelfdrop.maigo.party/mcp` through Cloudflare, or `http://10.66.0.2:8485/mcp` through WireGuard when Hermes runs on the proxy machine. Then Hermes is restarted (or its MCP connections reloaded) and lists the seven tools of `shelfdrop`; a first call of `list_downloads` checks the token (a `401` is a token refused or missing, a `429` more than 60 requests in a minute).

## What replaces the scripts
The rules of the user stay the same: Hermes proposes the releases and sends nothing without his agreement (the `--yes` of the scripts becomes « call `grab_releases` only after the agreement »).

| Today (skill `arr-stack`) | With shelfdrop |
|---|---|
| `shelfarr.py search` | `search_works` (`kind` `ebook` or `audiobook`): the work, its French name, its authors |
| `shelfarr.py request` then `results` | `search_releases` (`mode` `work`, the names of the work checked by default, 6 at most): the releases ranked and scored, the automatic ones marked |
| `shelfarr.py grab <id> <result> --yes` | `grab_releases` with the id of the search, the releases, `work_id`, `author`, `series` and the volumes of each release: the author and the series give the place on the shelf (no `Unknown Author/`) |
| `shelfarr.py list` | `list_downloads`: state, percent, speed, time left, destination once placed |
| `shelfarr.py retry` | `retry_download` (a torrent qBittorrent did not receive) |
| `manga_grab.py "<Série>"` (one release a volume, Nyaa > TOS > ABN > C411, then `--yes`) | `search_works` (`manga`) then `search_releases`; the releases come ranked by score, then the order of the trackers of the settings, then the seeds: Hermes proposes, for each volume, the first release that covers it (a pack first when one covers the whole), then `grab_releases` with the volumes of each |
| `releases.qui_add(url, kind)` for a release named by the user | `search_releases` with `mode` `manual` and the exact name, then `grab_releases`: a manual download waits in Ranger, `list_files_to_place` then `place_file` (volume, chapters, or the volumes of a release in chapters) |
| the cron `library_place.py`, its rules `state/library_place.json`, `comics_cover.py`, `audiobook_merge.py` | the placement worker of shelfdrop, from the author, the series and the volumes given at the send: nothing to write before a send |

Kept outside shelfdrop: the cross-seed of qui, the searches of anime and films (the other *arr), and what the plan leaves aside (the watch of new volumes, the waiting searches through MCP).

## At the deployment
In the same change as the removal of Shelfarr (plan section 11), on the side of Hermes, once the user agreed:
- `SHELFDROP_MCP_TOKEN` added to `~/.hermes/.env`, the entry `shelfdrop` to `mcp_servers`;
- `SHELFARR_*` removed from `~/.hermes/.env`; `scripts/shelfarr.py`, `scripts/manga_grab.py` and `references/shelfarr.md` of the skill `arr-stack` archived; the skill updated to the table above, its rule of agreement kept;
- the cron of `library_place.py` stopped once the downloads it still waits for are placed (shelfdrop leaves aside what carries the tag `placé`, and the other way round).
