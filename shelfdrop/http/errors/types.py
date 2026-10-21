"""Error codes of every error response body (each member's comment is its documentation) and
FieldError, one entry of a 422."""

from dataclasses import dataclass
from enum import StrEnum


class ErrorCode(StrEnum):
    """Stable values clients may branch on: adding one is additive, changing one is breaking."""

    # 401: no session, an expired one, or one Jellyfin no longer confirms (every route but the
    # sign-in, /health and the pages); data = null.
    NOT_SIGNED_IN = "not_signed_in"
    # 401: the sign-in is refused: wrong credentials, or an account that is not an
    # administrator of Jellyfin, or disabled; it never says which; data = null.
    LOGIN_REFUSED = "login_refused"
    # 403: a write (POST, PUT, PATCH, DELETE) whose Origin header is missing or names another
    # host than the request; data = null.
    ORIGIN_REFUSED = "origin_refused"
    # 404: no route for the path.
    NOT_FOUND = "not_found"
    # 404: no work with this id in the cache: unknown, or its search is older than 7 days;
    # data = null.
    WORK_NOT_FOUND = "work_not_found"
    # 404: no merge of works by hand with this id: unknown, or split already; data = null.
    WORK_MERGE_NOT_FOUND = "work_merge_not_found"
    # 422: a merge of works of fewer than two distinct works, or under an empty name (or one of
    # more than 300 characters); data = null.
    WORK_MERGE_REFUSED = "work_merge_refused"
    # 404: no release search with this id: unknown, or finished more than 10 minutes ago;
    # data = null.
    SEARCH_NOT_FOUND = "search_not_found"
    # 404: no release with this id in the searches kept (10 minutes after their end), or one
    # Prowlarr gave no download link for; data = null.
    RELEASE_NOT_FOUND = "release_not_found"
    # 404: no download with this id; data = null.
    DOWNLOAD_NOT_FOUND = "download_not_found"
    # 405: the path exists, the method does not; the Allow header lists the methods.
    METHOD_NOT_ALLOWED = "method_not_allowed"
    # Any other HTTP error raised by the framework itself, with its own status.
    HTTP_ERROR = "http_error"
    # 422: the request does not match the schema; data = {"errors": [{"type", "loc", "msg"}]},
    # never the values sent.
    VALIDATION_FAILED = "validation_failed"
    # 422: the search has fewer than 2 letters or digits once normalized; data = null.
    QUERY_TOO_SHORT = "query_too_short"
    # 422: a search of a work under more names than allowed (6); data = null.
    TOO_MANY_NAMES = "too_many_names"
    # 422: settings or secrets the catalog does not know, a value it refuses, or a test of an
    # unknown service; data = {"keys": [each key refused]}, never a value.
    INVALID_SETTINGS = "invalid_settings"
    # 422: a filter rule whose words or regular expression are empty or invalid;
    # data = {"positions": [index of each such rule in the list sent]}.
    INVALID_FILTER_RULE = "invalid_filter_rule"
    # 422: releases to download that the search does not hold (unknown, or Prowlarr gave no
    # download link); data = {"ids": [each id refused]}; nothing is sent.
    RELEASE_NOT_IN_SEARCH = "release_not_in_search"
    # 422: releases of the search of a work an automatic download may not take: set aside (a
    # missing word, a score under the minimum) or from a tracker not allowed for the automatic
    # downloads; data = {"ids": [each id refused]}; nothing is sent.
    RELEASE_NOT_AUTOMATIC = "release_not_automatic"
    # 409: a download that cannot be sent again: only a torrent qBittorrent did not receive is,
    # never a duplicate nor a download sent; data = null.
    DOWNLOAD_NOT_RETRYABLE = "download_not_retryable"
    # 429: too many sign-in attempts: 5 a minute from one address, 30 an hour in all;
    # data = null.
    TOO_MANY_ATTEMPTS = "too_many_attempts"
    # 503: Jellyfin does not answer, or its address is not set: nobody can sign in;
    # data = null.
    JELLYFIN_UNAVAILABLE = "jellyfin_unavailable"
    # 404: no series of a library of books of Jellyfin has this id; data = null.
    SERIES_NOT_FOUND = "series_not_found"
    # 404: no waiting search has this id (or it left the list); data = null.
    WAITING_NOT_FOUND = "waiting_not_found"
    # 404: no file of the page Ranger (`/items/{id}`), or of the shelf (`/shelf/{id}`), has
    # this id; data = null.
    PLACE_ITEM_NOT_FOUND = "place_item_not_found"
    # 409: the file of Ranger is placed already, or the worker has a request of it to do;
    # data = null.
    PLACE_ITEM_BUSY = "place_item_busy"
    # 422: the request does not fit the file: volumes of chapters for a file that is not a
    # release in chapters (or a volume for one), volumes repeated, ranges of chapters upside
    # down or that overlap, nothing to place; data = null.
    PLACE_REQUEST_REFUSED = "place_request_refused"
    # 422: a file the page Manuel cannot send; data = {"reason": "type"} (not an EPUB, PDF,
    # CBZ, CBR, M4B, MP3 or ZIP), {"reason": "size"} (empty, or over 5 GiB) or
    # {"reason": "name"} (empty, hidden or over 200 characters).
    UPLOAD_REFUSED = "upload_refused"
    # 404: no upload with this id; data = null.
    UPLOAD_NOT_FOUND = "upload_not_found"
    # 409: the upload is whole already (checked, or in Ranger), or was refused as corrupt;
    # data = null.
    UPLOAD_DONE = "upload_done"
    # 422: a chunk out of the file, or of another length than its place asks (50 MiB, the last
    # one the rest); at the end, chunks still missing; data = null.
    CHUNK_REFUSED = "chunk_refused"
    # 422: the file put together has another SHA-256 than the one given: it is removed, and is
    # to send again; data = null.
    UPLOAD_CORRUPT = "upload_corrupt"
    # 422: the image chosen for a series is not a JPEG, a PNG or a WebP of 5 MB at most, or its
    # address did not answer one; data = null.
    IMAGE_REFUSED = "image_refused"
    # 503: Prowlarr does not answer, answers an error, or its address or key is not set;
    # data = null.
    PROWLARR_UNAVAILABLE = "prowlarr_unavailable"
    # 503: none of the metadata sources of the kind answered (down, timed out, or skipped
    # because it failed less than 5 minutes ago); data = null.
    SOURCES_UNAVAILABLE = "sources_unavailable"
    # 500: unexpected error; the details stay in the logs.
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True)
class FieldError:
    """One entry of a 422 validation_failed: where, what and which rule (never the input)."""

    loc: tuple[str | int, ...]
    msg: str
    type: str
