# Verified facts

Behaviours of the metadata sources, libraries and tools this code relies on. Each fact has an ID (`Fnn`, never reused), its evidence, the test that pins it and a re-verification trigger. A source has no version: its heading names the endpoint, and its facts are re-verified when the fixtures are recorded again (`uv run python -m tests.unit.works.record`) or when a recorded search fails. A library heading names the version of `uv.lock`; a version change updates the heading in the same commit and re-reads the facts no test pins.

Next fact ID: F42.

## Metadata sources

### MangaUpdates (api.mangaupdates.com/v1)

- **F01** `POST /series/search` matches the associated names too, French ones included, and `GET /series/{id}` lists them in `associated` as `{"title"}` alone: no language, some with it in brackets ("Atelier of Witch Hat (Indonesian)"). `shelfdrop.works.clients.mangaupdates` gives them the language `latin` or the one of their script; `shelfdrop.works.names.language_of` tells the language of some after the merge (Turkish, Polish, Indonesian names among them in `atelier-des-sorciers.json`).
  - Evidence: the fixtures `chainsaw-man.json` and `atelier-des-sorciers.json` (recorded 2026-10-21).
  - Pinned by: `tests/unit/works/test_service.py::test_recorded_search`, `tests/unit/works/test_names.py::test_language_of`
  - Re-verify: on recording.

### Kitsu (kitsu.io/api/edge)

- **F02** `GET /manga?include=mappings` returns, in `included`, the ids of the same work at other sites (`externalSite` `myanimelist/manga`, `anilist/manga`...), which merge its candidate with theirs.
  - Evidence: the fixture `chainsaw-man.json`.
  - Pinned by: `tests/unit/works/test_service.py::test_recorded_search`
  - Re-verify: on recording.

### BnF catalogue (catalogue.bnf.fr/api/SRU)

- **F03** `searchRetrieve` with `recordSchema=dublincore` answers one record per volume of a series, its `dc:title` as `<series>. <n> / <authors>` (`Dusk maiden of amnesia. 10 / Maybe`), in catalogue case; editions and boxes add a note in brackets or parentheses, and a fan book is numbered `10.5`.
  - Evidence: the fixtures `dusk-maiden.json`, `chainsaw-man.json`; the answer of `bib.title all "horimiya"` read on 2026-10-21.
  - Pinned by: `tests/unit/works/clients/test_bnf.py::test_bnf_title`
  - Re-verify: on recording.
- **F04** A translated book's record does not give its original title: "Ne cède jamais" (Goggins, *Never Finished*) is found, but nothing ties it to the English work.
  - Evidence: the searches of "Never Finished" and "Ne cède jamais" in the BnF, Open Library and Wikidata on 2026-10-21.
  - Pinned by: none
  - Re-verify: on recording.

- **F13** `bib.title all` matches the title of the French edition alone: "Battle Angel Alita" finds no record of Gunnm, "Gunnm" finds its 9 French volumes.
  - Evidence: the fixture `battle-angel-alita.json` (recorded 2026-10-21 with `--missing`, a few requests to MangaUpdates, Kitsu, MangaDex, Wikidata and the BnF).
  - Pinned by: `tests/unit/works/test_service.py::test_recorded_search`
  - Re-verify: on recording.

### Open Library (openlibrary.org)

- **F05** `search.json` gives, for a work, a few of its editions; the French one is often missing there and found among `/works/{id}/editions.json` (`languages` `/languages/fre`). `shelfdrop.works.clients.openlibrary` reads the editions of its first 3 works (`FRENCH_LOOKUPS`).
  - Evidence: the fixture `can-t-hurt-me.json` ("Can't Hurt Me" → "Plus rien ne pourra me blesser").
  - Pinned by: `tests/unit/works/test_service.py::test_recorded_search`
  - Re-verify: on recording.

### AniList, MangaDex

- **F06** On 2026-10-21 AniList answered `403` "The AniList API has been temporarily disabled"; MangaDex answered. The fixtures replay that failure.
  - Evidence: the fixtures of every manga case.
  - Pinned by: `tests/unit/works/test_service.py::test_down_sources_are_named`
  - Re-verify: on recording.

### Prowlarr (API v1)

- **F14** `GET /api/v1/search` takes `query`, `type`, `categories` and `indexerIds` (both repeated), `limit`; a release (`ReleaseResource`) gives `guid`, `title`, `indexerId`, `indexer`, `size`, `seeders`, `infoUrl`, `infoHash`, `publishDate`, `protocol`, and a `downloadUrl` that goes through Prowlarr with its key. `GET /api/v1/indexer` gives `id`, `name`, `enable`, `language`, `protocol`. The key goes in the header `X-Api-Key`.
  - Evidence: the OpenAPI document of Prowlarr (`src/Prowlarr.Api.V1/openapi.json`, branch develop, read on 2026-10-21). No answer of a real Prowlarr: the tests never call one; `tests/unit/releases/fixtures/prowlarr.json` is written in this shape.
  - Pinned by: `tests/unit/releases/clients/test_prowlarr.py::test_a_search_sends_the_key_in_a_header_with_its_categories_and_indexers`
  - Re-verify: before the first search against a real Prowlarr, then when Prowlarr changes its major version.
- **F15** Searching with `categories=7030` (or 7020, 3030) also asks each tracker in the categories of its own that Prowlarr maps to it.
  - Evidence: the operator's use of Prowlarr; not observed by a test.
  - Pinned by: none
  - Re-verify: at the first search against a real Prowlarr.
- **F16** `GET /api/v1/system/status` (`SystemResource`) gives `appName` and `version`, with the key in `X-Api-Key`; `ProwlarrClient.version` reads `version`.
  - Evidence: the OpenAPI document of Prowlarr (`src/Prowlarr.Api.V1/openapi.json`, branch develop, read on 2026-10-21). No answer of a real Prowlarr; `prowlarr.json` holds one in this shape.
  - Pinned by: `tests/unit/releases/clients/test_prowlarr.py::test_the_status_gives_the_version`
  - Re-verify: when Prowlarr changes its major version.

- **F24** The `downloadUrl` and `magnetUrl` of a release are links of Prowlarr itself, `<address of the request>[<url base>]/<indexer id>/download?apikey=<key>&link=<link of the tracker, encrypted by Prowlarr>&file=<title>`. `GET /<indexer id>/download` takes the key as the query `apikey` or the header `X-Api-Key`, and answers the `.torrent` (`application/x-bittorrent`), a `301` to a magnet link, or, for an indexer set to redirect, a `301` to the link of the tracker; `410`, `429` or `500` with an XML body when the tracker fails. `POST /api/v1/search` (`guid`, `indexerId`) sends the release to a download client of Prowlarr, not to shelfdrop: shelfdrop does not use it.
  - Evidence: the source of Prowlarr, branch develop, read on 2026-10-21: `src/NzbDrone.Core/Download/DownloadMappingService.cs` (`ConvertToProxyLink`), `src/Prowlarr.Api.V1/Search/SearchController.cs` (`MapReleases`, `GrabRelease`), `src/Prowlarr.Api.V1/Indexers/NewznabController.cs` (`GetDownload`), `src/Prowlarr.Http/Authentication/ApiKeyAuthenticationHandler.cs` (`ParseApiKey`). No answer of a real Prowlarr; `ProwlarrReplay.downloads` and the stubs of the downloads answer in this shape.
  - Pinned by: `tests/unit/releases/clients/test_prowlarr.py::test_the_torrent_is_asked_at_the_address_of_prowlarr_with_its_key_in_a_header`, `tests/unit/releases/clients/test_prowlarr.py::test_a_download_link_is_kept_without_its_key`
  - Re-verify: before the first download through a real Prowlarr, then when Prowlarr changes its major version.
- **F41** `GET /api/v1/indexer` gives, for each indexer, `capabilities.categories`: a tree of `{"id", "name", "description", "subCategories"}` (`IndexerCategory`, from `IndexerCapabilitiesCategories.GetTorznabCategoryTree`): the standard (Newznab) categories with their sub-categories, named with their parent ("Books/Comics"), then the indexer's own categories, at the top, each with the id 100000 plus the number of the tracker's category, or plus the first 16 bits of the SHA-1 of its text when it is not a number (Nyaa's "3_0" gives 100920). A search takes these ids in `categories` as the standard ones.
  - Evidence: the source of Prowlarr (`src/NzbDrone.Core/Indexers/IndexerCapabilitiesCategories.cs`, `IndexerCategory.cs`, `src/Prowlarr.Api.V1/Indexers/IndexerCapabilityResource.cs`, branch develop, read on 2026-10-24). No answer of a real Prowlarr; the names of the categories of Nyaa in `prowlarr.json` are written in this shape, not read from its definition. That a search in an indexer's own category finds what the tracker files there is not observed by a test.
  - Pinned by: `tests/unit/releases/clients/test_prowlarr.py::test_the_indexers`, `tests/unit/releases/clients/test_prowlarr.py::test_the_categories_of_an_indexer_are_flattened_once_each`
  - Re-verify: at the first choice of a category of an indexer's own against a real Prowlarr, then when Prowlarr changes its major version.

### Jellyfin (REST API, OpenAPI 12.2.0)

- **F18** `POST /Users/AuthenticateByName` takes `{"Username", "Pw"}` and gives `AuthenticationResult`: `User` (`UserDto`: `Id`, `Name`, `Policy` with `IsAdministrator` and `IsDisabled`), `AccessToken`, `ServerId`. It needs no key; the header `Authorization: MediaBrowser Client="...", Device="...", DeviceId="...", Version="..."` names the device, and `Token="..."` added to it authenticates the next requests.
  - Evidence: the OpenAPI document of Jellyfin (`api.jellyfin.org/openapi/jellyfin-openapi-stable.json`, version 12.2.0, read on 2026-10-21: `AuthenticateUserByName`, `AuthenticationResult`, `UserDto`, `UserPolicy`, the security scheme `CustomAuthentication` on the header `Authorization`). No answer of a real Jellyfin: the one of the user is not to be called by the tests; `tests.unit.clients.support.FakeJellyfin` and `tests.integration.support.jellyfin_stubs` answer in this shape.
  - Pinned by: `tests/unit/clients/test_jellyfin.py::test_a_sign_in_sends_the_credentials_in_the_body_alone`
  - Re-verify: before the first sign-in against a real Jellyfin, then when Jellyfin changes its major version.
- **F19** `GET /Users/Me` gives the `UserDto` of the access token of the request (`401` once the token is gone); `POST /Sessions/Logout` ends the session of the token (`204`). The status of a wrong password at `AuthenticateByName` is not in the document (only `200` and `503`): shelfdrop takes `401` and `403` as a refusal, anything else as Jellyfin unavailable.
  - Evidence: the same OpenAPI document (`GetCurrentUser`, `ReportSessionEnded`).
  - Pinned by: `tests/unit/clients/test_jellyfin.py::test_the_session_is_read_and_ended_with_its_token`, `tests/unit/auth/test_service.py::test_a_session_jellyfin_revoked_ends`
  - Re-verify: before the first sign-in against a real Jellyfin (the status of a wrong password above all).
- **F20** `GET /System/Info` (with a key) gives `Version`; `GET /Library/VirtualFolders` (an administrator or a key) gives the libraries, `Name`, `Locations`, `CollectionType` (`books` for books, comics and audiobooks alike).
  - Evidence: the same OpenAPI document (`GetSystemInfo`, `GetVirtualFolders`, `VirtualFolderInfo`, `CollectionTypeOptions`).
  - Pinned by: `tests/unit/clients/test_jellyfin.py::test_the_server_and_its_libraries_are_read_with_the_api_key`
  - Re-verify: when Jellyfin changes its major version.

- **F26** `GET /Items?parentId=<library>&recursive=true&includeItemTypes=Book,AudioBook,Folder&fields=Path,Overview,Genres,People,ProductionYear,OriginalTitle` lists the items of a library with these fields, `ImageTags.Primary` when it has an image; `GET /Items/{id}` gives a whole `BaseItemDto`, but with an API key only when `userId` names a user (without it, Jellyfin 12.2.0 answers `400`, its log: `System.ArgumentException: Guid can't be empty (Parameter 'id')` in `UserManager.GetUserById`, from `UserLibraryController.GetItem`): shelfdrop reads it as the first administrator not disabled of `GET /Users`, which an API key lists with their `Policy`. `POST /Items/{id}` takes one back whole (the fields it lacks are emptied: shelfdrop always sends back what it read, changed). `POST /Items/{id}/Refresh` takes `metadataRefreshMode` and `imageRefreshMode` (`None`, `ValidationOnly`, `Default`, `FullRefresh`), `replaceAllMetadata` and `replaceAllImages`; `POST /Library/Refresh` scans every library. `POST /Items/{id}/Images/Primary` reads its body in base64 (`ImageController.GetFromBase64Stream`), whatever its `Content-Type` says. `GET /Users/{userId}/Items/{id}`, which the scripts of the user called, is no longer in the document.
  - Evidence: the same OpenAPI document (`GetItems`, `GetItem`, `UpdateItem`, `RefreshItem`, `RefreshLibrary`, `SetItemImage`), and the source of Jellyfin, branch master (`Jellyfin.Api/Controllers/ImageController.cs`, read on 2026-10-21). The `userId` of `GET /Items/{id}`: a real Jellyfin 12.2.0 on 2026-10-24, `400` without it and `200` with the id of an administrator, after the `503` of the page Métadonnées in production (`PUT /api/v1/library/series/{id}`). `FakeJellyfin` and the stubs of the placement answer in this shape.
  - Pinned by: `tests/unit/clients/test_jellyfin.py::test_an_image_is_sent_in_base64_and_read_as_bytes`, `tests/unit/clients/test_jellyfin.py::test_a_refresh_sends_the_modes_of_its_scan`, `tests/unit/clients/test_jellyfin.py::test_an_item_is_read_whole_and_written_back`, `tests/unit/clients/test_jellyfin.py::test_an_item_is_read_as_the_first_administrator_not_disabled`
  - Re-verify: before the first placement against a real Jellyfin, then when Jellyfin changes its major version.
- **F27** `GET /Library/VirtualFolders` gives each library its `ItemId` (the item `/Items/{id}/Refresh` and `parentId` take) and, while it scans, `RefreshStatus` (`Active`, otherwise `Idle`) and `RefreshProgress` (0 to 100).
  - Evidence: the same OpenAPI document (`VirtualFolderInfo`).
  - Pinned by: `tests/unit/clients/test_jellyfin.py::test_the_libraries_give_their_item_their_folders_and_their_scan`
  - Re-verify: before the first scan against a real Jellyfin.

- **F30** `LockedFields` of a `BaseItemDto` takes the values of `MetadataField`: `Cast`, `Genres`, `ProductionLocations`, `Studios`, `Tags`, `Name`, `Overview`, `Runtime`, `OfficialRating`; `SeriesName`, `IndexNumber`, `SortName` and `ForcedSortName` are fields of the item, none of them lockable alone.
  - Evidence: the OpenAPI document of Jellyfin 12.2.0 (`components.schemas.MetadataField`, `BaseItemDto`), read on 2026-10-21.
  - Pinned by: `tests/unit/placement/test_metadata.py::test_a_volume_gets_its_name_its_series_its_number_and_its_author_locked`, `tests/integration/test_placement_comics.py::test_the_volumes_missing_are_linked_tagged_scanned_locked_and_journaled`
  - Re-verify: before the first placement against a real Jellyfin.
- **F39** `GET /Items/{id}/Download` (`LibraryController.GetDownload`, policy `Download`) sends the file of an item through `PhysicalFile` with range processing on: its type by its extension, its name in `Content-Disposition`, `206` and `Content-Range: bytes 0-0/<size>` for `Range: bytes=0-0`. It takes no `userId`: with an API key (no user) it checks `CanDownload()` alone, which a `Book` and an `AudioBook` grant for a file on disk (`IsFileProtocol`), a folder never; with a user, his right `EnableContentDownloading` too. A `Book` has no size in `BaseItemDto` (it is no `IHasMediaSources`: no `MediaSources`), hence the size read from the first byte. shelfdrop asks it with its API key, never with a `userId`.
  - Evidence: the source of Jellyfin, branch master (`Jellyfin.Api/Controllers/LibraryController.cs`, `MediaBrowser.Controller/Entities/BaseItem.cs`, `Book.cs`, `AudioBook.cs`, `Audio/Audio.cs`, `Emby.Server.Implementations/Dto/DtoService.cs`, read on 2026-10-24). Not observed on a real Jellyfin: whether the policy `Download` lets an API key through is read from the code alone. `FakeJellyfin` and `jellyfin_file_stubs` answer in this shape.
  - Pinned by: `tests/unit/clients/test_jellyfin.py::test_a_file_is_streamed_as_jellyfin_sends_it_and_closed_at_its_end`, `tests/unit/clients/test_jellyfin.py::test_the_size_of_a_file_is_the_total_of_its_first_byte`, `tests/integration/test_library.py::test_the_volumes_of_a_series_are_listed_downloaded_and_changed`
  - Re-verify: before first use against a real Jellyfin (a download and the size of a CBZ, an EPUB and an M4B with the API key of the settings), then when Jellyfin changes its major version.
- **F40** `POST /Items/{id}/Refresh` only queues the refresh (`ProviderManager.QueueRefresh`, priority high) and answers `204` at once; `recursive=true` on a folder refreshes what it holds with the same options. `POST /Items/{id}` already sets the sort name from the new name (`BaseItem.Name` resets it) and saves the item at once, as `POST /Items/{id}/Images/Primary` saves the image: an item read just after either holds the change. The tag of an image (`ImageTags.Primary`) is the MD5 of the path of the item and the date of the image file (`ImageProcessor.GetImageCacheTag`): a new image has a new tag. The modes of a refresh: an item with `LockData` (`IsLocked`) is never changed by a provider; `metadataRefreshMode=Default` runs the providers only for a file changed (or a first refresh, or one past the automatic refresh interval of the library), and then *replaces* every field not locked with what they read (`shouldReplace` of `MetadataService.RefreshWithProviders`: "Scan for new and updated files"), the year, the original title and the number among them, none of which can be locked alone (F30); `metadataRefreshMode=FullRefresh` with `replaceAllMetadata=false` runs every provider, and fills only the fields that are empty (`MergeBaseItemData` with `replaceData` false: a name, a number, a year, a summary already set stay), but adds their people to the `Cast` not locked; `imageRefreshMode=Default` with `replaceAllImages=false` validates the images and takes the new local ones, replacing none. Hence the refresh shelfdrop asks after a change of its own (the mode `changed` of `shelfdrop.clients.jellyfin.REFRESH_MODES`): `FullRefresh`, `imageRefreshMode=Default`, `replaceAllMetadata=false`, `replaceAllImages=false`, on the folder of a series or on a volume.
  - Evidence: the source of Jellyfin, branch master (`Jellyfin.Api/Controllers/ItemRefreshController.cs`, `ItemUpdateController.cs`, `ImageController.cs`, `MediaBrowser.Providers/Manager/MetadataService.cs`, `MediaBrowser.Controller/Entities/BaseItem.cs`, `src/Jellyfin.Drawing/ImageProcessor.cs`, `Emby.Server.Implementations/Dto/DtoService.cs`, read on 2026-10-24). Not observed on a real Jellyfin; what a plugin's provider of books reads (ComicInfo, OPF) is not known here. `FakeJellyfin` and `jellyfin_library_stubs` answer in this shape.
  - Pinned by: `tests/unit/library/test_service.py::test_a_change_sets_and_locks_the_fields_and_copies_the_summary`, `tests/unit/library/test_service.py::test_a_new_image_is_read_back_with_its_new_tag`, `tests/unit/library/test_sync.py::test_a_sync_of_a_series_overwrites_the_authors_locks_and_leaves_the_images`, `tests/integration/test_library.py::test_a_series_is_read_changed_locked_and_its_cover_written`
  - Re-verify before first use against a real Jellyfin (a name changed then refreshed: its sort and its search follow, its year, its number and its summary stay), then when Jellyfin changes its major version.

### qBittorrent (WebUI API v2), behind qui

- **F21** `GET /api/v2/app/version` answers the version as text (`v4.1.3`); `GET /api/v2/torrents/categories` a JSON object by name (`{"name", "savePath"}`). Every method but the sign-in needs the cookie `SID`.
  - Evidence: the wiki of qBittorrent, "WebUI API (qBittorrent 5.0)" (read on 2026-10-21). No real qBittorrent asked; `FakeQui` and `qbittorrent_stubs` answer in this shape.
  - Pinned by: `tests/unit/clients/torrents/test_qui.py::test_the_version_and_the_categories_go_through_the_proxy_of_its_key`
  - Re-verify: before the first test against a real qBittorrent.
- **F22** The client proxy of qui stands for a qBittorrent at `<qui>/proxy/<client API key>`: an application uses it as the address of qBittorrent with no credentials, qui keeps the session of qBittorrent; a key missing or wrong gets a `401` from qui.
  - Evidence: the documentation of qui, "Reverse proxy for external applications" (getqui.com/docs/features/reverse-proxy, read on 2026-10-21), and its issue #3167 ("the qui proxy middleware only returns 401 for a missing or invalid API key").
  - Pinned by: `tests/unit/clients/torrents/test_qui.py::test_a_wrong_key_is_refused_and_a_missing_one_asks_nothing`
  - Re-verify: before the first test against a real qui, and when qui changes its major version.

- **F25** `POST /api/v2/torrents/add` takes a `multipart/form-data` body: `torrents` (the `.torrent` files) or `urls` (links, a magnet among them, one per line), `category`, and the options (`savepath`, `tags`...). qBittorrent 5.0 answers `200` (`Ok.`, or `Fails.` when it added nothing) and `415` for a file it cannot read; its later versions answer `200` with `added_torrent_ids`, `202` for a link still to fetch, `409` when nothing was added. `GET /api/v2/torrents/info?hashes=<a>|<b>` lists the torrents of these hashes it has, each with `hash`, `name`, `state` (`downloading`, `stalledDL`, `metaDL`, `queuedDL`, `pausedDL`, `uploading`, `stalledUP`...), `progress` (0 to 1), `dlspeed` (bytes a second), `eta` (seconds, `8640000` when unknown), `category`. `WebUiClient.add` (`shelfdrop/clients/torrents/webui.py`) takes `200` and `202` as accepted but `Fails.`; the hash decides, not the answer.
  - Evidence: the wiki of qBittorrent, "WebUI API (qBittorrent 5.0)" ("Add new torrent", "Get torrent list"), and its source, branch master (`src/webui/api/torrentscontroller.cpp`, `TorrentsController::addAction`), read on 2026-10-21. No real qBittorrent asked; `FakeQui` and the stubs of the downloads answer in this shape (a list of several hashes through `qbittorrent-lists`, F33).
  - Pinned by: `tests/unit/clients/torrents/test_qui.py::test_a_torrent_is_added_into_its_category_and_read_by_its_hash`
  - Re-verify: before the first download to a real qBittorrent, and when qBittorrent changes its major version.
- **F23** qBittorrent names a torrent (`hash` of `GET /api/v2/torrents/info`, the `hashes` it filters on) by its `TorrentID`, libtorrent's `info_hash_t::get_best()`: the SHA-256 of the bencoded `info` cut to 20 bytes when the torrent is of BitTorrent v2 (hybrid ones included), otherwise its SHA-1, in hex. `shelfdrop.utils.torrent.torrent_id` and `magnet_id` give the same id.
  - Evidence: the source of qBittorrent (`src/base/bittorrent/infohash.cpp`, `InfoHash::toTorrentID` returns `m_nativeHash.get_best()` with libtorrent 2) and of libtorrent (`include/libtorrent/info_hash.hpp`, branch RC_2_0: "returns the v2 (truncated) info-hash, if there is one, otherwise returns the v1 info-hash"), read on 2026-10-21. No real qBittorrent asked.
  - Pinned by: `tests/unit/utils/test_torrent.py::test_a_torrent_of_bittorrent_v2_is_named_by_its_sha256_cut_to_20_bytes`
  - Re-verify: before the first download to a real qBittorrent, and when qBittorrent changes its major version.

- **F28** Each torrent of `GET /api/v2/torrents/info` gives `content_path`, where qBittorrent keeps it as qBittorrent sees it: the file of a torrent of one file, the root folder of the others. `POST /api/v2/torrents/addTags` takes a form body, `hashes` (separated by `|`) and `tags` (separated by commas).
  - Evidence: the wiki of qBittorrent, "WebUI API (qBittorrent 5.0)" ("Get torrent list", "Add torrent tags"), read on 2026-10-21. No real qBittorrent asked; `FakeQui` and the stubs of the placement answer in this shape.
  - Pinned by: `tests/unit/clients/torrents/test_qui.py::test_a_torrent_gives_its_content_path_and_takes_the_mark_of_shelfdrop`
  - Re-verify: before the first placement of a download of a real qBittorrent.

### qBittorrent (WebUI API v2), signed in directly: 5.3.0 and 4.6.7 (lscr.io/linuxserver/qbittorrent `5.3.0_v2.1.2-ls484` and `4.6.7`, observed on 2026-10-24; the image run alone)

- **F60** `POST /api/v2/auth/login` takes a form body, `username` and `password` (a `GET` gets a `405`). qBittorrent 5.3.0 signs in with a `204`, no body, and the cookie `QBT_SID_<port of the WebUI>` (`QBT_SID_8080`; `HttpOnly`, `SameSite=Lax`, an hour); a wrong name or password gets a `401` `Unauthorized`. qBittorrent 4.6.7 answers `200` `Ok.` and the cookie `SID` (`SameSite=Strict`), or `200` `Fails.`. On both, every other method without a session, or with one ended (`POST /api/v2/auth/logout`), gets a `403` `Forbidden`. `QbittorrentClient` (`shelfdrop/clients/torrents/qbittorrent.py`) sends back every cookie of the sign-in whatever its name, takes `Fails.` as refused, and signs in again once on a `403`.
  - Evidence: curl and `QbittorrentClient` against the two images run alone, with the WebUI account of `docker/qbittorrent/qBittorrent.conf` (F64).
  - Pinned by: `tests/unit/clients/torrents/test_qbittorrent.py::test_it_signs_in_once_for_the_connectors_built_at_each_use`, `test_a_session_ended_is_opened_again_once`, `test_a_wrong_password_is_refused_and_keeps_no_session`; the block `torrent_qbittorrent`.
  - Re-verify: when the image of the test stack changes its version of qBittorrent.
- **F61** After 5 sign-ins refused from one address, qBittorrent 5.3.0 answers the next ones, the right password included, `403` `Your IP address has been banned after too many failed authentication attempts.` (its default: 5 failures, banned an hour). `QbittorrentClient` takes a `403` of the sign-in as refused, without a second try.
  - Evidence: 6 sign-ins with a wrong password then one with the right one, curl against the image run alone.
  - Pinned by: `tests/unit/clients/torrents/test_qbittorrent.py::test_a_banned_address_is_refused_without_a_second_try`
  - Re-verify: when the image of the test stack changes its version of qBittorrent.
- **F62** qBittorrent 5.3.0 refuses with a `401` a request whose `Referer` or `Origin` names another address than its `Host` ("Referer header & Target origin mismatch" in its log), and accepts one without either. With `WebUI\HostHeaderValidation` on (its default), a `Host` whose port is not the one it listens on gets a `401` too ("Invalid Host header, port mismatch": a port published as another one), whatever `WebUI\ServerDomains`. `QbittorrentClient` sends the address of the settings as `Referer`.
  - Evidence: curl against the image run alone, its port published as another one, and its log.
  - Pinned by: `tests/unit/clients/torrents/test_qbittorrent.py::test_it_signs_in_once_for_the_connectors_built_at_each_use` (the `Referer`); the block `torrent_qbittorrent`.
  - Re-verify: when the image of the test stack changes its version of qBittorrent.

### Discord (webhooks, API v10)

- **F29** `POST <webhook>?wait=true` posts a message and answers it (`200`); a `multipart/form-data` body carries the JSON in `payload_json` and the files in `files[0]`..., which an embed names `attachment://<file name>`. A webhook takes 30 messages a minute: beyond, `429` with `retry_after` (seconds) in its JSON body and the header `Retry-After`.
  - Evidence: the documentation of Discord, "Execute Webhook", "Uploading Files" and "Rate Limits" (read on 2026-10-21). No real webhook posted to; `FakeDiscord` answers in this shape.
  - Pinned by: `tests/unit/clients/test_discord.py::test_a_picture_goes_with_the_payload_in_a_multipart_body`, `tests/unit/clients/test_discord.py::test_a_429_gives_the_seconds_to_wait_and_an_error_its_status`
  - Re-verify: before the first message on a real webhook.

### The kernel and ffmpeg of the image

- **F31** With `fs.protected_hardlinks=1` (the default of Debian), a process may hardlink a file it does not own only when it can read and write it; a hardlink across two mount points fails with `EXDEV`, even on one file system. The placement worker runs in the group of the files and mounts the torrents and the libraries once.
  - Evidence: the documentation of the kernel, `Documentation/admin-guide/sysctl/fs.rst` (`protected_hardlinks`), and `link(2)` (`EXDEV`: "oldpath and newpath are not on the same mounted filesystem"), read on 2026-10-21.
  - Pinned by: `tests/integration/test_placement_comics.py::test_the_volumes_missing_are_linked_tagged_scanned_locked_and_journaled` (the inode and its 2 links), `tests/unit/placement/test_layout.py::test_the_volumes_missing_are_linked_and_the_others_left`
  - Re-verify: before the first placement on a new machine of the libraries (its sysctl, the owner and the mode of the files of qBittorrent).
- **F32** The ffmpeg of Debian trixie concatenates MP3 tracks (`-f concat -safe 0`), encodes AAC (`-c:a aac`), takes the chapters of an `FFMETADATA1` file (`-map_chapters 1`) and attaches a JPEG as the cover of an MP4 (`-c:v copy -disposition:v attached_pic`); `-progress pipe:1` writes `out_time_us=` lines.
  - Evidence: the run of `tests/integration/test_placement_audio.py` in the image (ffprobe reads 3 chapters, 6 seconds, `aac`, a video stream `attached_pic`).
  - Pinned by: `tests/integration/test_placement_audio.py::test_mp3_tracks_become_one_m4b_with_its_chapters_its_length_and_its_cover`
  - Re-verify: when the base image of `docker/api.Dockerfile` changes.

## Pinned components

### sqlalchemy 2.1.5, alembic 1.20.0

- **F07** SQLite cannot alter most of a table in place; Alembic's batch mode (`render_as_batch=True` in `shelfdrop/db/migrations/env.py`) copies the table instead.
  - Evidence: Alembic documentation, "Running “Batch” Migrations for SQLite and Other Databases".
  - Pinned by: none
  - Re-verify: on version change.

### cryptography 50.0.2

- **F17** `AESGCM.encrypt(nonce, data, associated_data)` returns the ciphertext followed by its 16-byte tag; `decrypt` raises `InvalidTag` when the key, the nonce, the associated data or a byte differ. A nonce must never be used twice under one key: `SecretBox` draws 12 random bytes per seal. `HKDF(SHA256, length=32)` derives the same key from the same text.
  - Evidence: the documentation of cryptography, "Authenticated encryption" (AESGCM) and "Key derivation functions" (HKDF).
  - Pinned by: `tests/unit/settings/test_cipher.py::test_another_key_another_name_or_a_change_cannot_open`
  - Re-verify: on version change.

### fastapi 0.157.0

- **F34** A route parameter `Annotated[bytes, Body(media_type="application/octet-stream")]`, the one body parameter of its route, receives the raw body when the content type of the request is not JSON: FastAPI reads `request.body()` and parses JSON only for `application/json` (or no content type). The chunks of an upload come this way (`shelfdrop.modules.uploads.router.receive_chunk`); the whole chunk is in memory (50 MiB).
  - Evidence: Source: `fastapi/routing.py` `get_request_handler` (`body_bytes = await request.body()`, `json_body` only when the subtype is `json`); a run of `tests/integration/test_uploads.py` on 2026-10-21.
  - Pinned by: `tests/integration/test_uploads.py::test_a_file_sent_in_chunks_is_resumed_checked_taken_into_ranger_and_placed`
  - Re-verify: on version change.

### wireup 2.13.0

- **F08** With `create_async_container` and `setup(..., middleware_mode=True)`, the scope of a request closes on the event loop after the response: a session closed there would block it. `release_session`, a sync dependency of every route, closes the session in the threadpool first.
  - Evidence: Source: `wireup/integration/starlette.py` `WireupAsgiMiddleware.__call__` (`async with ... enter_scope(...)` around the whole application call).
  - Pinned by: none
  - Re-verify: on version change.

### wiremock/wiremock 3.13.2 (sha256:0d4ecb3e..., observed on 2026-10-21; the test stack alone)

- **F09** A stub matches `queryParameters` whatever their order, on their decoded values; `bodyPatterns` `equalToJson` compares JSON values, not the text; a request no stub matches gets a `404`, and is listed by `GET /__admin/requests/unmatched`.
  - Evidence: WireMock documentation, "Request Matching"; the runs of `tests/integration/test_work_search.py`.
  - Pinned by: `tests/integration/test_work_search.py::test_every_request_of_the_searches_was_recorded`, `tests/integration/test_work_sources.py::test_no_source_answering_is_a_503`
  - Re-verify: on version change.
- **F10** `POST /__admin/mappings/import` loads stubs over the running ones with `duplicatePolicy` `OVERWRITE`, and answers `500` (a `NullPointerException`) when `importOptions` has no `deleteAllNotInImport`; `POST /__admin/requests/count` counts the journal entries that match a request pattern.
  - Evidence: WireMock documentation, "Administration API".
  - Pinned by: `tests/integration/test_work_sources.py::test_two_identical_searches_at_once_share_one_run`
  - Re-verify: on version change.
- **F33** A request gets the answer of one stub alone, of the highest priority (the lowest `priority`): `GET /torrents/info?hashes=<a>|<b>|<c>`, matched by the stubs of each of the three torrents, got the one torrent of one of them, where qBittorrent lists the three (F25). A stub with `proxyBaseUrl` sends the request, its path and its query, to that address and answers what it answers.
  - Evidence: WireMock documentation, "Stubbing" (priority) and "Proxying"; the journal of WireMock in a run of `tests/integration/test_journal.py` on 2026-10-21 (every list of the three hashes answered with one torrent, a download left `waiting`).
  - Pinned by: `tests/integration/test_journal.py::test_the_volumes_sent_by_one_request_make_one_embed`
  - Re-verify: on version change.

### mcp 2.3.0 (the official MCP SDK for Python)

- **F35** The server class is `mcp.server.mcpserver.MCPServer` (`FastMCP` of 1.x is gone: `mcp.server.fastmcp` raises `ModuleNotFoundError`). `streamable_http_app(streamable_http_path=..., json_response=True, stateless_http=True)` gives a Starlette app whose session manager (`MCPServer.session_manager.run()`) must run for the requests to be served: mounted in another application, its lifespan does not run by itself. A tool reaches the Starlette `Request` of its HTTP request at `ctx.request_context.request`, its scope included. A parameter typed `Context` is left out of the input schema of the tool.
  - Evidence: the sources of `mcp` 2.3.0 (`mcp/server/mcpserver/server.py`, `mcp/server/lowlevel/server.py`, `mcp/server/streamable_http.py`), read on 2026-10-22; the runs of `tests/integration/test_mcp.py`.
  - Pinned by: `tests/integration/test_mcp.py::test_a_token_finds_a_work_its_releases_and_sends_one_under_its_name`, `tests/unit/modules/mcp/test_router.py::test_the_tools_of_the_plan_and_which_ones_only_read`
  - Re-verify: on version change.
- **F36** `streamable_http_app` turns on its protection against DNS rebinding when its `host` is `127.0.0.1` (the default), `localhost` or `::1` and no `transport_security` is given: a request whose `Host` is another name is refused. `TransportSecuritySettings(enable_dns_rebinding_protection=False)` turns it off.
  - Evidence: `mcp/server/lowlevel/server.py`, `streamable_http_app`, read on 2026-10-22.
  - Pinned by: `tests/integration/test_mcp.py::test_a_token_revoked_is_refused_at_once` (a `Host` of a public name answered 200)
  - Re-verify: on version change.

### fastapi 0.157.0 (routes)

- **F37** `include_router` keeps the router whole in `app.routes` (an `_IncludedRouter`, private) instead of copying its `APIRoute`s with their dependencies: the routes and their guards cannot be read back from the application. `DocumentedApi.include` records the access of each route as it includes its router.
  - Evidence: `fastapi/routing.py` 0.157.0 (`_IncludedRouter`), and `app.routes` of `build_app()` listing `_IncludedRouter` objects on 2026-10-22.
  - Pinned by: `tests/unit/http/test_openapi.py::test_each_operation_names_who_may_call_it`
  - Re-verify: on version change.

### swagger-ui-dist 5.34.0 (web/pnpm-lock.yaml)

- **F38** `swagger-ui-es-bundle.js` (Swagger UI with its React, one CommonJS module) creates no `<style>` element, calls neither `setAttribute("style", ...)` nor `insertRule`, and reaches `Function("return this")` only when `globalThis` is missing; `swagger-ui.css` loads no font nor `@import`, its images are `data:` URIs. `/api/docs` runs it under `script-src 'self'; style-src 'self'; img-src 'self' data:` without `unsafe-inline` nor `unsafe-eval` (ADR 0021). Its `validatorUrl` defaults to `https://validator.swagger.io/validator`, set to `null` by `web/src/docs.ts`. `index.js` of the package requires `path` (Node), so `web/src/docs.ts` imports the bundle itself.
  - Evidence: the files of the package and the build of `web/` read on 2026-10-24 (searches for `createElement("style")`, `cssText`, `insertRule`, `new Function`, `eval(`, `@import`, `url(`). Not yet observed in a browser: the console of `/api/docs` under its policy is to be read once.
  - Pinned by: `tests/integration/test_openapi.py::test_the_page_is_swagger_ui_from_the_same_origin` (the policy and the page, not the behaviour of the bundle in a browser)
  - Re-verify: on version change, and in a browser.

### docker compose 2.26 and later

- **F11** The YAML tag `!override` in a file given after another replaces a list (`ports`) instead of adding to it; `docker compose port` prints `127.0.0.1:<port>` of a port published as `127.0.0.1::8000`.
  - Evidence: Compose documentation, "Merge and override"; the start of the test stack.
  - Pinned by: the fixture `stack` of `tests/integration/conftest.py`
  - Re-verify: when Compose changes.

### python:3.13-slim-trixie (the image of the API)

- **F12** The image has no `/etc/mime.types`: `mimetypes` knows no `.woff2`, and Starlette would serve a font as `application/octet-stream`. `shelfdrop.modules.web.router.web_router` adds `font/woff2`.
  - Evidence: `tests/integration/test_pages.py::test_the_icon_and_the_font_are_served` failed without it on 2026-10-21.
  - Pinned by: `tests/integration/test_pages.py::test_the_icon_and_the_font_are_served`
  - Re-verify: when the base image changes.
