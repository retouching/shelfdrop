# 0010. Integration tests: a throwaway stack and fake sources
Status: Accepted
Date: 2026-10-24

## Context
Decided on 2026-10-21: integration tests against the real image, cut in parts, before the work goes on. The unit tests prove the rules on the code in-process; they cannot prove the image, its migrations, its headers, its logs nor the search through HTTP. The real metadata sources cannot be the ones tested against: they go down (AniList, MyAnimeList on the day of the recording), they change their answers, and a test must not depend on the network.

## Decision
- `tests/integration/` starts one Compose stack per pytest session, `shelfdrop-test-<random>`, from `docker/compose.yaml` and `docker/compose.test.yaml`, talks to it over HTTP, runs commands in its container, reads its logs, and runs `down --volumes` at the end.
- The sources are played by `fake-sources`, a WireMock by digest, on a network with no way out, loaded with the exchanges recorded from the real sources (`tests/unit/works/fixtures/`). Two settings reserved for the test stack (`shelfdrop.config.TEST_STACK_SETTINGS`), which a `.env` file never sets: `SHELFDROP_SOURCES_ORIGIN` sends every request of the metadata clients to the fake, its first origin in a header; `SHELFDROP_SOURCE_REST_SECONDS=0` keeps a failed source from being skipped.
- Real torrent clients are tested in the stack too, their images pinned, on the volume of the placement worker, with no peer to find ([ADR 0025](0025-torrent-clients.md)): Deluge (`deluge`, the block `torrent_deluge`), Transmission (`transmission`, the block `torrent_transmission`), and qBittorrent under a profile of its own that its module of tests alone starts and removes (`qbittorrent`: the block `torrent_qbittorrent`, its account set by a file of `docker/`). The other blocks keep qBittorrent played by WireMock, behind qui.
- A list of several torrents of qBittorrent (`hashes=<a>|<b>`), which one stub cannot answer (F33), goes from WireMock to `qbittorrent-lists`, a script of the suite run by the image of the API, which asks WireMock for each hash and joins the torrents.
- The suite is cut in parts and blocks, pytest markers declared in `pyproject.toml` and pinned by `tests/unit/test_integration_parts.py`; an agent runs the blocks a change calls for, at its end; the whole suite runs on the request of the owner alone. The hook before a push runs the unit tests alone.

## Rejected alternatives
- The real sources: down or changed answers fail the suite for reasons outside the code.
- Mocking the sources inside the process: it would not test the image nor the requests it sends.
- An HTTPS proxy in front of the real addresses: a certificate authority to forge, for the same coverage as a changed origin.

## Consequences
- A new source, or a changed request of a source, records its fixtures again before its integration tests can pass.
