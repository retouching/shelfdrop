# An MCP client

What a program (an agent, an assistant, a script) needs to call shelfdrop through its MCP server ([ADR 0022](adr/0022-mcp-server.md)). The arguments and the answers of each tool: [API](api.md#mcp-server).

## The token
An administrator creates it on the page Paramètres, API et MCP: a name (the author of what the client does, shown in the downloads and the journal), the rights (**Lecture**, or **Lecture et téléchargement** for a client that sends releases and places files) and a duration. The secret (`sd_...`) is shown once: keep it in the secret store or the environment of the client, never in a file of the repository nor in a log.

## The entry of the client
The MCP server is at `/mcp` of the address of the pages, on the transport Streamable HTTP, with the token in the header `Authorization`. The keys depend on the client; an example, with `shelfdrop.example.com` standing for the address of your installation:

```yaml
shelfdrop:
  url: https://shelfdrop.example.com/mcp
  headers:
    Authorization: "Bearer ${SHELFDROP_MCP_TOKEN}"
  # search_releases waits for the search of Prowlarr (60 seconds at most a name, two names at
  # a time): more than the 30 seconds many clients wait by default.
  timeout: 180
  connect_timeout: 30
```

- **Timeout**: 180 seconds at least for a call; a call of `search_releases` holds its request until the search ends. A proxy in front of shelfdrop needs a read timeout as long ([installation](installation.md#reverse-proxy)).
- **Connect timeout**: a few seconds to 30, as for any HTTP request.

## The first call
Once the client lists the seven tools of `shelfdrop`, a call of `list_downloads` checks the token:
- an answer: the token is accepted;
- `401`: the token is missing, unknown, revoked or expired (the answer never says which);
- `429`: more than 60 requests in a minute with that token;
- a tool that writes refused (`token_forbidden`): the token has the rights **Lecture** alone.

## The tools
| Tool | Rights | What it does |
|---|---|---|
| `search_works` | read | Finds a work in the metadata sources: its names in each language, the ones to search, its authors, its volumes and its name on the shelf (`kind` `manga`, `ebook` or `audiobook`). |
| `search_releases` | read | Searches Prowlarr and waits for the releases, ranked and scored as on the page: under the names of a work (`mode` `work`, 6 at most), or one text as typed (`mode` `manual`). |
| `grab_releases` | write | Sends releases of a search to qBittorrent, each with its volumes; for a search of a work, with the work, the author and the series that give its place on the shelf. Sent under the name of the token. |
| `list_downloads` | read | The downloads, the newest first: state, percent, speed, time left, and where each was shelved. |
| `retry_download` | write | Sends again a download qBittorrent did not receive, the same torrent with the same settings. |
| `list_files_to_place` | read | The files of Ranger: manual downloads, files sent, downloads the placement left, files misplaced. |
| `place_file` | write | Links a file of Ranger to a work and shelves it (a volume, chapters, the volumes of a release in chapters), or ignores it. |

The usual path: `search_works`, then `search_releases` with the names of the work, then `grab_releases` with the releases chosen, then `list_downloads`. A text that finds no work goes to a manual search; its downloads wait in Ranger (`list_files_to_place`, then `place_file`). The server asks its client, in its instructions, to propose the releases before sending any: nothing is downloaded without the agreement of the person the client works for.
