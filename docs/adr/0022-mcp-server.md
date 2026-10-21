# 0022. The MCP server
Status: Accepted
Date: 2026-10-22

## Context
Decided by the user on 2026-10-21 (plan section 3 quater): a server MCP at `/mcp`, on the transport Streamable HTTP, with the official MCP SDK for Python mounted in the application, the same access token as the API in `Bearer`, and the tools `search_works`, `search_releases` (reading), `grab_releases`, `retry_download`, `place_file` (download) and `list_downloads`, `list_files_to_place` (reading). The tools go through the services of the page: the same rules, the same shared queue of Prowlarr, the same events of the journal, the name of the token as their author. 60 requests a minute for each token. Hermes reaches it to propose releases, and sends nothing without the agreement of the user.

## Decision
- **The server** (`shelfdrop/modules/mcp/router.py`, `new_mcp_server`): an `MCPServer` of the SDK `mcp` 2.x, its seven tools typed by the schemas of the API (`WorkSearchRead`, `ReleaseSearchRead`, `DownloadsRead`, `ItemsRead`...), their answers structured; each tool opens a scope of the container of its own (`shelfdrop.http.dependencies.scope_of`), since a call runs in the task group of the MCP server and not in the one of its request, and closes its database session in the threadpool. `search_releases` starts the search on the shared board and waits for its end. A refusal of a service is a tool error whose text starts with the code of the API (`search_not_found: ...`).
- **The transport**: Streamable HTTP at `/mcp` exactly, stateless (no `Mcp-Session-Id`, nothing kept between two requests) with JSON answers (no event stream): each request of the client is one HTTP request, answered at once, and a proxy needs nothing for a stream. The session manager of the SDK runs in the lifespan of the API.
- **The token** (`shelfdrop/http/middleware/mcp.py`, `McpMiddleware`): each request to `/mcp` needs `Authorization: Bearer <secret>`, checked by `TokenService.check` as for the API ([ADR 0020](0020-access-tokens.md)): counted (60 a minute), its last use written; without one, or one refused, `401 not_signed_in` with `WWW-Authenticate: Bearer`; past the limit, `429 too_many_requests`. The session cookie is never read there. The token goes in the scope of the request for the tools: `grab_releases`, `retry_download` and `place_file` refuse a token of reading (`token_forbidden`).
- **The host**: the protection of the SDK against DNS rebinding (on by default for a server on 127.0.0.1) is off: the host of shelfdrop is its public name, and a page of another site cannot send the token, which is what the server asks for.
- **The headers**: `/mcp` gets those of the API (`Cache-Control: no-store`, `Content-Security-Policy: default-src 'none'`).

## Rejected alternatives
- The auth of the SDK (`token_verifier`, `AuthSettings`): it describes an OAuth resource server (issuer, metadata) shelfdrop is not; a token of the page is checked by the code that checks it for the API.
- A stateful transport with event streams: Hermes calls one tool at a time and waits for its answer; sessions in memory would be lost at each restart, and a stream needs `proxy_buffering off` on every proxy.
- The session cookie on `/mcp`: a client of MCP is a program, it holds a token; the cookie would make `/mcp` a target of the pages of other sites.
- Tools for the waiting searches, the settings or the tokens: not in the plan; the settings and the tokens stay with the session of an administrator.

## Consequences
- A tool call that waits on Prowlarr (`search_releases`) holds its HTTP request for the time of the search (60 seconds at most for a name stuck): the proxy in front of `/mcp` waits that long ([installation](../installation.md#the-mcp-server-and-the-access-tokens)).
