# 0014. Downloads sent to qBittorrent, verified by their hash
Status: Accepted
Date: 2026-10-21

## Context
Decided on 2026-10-21: the releases chosen on the Automatic page are downloaded with their author, their series and their volumes, to be placed alone later; those of the Manual page are placed by hand, in Ranger. Sends to qBittorrent have been lost before (accepted, then never there): a send counts only once qBittorrent lists its torrent, looked for by its hash 3 times, 8 seconds apart. A torrent qBittorrent already has is a duplicate, with no button; a torrent not received can be sent again, the same one with the same settings, and another release of the same work searched. The page follows the downloads by hand or live (every 2, 5, 10 or 30 seconds), with the speed and the time left of qBittorrent. A release under the minimum score, or from a tracker not allowed for the automatic downloads, is never taken in automatic.

## Decision
- `POST /api/v1/downloads` takes releases of a search kept, by their id, with their volumes, and the work, the author and the series. The search decides the mode: a search of a work gives automatic downloads (category of qBittorrent `manga`, `ebook` or `audiobook`, the kind), a manual search manual ones (`shelfdrop-manual`, no work, no author, no series). An automatic download takes only releases `automatic` ([ADR 0011](0011-release-search.md)): otherwise `422 release_not_automatic`, and nothing is sent. Each release is a row of `downloads`, with the account of the session.
- The send runs after the answer, in `shelfdrop.downloads.sender.DownloadSender` (a singleton, in memory, 2 sends at a time): the torrent through Prowlarr (`ProwlarrClient.torrent`), its id (`shelfdrop.utils.torrent`: the SHA-1 of its `info`, the SHA-256 cut to 20 bytes for BitTorrent v2, or the hash of its magnet link); qBittorrent already lists it and shelfdrop never added it: `duplicate`. Otherwise `POST /api/v2/torrents/add` into its category, then `GET /api/v2/torrents/info?hashes=` 3 times, `SHELFDROP_SEND_CHECK_SECONDS` apart (8 seconds; the test stack alone sets another): found, `sent`; never found, or refused, or no torrent from Prowlarr: `not_received`.
- The torrent read (the `.torrent` file or the magnet link) is kept with its download: a retry (`POST /api/v1/downloads/{id}/retry`, a `not_received` alone) sends it again as it is, into the same category, one more attempt; a torrent an earlier attempt added and qBittorrent lists now is `sent`, not a duplicate. The download link is kept without the key of Prowlarr.
- `GET /api/v1/downloads` reads the 200 newest downloads and asks qBittorrent, in one request, for those sent: downloading (`downloading`, `forcedDL`, `stalledDL`) with its percent, speed and time left; waiting for any other state, or when qBittorrent does not list it or does not answer; a torrent complete is `completed` from then on and qBittorrent is not asked for it again: an automatic one waits for its placement (`placing`), a manual one is to place in Ranger (`to_place`).
- A send left `sending` by a stop is sent again at start (the lifespan).

## Rejected alternatives
- The grab of Prowlarr (`POST /api/v1/search` with `guid` and `indexerId`): Prowlarr sends the release to a download client of its own, without the category of shelfdrop nor its id.
- The send in the request: 22 volumes, each looked for during up to 16 seconds, outlast the request (and the timeout of a reverse proxy, often 100 seconds).
- The infohash Prowlarr gives (`infoHash`): many trackers give none, and the torrent sent must be the one looked for.
- Asking qBittorrent each torrent apart: one request for every download sent.

## Consequences
- The state of a download shown comes from qBittorrent at each read: a torrent removed from qBittorrent before its end shows as waiting.
- A download of the automatic mode complete shows as `placing`: nothing places it yet.
- A search is kept 10 minutes after its end: a download of an older search is refused (`404 search_not_found`).
