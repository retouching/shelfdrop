# 0019. Uploads: the files sent from the page Manuel
Status: Accepted
Date: 2026-10-21

## Context
Decided on 2026-10-21: the page Manuel sends EPUB, PDF, CBZ, CBR, M4B, MP3 or ZIP files, which then wait in Ranger to be linked to a work. A reverse proxy may refuse a request of more than 100 MB: the file goes in chunks of 50 MB, resumes after a cut, and is put together then checked by its SHA-256 on the machine of the libraries, out of the libraries. A ZIP of MP3 tracks is opened then merged into one M4B. 5 GB at most a file; a file sent and not linked goes after 7 days. The API never writes in the libraries (ADR 0016), and runs read-only with a `tmpfs` on `/tmp` in production.

## Decision
- **The API** (`shelfdrop/uploads/`, routes in `shelfdrop/modules/uploads/`): `POST /api/v1/uploads` starts an upload (a file name alone, of a type of `UPLOAD_EXTENSIONS`, 1 byte to 5 GiB), or resumes the one of the same name and size still receiving its chunks; `PUT .../chunks/{n}` writes chunk `n` (50 MiB, the last one the rest; written through a `.part`); `POST .../finish` puts the chunks together and compares the SHA-256 the page read from the file: the same, the upload is `verified` and the journal tells `uploaded`; another, the file is removed, the upload `corrupt`, the journal tells `failed`. The chunks and the file go to `uploads/<id>/` of `SHELFDROP_DATA_DIR` (`UploadStore`): the volume of the database, writable in production, never `/tmp` (a `tmpfs` in RAM). The table `uploads` keeps the name, the size, the chunks received, the SHA-256 and the state.
- **The page** reads the file once, slice by slice: each slice adds to the SHA-256 (`web/src/utils/sha256.ts`: `crypto.subtle` digests one buffer alone, not 5 GB) and is sent unless the server has it; a chunk is tried again three times (2, 5 and 10 seconds after), then the upload stops (« Envoi interrompu. »); sent again, the same file resumes at its first chunk missing.
- **The worker** (`HandPlacement.take_uploads`, each round): a `verified` upload is moved (copied through a `.part`, then removed) from `uploads/<id>/` of its own data directory (the same volume) into `<uploads.folder>/<id>/` (`/data/envois` by default: on the file system of the libraries, so that a file placed from Ranger is hardlinked then its old name removed, as a file of the libraries); a ZIP is opened there (its entries out of their folder, hidden, or past 10 GiB in all refused; a ZIP that does not open stays a file of no kind); each book is one row of `place_items` (`origin` `upload`, `unlinked`, `reason` `upload`), the MP3 tracks of one folder one audiobook, merged into one M4B when placed (`placement.merge_mp3`). The upload becomes `listed`.
- **Kept 7 days** (`uploads.keep_days`, `tidy_uploads`, each round): a file sent still in Ranger after them is removed with its row; an upload stopped (receiving, corrupt, lost) or listed that long ago goes with its chunks; the empty folders of `uploads.folder` go.

## Rejected alternatives
- The API writing into the folder of the uploads: it has no mount of the libraries, and must not (ADR 0016).
- The chunks in `/tmp`: a `tmpfs` in RAM in production, lost at each restart; 5 GB there would fill the memory.
- The SHA-256 given at the start: the page would read a file of 5 GB twice; given at the end, the file is read once, and a resumed upload is checked whole.
- A hardlink from the data volume into a library: two file systems (`EXDEV`); the copy into `uploads.folder` happens once, then the placement links.

## Consequences
- The data volume holds the uploads in progress (5 GiB each at most) next to the database.
- A file sent reaches Ranger at the next round of the worker (30 seconds at most); the page shows it at 100 % until then.
- `uploads.folder` must exist and be writable by the worker (its group), on the mount of the libraries.
