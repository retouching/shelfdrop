"""Record the fixtures of the work search from the real sources (network needed).

    uv run python -m tests.unit.works.record [--missing] [slug ...]

Writes tests/unit/works/fixtures/<slug>.json again for every case of tests/unit/works/cases.py
(or only those named). Run it again when a source changes its answers. With `--missing`, the
exchanges already recorded are kept and replayed, and only the requests no fixture holds are
sent: what a change of the search asks more, without asking the sources everything again.
"""

import asyncio
import sys

import httpx

from shelfdrop.container import REQUEST_TIMEOUT_SECONDS
from tests.unit.works.cases import CASES
from tests.unit.works.support import FIXTURES, RecordingTransport, load, replayed_service, save

USER_AGENT = "shelfdrop/0.1.0 (fixtures of the tests)"


async def record(slugs: set[str], *, missing: bool) -> None:
    for case in CASES:
        if slugs and case.slug not in slugs:
            continue
        kept = load(case.slug) if missing and (FIXTURES / f"{case.slug}.json").is_file() else {}
        transport = RecordingTransport(kept)
        async with httpx.AsyncClient(
            transport=transport,
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS),
            follow_redirects=True,
        ) as http:
            result = await replayed_service(http).search(case.query, case.kind)
        save(case.slug, transport.exchanges)
        first = result.works[0].shelf_name if result.works else "-"
        added = len(set(transport.exchanges) - set(kept))
        dropped = len(set(kept) - set(transport.exchanges))
        sys.stdout.write(f"{case.slug}: +{added} -{dropped} exchanges, first: {first}\n")


if __name__ == "__main__":
    arguments = sys.argv[1:]
    asyncio.run(record(set(arguments) - {"--missing"}, missing="--missing" in arguments))
