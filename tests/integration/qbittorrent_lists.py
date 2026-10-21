"""The lists of several torrents of the fake qBittorrent, a service of the test stack
(`docker/compose.test.yaml`), run by the Python of the image of the API.

qBittorrent answers `GET /api/v2/torrents/info?hashes=<a>|<b>` with every torrent of these
hashes it has. WireMock answers a request with one stub alone, and a torrent of the tests is
played by the stubs of a scenario of its own (`tests.integration.support.torrent_stubs`), on its
hash alone: WireMock sends a list of several hashes here (`qbittorrent_stubs`), which asks it
for each hash under the same path and joins the torrents, in the order of the hashes."""

import json
from http import HTTPStatus
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Final
from urllib.parse import parse_qsl, urlencode, urlsplit

SOURCES: Final = ("fake-sources", 8080)
# The mark of the requests of one hash, so that the journal of WireMock tells them from those of
# the API (`tests.integration.support.PART_HEADER`).
PART_HEADER: Final = "X-Fake-Part"
PORT: Final = 8080


class Lists(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        url = urlsplit(self.path)
        if url.path == "/health":
            self.answer(HTTPStatus.OK, b"ok")
            return
        params = parse_qsl(url.query)
        hashes = [h for name, value in params if name == "hashes" for h in value.split("|") if h]
        others = [(name, value) for name, value in params if name != "hashes"]
        torrents: list[object] = []
        for digest in hashes:
            query = urlencode([*others, ("hashes", digest)])
            connection = HTTPConnection(*SOURCES, timeout=10)
            try:
                connection.request("GET", f"{url.path}?{query}", headers={PART_HEADER: "1"})
                response = connection.getresponse()
                body = response.read()
            finally:
                connection.close()
            if response.status != HTTPStatus.OK:
                self.answer(response.status, body)
                return
            torrents += json.loads(body)
        self.answer(HTTPStatus.OK, json.dumps(torrents).encode(), "application/json")

    def answer(self, status: int, body: bytes, content_type: str = "text/plain") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Lists).serve_forever()  # noqa: S104
