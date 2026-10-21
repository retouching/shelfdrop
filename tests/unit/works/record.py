"""Record the fixtures of the work search from the real sources (network needed).

    uv run python -m tests.unit.works.record [slug ...]

Writes tests/unit/works/fixtures/<slug>.json again for every case of tests/unit/works/cases.py
(or only those named). Run it again when a source changes its answers.
"""

import asyncio
import sys

import httpx

from shelfdrop.container import REQUEST_TIMEOUT_SECONDS
from tests.unit.works.cases import CASES
from tests.unit.works.support import RecordingTransport, replayed_service, save

USER_AGENT = "shelfdrop/0.1.0 (fixtures of the tests)"


async def record(slugs: set[str]) -> None:
    for case in CASES:
        if slugs and case.slug not in slugs:
            continue
        transport = RecordingTransport()
        async with httpx.AsyncClient(
            transport=transport,
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS),
            follow_redirects=True,
        ) as http:
            result = await replayed_service(http).search(case.query, case.kind)
        save(case.slug, transport.exchanges)
        first = result.works[0].shelf_name if result.works else "-"
        sys.stdout.write(f"{case.slug}: {len(transport.exchanges)} exchanges, first: {first}\n")


if __name__ == "__main__":
    asyncio.run(record(set(sys.argv[1:])))
